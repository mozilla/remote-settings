import json
import tempfile

import pygit2
import pytest
from fastapi.testclient import TestClient


def upsert_blobs(repo, items, base_tree=None):
    if isinstance(base_tree, pygit2.Oid):
        base_tree = repo[base_tree]
    root = repo.TreeBuilder(base_tree)

    def rec(b, parts, oid):
        if len(parts) == 1:
            b.insert(parts[0], oid, pygit2.GIT_FILEMODE_BLOB)
            return
        h, *t = parts
        e = b.get(h)
        sb = (
            repo.TreeBuilder(repo[e.oid])
            if e and e.filemode == pygit2.GIT_FILEMODE_TREE
            else repo.TreeBuilder()
        )
        rec(sb, t, oid)
        b.insert(h, sb.write(), pygit2.GIT_FILEMODE_TREE)

    for path, data in items:
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
                        }
                    ],
                },
            ),
            (
                "broadcast.json",
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
                {"id": "abc", "last_modified": 123456789, "foo": "bar"},
            ),
        ],
        base_tree=base_tree,
    )
    oid = repo.create_commit(
        "refs/heads/v1/buckets/main", author, author, "Message", tree_oid, []
    )
    repo.create_tag(
        "v1/timestamps/main/password-rules/123456789",
        oid,
        pygit2.GIT_OBJECT_COMMIT,
        author,
        "Message",
    )

    return repo


@pytest.fixture
def get_settings_override(fake_repo):
    from app import Settings

    return lambda: Settings(self_contained=True, git_repo_path=fake_repo.path)


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


def test_monitor_changes_view(api_client):
    resp = api_client.get(
        "/v2/buckets/monitor/collections/changes/changeset?_expected=0"
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["changes"][0]["bucket"] == "main"
    assert data["changes"][0]["collection"] == "password-rules"
    assert "last_modified" in data["changes"][0]
