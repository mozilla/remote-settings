import json
import os
import shutil
import tempfile

import pygit2
import pytest
from app import read_json_mozlz4, write_json_mozlz4
from fastapi.testclient import TestClient


def upsert_blobs(repo, items, base_tree=None):
    if isinstance(base_tree, pygit2.Oid):
        base_tree = repo[base_tree]
    root = repo.TreeBuilder(base_tree)

    def rec(b, parts, oid):
        if len(parts) == 1:
            if oid is None:
                # Deletion
                try:
                    b.remove(parts[0])
                except KeyError:
                    pass
            else:
                b.insert(parts[0], oid, pygit2.GIT_FILEMODE_BLOB)
            return
        h, *t = parts
        e = b.get(h)
        sb = (
            repo.TreeBuilder(repo[e.id])
            if e and e.filemode == pygit2.GIT_FILEMODE_TREE
            else repo.TreeBuilder()
        )
        rec(sb, t, oid)
        b.insert(h, sb.write(), pygit2.GIT_FILEMODE_TREE)

    for path, data in items:
        if data is None:
            oid = None
        else:
            if isinstance(data, dict):
                data = json.dumps(data)
            if isinstance(data, str):
                data = data.encode()
            oid = repo.create_blob(data)
        rec(root, [p for p in path.strip("/").split("/") if p], oid)

    return root.write()


@pytest.fixture(scope="module")
def temp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture(scope="module", autouse=True)
def fake_repo(temp_dir):
    author = pygit2.Signature("Test", "test@example.com", 1234567890)
    repo = pygit2.init_repository(temp_dir, bare=False, initial_head="v1/common")
    base_tree = repo.TreeBuilder().write()
    tree_oid = upsert_blobs(
        repo,
        items=[
            (
                "monitor-changes.json",
                {
                    "metadata": {},
                    "timestamp": 1759201028849,
                    "changes": [
                        {
                            "collection": "password-rules",
                            "bucket": "main",
                            "last_modified": 123456789,
                        },
                        {
                            "collection": "intermediates",
                            "bucket": "security-state",
                            "last_modified": 123456788,
                        },
                    ],
                },
            ),
            (
                "broadcasts.json",
                {
                    "broadcasts": {
                        "remote-settings/monitor_changes": '"1759201028849"'
                    },
                    "code": 200,
                },
            ),
            (
                "server-info.json",
                {
                    "project_name": "Remote Settings PROD",
                    "project_docs": "https://remote-settings.readthedocs.io",
                    "capabilities": {
                        "attachments": {
                            "description": "Add file attachments to records",
                            "url": "https://github.com/Kinto/kinto-attachment/",
                            "version": "7.1.0",
                            "base_url": "https://firefox-settings-attachments.cdn.mozilla.net/",
                        },
                    },
                },
            ),
            (
                "cert-chains/a/b/cert.pem",
                "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----\n".encode(),
            ),
        ],
        base_tree=base_tree,
    )
    # Create a common branch with some data.
    repo.create_commit("refs/heads/v1/common", author, author, "Message", tree_oid, [])

    # Create a bucket branch with a collection and a record.
    base_tree = repo.TreeBuilder().write()
    tree_oid = upsert_blobs(
        repo,
        items=[
            (
                "password-rules/abc.json",
                {"id": "abc", "last_modified": 113456788, "foo": "baz"},
            ),
            (
                "password-rules/def.json",
                {"id": "def", "last_modified": 113456789, "pim": "pam"},
            ),
            (
                "password-rules/metadata.json",
                {
                    "id": "password-rules",
                    "bucket": "main",
                    "signature": {"x5u": "https://autograph/a/b/cert.pem"},
                },
            ),
        ],
        base_tree=base_tree,
    )
    oid = repo.create_commit(
        "refs/heads/v1/buckets/main", author, author, "Message", tree_oid, []
    )
    repo.create_tag(
        "v1/timestamps/main/password-rules/113456789",
        oid,
        pygit2.GIT_OBJECT_COMMIT,
        author,
        "Message",
    )

    # Create a new version of this collection.
    base_tree = repo[oid].tree
    tree_oid = upsert_blobs(
        repo,
        items=[
            (
                "password-rules/abc.json",
                {"id": "abc", "last_modified": 123456789, "foo": "bar"},
            ),
            (
                "password-rules/def.json",
                None,
            ),
        ],
        base_tree=base_tree,
    )

    oid = repo.create_commit(
        "refs/heads/v1/buckets/main", author, author, "Message", tree_oid, [oid]
    )
    repo.create_tag(
        "v1/timestamps/main/password-rules/123456789",
        oid,
        pygit2.GIT_OBJECT_COMMIT,
        author,
        "Message",
    )

    # Create some attachments.
    os.makedirs(f"{temp_dir}/attachments/bundles", exist_ok=True)
    for path in [
        "main-workspace/regions/world.geojson",
        "security-state/crlite/bloomfilter.bin",
        "security-state/intermediates/file.pem",
    ]:
        full_path = os.path.join(temp_dir, "attachments", path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(b"x" * 1000)

    return repo


@pytest.fixture(autouse=True)
def clear_settings_cache():
    from app import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def get_settings_override(temp_dir):
    from app import Settings

    return lambda: Settings(self_contained=True, git_repo_path=temp_dir)


@pytest.fixture
def app(get_settings_override):
    from app import app, get_settings

    app.dependency_overrides[get_settings] = get_settings_override
    return app


@pytest.fixture
def api_client(app):
    with TestClient(app=app, base_url="http://test") as client:
        yield client


def test_lbheartbeat(api_client):
    resp = api_client.get("/v2/__lbheartbeat__")
    assert resp.status_code == 200


def test_heartbeat(api_client, monkeypatch, fake_repo):
    monkeypatch.setenv("GIT_REPO_PATH", fake_repo.path)

    resp = api_client.get("/v2/__heartbeat__")
    assert resp.status_code == 200


def test_version(api_client):
    resp = api_client.get("/v2/__version__")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "v0.0.0"


def test_heartbeat_failing(api_client, temp_dir, monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        # Copy the fake repo to a temp dir and delete stuff.
        shutil.copytree(temp_dir, td, dirs_exist_ok=True)

        repo = pygit2.init_repository(td)

        for tag in repo.references:
            if tag.startswith("refs/tags/v1/timestamps/"):
                repo.references.delete(tag)

        monkeypatch.setenv("GIT_REPO_PATH", td)

        resp = api_client.get("/v2/__heartbeat__")

    assert resp.status_code == 500
    assert resp.json()["checks"]["git_repo_health"] == "error"


def test_bad_git_folder(api_client, monkeypatch):
    monkeypatch.setenv("GIT_REPO_PATH", "/tmp/does/not/exist")

    resp = api_client.get("/v2/__heartbeat__")

    assert resp.status_code == 500
    assert resp.json()["checks"]["git_repo_health"] == "error"


def test_lfs_pointer_found(api_client, temp_dir, monkeypatch):
    monkeypatch.setenv("GIT_REPO_PATH", temp_dir)
    monkeypatch.setenv("SELF_CONTAINED", "true")
    with open(f"{temp_dir}/attachments/bundles/startup.json.mozlz4", "wb") as f:
        f.write(b"version https://git-lfs.github.com/spec/v1\n")

    resp = api_client.get("/v2/__heartbeat__")

    assert resp.status_code == 500
    assert "git.health.0002" in resp.json()["details"]["git_repo_health"]["messages"]


def test_hello_view_redirects(api_client):
    resp = api_client.get("/", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["Location"] == "/v2/"

    resp = api_client.get("/v2", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["Location"] == "/v2/"


def test_hello_view(api_client):
    resp = api_client.get("/v2/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_version"] == "0.0.1"
    assert (
        data["capabilities"]["attachments"]["base_url"] == "http://test/v2/attachments/"
    )


def test_broadcast_view(api_client):
    resp = api_client.get("/v2/__broadcasts__")
    assert resp.status_code == 200
    data = resp.json()
    assert "remote-settings/monitor_changes" in data["broadcasts"]


def test_monitor_changes_view(api_client):
    resp = api_client.get(
        "/v2/buckets/monitor/collections/changes/changeset?_expected=0"
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["changes"][0]["bucket"] == "main"
    assert data["changes"][0]["collection"] == "password-rules"
    assert "last_modified" in data["changes"][0]


def test_monitor_changes_view_filtered_since(api_client):
    resp = api_client.get(
        '/v2/buckets/monitor/collections/changes/changeset?_since="223456789"&_expected=0'
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["changes"] == []


def test_monitor_changes_view_filtered_bad_since(api_client):
    resp = api_client.get(
        '/v2/buckets/monitor/collections/changes/changeset?_since="223456789"&_expected=123456789'
    )
    assert resp.status_code == 400


def test_monitor_changes_view_filtered_bid(api_client):
    resp = api_client.get(
        "/v2/buckets/monitor/collections/changes/changeset?bucket=main"
    )
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["changes"]) == 1
    assert data["changes"][0]["bucket"] == "main"


def test_monitor_changes_view_filtered_cid(api_client):
    resp = api_client.get(
        "/v2/buckets/monitor/collections/changes/changeset?collection=intermediates"
    )
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["changes"]) == 1
    assert data["changes"][0]["collection"] == "intermediates"


def test_changeset(api_client):
    resp = api_client.get("/v2/buckets/main/collections/password-rules/changeset")
    assert resp.status_code == 200
    data = resp.json()

    assert data["timestamp"] == 123456789
    assert (
        data["metadata"]["signature"]["x5u"]
        == "http://test/v2/cert-chains/a/b/cert.pem"
    )
    assert data["changes"] == [{"id": "abc", "last_modified": 123456789, "foo": "bar"}]


def test_changeset_unknown_collection(api_client):
    resp = api_client.get("/v2/buckets/main/collections/wallpapers/changeset")
    assert resp.status_code == 404


@pytest.mark.parametrize(
    "since", ["42", '"not-a-number"', "123.456", "-1", '"223456789"']
)
def test_changeset_bad_since(api_client, since):
    resp = api_client.get(
        f"/v2/buckets/main/collections/password-rules/changeset?_since={since}&_expected=123456789"
    )
    assert resp.status_code in (400, 422)


def test_changeset_unknown_since(api_client):
    resp = api_client.get(
        '/v2/buckets/main/collections/password-rules/changeset?_since="42"',
        follow_redirects=False,
    )
    assert resp.status_code == 307
    assert (
        resp.headers["Location"]
        == "http://test/v2/buckets/main/collections/password-rules/changeset"
    )


def test_changeset_since(api_client):
    resp = api_client.get(
        '/v2/buckets/main/collections/password-rules/changeset?_since="113456789"'
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["timestamp"] == 123456789
    assert data["changes"] == [
        {"id": "abc", "last_modified": 123456789, "foo": "bar"},
        {"id": "def", "deleted": True},
    ]


def test_cert_chain(api_client):
    resp = api_client.get("/v2/cert-chains/a/b/cert.pem")
    assert resp.status_code == 200
    assert "-----BEGIN CERTIFICATE-----" in resp.text


def test_startup_rewrites_x5u(api_client, temp_dir):
    with open(
        os.path.join(temp_dir, "attachments", "bundles", "startup.json.mozlz4"), "wb"
    ) as f:
        write_json_mozlz4(
            f,
            [
                {"metadata": {"signature": {"x5u": "https://autograph/a/b/cert.pem"}}},
            ],
        )

    resp = api_client.get("/v2/attachments/bundles/startup.json.mozlz4")
    assert resp.status_code == 200
    data = read_json_mozlz4(resp.content)
    assert (
        data[0]["metadata"]["signature"]["x5u"]
        == "http://test/v2/cert-chains/a/b/cert.pem"
    )


def test_attachment_bad_path(api_client):
    resp = api_client.get("/v2/attachments/../../etc/hosts")
    assert resp.status_code == 404


def test_attachment_unknown_file(api_client):
    resp = api_client.get("/v2/attachments/path/unknown.txt")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Attachment path/unknown.txt not found"


def test_attachment_lfs_file(api_client, temp_dir):
    with open(
        f"{temp_dir}/attachments/bundles/security-state--intermediates.zip", "w"
    ) as f:
        f.write("version https://git-lfs.github.com/spec/v1")

    with pytest.raises(Exception, match="LFS pointer"):
        api_client.get("/v2/attachments/bundles/security-state--intermediates.zip")


def test_attachment_real_file(api_client):
    resp = api_client.get("/v2/attachments/main-workspace/regions/world.geojson")
    assert resp.status_code == 200
    assert len(resp.content) == 1000


def test_attachment_supports_head(api_client):
    resp = api_client.head("/v2/attachments/main-workspace/regions/world.geojson")
    assert resp.status_code == 200


def test_attachment_mimetype(api_client):
    resp = api_client.get("/v2/attachments/main-workspace/regions/world.geojson")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "application/geo+json"


def test_attachment_custom_mimetype(api_client):
    resp = api_client.get("/v2/attachments/security-state/intermediates/file.pem")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "application/x-pem-file"


def test_attachment_unknown_mimetype(api_client):
    resp = api_client.get("/v2/attachments/security-state/crlite/bloomfilter.bin")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "application/octet-stream"


def test_metrics_traces_durations(api_client):
    resp = api_client.get("/v2/__metrics__")
    assert resp.status_code == 200
    metrics_text = resp.text

    assert (
        'remotesettings_request_duration_seconds_bucket{bucket_id="main",collection_id="password-rules",endpoint="collection_changeset"'
        in metrics_text
    )
    assert (
        'remotesettings_request_summary_total{bucket_id="main",collection_id="password-rules",endpoint="collection_changeset"'
        in metrics_text
    )
    assert "remotesettings_repository_age_seconds " in metrics_text
    assert (
        'remotesettings_repository_read_latency_seconds_bucket{le="0.001",operation="get_file_content"}'
        in metrics_text
    )
