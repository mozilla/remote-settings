import os
import time
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
        if not repo.raw_listall_references():
            print("No branches or tags found in the repository.")
        else:
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
    # 2) Force update all local tags and delete old tags
    for t in sorted(tags):
        deleting = t.startswith("-")
        name = t[1:]
        full = name if name.startswith("refs/tags/") else f"refs/tags/{name}"
        if deleting:
            to_push.append(f":{full}")
        else:
            to_push.append(f"+{full}:{full}")

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

    def put(trie: dict[str, Any], path: str, blob_oid: pygit2.Oid) -> None:
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


def delete_old_tags(
    repo: pygit2.Repository, max_age_days: int, min_tags_per_collection: int = 2
) -> list[str]:
    """
    Delete old tags from the repository, keeping the most recent `min_tags_per_collection` tags for each collection.

    Return the list of deleted tag names.
    """
    print(
        f"Delete tags older than {max_age_days} days, keeping at least {min_tags_per_collection} per collection."
    )
    deleted_tags = []
    now_ts = int(time.time())

    timestamp_tags = [
        ref_name
        for ref_name in repo.references
        if ref_name.startswith("refs/tags/") and "/timestamps/" in ref_name
    ]
    group_by_collection: dict[str, list[tuple[str, int]]] = {}
    for ref_name in sorted(timestamp_tags):
        collection, timestamp = ref_name.rsplit("/", 1)
        timestamp = int(timestamp)
        group_by_collection.setdefault(collection, []).append((ref_name, timestamp))

    # For each collection, we find all the tags that are older than
    # theshold. We keep at least `min_tags_per_collection` after that threshold
    # to make sure let client catch up with synchronization.
    # This logics helps us cover the situation described in mozilla/remote-settings#1109
    # (several updates in a short period of time after a long inactivity).
    for collection, tags in group_by_collection.items():
        kept_count = 0
        for ref_name, timestamp in tags:
            age_days = (now_ts - timestamp) / (60 * 60 * 24)
            if age_days < max_age_days:
                continue
            if kept_count < min_tags_per_collection:
                kept_count += 1
                continue

            print(f"Deleting tag {ref_name} (timestamp: {timestamp})")
            repo.references.delete(ref_name)
            deleted_tags.append(ref_name)

    return deleted_tags


def truncate_branch(
    repo: pygit2.Repository, branch: str, tags_deletion_threshold: int
) -> None:
    """
    Rewrite the specified branch to start from the oldest tagged commit.

    This removes all commits prior to the oldest tagged commit in the branch,
    and force-updates the branch to point to the new tip.
    This function is destructive and rewrites history.

    A branch like:

    o--o--o--o--o--o(tag)--o(tag)--o(tag)

    would be forced to become

    o(tag)--o(tag)--o(tag)
    """
    branch_ref_name = "refs/heads/" + branch
    branch_ref = repo.references[branch_ref_name]
    tip_oid = branch_ref.target

    # Precompute set of commits with tags
    commits_to_refs = {}
    for ref_name in repo.references:
        if not ref_name.startswith("refs/tags/") or "/timestamps/" not in ref_name:
            continue
        tag_ref = repo.references[ref_name]
        target_oid = tag_ref.target
        tag_obj = repo[target_oid]
        obj = tag_obj.peel(pygit2.Commit)
        assert isinstance(obj, pygit2.Commit), (
            f"Tag {ref_name} does not point to a commit"
        )
        commits_to_refs[obj.id] = ref_name

    assert commits_to_refs, "No timestamps tags found in the repository."

    # Walk commits from the tip towards roots: newest -> oldest
    chain_commits: list[pygit2.Commit] = []
    walker = repo.walk(tip_oid, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_TIME)
    to_delete_count = 0
    for commit in walker:
        # Stop when we reach an untagged commit
        if commit.id not in commits_to_refs:
            assert len(chain_commits) > 0, (
                f"No tagged commit found in branch {branch}, cannot truncate"
            )
            to_delete_count += 1
            break
        chain_commits.append(commit)

    assert chain_commits, f"No tagged commit found in branch {branch}"

    # Reverse to have oldest -> newest
    chain_commits.reverse()
    if len(chain_commits[0].parents) == 0:
        print(
            f"Branch {branch} already starts from a tagged commit ({str(chain_commits[0].id)[:7]}), nothing to do."
        )
        return

    if to_delete_count < tags_deletion_threshold:
        print(
            f"Wait until more tags are deleted before truncating branch ({to_delete_count}/{tags_deletion_threshold})"
        )
        return

    # Recreate the chain of commits to "rebuild" the branch.
    print(
        f"Rebuilding branch (from {len(chain_commits) + to_delete_count} commits to {len(chain_commits)})"
    )
    parents_list = []  # for the first in chain, parent list will be []
    new_root = None
    for commit in chain_commits:
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
        # Next commit will parent this one
        parents_list = [new_oid]
        # Move the tags that pointed to the old commit into the new commit
        tag_ref = commits_to_refs[commit.id]
        repo.references.create(tag_ref, new_oid, force=True)

    # Now force-move the branch to the new tip
    new_tip_oid = parents_list[0]
    msg = f"Truncate {branch} at oldest tagged commit (root from {str(chain_commits[0].id)[:7]} to {str(new_root)[:7]}, tip from {str(tip_oid)[:7]} to {str(new_tip_oid)[:7]})"
    branch_ref.set_target(new_tip_oid, msg)
    print(msg)
