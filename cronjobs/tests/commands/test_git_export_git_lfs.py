import json
from unittest import mock

import commands
import commands._git_export_lfs
import jwt
import pytest
import requests
import responses
from commands._git_export_lfs import (
    _download_from_cdn_and_upload_to_lfs_volume,
    _github_lfs_verify_upload,
    _new_retrying_session,
    _run_in_parallel,
    github_lfs_batch_request,
)
from commands.git_export import (
    github_lfs_batch_upload_many,
    github_lfs_validate_credentials,
)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(
        commands._git_export_lfs.time, "sleep", lambda s: None, raising=False
    )


@pytest.fixture
def mock_jwt():
    with mock.patch("commands._git_export_lfs.jwt", spec=jwt) as mocked:
        mocked.encode.return_value = "JWT"
        yield mocked


@pytest.fixture
def temp_key(tmp_path):
    key_path = tmp_path / "key.pem"
    key_path.write_text("PRIVATE_KEY")
    return str(key_path)


@responses.activate
def test_pat_token_success():
    responses.add(
        responses.GET,
        "https://api.github.com/user",
        json={"login": "leplatrem", "id": 123},
        status=200,
    )
    responses.add(
        responses.POST,
        "https://github.com/leplatrem/remote-settings-data.git/info/lfs/objects/batch",
        json={},
        status=200,
        content_type="application/vnd.git-lfs+json",
    )

    github_lfs_validate_credentials(
        repo_owner="leplatrem",
        repo_name="remote-settings-data",
        github_username="leplatrem",
        github_token="TOKEN",
    )


@responses.activate
def test_pat_token_failing():
    responses.add(
        responses.GET,
        "https://api.github.com/user",
        status=403,
    )

    with pytest.raises(requests.HTTPError):
        github_lfs_validate_credentials(
            repo_owner="leplatrem",
            repo_name="remote-settings-data",
            github_username="leplatrem",
            github_token="TOKEN",
        )


@responses.activate
def test_app_id_token_flow_success(mock_jwt, temp_key):
    # _resolve_installation_id() call
    responses.add(
        responses.GET,
        "https://api.github.com/repos/leplatrem/remote-settings-data/installation",
        json={"id": 42, "name": "remote-settings-data"},
        status=200,
    )
    # _mint_installation_access_token() call
    responses.add(
        responses.POST,
        "https://api.github.com/app/installations/42/access_tokens",
        json={"token": "TOKEN", "expires_at": "1982-05-08T13:29:59Z"},
        status=201,
    )
    # _verify_installation_token() call
    responses.add(
        responses.GET,
        "https://api.github.com/repos/leplatrem/remote-settings-data",
        json={"id": 123, "full_name": "FULLNAME"},
        status=200,
    )
    # LFS batch call
    responses.add(
        responses.POST,
        "https://github.com/leplatrem/remote-settings-data.git/info/lfs/objects/batch",
        json={},
        status=200,
        content_type="application/vnd.git-lfs+json",
    )

    # Does not raise
    github_lfs_validate_credentials(
        repo_owner="leplatrem",
        repo_name="remote-settings-data",
        github_app_id=12345,
        github_app_private_key_path=temp_key,
    )


@responses.activate
def test_app_id_token_flow_failing(mock_jwt, temp_key):
    # Fails to resolve installation ID
    responses.add(
        responses.GET,
        "https://api.github.com/repos/leplatrem/remote-settings-data/installation",
        json={"error": "bad"},
        status=400,
    )
    with pytest.raises(requests.HTTPError):
        github_lfs_validate_credentials(
            repo_owner="leplatrem",
            repo_name="remote-settings-data",
            github_app_id=12345,
            github_app_private_key_path=temp_key,
        )

    # Fails to mint installation token
    responses.add(
        responses.GET,
        "https://api.github.com/repos/leplatrem/remote-settings-data/installation",
        json={"id": 42, "name": "remote-settings-data"},
        status=200,
    )
    responses.add(
        responses.POST,
        "https://api.github.com/app/installations/42/access_tokens",
        json={"error": "bad"},
        status=403,
    )
    with pytest.raises(requests.HTTPError):
        github_lfs_validate_credentials(
            repo_owner="leplatrem",
            repo_name="remote-settings-data",
            github_app_id=12345,
            github_app_private_key_path=temp_key,
        )

    # Fails to obtain repo details with token
    responses.add(
        responses.POST,
        "https://api.github.com/app/installations/42/access_tokens",
        json={"token": "TOKEN", "expires_at": "1982-05-08T13:29:59Z"},
        status=201,
    )
    responses.add(
        responses.GET,
        "https://api.github.com/repos/leplatrem/remote-settings-data",
        status=403,
    )
    with pytest.raises(requests.HTTPError):
        github_lfs_validate_credentials(
            repo_owner="leplatrem",
            repo_name="remote-settings-data",
            github_app_id=12345,
            github_app_private_key_path=temp_key,
        )


def test_run_in_parallel_cancels_pending_tasks_on_error():
    executed = []

    def task(index):
        if index == 0:
            raise ValueError("boom")
        executed.append(index)

    # Single worker, so the tasks queued behind the failing one can be cancelled.
    with pytest.raises(ValueError, match="boom"):
        _run_in_parallel(task, [(i,) for i in range(6)], max_workers=1)

    assert len(executed) < 5


def test_run_in_parallel_without_any_task():
    _run_in_parallel(mock.Mock(side_effect=AssertionError), [], max_workers=2)


@responses.activate
def test_batch_upload_does_not_slow_down_after_last_chunk():
    objects = [(c * 64, 5, f"https://cdn.example.com/{c}") for c in "ab"]
    responses.add(
        responses.POST,
        "https://github.com/foo/bar.git/info/lfs/objects/batch",
        status=200,
        json={"objects": [{"oid": oid, "actions": {}} for oid, _s, _u in objects]},
        content_type="application/vnd.git-lfs+json",
    )

    with mock.patch.object(commands._git_export_lfs, "GITHUB_MAX_LFS_BATCH_SIZE", 1):
        with mock.patch.object(commands._git_export_lfs.time, "sleep") as mock_sleep:
            github_lfs_batch_upload_many(
                objects,
                repo_owner="foo",
                repo_name="bar",
                auth_header="Bearer TOKEN",
            )

    # Two chunks, one pause between them, none after the last.
    assert mock_sleep.call_count == 1


def test_retrying_session_retries_transient_failures():
    session = _new_retrying_session()
    retries = session.get_adapter("https://example.com").max_retries

    assert retries.total == commands._git_export_lfs.HTTP_RETRY_MAX_COUNT
    # Transient statuses that must not abort a whole export run.
    for status in (500, 502, 503, 504, 429):
        assert status in retries.status_forcelist
    # Uploads and verifications are POST/PUT.
    assert {"POST", "PUT"} <= set(retries.allowed_methods)


@pytest.mark.parametrize(
    "call",
    [
        # Every network call of the export goes through a retrying session:
        # a single transient error must not discard the run's whole work.
        lambda: commands._git_export_lfs.fetch_and_hash("https://cdn.example.com/x"),
        lambda: _download_from_cdn_and_upload_to_lfs_volume(
            ("a" * 64, 1, "https://cdn.example.com/x"),
            ("https://lfs.example.com/up", "PUT", {}),
        ),
        lambda: _github_lfs_verify_upload(
            ("a" * 64, 1), ("https://lfs.example.com/verify", "POST", {})
        ),
    ],
)
def test_transfers_use_a_retrying_session(call):
    with mock.patch.object(
        commands._git_export_lfs, "_new_retrying_session"
    ) as mock_session:
        # Bail out right after the session is built.
        mock_session.return_value.get.side_effect = RuntimeError("stop")
        mock_session.return_value.request.side_effect = RuntimeError("stop")

        with pytest.raises(RuntimeError, match="stop"):
            call()

    assert mock_session.called


@responses.activate
@pytest.mark.parametrize("operation", ["download", "upload"])
def test_github_lfs_batch_request_success(operation):
    url = "https://github.com/foo/bar.git/info/lfs/objects/batch"

    # Mock the HTTP 200 response
    payload_return = {"objects": [{"oid": "abc", "size": 123, "actions": {}}]}
    responses.add(
        responses.POST,
        url,
        json=payload_return,
        status=200,
        content_type="application/vnd.git-lfs+json",
    )

    objects = [{"oid": "abc", "size": 123}]
    result = github_lfs_batch_request(
        "Bearer TOKEN", objects, operation, repo_owner="foo", repo_name="bar"
    )

    # Returned JSON is passed through
    assert result == payload_return

    # Inspect the actual request that was sent
    assert len(responses.calls) == 1
    call = responses.calls[0]
    assert call.request.url == url
    assert call.request.method == "POST"
    # Headers
    assert call.request.headers["Accept"] == "application/vnd.git-lfs+json"
    assert call.request.headers["Content-Type"] == "application/vnd.git-lfs+json"
    assert call.request.headers["Authorization"] == "Bearer TOKEN"
    # Body
    sent = json.loads(call.request.body.decode("utf-8"))
    assert sent["operation"] == operation
    assert sent["transfers"] == ["basic"]
    assert sent["objects"] == objects


@responses.activate
def test_github_lfs_batch_request_failure(capsys):
    url = "https://github.com/acme/widgets.git/info/lfs/objects/batch"

    responses.add(
        responses.POST,
        url,
        body="Server error",
        status=500,
        content_type="application/vnd.git-lfs+json",
    )

    with pytest.raises(requests.HTTPError):
        github_lfs_batch_request(
            "Bearer TOKEN",
            [{"oid": "def", "size": 456}],
            "upload",
            repo_owner="acme",
            repo_name="widgets",
        )

    out = capsys.readouterr().out
    assert "LFS: batch failed with status 500: Server error" in out


@responses.activate
def test_success_first_try(no_sleep):
    attachment_content = b"deadbeef"
    sha256_hex = "2baf1f40105d9501fe319a8ec463fdf4325a2a5df445adf3f572f626253678c9"  # pragma: allowlist secret
    size = len(attachment_content)

    download_url = "https://cdn.example.com/file.bin"
    responses.get(
        download_url,
        status=200,
        body=attachment_content,
        content_type="octet/stream",
    )

    upload_url = "https://lfs.example.com/upload/here"
    responses.put(
        upload_url,
        status=201,
        json={"ok": True},
        content_type="application/json",
    )

    # Inputs
    source = (sha256_hex, size, download_url)
    dest = (upload_url, "put", {"X-Foo": "Bar"})

    # Run
    _download_from_cdn_and_upload_to_lfs_volume(source, dest)

    # Assertions: single HTTP call, correct method/URL/headers
    assert len(responses.calls) == 2
    download = responses.calls[0]
    assert download.request.url == download_url

    upload = responses.calls[1]
    assert upload.request.url == upload_url
    assert upload.request.method == "PUT"
    assert upload.request.headers.get("X-Foo") == "Bar"
    # Body came from the temp file; just ensure something was sent
    assert upload.request.body is not None


@responses.activate
def test_fail_after_max_retries(no_sleep):
    # Always wrong (size or digest) -> should never attempt upload
    download_url = "https://cdn.example.com/file.bin"
    responses.get(
        download_url,
        status=200,
        body="wrong",
        content_type="octet/stream",
    )

    source = ("correct" * 8, 7, download_url)
    dest = ("https://lfs.example.com/upload", "PUT", {})

    with pytest.raises(RuntimeError, match="failed to download"):
        _download_from_cdn_and_upload_to_lfs_volume(source, dest)

    methods = [r.request.method.upper() for r in responses.calls]
    assert "PUT" not in methods


@responses.activate
def test_upload_http_error(capsys, no_sleep):
    # Download OK, but upload returns 500 and raise_for_status should raise
    download_url = "https://cdn.example.com/file.bin"
    attachment_content = b"deadbeef"
    sha256_hex = "2baf1f40105d9501fe319a8ec463fdf4325a2a5df445adf3f572f626253678c9"  # pragma: allowlist secret
    size = len(attachment_content)
    responses.get(
        download_url,
        status=200,
        body=attachment_content,
        content_type="octet/stream",
    )

    upload_url = "https://lfs.example.com/upload"
    responses.add(
        responses.POST,
        upload_url,
        status=500,
        body="oops",
        content_type="text/plain",
    )

    source = (sha256_hex, size, download_url)
    dest = (upload_url, "post", {"Z": "1"})

    with pytest.raises(requests.HTTPError):
        _download_from_cdn_and_upload_to_lfs_volume(source, dest)

    out = capsys.readouterr().out
    # log line from upload failure should be printed
    assert "upload failed with 500: oops" in out


@responses.activate
@pytest.mark.parametrize("status", [200, 201, 204])
def test_verify_upload_success(status):
    oid = "a" * 64
    size = 123
    href = "https://lfs.example.com/verify"
    headers = {"X-Verify": "yes"}

    responses.add(
        responses.POST,
        href,
        status=status,
        json={"ok": True} if status != 204 else None,
        content_type="application/json",
    )

    _github_lfs_verify_upload((oid, size), (href, "POST", headers))

    assert len(responses.calls) == 1
    call = responses.calls[0]
    assert call.request.method == "POST"
    assert call.request.url == href
    assert call.request.headers.get("X-Verify") == "yes"
    payload = json.loads(call.request.body.decode("utf-8"))
    assert payload == {"oid": oid, "size": size}


@responses.activate
def test_verify_upload_failure_raises_and_logs(capsys):
    oid = "b" * 64
    size = 42
    href = "https://lfs.example.com/verify-fail"

    responses.add(
        responses.POST,
        href,
        status=500,
        body="bad",
        content_type="text/plain",
    )

    with pytest.raises(requests.HTTPError):
        _github_lfs_verify_upload((oid, size), (href, "POST", {"H": "1"}))

    out = capsys.readouterr().out
    assert f"LFS: verify for {oid} failed with 500: bad" in out


@responses.activate
def test_batch_upload_already_present_and_no_verify(capsys):
    # record if upload helper was called (should NOT be)
    download_url = "https://cdn.example.com/file.bin"
    attachment_content = b"deadbeef"
    sha256_hex = "2baf1f40105d9501fe319a8ec463fdf4325a2a5df445adf3f572f626253678c9"  # pragma: allowlist secret
    size = len(attachment_content)

    obj = (sha256_hex, size, download_url)
    batch_objects = [
        {
            "oid": obj[0],
            "actions": {
                # no 'upload' -> already present
                # no 'verify' -> nothing to call
            },
        }
    ]
    responses.add(
        responses.POST,
        "https://github.com/foo/bar.git/info/lfs/objects/batch",
        status=200,
        json={"objects": batch_objects},
        content_type="application/vnd.git-lfs+json",
    )

    github_lfs_batch_upload_many(
        [obj],
        repo_owner="foo",
        repo_name="bar",
        auth_header="Bearer TOKEN",
    )

    # only the batch call
    assert len(responses.calls) == 1
    out = capsys.readouterr().out
    assert f"already present {download_url}" in out
    assert "no verify action for" in out


@responses.activate
def test_batch_upload_raises_on_error_objects(capsys):
    o = ("d" * 64, 5, "https://cdn.example.com/d")
    batch_objects = [
        {
            "oid": o[0],
            "error": {"code": 422, "message": "unprocessable"},
        }
    ]
    responses.add(
        responses.POST,
        "https://github.com/foo/bar.git/info/lfs/objects/batch",
        status=200,
        json={"objects": batch_objects},
        content_type="application/vnd.git-lfs+json",
    )

    # The object was refused by the server: the caller must not push a pointer
    # for it, so the whole run has to fail.
    with pytest.raises(RuntimeError, match="1 object\\(s\\) could not be uploaded"):
        github_lfs_batch_upload_many(
            [o],
            repo_owner="foo",
            repo_name="bar",
            auth_header="Bearer TOKEN",
        )

    assert len(responses.calls) == 1  # only batch
    out = capsys.readouterr().out
    assert "upload error for" in out
    assert "422" in out
    assert "unprocessable" in out


@responses.activate
def test_batch_upload_raises_when_server_omits_object(capsys):
    o = ("e" * 64, 5, "https://cdn.example.com/e")
    responses.add(
        responses.POST,
        "https://github.com/foo/bar.git/info/lfs/objects/batch",
        status=200,
        # Server answers without the object we asked for.
        json={"objects": []},
        content_type="application/vnd.git-lfs+json",
    )

    with pytest.raises(RuntimeError, match="1 object\\(s\\) could not be uploaded"):
        github_lfs_batch_upload_many(
            [o],
            repo_owner="foo",
            repo_name="bar",
            auth_header="Bearer TOKEN",
        )

    out = capsys.readouterr().out
    assert f"server omitted oid {o[0]}" in out


@responses.activate
def test_batch_upload_reports_every_failed_object():
    objects = [(c * 64, 5, f"https://cdn.example.com/{c}") for c in "fgh"]
    responses.add(
        responses.POST,
        "https://github.com/foo/bar.git/info/lfs/objects/batch",
        status=200,
        json={
            "objects": [
                {"oid": oid, "error": {"code": 422, "message": "nope"}}
                for oid, _size, _url in objects
            ]
        },
        content_type="application/vnd.git-lfs+json",
    )

    # One bad object must not mask the others.
    with pytest.raises(RuntimeError) as exc_info:
        github_lfs_batch_upload_many(
            objects,
            repo_owner="foo",
            repo_name="bar",
            auth_header="Bearer TOKEN",
        )

    for oid, _size, _url in objects:
        assert oid in str(exc_info.value)


@responses.activate
def test_batch_upload_and_verify():
    download_url_1 = "https://cdn.example.com/file.bin"
    attachment_content_1 = b"deadbeef"
    sha256_hex_1 = "2baf1f40105d9501fe319a8ec463fdf4325a2a5df445adf3f572f626253678c9"  # pragma: allowlist secret
    size_1 = len(attachment_content_1)

    download_url_2 = "https://cdn.example.com/file2.bin"
    attachment_content_2 = b"deadbeef2"
    sha256_hex_2 = "5e2e0e8a6ce8ed283ade50645227a5a62bbd6c2dd80483880a640ad9d2236801"  # pragma: allowlist secret
    size_2 = len(attachment_content_2)

    # two objects, both need upload + verify
    o1 = (sha256_hex_1, size_1, download_url_1)
    o2 = (sha256_hex_2, size_2, download_url_2)
    batch_objects = [
        {
            "oid": o1[0],
            "actions": {
                "upload": {
                    "href": "https://upload.example.com/a",
                    "method": "PUT",
                    "header": {"U": "1"},
                },
                "verify": {
                    "href": "https://verify.example.com/a",
                    "header": {"V": "A"},
                },
            },
        },
        {
            "oid": o2[0],
            "actions": {
                "upload": {
                    "href": "https://upload.example.com/b",
                    # no method -> default to PUT
                    "header": {"U": "2"},
                },
                "verify": {
                    "href": "https://verify.example.com/b",
                    "header": {"V": "B"},
                },
            },
        },
    ]
    responses.add(
        responses.POST,
        "https://github.com/foo/bar.git/info/lfs/objects/batch",
        status=200,
        json={"objects": batch_objects},
        content_type="application/vnd.git-lfs+json",
    )

    # mock the download endpoints
    responses.get(download_url_1, body=attachment_content_1)
    responses.get(download_url_2, body=attachment_content_2)

    # mock the upload endpoints
    responses.put("https://upload.example.com/a")
    responses.put("https://upload.example.com/b")

    # mock the verify endpoints
    responses.add(responses.POST, "https://verify.example.com/a", status=204)
    responses.add(responses.POST, "https://verify.example.com/b", json={"ok": True})

    github_lfs_batch_upload_many(
        [o1, o2],
        repo_owner="foo",
        repo_name="bar",
        auth_header="Bearer TOKEN",
    )

    calls = responses.calls

    batch_call = next(
        c for c in calls if c.request.url.endswith("/info/lfs/objects/batch")
    )

    download_calls = [
        c for c in calls if c.request.url in {download_url_1, download_url_2}
    ]

    upload_calls = [
        c
        for c in calls
        if c.request.url
        in {
            "https://upload.example.com/a",
            "https://upload.example.com/b",
        }
    ]

    verify_calls = [
        c
        for c in calls
        if c.request.url
        in {
            "https://verify.example.com/a",
            "https://verify.example.com/b",
        }
    ]
    assert len(download_calls) == 2
    assert len(upload_calls) == 2
    assert len(verify_calls) == 2

    sent = json.loads(batch_call.request.body.decode("utf-8"))
    # order preserved: two objects with (oid,size)
    assert sent["operation"] == "upload"
    assert {o["oid"] for o in sent["objects"]} == {o1[0], o2[0]}

    if download_calls[0].request.url == download_url_2:
        download_calls.reverse()
    assert download_calls[0].request.url == download_url_1
    assert download_calls[1].request.url == download_url_2

    assert upload_calls[0].request.method == "PUT"
    assert upload_calls[1].request.method == "PUT"

    verify_a = next(c for c in verify_calls if c.request.url.endswith("/a"))
    assert verify_a.request.method == "POST"
    body_a = json.loads(verify_a.request.body.decode())
    assert body_a == {"oid": o1[0], "size": o1[1]}
    assert verify_a.request.headers["V"] == "A"

    verify_b = next(c for c in verify_calls if c.request.url.endswith("/b"))
    assert verify_b.request.method == "POST"
    body_b = json.loads(verify_b.request.body.decode())
    assert body_b == {"oid": o2[0], "size": o2[1]}
    assert verify_b.request.headers["V"] == "B"
