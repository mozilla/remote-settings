import time

import pygit2
import pytest
from commands._git_export_git_tools import delete_old_tags
from commands.git_export import iter_tree, parse_lfs_pointer, tree_upsert_blobs


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
    return repo


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


def test_delete_old_tags(tmp_repo):
    repo = tmp_repo
    now_ts = int(time.time())

    commit = tmp_repo.revparse_single("main")
    old_tag = "v1/timestamps/common/" + str(now_ts - 10 * 86400)  # 10 days ago
    repo.create_tag(
        old_tag,
        commit.id,
        pygit2.GIT_OBJECT_COMMIT,
        pygit2.Signature("Tester", "test@example.com"),
        "An old tag",
    )
    recent_tag = f"v1/timestamps/common/{now_ts}"
    repo.create_tag(
        recent_tag,
        commit.id,
        pygit2.GIT_OBJECT_COMMIT,
        pygit2.Signature("Tester", "test@example.com"),
        "A recent tag",
    )
    assert f"refs/tags/{old_tag}" in repo.references
    assert f"refs/tags/{recent_tag}" in repo.references

    deleted = delete_old_tags(repo, max_age_days=8, keep_last_count=1)

    assert deleted == [f"refs/tags/{old_tag}"]
    assert f"refs/tags/{old_tag}" not in repo.references
    assert f"refs/tags/{recent_tag}" in repo.references
