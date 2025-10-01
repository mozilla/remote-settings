import os
from typing import Any, Generator, Iterable, Optional

import pygit2
from pygit2 import (
    GIT_FILEMODE_BLOB,
    GIT_FILEMODE_TREE,
)


REMOTE_NAME = "origin"


def clone_or_fetch(
    repo_url: str,
    repo_path: str,
    callbacks: pygit2.RemoteCallbacks,
) -> pygit2.Repository:
    """
    Clone the remote repository into the specified path, or if it already exists,
    fetch the latest changes.
    """
    if os.path.exists(repo_path):
        print(f"Work dir {repo_path} already exists, skipping clone.")
        repo = pygit2.Repository(repo_path)
        remote = repo.remotes[REMOTE_NAME]
        if remote.url != repo_url:
            raise ValueError(
                f"Remote URL {remote.url} of work dir {repo_path} does not match {repo_url}"
            )
        print("Head was at", repo.head.target)
        print(f"Fetching from {repo_url}...")
        remote.fetch(callbacks=callbacks, prune=True)
        reset_repo(repo, callbacks=callbacks)
    else:
        # Clone remote repository into work dir.
        print(f"Clone {repo_url} into {repo_path}...")
        pygit2.clone_repository(repo_url, repo_path, callbacks=callbacks)
        repo = pygit2.Repository(repo_path)
    return repo


def reset_repo(repo: pygit2.Repository, callbacks: pygit2.RemoteCallbacks):
    print("Reset local content to remote content...")
    # Reset all local branches to their remote
    for branch_name in repo.branches.local:
        remote_ref_name = f"{REMOTE_NAME}/{branch_name}"
        if remote_ref_name not in repo.branches:
            print(f"Delete local branch {branch_name}")
            repo.branches.delete(branch_name)
        else:
            local_branch = repo.branches[branch_name]
            remote_branch = repo.branches[remote_ref_name]
            if local_branch.target != remote_branch.target:
                # Reset local branch to remote target
                print(
                    f"Resetting local branch {branch_name} to remote {remote_ref_name}"
                )
                local_branch.set_target(remote_branch.target)

    # Delete local tags that are not on remote
    origin = repo.remotes[REMOTE_NAME]
    remote_tags = {
        obj["name"]
        for obj in origin.ls_remotes(callbacks=callbacks)
        if obj["name"].startswith("refs/tags/") and not obj["local"]
    }
    for ref in repo.references:
        if not ref.startswith("refs/tags/") or ref in remote_tags:
            continue
        print(f"Delete local tag {ref}")
        repo.references.delete(ref)


def push_mirror(
    repo: pygit2.Repository,
    branches: list[str],
    tags: list[str],
    callbacks: pygit2.RemoteCallbacks,
):
    """
    An equivalent of `git push --force --mirror` for branches + tags only.
    """
    to_push = []
    # 1) Force update all local branches
    for b in sorted(branches):
        to_push.append(f"+{b}:{b}")
    # 2) Force update all local tags
    for t in sorted(tags):
        to_push.append(f"+refs/tags/{t}:refs/tags/{t}")

    if not to_push:
        print("Everything up-to-date.")
        return

    remote = repo.remotes[REMOTE_NAME]
    print(f"Pushing to remote {remote.url}:\n - {'\n - '.join(to_push)}")
    # This is the critical bit: non-fast-forward updates require the '+' force.
    # The deletions use the ':refs/...'; '+' is ignored for deleted refspecs.
    remote.push(to_push, callbacks=callbacks)


def make_lfs_pointer(sha256_hex: str, size: int) -> pygit2.Oid:
    """
    Create a Git LFS pointer blob with the given object id and size.
    """
    pointer = (
        "version https://git-lfs.github.com/spec/v1\n"
        f"oid sha256:{sha256_hex}\n"
        f"size {size}\n"
    )
    return pointer.encode("ascii")


def parse_lfs_pointer(data: bytes) -> tuple[str, int]:
    """
    Parse a Git LFS pointer blob and return the object id and size.
    """
    lines = data.decode("ascii").strip().split("\n")
    sha256_hex = size = None
    for line in lines:
        if line.startswith("oid sha256:"):
            sha256_hex = line.split(":", 1)[1].strip()
        elif line.startswith("size "):
            size = int(line.split(" ", 1)[1].strip())
    if sha256_hex is None or size is None:
        raise ValueError(f"Invalid LFS pointer: {data}")
    return sha256_hex, size


def iter_tree(
    repo: pygit2.Repository, tree: pygit2.Tree, prefix=""
) -> Generator[tuple[str, pygit2.Oid], None, None]:
    """
    Iterate over the entries in a Git tree, and return their paths and IDs.

    Note: This is built into libgit2 as `git_tree_walk()`, but it doesn't appear to be exposed in Python.
    """
    for entry in tree:
        path = f"{prefix}{entry.name}"
        if entry.type == pygit2.GIT_OBJECT_BLOB:
            yield path, entry.id  # file
        elif entry.type == pygit2.GIT_OBJECT_TREE:  # descend
            yield from iter_tree(repo, repo[entry.id], prefix=path + "/")


def tree_upsert_blobs(
    repo: pygit2.Repository,
    items: Iterable[tuple[str, bytes]],
    *,
    base_tree: Optional[pygit2.Tree],
) -> pygit2.Oid:
    """
    Create/update blobs at the provided paths and return the resulting *tree OID*.

    - Paths may be nested ('a/b/c.json').
    - This function merges the provided items into the existing tree (base_tree)
      by building a small trie of updates and recursively writing subtrees.
    - If base_tree is None, a new tree is created from scratch.

    The stable tree hashing means if content is unchanged, the returned OID
    will equal base_tree.id, which upstream code uses to skip commits.
    """
    updates_trie: dict[str, Any] = {}

    def put(trie: dict[str, Any], path: str, blob_oid: pygit2.Oid) -> None:
        parts = [p for p in path.lstrip("/").split("/") if p]
        *dirs, fname = parts
        node = trie
        for d in dirs:
            node = node.setdefault(d, {})
        node[fname] = blob_oid

    for path, blob_bytes in items:
        blob_oid = repo.create_blob(blob_bytes)
        put(updates_trie, path, blob_oid)

    def merge(node: dict[str, Any], base: Optional[pygit2.Tree]) -> pygit2.Oid:
        # Merge updates into the existing subtree (if any) recursively.
        builder = repo.TreeBuilder(base) if base is not None else repo.TreeBuilder()
        for name in sorted(node.keys()):
            val = node[name]
            if isinstance(val, dict):
                # Descend into existing subtree if present.
                existing_subtree = None
                if base is not None:
                    try:
                        entry = base[name]
                        if entry.filemode == GIT_FILEMODE_TREE:
                            existing_subtree = repo[entry.id]
                    except KeyError:
                        pass
                child_oid = merge(val, existing_subtree)
                builder.insert(name, child_oid, GIT_FILEMODE_TREE)
            else:
                # Leaf file blob.
                builder.insert(name, val, GIT_FILEMODE_BLOB)
        return builder.write()

    return merge(updates_trie, base_tree)
