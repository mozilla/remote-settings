import pygit2
import pytest
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
