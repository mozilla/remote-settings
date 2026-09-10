import asyncio
import importlib
import json
import os
import shutil
from unittest import mock

import pygit2
import pytest
import responses
from commands import git_export
from commands._git_export_git_tools import tree_upsert_blobs


@pytest.fixture(autouse=True)
def configs(monkeypatch, tmp_path):
    monkeypatch.setenv("WORK_DIR", str(tmp_path / "workdir"))
    monkeypatch.setenv("SERVER", "http://testserver:9999/v1")
    monkeypatch.setenv("REPO_NAME", "remote-settings-data-stage")
    monkeypatch.setenv("FORCE", "false")
    # Fake SSH keys
    ssh_privkey = tmp_path / "id_ed25519"
    ssh_pubkey = tmp_path / "id_ed25519.pub"
    monkeypatch.setenv("SSH_PRIVKEY_PATH", str(ssh_privkey))
    monkeypatch.setenv("SSH_PUBKEY_PATH", str(ssh_pubkey))
    ssh_privkey.write_text("private_key_content")
    ssh_pubkey.write_text("public_key_content")

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
        mock_sync.return_value = [], set()
        yield mock_sync


@pytest.fixture
def mock_github_lfs():
    with mock.patch.object(git_export, "github_lfs_batch_upload_many") as mock_lfs:
        with mock.patch.object(
            git_export, "github_lfs_validate_credentials"
        ) as mock_creds:
            mock_creds.return_value = "Bearer TOKEN"
            yield mock_lfs


@pytest.fixture
def mock_truncate_branch():
    with mock.patch.object(git_export, "truncate_branch") as mock_truncate:
        mock_truncate.return_value = False
        yield mock_truncate


@pytest.fixture
def mock_rs_server_content():
    responses.add(
        responses.GET,
        "http://testserver:9999/v1/",
        json={
            "capabilities": {
                "attachments": {"base_url": "http://cdn.example.com/v1/attachments/"}
            },
            "config": {
                "modified": "2024-01-01T00:00:00Z",
            },
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
                {
                    "last_modified": 1500000000000,
                    "bucket": "bid2",
                    "collection": "cid3",
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
                "last_modified": 1777777777000,
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
                "last_modified": 16666666666000,
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
        "http://testserver:9999/v1/buckets/bid2/collections/cid3/changeset",
        json={
            "timestamp": 1500000000000,
            "metadata": {
                "bucket": "bid2",
                "id": "cid3",
                "signature": {
                    "x5u": "https://autograph.example.com/keys/123",
                },
                "last_modified": 15555555555000,
            },
            "changes": [],
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


def read_file(repo, ref_or_branch_name, filepath):
    if not ref_or_branch_name.startswith("refs/"):
        ref_name = f"refs/heads/{ref_or_branch_name}"
    else:
        ref_name = ref_or_branch_name
    ref = repo.lookup_reference(ref_name)
    commit = repo[ref.target]
    # If it's a tag, peel to commit
    if commit.type == pygit2.GIT_OBJECT_TAG:
        commit = commit.peel(pygit2.GIT_OBJECT_COMMIT)
    node = commit.tree
    for part in filepath.split("/"):
        entry = node[part]
        obj = repo[entry.id]
        node = obj
    return obj.data


def build_tree(repo, items):
    """Build a tree from a list of (path, content) tuples."""
    return repo[tree_upsert_blobs(repo, items, base_tree=None)]


def changeset(cid, records):
    """Minimal changeset for the specified collection."""
    return {
        "metadata": {"id": cid, "bucket": "main"},
        "timestamp": 100,
        "changes": records,
    }


def init_fake_repo(path):
    repo = pygit2.init_repository(path, bare=True, initial_head="main")
    repo.remotes.create("origin", git_export.GIT_REMOTE_URL)
    return repo


def create_branch_with_empty_commit(repo, branch_name, set_as_repo_head=False):
    author = pygit2.Signature("Test User", "test@example.com")
    builder = repo.TreeBuilder()
    tree = builder.write()
    commit_id = repo.create_commit(
        branch_name,  # reference name
        author,  # author
        author,  # committer
        "initial commit",
        tree,
        [],  # no parents
    )
    commit = repo[commit_id]

    refname = f"refs/remotes/origin/{branch_name}"
    repo.references.create(refname, commit.id)
    if set_as_repo_head:
        repo.set_head(branch_name)


def set_previous_run(repo, timestamp):
    """Simulate a previous run that exported the monitor changeset at `timestamp`."""
    author = committer = pygit2.Signature("Test User", "test@example.com")
    remote_ref = "refs/remotes/origin/v1/common"
    parent = repo[repo.lookup_reference(remote_ref).target]
    tree_id = tree_upsert_blobs(
        repo,
        [("monitor-changes.json", json.dumps({"timestamp": timestamp}).encode())],
        base_tree=parent.tree,
    )
    commit_id = repo.create_commit(
        None, author, committer, f"common@{timestamp}", tree_id, [parent.id]
    )
    # Remote always wins when the repo is reset, so both refs must point to it.
    repo.references.create(remote_ref, commit_id, force=True)
    repo.references.create("refs/heads/v1/common", commit_id, force=True)


def simulate_pushed(repo):
    # Simulate that these branches were pushed in previous `git_export` call.
    for branch in repo.branches.local:
        commit = repo.lookup_reference(f"refs/heads/{branch}").peel()
        refname = f"refs/remotes/origin/{branch}"
        repo.references.create(refname, commit.id, force=True)


@pytest.fixture
def repo():
    repo = init_fake_repo(git_export.WORK_DIR)
    yield repo
    shutil.rmtree(git_export.WORK_DIR, ignore_errors=True)


def test_clone_must_match_remote_url_if_dir_exists(mock_github_lfs):
    pygit2.init_repository(git_export.WORK_DIR, bare=True)
    repo = pygit2.Repository(git_export.WORK_DIR)
    repo.remotes.create("origin", "https://example.com/repo.git")

    with pytest.raises(ValueError, match="does not match"):
        git_export.git_export()


def test_remote_is_clone_if_dir_missing(
    mock_repo_sync_content,
    mock_truncate_branch,
    mock_github_lfs,
    mock_git_push,
):
    def _fake_clone(url, path, *args, **kwargs):
        return init_fake_repo(path)

    with mock.patch.object(
        pygit2, "clone_repository", side_effect=_fake_clone
    ) as mock_clone:
        assert not os.path.exists(git_export.WORK_DIR)

        git_export.git_export()

    ((called_url, called_path, *_), _kwargs) = mock_clone.call_args
    assert called_url == git_export.GIT_REMOTE_URL
    assert called_path == git_export.WORK_DIR


@responses.activate
def test_repo_sync_content_starts_from_scratch_if_no_previous_run(
    capsys,
    repo,
    mock_git_fetch,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    git_export.git_export()

    mock_git_fetch.assert_called_once()
    stdout = capsys.readouterr().out
    assert "No previous run found" in stdout
    assert "3 collections changed" in stdout

    (args, _) = mock_git_push.call_args_list[0]
    assert args == (
        [
            "refs/heads/v1/buckets/bid1:refs/heads/v1/buckets/bid1",
            "refs/heads/v1/buckets/bid2:refs/heads/v1/buckets/bid2",
            "refs/heads/v1/common:refs/heads/v1/common",
        ],
    )

    # Verify that branch root contains all collections folders.
    tree = repo.lookup_reference("refs/heads/v1/buckets/bid2").peel().tree
    assert "cid2" in tree
    assert "cid3" in tree


@responses.activate
def test_common_branch_is_force_pushed_if_history_was_truncated(
    repo,
    mock_git_fetch,
    mock_rs_server_content,
    mock_truncate_branch,
    mock_github_lfs,
    mock_git_push,
):
    mock_truncate_branch.return_value = True

    git_export.git_export()

    (args, _) = mock_git_push.call_args_list[0]
    assert "+refs/heads/v1/common:refs/heads/v1/common" in args[0]


@responses.activate
def test_repo_sync_does_nothing_if_up_to_date(
    capsys,
    repo,
    mock_git_fetch,
    mock_rs_server_content,
    mock_truncate_branch,
    mock_github_lfs,
    mock_git_push,
):
    create_branch_with_empty_commit(repo, "v1/common", set_as_repo_head=True)
    create_branch_with_empty_commit(repo, "v1/buckets/bid1")
    create_branch_with_empty_commit(repo, "v1/buckets/bid2")

    git_export.git_export()
    simulate_pushed(repo)
    capsys.readouterr()  # Clear previous output

    git_export.git_export()

    stdout = capsys.readouterr().out
    assert "Previous run exported 1700000000000" in stdout
    assert "No new changes since last run" in stdout
    assert "0 attachments to upload" in stdout
    assert "Everything up-to-date" in stdout


@responses.activate
def test_repo_sync_can_be_forced_even_if_up_to_date(
    capsys,
    repo,
    mock_git_fetch,
    mock_rs_server_content,
    mock_truncate_branch,
    mock_github_lfs,
    mock_git_push,
):
    create_branch_with_empty_commit(repo, "v1/common", set_as_repo_head=True)
    create_branch_with_empty_commit(repo, "v1/buckets/bid1")
    create_branch_with_empty_commit(repo, "v1/buckets/bid2")

    git_export.git_export()
    simulate_pushed(repo)
    capsys.readouterr()  # Clear previous output

    git_export.FORCE = True
    git_export.git_export()

    stdout = capsys.readouterr().out
    assert "No changes for common branch" in stdout
    assert "No changes for bid1/cid1 branch" in stdout
    assert "No changes for bid2/cid2 branch" in stdout


@responses.activate
def test_repo_sync_content_uses_previous_run_to_fetch_changes(
    capsys,
    repo,
    mock_git_fetch,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    create_branch_with_empty_commit(repo, "v1/common", set_as_repo_head=True)
    create_branch_with_empty_commit(repo, "v1/buckets/bid1")
    create_branch_with_empty_commit(repo, "v1/buckets/bid2")

    set_previous_run(repo, 1600000000000)

    git_export.git_export()

    stdout = capsys.readouterr().out
    assert "Previous run exported 1600000000000" in stdout
    assert "1 collections changed" in stdout

    urls = [call.request.url.split("?")[0] for call in responses.calls]
    assert "http://testserver:9999/v1/buckets/bid1/collections/cid1/changeset" in urls
    assert (
        "http://testserver:9999/v1/buckets/bid2/collections/cid2/changeset" not in urls
    )

    (args, _) = mock_git_push.call_args_list[0]
    assert args == (
        [
            "refs/heads/v1/buckets/bid1:refs/heads/v1/buckets/bid1",
            "refs/heads/v1/common:refs/heads/v1/common",
        ],
    )


@responses.activate
def test_repo_sync_content_ignores_previous_run_if_forced(
    capsys,
    repo,
    mock_git_fetch,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    create_branch_with_empty_commit(repo, "v1/common", set_as_repo_head=True)
    create_branch_with_empty_commit(repo, "v1/buckets/bid1")
    create_branch_with_empty_commit(repo, "v1/buckets/bid2")

    set_previous_run(repo, 1600000000000)

    git_export.FORCE = True
    git_export.git_export()

    stdout = capsys.readouterr().out
    assert "Previous run exported 1600000000000. Ignoring (forced)" in stdout
    assert "3 collections changed" in stdout
    git_export.FORCE = False


@responses.activate
def test_repo_sync_stores_server_info(
    repo,
    mock_git_fetch,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    git_export.git_export()

    blob = read_file(repo, "v1/common", "server-info.json")
    assert "capabilities" in blob.decode()


@responses.activate
def test_repo_sync_stores_monitor_changes(
    repo,
    mock_git_fetch,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    git_export.git_export()

    blob = read_file(repo, "v1/common", "monitor-changes.json")
    assert '{"changes":[{"bucket":"bid1","collection":"cid1"' in blob.decode()


@responses.activate
def test_repo_sync_stores_broadcasts(
    repo,
    mock_git_fetch,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    git_export.git_export()

    blob = read_file(repo, "v1/common", "broadcasts.json")
    assert "broadcasts/rs" in blob.decode()


@responses.activate
def test_repo_sync_stores_cert_chains(
    repo,
    mock_git_fetch,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    git_export.git_export()

    blob = read_file(repo, "v1/common", "cert-chains/keys/123")
    assert "---CERTIFICATE---" in blob.decode()


@responses.activate
def test_repo_updates_common_branch_if_only_bundle_changed(
    repo,
    mock_git_fetch,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    git_export.git_export()

    branch_ref = "refs/heads/v1/common"
    before_commit = repo.lookup_reference(branch_ref).target

    simulate_pushed(repo)

    # Now simulate that a new bundle was published, but no new entry on
    # monitor/changes (its timestamp is unchanged). This is detected during the
    # daily full sync.
    responses.add(
        responses.GET,
        "http://cdn.example.com/v1/attachments/bundles/startup.json.mozlz4",
        body=b"b" * 99,
    )
    git_export.FORCE = True

    git_export.git_export()

    # The common branch has a new commit for the new bundle.
    after_commit = repo.lookup_reference(branch_ref).target
    assert after_commit != before_commit


@responses.activate
def test_repo_sync_stores_collections_records_in_buckets_branches(
    repo,
    mock_git_fetch,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    git_export.git_export()

    branches = [
        b for b in repo.listall_references() if b.startswith("refs/heads/v1/buckets/")
    ]
    assert "refs/heads/v1/buckets/bid1" in branches
    assert "refs/heads/v1/buckets/bid2" in branches

    rid1 = read_file(repo, "v1/buckets/bid1", "cid1/rid1-1.json")
    assert '"hello":"world"' in rid1.decode()

    rid2 = read_file(repo, "v1/buckets/bid2", "cid2/rid2-1.json")
    assert '"attachment":{' in rid2.decode()


@responses.activate
def test_repo_sync_deletes_records_from_past_runs(
    repo,
    mock_git_fetch,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    git_export.git_export()
    simulate_pushed(repo)

    # File exists before next run (not raising).
    read_file(repo, "v1/buckets/bid2", "cid2/rid2-1.json")

    # Now simulate that cid2 deleted its record.
    responses.replace(
        responses.GET,
        "http://testserver:9999/v1/buckets/monitor/collections/changes/changeset",
        json={
            "timestamp": 1800000000000,
            "changes": [
                {
                    "last_modified": 1800000000000,
                    "bucket": "bid2",
                    "collection": "cid2",
                }
            ],
        },
    )
    responses.add(
        responses.GET,
        "http://testserver:9999/v1/buckets/bid2/collections/cid2/changeset",
        json={
            "timestamp": 1800000000000,
            "metadata": {
                "bucket": "bid2",
                "id": "cid2",
                "signature": {
                    "x5u": "https://autograph.example.com/keys/123",
                },
                "last_modified": 1888888888000,
            },
            # Record was deleted: with `_since`, the changeset has its tombstone.
            "changes": [
                {"id": "rid2-1", "deleted": True, "last_modified": 1800000000000}
            ],
        },
    )

    git_export.git_export()

    # File not there anymore.
    with pytest.raises(KeyError):
        read_file(repo, "v1/buckets/bid2", "cid2/rid2-1.json")


@responses.activate
def test_repo_sync_appends_tombstones_to_the_ledger(
    repo,
    mock_git_fetch,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    git_export.git_export()
    simulate_pushed(repo)

    # No record was deleted yet, the collection has no ledger.
    with pytest.raises(KeyError):
        read_file(repo, "v1/buckets/bid2", "cid2/tombstones/202701.txt")

    # Now simulate that cid2 deleted its record.
    responses.replace(
        responses.GET,
        "http://testserver:9999/v1/buckets/monitor/collections/changes/changeset",
        json={
            "timestamp": 1800000000000,
            "changes": [
                {
                    "last_modified": 1800000000000,
                    "bucket": "bid2",
                    "collection": "cid2",
                }
            ],
        },
    )
    responses.add(
        responses.GET,
        "http://testserver:9999/v1/buckets/bid2/collections/cid2/changeset",
        json={
            "timestamp": 1800000000000,
            "metadata": {
                "bucket": "bid2",
                "id": "cid2",
                "signature": {"x5u": "https://autograph.example.com/keys/123"},
                "last_modified": 1888888888000,
            },
            "changes": [
                {"id": "rid2-1", "deleted": True, "last_modified": 1800000000000}
            ],
        },
    )

    git_export.git_export()

    # 1800000000000 is 2027-01: the tombstone goes to the file of its own month.
    ledger = read_file(repo, "v1/buckets/bid2", "cid2/tombstones/202701.txt")
    assert ledger.decode() == "1800000000000\trid2-1\n"


@responses.activate
def test_repo_sync_stores_attachments_as_lfs_pointers(
    repo,
    mock_git_fetch,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    git_export.git_export()

    rid2 = read_file(repo, "v1/common", "attachments/bid2/random-name.bin")
    assert "lfs" in rid2.decode()

    (_, kwargs) = mock_github_lfs.call_args_list[0]
    assert kwargs["auth_header"] == "Bearer TOKEN"
    assert kwargs["repo_owner"] == git_export.REPO_OWNER
    assert kwargs["repo_name"] == git_export.REPO_NAME
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
                "last_modified": 188888888880000,
            },
            "changes": [
                {
                    "id": "rid1-1",
                    "last_modified": 1800000000000,
                    "attachment": {
                        "location": "whatever/file.bin",
                        "content-type": "application/octet-stream",
                        "size": 12345,
                        "hash": "abcd",
                    },
                }
            ],
        },
    )
    responses.add(
        responses.GET,
        "http://cdn.example.com/v1/attachments/bundles/bid1--cid1.zip",
        body=b"fake bundle content",
    )

    git_export.git_export()

    bundle = read_file(repo, "v1/common", "attachments/bundles/bid1--cid1.zip")
    assert "lfs" in bundle.decode()


@responses.activate
def test_attachment_bundles_is_skipped_if_no_attachment_in_changeset(
    repo,
    mock_git_fetch,
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
                "last_modified": 188888888880000,
            },
            "changes": [{"id": "rid1-1", "last_modified": 1800000000000}],
        },
    )

    # Does not fail with 404 on "http://cdn.example.com/v1/attachments/bundles/bid1--cid1.zip"
    git_export.git_export()


@responses.activate
def test_repo_prunes_inactive_attachments_on_full_sync(
    repo,
    mock_git_fetch,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    git_export.git_export()
    # First check that attachment exists in repo.
    blob = read_file(repo, "v1/common", "attachments/bid2/random-name.bin")
    assert "lfs" in blob.decode()

    # Now the record no longer references that attachment.
    responses.replace(
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
                "last_modified": 16666666666000,
            },
            "changes": [],
        },
    )

    # A full sync re-fetches every collection, so inactive attachments are pruned.
    git_export.FORCE = True
    asyncio.run(git_export.repo_sync_content(repo))

    # Attachment should be deleted from repo.
    with pytest.raises(KeyError):
        read_file(repo, "v1/common", "attachments/bid2/random-name.bin")


@responses.activate
def test_repo_keeps_inactive_attachments_on_incremental_sync(
    repo,
    mock_git_fetch,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    git_export.git_export()
    simulate_pushed(repo)
    blob = read_file(repo, "v1/common", "attachments/bid2/random-name.bin")
    assert "lfs" in blob.decode()

    # Only cid1 changed, so we don't fetch cid2 and cannot know whether its
    # attachment is still active. It must be kept.
    responses.replace(
        responses.GET,
        "http://testserver:9999/v1/buckets/monitor/collections/changes/changeset",
        json={
            "timestamp": 1800000000000,
            "changes": [
                {
                    "last_modified": 1800000000000,
                    "bucket": "bid1",
                    "collection": "cid1",
                },
            ],
        },
    )

    asyncio.run(git_export.repo_sync_content(repo))

    # Attachment of the collection that didn't change is still there.
    blob = read_file(repo, "v1/common", "attachments/bid2/random-name.bin")
    assert "lfs" in blob.decode()


@responses.activate
def test_repo_is_reset_to_local_content_on_error(
    capsys,
    repo,
    mock_git_fetch,
    mock_rs_server_content,
    mock_github_lfs,
    mock_git_push,
):
    create_branch_with_empty_commit(repo, "v1/common", set_as_repo_head=True)
    create_branch_with_empty_commit(repo, "v1/buckets/bid1")
    create_branch_with_empty_commit(repo, "v1/buckets/bid2")

    git_export.git_export()
    simulate_pushed(repo)

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
                "last_modified": 188888888880000,
            },
            "changes": [],
        },
    )

    mock_github_lfs.side_effect = Exception("GitHub LFS error")

    with pytest.raises(Exception, match="GitHub LFS error"):
        git_export.git_export()

    stdout = capsys.readouterr().out
    assert "Error occurred: GitHub LFS error" in stdout

    assert "Rolling back local changes" in stdout
    assert "Resetting local branch v1/common to remote origin/v1/common" in stdout
    assert (
        "Resetting local branch v1/buckets/bid1 to remote origin/v1/buckets/bid1"
        in stdout
    )
    assert "Delete local tag" not in stdout


def test_tombstones_are_split_by_month_and_stored_in_ascending_order(repo):
    files = git_export.tombstones_to_ledger_files(
        None,
        "cid",
        # 1733000000000 is 2024-11, 1736000000000 is 2025-01.
        [("ccc", 1737000000002), ("bbb", 1736000000000), ("aaa", 1733000000000)],
    )

    assert dict(files) == {
        "cid/tombstones/202411.txt": b"1733000000000\taaa\n",
        "cid/tombstones/202501.txt": b"1736000000000\tbbb\n1737000000002\tccc\n",
    }


def test_already_known_tombstones_are_deduped(repo):
    tree = build_tree(
        repo,
        [("cid/tombstones/202501.txt", b"1736000000000\taaa\n1737000000001\tbbb\n")],
    )

    files = git_export.tombstones_to_ledger_files(
        tree, "cid", [("aaa", 1736000000000), ("ccc", 1737000000002)]
    )

    # "aaa" is not repeated.
    assert dict(files) == {
        "cid/tombstones/202501.txt": (
            b"1736000000000\taaa\n1737000000001\tbbb\n1737000000002\tccc\n"
        )
    }


def test_ledger_file_is_not_rewritten_when_nothing_is_new(repo):
    # A full sync repeats every tombstone of the collection.
    tree = build_tree(repo, [("cid/tombstones/202501.txt", b"1736000000000\taaa\n")])

    files = git_export.tombstones_to_ledger_files(tree, "cid", [("aaa", 1736000000000)])

    assert files == []


def test_changeset_to_branch_folder_removes_deleted_records(repo):
    tree = build_tree(
        repo,
        [
            ("cid/metadata.json", b"{}"),
            ("cid/aaa.json", b"{}"),
            ("cid/bbb.json", b"{}"),
        ],
    )

    content = dict(
        git_export.changeset_to_branch_folder(
            tree,
            changeset(
                "cid",
                [
                    {"id": "aaa", "last_modified": 1737000000000},
                    {"id": "bbb", "deleted": True, "last_modified": 1737000000001},
                ],
            ),
        )
    )

    assert content["cid/bbb.json"] is None
    assert content["cid/aaa.json"] is not None
    # The deletion is recorded in the same set of files as the record removal.
    assert content["cid/tombstones/202501.txt"] == b"1737000000001\tbbb\n"


@pytest.mark.parametrize("with_tree", [True, False])
def test_changeset_to_branch_folder_ignores_missing_record_files(repo, with_tree):
    # A full sync (`_since=0`) repeats tombstones of records that were never
    # published in the branch, or already removed by a previous run.
    tree = (
        build_tree(repo, [("cid/metadata.json", b"{}")])  # No `cid/bbb.json`.
        if with_tree
        else None  # First run, the branch does not exist yet.
    )

    content = dict(
        git_export.changeset_to_branch_folder(
            tree,
            changeset(
                "cid",
                [{"id": "bbb", "deleted": True, "last_modified": 1737000000000}],
            ),
        )
    )

    assert "cid/bbb.json" not in content
    # The deletion is still recorded in the ledger.
    assert content["cid/tombstones/202501.txt"] == b"1737000000000\tbbb\n"


def test_changeset_to_branch_folder_appends_to_existing_ledger(repo):
    tree = build_tree(
        repo,
        [
            ("cid/metadata.json", b"{}"),
            ("cid/bbb.json", b"{}"),
            ("cid/tombstones/202501.txt", b"1736000000000\told\n"),
        ],
    )

    content = dict(
        git_export.changeset_to_branch_folder(
            tree,
            changeset(
                "cid",
                [{"id": "bbb", "deleted": True, "last_modified": 1737000000000}],
            ),
        )
    )

    assert content["cid/bbb.json"] is None
    assert content["cid/tombstones/202501.txt"] == (
        b"1736000000000\told\n1737000000000\tbbb\n"
    )


def test_changeset_to_branch_folder_ignores_already_known_tombstones(repo):
    # A full sync (`_since=0`) repeats every tombstone of the collection.
    tree = build_tree(
        repo,
        [
            ("cid/metadata.json", b"{}"),
            ("cid/tombstones/202501.txt", b"1736000000000\tbbb\n"),
        ],
    )

    content = dict(
        git_export.changeset_to_branch_folder(
            tree,
            changeset(
                "cid",
                [{"id": "bbb", "deleted": True, "last_modified": 1736000000000}],
            ),
        )
    )

    # Nothing appended, the ledger file is not even rewritten.
    assert "cid/tombstones/202501.txt" not in content
