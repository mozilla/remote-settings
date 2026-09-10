import os
import time
from typing import Any, Generator, Iterable, Optional, cast

import pygit2
from pygit2 import (
    GIT_FILEMODE_BLOB,
    GIT_FILEMODE_TREE,
)
from pygit2.enums import FetchPrune, SortMode


REMOTE_NAME = "origin"
# Extra age tolerated before truncating, as a ratio of `keep_days`.
TRUNCATE_MARGIN_RATIO = 0.1


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
        if not repo.raw_listall_references():
            print("No branches found in the repository.")
        else:
            if not repo.head_is_unborn:
                print("Head was at", repo.head.target)
        print(f"Fetching from {repo_url}...")
        remote.fetch(callbacks=callbacks, prune=FetchPrune.PRUNE)
    else:
        # Clone remote repository into work dir.
        print(f"Clone {repo_url} into {repo_path}...")
        pygit2.clone_repository(repo_url, repo_path, callbacks=callbacks)
        repo = pygit2.Repository(repo_path)
    reset_repo(repo)
    return repo


def reset_repo(repo: pygit2.Repository) -> None:
    print("Reset local content to remote content...")
    # If the repo is freshly cloned, the remotes branches do not exist locally. Create them.
    # If the repo was cloned from previous run, reset the local branches to the remote targets.
    # Remote always wins.

    for branch_name in repo.branches.remote:
        branch = repo.branches.remote[branch_name]
        assert branch.remote_name == REMOTE_NAME
        remote_target = branch.target
        local_branch_name = branch_name.removeprefix(f"{REMOTE_NAME}/")
        local_refname = f"refs/heads/{local_branch_name}"
        if local_refname in repo.references:
            local_ref = repo.lookup_reference(local_refname)
            if local_ref.target != remote_target:
                print(
                    f"Resetting local branch {local_branch_name} to remote {branch_name}"
                )
                local_ref.set_target(
                    remote_target,
                    f"reset to {REMOTE_NAME}/{branch_name}",
                )
        else:
            repo.create_reference(local_refname, remote_target)

    # Delete local branches that are not on remote
    for branch_name in repo.branches.local:
        remote_branch_name = f"{REMOTE_NAME}/{branch_name}"
        if remote_branch_name not in repo.branches.remote:
            ref = repo.lookup_reference(f"refs/heads/{branch_name}")
            print(f"Delete local branch {branch_name}")
            ref.delete()


def push_mirror(
    repo: pygit2.Repository,
    branches: Iterable[str],
    callbacks: pygit2.RemoteCallbacks,
) -> None:
    """
    An equivalent of `git push --mirror` for branches only.
    Only branches with `+` prefix will be pushed forced.
    """
    if not branches:
        print("Everything up-to-date.")
        return

    to_push = [f"{b}:{b.replace('+', '')}" for b in sorted(branches)]
    remote = repo.remotes[REMOTE_NAME]
    print(f"Pushing to remote {remote.url}:\n - {'\n - '.join(to_push)}")
    remote.push(to_push, callbacks=callbacks)


def make_lfs_pointer(sha256_hex: str, size: int) -> bytes:
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


def list_lfs_pointers(
    repo: pygit2.Repository, tree: pygit2.Tree | None
) -> dict[str, tuple[str, int]]:
    """
    List all LFS pointers in the given tree.
    Return a mapping of attachment path to (sha256, size).
    """
    if tree is None:
        return {}

    existing_attachments = {}
    try:
        attachment_tree = cast(pygit2.Tree, tree / "attachments")
        objs = iter_tree(repo, attachment_tree)
    except KeyError:
        # No attachments/ folder yet.
        objs = []
    for path, oid in objs:
        blob = repo[oid]
        try:
            sha256_hex, size = parse_lfs_pointer(blob.data)  # ty: ignore[unresolved-attribute]
        except ValueError as exc:
            print(f"Failed to parse LFS pointer for {path}: {exc}")
        existing_attachments[path] = (sha256_hex, size)
    return existing_attachments


def iter_tree(
    repo: pygit2.Repository, tree: pygit2.Tree, prefix: str = ""
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
            yield from iter_tree(
                repo, cast(pygit2.Tree, repo[entry.id]), prefix=path + "/"
            )


def tree_upsert_blobs(
    repo: pygit2.Repository,
    items: Iterable[tuple[str, bytes | None]],
    *,
    base_tree: Optional[pygit2.Tree],
) -> pygit2.Oid:
    """
    Create/update/delete blobs at the provided paths and return the resulting *tree OID*.

    - Paths may be nested ('a/b/c.json').
    - This merges the provided items into the existing tree (base_tree)
      by building a small trie of updates and recursively writing subtrees.
    - If base_tree is None, a new tree is created from scratch.

    The stable tree hashing means if content is unchanged, the returned OID
    will equal base_tree.id, which upstream code uses to skip commits.
    Pass `(path, None)` to delete the blob at that path.
    """
    DELETE = object()  # sentinel for deletions
    # Ensure items is a concrete list for multiple iterations.
    items = list(items)
    updates_trie: dict[str, Any] = {}

    def put(trie: dict[str, Any], path: str, blob_oid: pygit2.Oid | object) -> None:
        parts = [p for p in path.lstrip("/").split("/") if p]
        *dirs, fname = parts
        node = trie
        for d in dirs:
            node = node.setdefault(d, {})
        node[fname] = blob_oid

    for path, blob_bytes in items:
        blob_oid = DELETE if blob_bytes is None else repo.create_blob(blob_bytes)
        put(updates_trie, path, blob_oid)

    def merge(node: dict[str, Any], base: Optional[pygit2.Tree]) -> pygit2.Oid:
        # Merge updates into the existing subtree (if any) recursively.
        builder = repo.TreeBuilder(base) if base is not None else repo.TreeBuilder()
        for name in sorted(node.keys()):
            val = node[name]
            if val is DELETE:
                # Delete from tree, will raise if missing.
                builder.remove(name)
            elif isinstance(val, dict):
                # Descend into existing subtree if present.
                existing_subtree = None
                if base is not None:
                    try:
                        entry = base[name]
                        if entry.filemode == GIT_FILEMODE_TREE:
                            existing_subtree = cast(pygit2.Tree, repo[entry.id])
                    except KeyError:
                        pass
                child_oid = merge(val, existing_subtree)
                builder.insert(name, child_oid, GIT_FILEMODE_TREE)
            else:
                # Leaf file blob.
                builder.insert(name, val, GIT_FILEMODE_BLOB)
        return builder.write()

    return merge(updates_trie, base_tree)


def truncate_branch(repo: pygit2.Repository, branch: str, keep_days: int) -> bool:
    """
    Rewrite the specified branch to drop the commits older than `keep_days`.

    This removes the oldest commits of the branch, and force-updates it to point
    to the rewritten tip. This function is destructive and rewrites history.
    Return whether the branch was rewritten.

    A branch like:

    o--o--o--o--o--o--o
    <- older -><- kept ->

    would be forced to become

    o--o--o

    The most recent commit is always kept, even if it is older than `keep_days`.

    Since rewriting is expensive, it only happens once the oldest commit exceeds
    `keep_days` by `TRUNCATE_MARGIN_RATIO` (eg. 11 days when keeping 10 days).
    """
    branch_ref = repo.references.get("refs/heads/" + branch)
    if branch_ref is None:  # pragma: no cover
        raise ValueError(f"Branch {branch} does not exist.")

    if keep_days < 0:
        return False

    tip_oid = branch_ref.target

    # `commit_time` is in seconds since epoch.
    now = int(time.time())
    cutoff = now - keep_days * 24 * 60 * 60
    margin_days = keep_days * (1 + TRUNCATE_MARGIN_RATIO)
    margin_cutoff = now - int(margin_days * 24 * 60 * 60)

    # Walk commits from the tip towards roots: newest -> oldest.
    kept: list[pygit2.Commit] = []
    dropped = 0
    truncating = False
    beyond_margin = False
    for commit in repo.walk(tip_oid, SortMode.TOPOLOGICAL | SortMode.TIME):
        if truncating or (kept and commit.commit_time < cutoff):
            truncating = True
            dropped += 1
            beyond_margin = beyond_margin or commit.commit_time < margin_cutoff
        else:
            kept.append(commit)

    if not dropped:
        print(f"Branch {branch} has no commit older than {keep_days} days.")
        return False

    if not beyond_margin:
        print(
            f"Branch {branch} has {dropped} commit(s) older than {keep_days} days, "
            f"but none older than {margin_days:.0f} days."
        )
        return False

    # Recreate the chain of commits to "rebuild" the branch, from oldest to newest.
    kept.reverse()
    print(f"Rebuilding {branch} (from {len(kept) + dropped} commits to {len(kept)})")
    parents_list: list[pygit2.Oid] = []
    new_root = None
    for commit in kept:
        new_oid = repo.create_commit(
            None,  # no ref update
            commit.author,
            commit.committer,
            commit.message,
            commit.tree.id,
            parents_list,
        )
        if new_root is None:
            new_root = new_oid
        # Next commit will parent this one.
        parents_list = [new_oid]

    # Now force-move the branch to the new tip.
    new_tip_oid = parents_list[0]
    msg = (
        f"Truncate {branch} to the last {keep_days} days "
        f"(root from {str(kept[0].id)[:7]} to {str(new_root)[:7]}, "
        f"tip from {str(tip_oid)[:7]} to {str(new_tip_oid)[:7]})"
    )
    branch_ref.set_target(new_tip_oid, msg)
    print(msg)
    return True
