import time
from unittest import mock

import pygit2
import pytest
from commands import git_export
from commands._git_export_git_tools import (
    iter_tree,
    parse_lfs_pointer,
    push_mirror,
    reset_repo,
    tree_upsert_blobs,
    truncate_branch,
)


@pytest.fixture
def tmp_repo(tmp_path):
    repo = pygit2.init_repository(tmp_path, bare=True)
    tree_oid = tree_upsert_blobs(
        repo,
        items=[
            ("a/b.txt", b"B"),
            ("a/c/d.json", b"{}"),
            ("root.txt", b"R"),
        ],
        base_tree=None,
    )
    author = pygit2.Signature("Test", "test@example.com")
    committer = author
    repo.create_commit(
        "refs/heads/main",
        author,
        committer,
        "initial commit",
        tree_oid,
        [],
    )
    repo.remotes.create("origin", git_export.GIT_REMOTE_URL)
    return repo


@pytest.fixture
def mock_remote_push():
    with mock.patch("pygit2.Remote.push") as mock_push:
        yield mock_push


def test_valid_lfs_pointer():
    data = b"""version https://git-lfs.github.com/spec/v1
oid sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
size 42
"""
    sha, size = parse_lfs_pointer(data)
    assert (
        sha
        == "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"  # pragma: allowlist secret
    )
    assert size == 42


def test_iter_tree_single_file(tmp_repo):
    commit = tmp_repo.revparse_single("main")
    tree = commit.tree

    entries = list(iter_tree(tmp_repo, tree))

    assert entries == [
        (
            "a/b.txt",
            "7371f47a6f8bd23a8fa1a8b2a9479cdd76380e54",  # pragma: allowlist secret
        ),
        (
            "a/c/d.json",
            "9e26dfeeb6e641a33dae4961196235bdb965b21b",  # pragma: allowlist secret
        ),
        (
            "root.txt",
            "ac044e5e4649cd149e3d0cf9d23720d299288a1e",  # pragma: allowlist secret
        ),
    ]


def test_reset_repo_creates_local_branches(tmp_repo):
    repo = tmp_repo
    commit = repo.revparse_single("main")
    # remote branch can be created via reference only.
    repo.create_reference(
        "refs/remotes/origin/v1/buckets/main",
        commit.id,
        force=True,
    )
    assert "v1/buckets/main" not in repo.branches.local

    reset_repo(repo)

    local_ref = repo.lookup_reference("refs/heads/v1/buckets/main")
    remote_ref = repo.lookup_reference("refs/remotes/origin/v1/buckets/main")
    assert local_ref.target == remote_ref.target


@pytest.mark.parametrize(
    ("branches", "expected"),
    [
        (["+v1/common"], ["+v1/common:v1/common"]),
        (["v1/common"], ["v1/common:v1/common"]),
        (
            ["v1/buckets/main", "v1/common"],
            ["v1/buckets/main:v1/buckets/main", "v1/common:v1/common"],
        ),
    ],
)
def test_push_mirror_force_pushes_branches(
    tmp_repo, mock_remote_push, branches, expected
):
    push_mirror(tmp_repo, branches, callbacks=None)

    mock_remote_push.assert_called_once_with(expected, callbacks=None)


def test_push_mirror_does_nothing_without_branches(tmp_repo, mock_remote_push):
    push_mirror(tmp_repo, [], callbacks=None)

    mock_remote_push.assert_not_called()


def test_reset_repo_resets_local_branches_to_remote(tmp_repo):
    repo = tmp_repo
    commit = repo.revparse_single("main")
    author = committer = pygit2.Signature("Test", "test@example.com")
    repo.create_commit(
        "refs/heads/v1/buckets/main",
        author,
        committer,
        "diverging commit",
        repo.TreeBuilder().write(),
        [commit.id],
    )
    # remote branch can be created via reference only.
    repo.create_reference(
        "refs/remotes/origin/v1/buckets/main",
        commit.id,
        force=True,
    )
    # With this local commit, the branches have diverged.
    local_ref = repo.lookup_reference("refs/heads/v1/buckets/main")
    remote_ref = repo.lookup_reference("refs/remotes/origin/v1/buckets/main")
    assert local_ref.target != remote_ref.target

    reset_repo(repo)

    # Now they match.
    local_ref = repo.lookup_reference("refs/heads/v1/buckets/main")
    remote_ref = repo.lookup_reference("refs/remotes/origin/v1/buckets/main")
    assert local_ref.target == remote_ref.target


def test_reset_repo_deletes_extra_local_branches(tmp_repo):
    repo = tmp_repo
    some_target = repo.references["refs/heads/main"].target
    repo.create_reference("refs/remotes/origin/v1/buckets/main", some_target)
    repo.create_reference("refs/heads/v1/buckets/main", some_target)
    assert "v1/buckets/main" in repo.branches.local
    # Create another ref that wouldn't be repo's head (to allow delete)
    author = committer = pygit2.Signature("Test", "test@example.com")
    commit_id = repo.create_commit(
        "refs/heads/v1/buckets/main",
        author,
        committer,
        "initial commit",
        repo.TreeBuilder().write(),
        [some_target],
    )
    # Create an extra branch.
    repo.create_reference("refs/heads/v1/buckets/unknown", commit_id)

    reset_repo(repo)

    assert "v1/buckets/main" in repo.branches.local
    assert "v1/buckets/unknown" not in repo.branches.local


DAY_SECONDS = 24 * 60 * 60


@pytest.fixture
def repo_with_dated_commits(tmp_repo):
    """A branch of 4 commits, aged 30, 20, 10 and 0 days."""
    repo = tmp_repo
    now = int(time.time())

    commit_oid = repo.revparse_single("main").id
    for i, age_days in enumerate((30, 20, 10, 0)):
        when = now - age_days * DAY_SECONDS
        author = committer = pygit2.Signature("Test", "test@example.com", when, 0)
        tree_oid = tree_upsert_blobs(
            repo,
            items=[("file.txt", f"content-{i}".encode())],
            base_tree=repo.revparse_single("main").tree,
        )
        commit_oid = repo.create_commit(
            "refs/heads/main",
            author,
            committer,
            f"commit-{age_days}-days-old",
            tree_oid,
            [commit_oid],
        )
    return repo


def test_truncate_branch_keeps_recent_commits(repo_with_dated_commits):
    repo = repo_with_dated_commits
    before = len(list(repo.walk(repo.references["refs/heads/main"].target)))

    assert truncate_branch(repo, "main", keep_days=90) is False

    after = len(list(repo.walk(repo.references["refs/heads/main"].target)))
    assert after == before


def test_truncate_branch_drops_commits_older_than_keep_days(repo_with_dated_commits):
    repo = repo_with_dated_commits
    before_sha1s = [c.id for c in repo.walk(repo.references["refs/heads/main"].target)]

    assert truncate_branch(repo, "main", keep_days=25) is True

    commits = list(repo.walk(repo.references["refs/heads/main"].target))
    assert [c.message for c in commits] == [
        "commit-0-days-old",
        "commit-10-days-old",
        "commit-20-days-old",
    ]
    # History was rewritten, the kept commits have new ids.
    assert [c.id for c in commits] != before_sha1s[:3]
    # The tree content is preserved.
    assert (commits[0].tree / "file.txt").data == b"content-3"


def test_truncate_branch_tolerates_commits_within_the_margin(repo_with_dated_commits):
    repo = repo_with_dated_commits
    before_sha1s = [c.id for c in repo.walk(repo.references["refs/heads/main"].target)]

    # The oldest commit is 30 days old, ie. older than 28 days, but still within
    # the 10% margin (30.8 days).
    assert truncate_branch(repo, "main", keep_days=28) is False

    commits = list(repo.walk(repo.references["refs/heads/main"].target))
    assert [c.id for c in commits] == before_sha1s


def test_truncate_branch_always_keeps_the_tip(repo_with_dated_commits):
    repo = repo_with_dated_commits

    assert truncate_branch(repo, "main", keep_days=0) is True

    commits = list(repo.walk(repo.references["refs/heads/main"].target))
    assert [c.message for c in commits] == ["commit-0-days-old"]


def test_truncate_branch_does_nothing_if_keep_days_is_negative(repo_with_dated_commits):
    repo = repo_with_dated_commits

    assert truncate_branch(repo, "main", keep_days=-1) is False
