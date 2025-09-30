import importlib
import os
import shutil
from unittest import mock

import pygit2
import pytest
import responses
from commands import git_export


@pytest.fixture(autouse=True)
def configs(monkeypatch, tmp_path):
    monkeypatch.setenv("WORK_DIR", str(tmp_path / "workdir"))
    monkeypatch.setenv("SERVER", "http://testserver:9999/v1")
    monkeypatch.setenv("REPO_NAME", "remote-settings-data-stage")

    reloaded = importlib.reload(git_export)
    yield reloaded

    # Restore defaults
    importlib.reload(git_export)


@pytest.fixture
def mock_git_fetch():
    with mock.patch("pygit2.Remote.fetch") as mock_fetch:
        yield mock_fetch


@pytest.fixture
def mock_git_push():
    with mock.patch("pygit2.Remote.push") as mock_push:
        yield mock_push


@pytest.fixture
def mock_repo_sync_content():
    with mock.patch.object(git_export, "repo_sync_content") as mock_sync:
        mock_sync.return_value = [], [], []
        yield mock_sync


@pytest.fixture
def mock_github_lfs():
    with mock.patch.object(git_export, "github_lfs_batch_upload_many") as mock_lfs:
        yield mock_lfs


@pytest.fixture
def mock_ls_remotes():
    with mock.patch("pygit2.Remote.ls_remotes") as mock_ls:
        mock_ls.return_value = []
        yield mock_ls


@pytest.fixture
def mock_rs_server_content():
    responses.add(
        responses.GET,
        "http://testserver:9999/v1/",
        json={
            "capabilities": {
                "attachments": {"base_url": "http://cdn.example.com/v1/attachments/"}
            }
        },
    )

    responses.add(
        responses.GET,
        "http://testserver:9999/v1/__broadcasts__",
        json={"broadcasts/rs": '"42"'},
    )

    responses.add(
        responses.GET,
        "http://testserver:9999/v1/buckets/monitor/collections/changes/changeset",
        json={
            "timestamp": 1700000000000,
            "changes": [
                {
                    "last_modified": 1700000000000,
                    "bucket": "bid1",
                    "collection": "cid1",
                },
                {
                    "last_modified": 1600000000000,
                    "bucket": "bid2",
                    "collection": "cid2",
                },
            ],
        },
    )

    responses.add(
        responses.GET,
        "http://testserver:9999/v1/buckets/bid1/collections/cid1/changeset",
        json={
            "timestamp": 1700000000000,
            "metadata": {
                "bucket": "bid1",
                "id": "cid1",
                "signature": {
                    "x5u": "https://autograph.example.com/keys/123",
                },
            },
            "changes": [
                {
                    "id": "rid1-1",
                    "last_modified": 1700000000000,
                    "hello": "world",
                }
            ],
        },
    )

    responses.add(
        responses.GET,
        "http://testserver:9999/v1/buckets/bid2/collections/cid2/changeset",
        json={
            "timestamp": 1600000000000,
            "metadata": {
                "bucket": "bid2",
                "id": "cid2",
                "signature": {
                    "x5u": "https://autograph.example.com/keys/123",
                },
            },
            "changes": [
                {
                    "id": "rid2-1",
                    "last_modified": 1600000000000,
                    "attachment": {
                        "location": "bid2/random-name.bin",
                        "content-type": "application/wasm",
                        "size": 30000,
                        "hash": "abcdefghijklmnopqrstuvwxyz",
                    },
                }
            ],
        },
    )

    responses.add(
        responses.GET,
        "https://autograph.example.com/keys/123",
        body="---CERTIFICATE---",
    )

    responses.add(
        responses.GET,
        "http://cdn.example.com/v1/attachments/bundles/startup.json.mozlz4",
        body=b"a" * 42,
    )

    responses.add(
        responses.GET,
        "http://cdn.example.com/v1/attachments/bid2/random-name.bin",
        body=b"123",
    )


def read_file(repo, branch, filepath):
    ref = f"refs/heads/{branch}"
    branch_ref = repo.lookup_reference(ref)
    commit = repo[branch_ref.target]
    node = commit.tree
    for part in filepath.split("/"):
        entry = node[part]
        obj = repo[entry.id]
        node = obj
    return obj.data


def init_fake_repo(path):
    repo = pygit2.init_repository(path, bare=True, initial_head="main")
    repo.remotes.create("origin", git_export.GIT_REMOTE_URL)
    author = pygit2.Signature("Test User", "test@example.com")
    builder = repo.TreeBuilder()
    tree = builder.write()
    commit_id = repo.create_commit(
        "HEAD",  # reference name
        author,  # author
        author,  # committer
        "initial commit",
        tree,
        [],  # no parents
    )
    commit = repo[commit_id]

    repo.branches.local.create("v1/common", commit)
    refname = "refs/remotes/origin/v1/common"
    repo.references.create(refname, commit.id)

    repo.set_head("refs/heads/v1/common")
    return repo


def simulate_pushed(repo, mock_ls_remotes):
    # Simulate that these branches and tags were pushed in previous `git_export` call.
    for branch in repo.branches.local:
        commit = repo.lookup_reference(f"refs/heads/{branch}").peel()
        refname = f"refs/remotes/origin/{branch}"
        try:
            repo.references.create(refname, commit.id)
        except pygit2.AlreadyExistsError:
            repo.references.delete(refname)
            repo.references.create(refname, commit.id)
    ref_names = [
        {"name": tag, "local": False}
        for tag in repo.listall_references()
        if tag.startswith("refs/tags/")
    ]
    print(ref_names)
    mock_ls_remotes.return_value = ref_names


@pytest.fixture
def repo():
    repo = init_fake_repo(git_export.WORK_DIR)
    yield repo
    shutil.rmtree(git_export.WORK_DIR, ignore_errors=True)


def test_clone_must_match_remote_url_if_dir_exists():
    pygit2.init_repository(git_export.WORK_DIR, bare=True)
    repo = pygit2.Repository(git_export.WORK_DIR)
    repo.remotes.create("origin", "https://example.com/repo.git")

    with pytest.raises(ValueError, match="does not match"):
        git_export.git_export(None, None)


def test_remote_is_clone_if_dir_missing(
    mock_repo_sync_content, mock_github_lfs, mock_git_push
):
    def _fake_clone(url, path, *args, **kwargs):
        return init_fake_repo(path)

    with mock.patch.object(
        pygit2, "clone_repository", side_effect=_fake_clone
    ) as mock_clone:
        assert not os.path.exists(git_export.WORK_DIR)

        git_export.git_export(None, None)

    ((called_url, called_path, *_), _kwargs) = mock_clone.call_args
    assert called_url == git_export.GIT_REMOTE_URL
    assert called_path == git_export.WORK_DIR


@responses.activate
def test_repo_sync_content_starts_from_scratch_if_no_previous_run(
    capsys,
    repo,
    mock_git_fetch,
    mock_ls_remotes,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    git_export.git_export(None, None)

    mock_git_fetch.assert_called_once()
    stdout = capsys.readouterr().out
    assert "No previous tags found" in stdout
    assert "2 collections changed" in stdout

    (args, _) = mock_git_push.call_args_list[0]
    assert args == (
        [
            "+refs/heads/v1/buckets/bid1:refs/heads/v1/buckets/bid1",
            "+refs/heads/v1/buckets/bid2:refs/heads/v1/buckets/bid2",
            "+refs/heads/v1/common:refs/heads/v1/common",
            "+refs/tags/v1/timestamps/bid1/cid1/1700000000000:refs/tags/v1/timestamps/bid1/cid1/1700000000000",
            "+refs/tags/v1/timestamps/bid2/cid2/1600000000000:refs/tags/v1/timestamps/bid2/cid2/1600000000000",
            "+refs/tags/v1/timestamps/common/1700000000000:refs/tags/v1/timestamps/common/1700000000000",
        ],
    )


@responses.activate
def test_repo_sync_does_nothing_if_up_to_date(
    capsys,
    repo,
    mock_git_fetch,
    mock_ls_remotes,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    git_export.git_export(None, None)
    simulate_pushed(repo, mock_ls_remotes)
    capsys.readouterr()  # Clear previous output

    git_export.git_export(None, None)

    stdout = capsys.readouterr().out
    assert "Found latest tag: 1700000000000" in stdout
    assert "No new changes since last run" in stdout
    assert "0 attachments to upload" in stdout
    assert "Everything up-to-date" in stdout


@responses.activate
def test_repo_sync_can_be_forced_even_if_up_to_date(
    capsys,
    repo,
    mock_git_fetch,
    mock_ls_remotes,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    git_export.git_export(None, None)
    simulate_pushed(repo, mock_ls_remotes)
    capsys.readouterr()  # Clear previous output

    git_export.FORCE = True
    git_export.git_export(None, None)

    stdout = capsys.readouterr().out
    assert "No changes for common branch" in stdout
    assert "No changes for bid1/cid1 branch" in stdout
    assert "No changes for bid2/cid2 branch" in stdout


@responses.activate
def test_repo_sync_content_uses_previous_run_to_fetch_changes(
    capsys,
    repo,
    mock_git_fetch,
    mock_ls_remotes,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    repo.create_tag(
        "v1/timestamps/common/1600000000000",
        repo.lookup_reference("refs/heads/v1/common").target,
        pygit2.GIT_OBJECT_COMMIT,
        pygit2.Signature("Test User", "test@example.com"),
        "Test tag at 1600000000000",
    )
    mock_ls_remotes.return_value = [
        {"name": "refs/tags/v1/timestamps/common/1600000000000", "local": False}
    ]

    git_export.git_export(None, None)

    stdout = capsys.readouterr().out
    assert "Found latest tag: 1600000000000" in stdout
    assert "1 collections changed" in stdout

    urls = [call.request.url.split("?")[0] for call in responses.calls]
    assert "http://testserver:9999/v1/buckets/bid1/collections/cid1/changeset" in urls
    assert (
        "http://testserver:9999/v1/buckets/bid2/collections/cid2/changeset" not in urls
    )

    (args, _) = mock_git_push.call_args_list[0]
    assert args == (
        [
            "+refs/heads/v1/buckets/bid1:refs/heads/v1/buckets/bid1",
            "+refs/heads/v1/common:refs/heads/v1/common",
            "+refs/tags/v1/timestamps/bid1/cid1/1700000000000:refs/tags/v1/timestamps/bid1/cid1/1700000000000",
            "+refs/tags/v1/timestamps/common/1700000000000:refs/tags/v1/timestamps/common/1700000000000",
        ],
    )


@responses.activate
def test_repo_sync_content_ignores_previous_run_if_forced(
    capsys,
    repo,
    mock_git_fetch,
    mock_ls_remotes,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    repo.create_tag(
        "v1/timestamps/common/1600000000000",
        repo.lookup_reference("refs/heads/v1/common").target,
        pygit2.GIT_OBJECT_COMMIT,
        pygit2.Signature("Test User", "test@example.com"),
        "Test tag at 1600000000000",
    )
    mock_ls_remotes.return_value = [
        {"name": "refs/tags/v1/timestamps/common/1600000000000", "local": False}
    ]

    git_export.FORCE = True
    git_export.git_export(None, None)

    stdout = capsys.readouterr().out
    assert "Found latest tag: 1600000000000. Ignoring (forced)" in stdout
    assert "2 collections changed" in stdout
    git_export.FORCE = False


@responses.activate
def test_repo_sync_stores_server_info(
    repo,
    mock_git_fetch,
    mock_ls_remotes,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    git_export.git_export(None, None)

    blob = read_file(repo, "v1/common", "server-info.json")
    assert "capabilities" in blob.decode()


@responses.activate
def test_repo_sync_stores_monitor_changes(
    repo,
    mock_git_fetch,
    mock_ls_remotes,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    git_export.git_export(None, None)

    blob = read_file(repo, "v1/common", "monitor-changes.json")
    assert '{"changes":[{"bucket":"bid1","collection":"cid1"' in blob.decode()


@responses.activate
def test_repo_sync_stores_broadcasts(
    repo,
    mock_git_fetch,
    mock_ls_remotes,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    git_export.git_export(None, None)

    blob = read_file(repo, "v1/common", "broadcasts.json")
    assert "broadcasts/rs" in blob.decode()


@responses.activate
def test_repo_sync_stores_cert_chains(
    repo,
    mock_git_fetch,
    mock_ls_remotes,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    git_export.git_export(None, None)

    blob = read_file(repo, "v1/common", "cert-chains/keys/123")
    assert "---CERTIFICATE---" in blob.decode()


@responses.activate
def test_repo_sync_tags_common_branch(
    repo,
    mock_git_fetch,
    mock_ls_remotes,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    git_export.git_export(None, None)

    tags = [
        tag
        for tag in repo.listall_references()
        if tag.startswith("refs/tags/v1/timestamps/common/")
    ]
    assert "refs/tags/v1/timestamps/common/1700000000000" in tags


@responses.activate
def test_repo_sync_stores_collections_records_in_buckets_branches_with_tags(
    repo,
    mock_git_fetch,
    mock_ls_remotes,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    git_export.git_export(None, None)

    branches = [
        b for b in repo.listall_references() if b.startswith("refs/heads/v1/buckets/")
    ]
    assert "refs/heads/v1/buckets/bid1" in branches
    assert "refs/heads/v1/buckets/bid2" in branches

    tags = [tag for tag in repo.listall_references() if tag.startswith("refs/tags")]
    assert "refs/tags/v1/timestamps/bid1/cid1/1700000000000" in tags
    assert "refs/tags/v1/timestamps/bid2/cid2/1600000000000" in tags

    rid1 = read_file(repo, "v1/buckets/bid1", "cid1/rid1-1.json")
    assert '"hello":"world"' in rid1.decode()

    rid2 = read_file(repo, "v1/buckets/bid2", "cid2/rid2-1.json")
    assert '"attachment":{' in rid2.decode()


@responses.activate
def test_repo_sync_stores_attachments_as_lfs_pointers(
    repo,
    mock_git_fetch,
    mock_ls_remotes,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    git_export.git_export(None, None)

    rid2 = read_file(repo, "v1/common", "attachments/bid2/random-name.bin")
    assert "lfs" in rid2.decode()

    (_, kwargs) = mock_github_lfs.call_args_list[0]
    objs = [(size, url) for hash, size, url in kwargs["objects"]]
    assert (30000, "http://cdn.example.com/v1/attachments/bid2/random-name.bin") in objs
    assert (
        42,
        "http://cdn.example.com/v1/attachments/bundles/startup.json.mozlz4",
    ) in objs


@responses.activate
def test_repo_syncs_attachment_bundles(
    repo,
    mock_git_fetch,
    mock_ls_remotes,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    responses.replace(
        responses.GET,
        "http://testserver:9999/v1/buckets/bid1/collections/cid1/changeset",
        json={
            "timestamp": 1800000000000,
            "metadata": {
                "bucket": "bid1",
                "id": "cid1",
                "attachment": {"bundle": True},
                "signature": {
                    "x5u": "https://autograph.example.com/keys/123",
                },
            },
            "changes": [],
        },
    )
    responses.add(
        responses.GET,
        "http://cdn.example.com/v1/attachments/bundles/bid1--cid1.zip",
        body=b"fake bundle content",
    )

    git_export.git_export(None, None)

    bundle = read_file(repo, "v1/common", "attachments/bundles/bid1--cid1.zip")
    assert "lfs" in bundle.decode()


@responses.activate
def test_repo_is_resetted_to_local_content_on_error(
    capsys,
    repo,
    mock_git_fetch,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
    mock_ls_remotes,
):
    git_export.git_export(None, None)
    simulate_pushed(repo, mock_ls_remotes)

    responses.replace(
        responses.GET,
        "http://testserver:9999/v1/buckets/monitor/collections/changes/changeset",
        json={
            "timestamp": 1800000000000,
            "changes": [
                {
                    "last_modified": 1800000000000,
                    "bucket": "bid1",
                    "collection": "cid0",
                },
                {
                    "last_modified": 1700000000000,
                    "bucket": "bid1",
                    "collection": "cid1",
                },
                {
                    "last_modified": 1600000000000,
                    "bucket": "bid2",
                    "collection": "cid2",
                },
            ],
        },
    )
    responses.add(
        responses.GET,
        "http://testserver:9999/v1/buckets/bid1/collections/cid0/changeset",
        json={
            "timestamp": 1800000000000,
            "metadata": {
                "bucket": "bid1",
                "id": "cid0",
                "signature": {
                    "x5u": "https://autograph.example.com/keys/123",
                },
            },
            "changes": [],
        },
    )

    mock_github_lfs.side_effect = Exception("GitHub LFS error")

    with pytest.raises(Exception, match="GitHub LFS error"):
        git_export.git_export(None, None)

    stdout = capsys.readouterr().out
    assert "Error occurred: GitHub LFS error" in stdout

    assert "Rolling back local changes" in stdout
    assert "Resetting local branch v1/common to remote origin/v1/common" in stdout
    assert (
        "Resetting local branch v1/buckets/bid1 to remote origin/v1/buckets/bid1"
        in stdout
    )
    assert "Delete local tag refs/tags/v1/timestamps/bid1/cid0/1800000000000" in stdout
    assert "Delete local tag refs/tags/v1/timestamps/common/1800000000000" in stdout
