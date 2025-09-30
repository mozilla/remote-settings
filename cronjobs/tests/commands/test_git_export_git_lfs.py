import json

import commands
import pytest
import requests
import responses
from commands._git_export_lfs import (
    _download_from_cdn_and_upload_to_lfs_volume,
    _github_lfs_verify_upload,
    github_lfs_batch_request,
)
from commands.git_export import (
    github_lfs_batch_upload_many,
)


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(
        commands._git_export_lfs.time, "sleep", lambda s: None, raising=False
    )


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
        github_username="bob",
        github_token="token",
    )

    # only the batch call
    assert len(responses.calls) == 1
    out = capsys.readouterr().out
    assert f"already present {download_url}" in out
    assert "no verify action for" in out


@responses.activate
def test_batch_upload_handles_error_objects(capsys):
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

    github_lfs_batch_upload_many(
        [o],
        repo_owner="foo",
        repo_name="bar",
        github_username="bob",
        github_token="token",
    )

    assert len(responses.calls) == 1  # only batch
    out = capsys.readouterr().out
    assert "upload error for" in out
    assert "422" in out
    assert "unprocessable" in out


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
        github_username="user",
        github_token="token",
    )

    (
        _batch_call,
        _dl_call_1,
        _dl_call_2,
        _upload_call_1,
        _upload_call_2,
        verify_call_1,
        verify_call_2,
    ) = responses.calls

    # batch call auth header present
    expected_header = "Basic dXNlcjp0b2tlbg=="  # pragma: allowlist secret
    assert _batch_call.request.headers.get("Authorization") == expected_header
    sent = json.loads(_batch_call.request.body.decode("utf-8"))
    # order preserved: two objects with (oid,size)
    assert sent["operation"] == "upload"
    assert {o["oid"] for o in sent["objects"]} == {o1[0], o2[0]}

    if _dl_call_1.request.url == download_url_2:
        _dl_call_1, _dl_call_2 = _dl_call_2, _dl_call_1

    assert _dl_call_1.request.url == download_url_1
    assert _dl_call_2.request.url == download_url_2

    assert _upload_call_1.request.method == "PUT"
    assert _upload_call_2.request.method == "PUT"

    if verify_call_1.request.url == "https://verify.example.com/b":
        verify_call_1, verify_call_2 = verify_call_2, verify_call_1

    assert verify_call_1.request.url == "https://verify.example.com/a"
    assert verify_call_1.request.method == "POST"
    assert verify_call_1.request.headers.get("V") == "A"
    body1 = json.loads(verify_call_1.request.body.decode("utf-8"))
    assert body1 == {"oid": o1[0], "size": o1[1]}

    assert verify_call_2.request.url == "https://verify.example.com/b"
    assert verify_call_2.request.method == "POST"
    assert verify_call_2.request.headers.get("V") == "B"
    body2 = json.loads(verify_call_2.request.body.decode("utf-8"))
    assert body2 == {"oid": o2[0], "size": o2[1]}
