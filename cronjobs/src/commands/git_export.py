import asyncio
import hashlib
import json
import os
import urllib
from typing import Any, Dict, Iterable, Optional, Tuple

import kinto_http
import pygit2
import requests
from decouple import config
from pygit2 import (
    GIT_FILEMODE_BLOB,
    GIT_FILEMODE_TREE,
    Keypair,
    RemoteCallbacks,
)


MAX_PARALLEL_REQUESTS = config("MAX_PARALLEL_REQUESTS", default=10, cast=int)
LOG_LEVEL = config("LOG_LEVEL", default="INFO").upper()
HTTP_TIMEOUT_SECONDS = (5, 60)  # (connect, read) seconds for requests

SERVER_URL = config("SERVER", default="http://localhost:8888/v1")
GIT_AUTHOR = config("GIT_AUTHOR", default="User <user@example.com>")
WORK_DIR = config("WORK_DIR", default="/tmp/git-export.git")
GIT_REMOTE_URL = config(
    "GIT_REMOTE_URL", default="git@github.com:leplatrem/remote-settings-data.git"
)
GIT_SSH_USERNAME = config("GIT_SSH_USERNAME", default="git")
GIT_PUBKEY_PATH = config("GIT_PUBKEY_PATH", default="~/.ssh/id_ed25519.pub")
GIT_PRIVKEY_PATH = config("GIT_PRIVKEY_PATH", default="~/.ssh/id_ed25519")
GIT_PASSPHRASE = config("GIT_PASSPHRASE", default="")
COMMON_BRANCH = "common"


def git_export(event, context):
    credentials = Keypair(
        GIT_SSH_USERNAME,
        os.path.expanduser(GIT_PUBKEY_PATH),
        os.path.expanduser(GIT_PRIVKEY_PATH),
        GIT_PASSPHRASE,
    )

    # Clone remote repository into work dir.
    callbacks = RemoteCallbacks(credentials=credentials)
    print(f"Clone {GIT_REMOTE_URL} into {WORK_DIR} using {GIT_PUBKEY_PATH} with passphrase '{'*' * len(GIT_PASSPHRASE)}'...")
    pygit2.clone_repository(GIT_REMOTE_URL, WORK_DIR, callbacks=callbacks)

    # TODO: use PGP key to sign commits

    asyncio.run(sync_git_content())

    # TODO: download attachments actual files and add them to LFS volume

    push_mirror(callbacks=callbacks)

    print("Done.")


def push_mirror(callbacks):
    """
    Equivalent of `git push --mirror`
    """
    repo = pygit2.Repository(WORK_DIR)
    remote = repo.remotes["origin"]
    local_branches = {ref for ref in repo.branches.local}
    remote_branches = {
        ref.split("/", 1)[1]
        for ref in repo.branches.remote
        if ref.startswith("origin/")
    }
    refspecs = []
    for branch in local_branches:
        refspecs.append(f"refs/heads/{branch}:refs/heads/{branch}")
    stale_branches = remote_branches - local_branches
    for branch in stale_branches:
        # empty source (left side) deletes the remote ref
        refspecs.append(f":refs/heads/{branch}")
    print("Pushing refspecs:", refspecs)
    remote.push(refspecs, callbacks=callbacks)


def json_dumpb(obj: Any) -> bytes:
    """
    Serialize an object to a JSON-formatted byte string.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


async def fetch_all_changesets(
    client: kinto_http.AsyncClient, collections: Iterable[Tuple[str, str]]
):
    sem = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)

    async def fetch(bid, cid):
        async with sem:
            print("Fetching %s/%s" % (bid, cid))
            return await client.get_changeset(
                bucket=bid, collection=cid, bust_cache=True
            )

    return await asyncio.gather(*[fetch(bid, cid) for bid, cid in collections])


def fetch_attachment(url):
    """
    Fetch the attachment at the given URL and return its sha256 hash and size.
    """
    print("Fetch %r" % url)
    h = hashlib.sha256()
    total = 0
    with requests.get(url, stream=True, timeout=HTTP_TIMEOUT_SECONDS) as r:
        r.raise_for_status()
        for chunk in r.iter_content(1024 * 64):
            if not chunk:
                continue
            h.update(chunk)
            total += len(chunk)
    return h.hexdigest(), total


def fetch_all_cert_chains(client: kinto_http.AsyncClient, changesets):
    all_x5u = set()
    for changeset in changesets:
        all_x5u.add(changeset["metadata"]["signature"]["x5u"])

    pem_files = []
    for x5u in all_x5u:
        resp = requests.get(x5u)
        resp.raise_for_status()
        pem_files.append((x5u, resp.text))
    return pem_files


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


def upsert_blobs(
    repo: pygit2.Repository,
    items: Iterable[Tuple[str, bytes]],
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
    will equal base_tree.id, which upstream code can use to skip commits.
    """
    updates_trie: Dict[str, Any] = {}

    def put(trie: Dict[str, Any], path: str, blob_oid: pygit2.Oid) -> None:
        parts = [p for p in path.lstrip("/").split("/") if p]
        *dirs, fname = parts
        node = trie
        for d in dirs:
            node = node.setdefault(d, {})
        node[fname] = blob_oid

    for path, blob_bytes in items:
        blob_oid = repo.create_blob(blob_bytes)
        put(updates_trie, path, blob_oid)

    def merge(node: Dict[str, Any], base: Optional[pygit2.Tree]) -> pygit2.Oid:
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


async def sync_git_content():
    user, email = GIT_AUTHOR.split("<")
    user = user.strip()
    email = email.rstrip(">")
    author = pygit2.Signature(user, email)
    committer = author

    common_branch = f"refs/heads/{COMMON_BRANCH}"

    print(f"Opening existing repository in {WORK_DIR}")
    repo = pygit2.Repository(WORK_DIR)
    # The repo may exist without the 'common' ref (first run).
    try:
        common_tip = repo.lookup_reference(common_branch).target
        common_base_tree = repo.get(common_tip).tree
        parents = [common_tip]
    except KeyError:
        common_base_tree = None
        parents = []

    # Previous run timestamp, find latest tag starting with `timestamps/common/*`
    refs = [ref.decode() for ref in repo.raw_listall_references()]
    timestamps = [
        int(t.split("/")[-1])
        for t in refs
        if t.startswith("refs/tags/timestamps/common/")
    ]
    if timestamps:
        latest_timestamp = max(timestamps)
        print(f"Found latest tag: {latest_timestamp}")
    else:
        print("No previous tags found.")
        latest_timestamp = 0

    # Fetch content from Remote Settings server.
    client = kinto_http.AsyncClient(server_url=SERVER_URL)

    monitor_changeset = await client.get_changeset(
        bucket="monitor", collection="changes", bust_cache=True
    )
    if monitor_changeset["timestamp"] == latest_timestamp:
        print("No new changes since last run.")
        return

    # Store the monitor changeset in `common` branch.
    # Anything from previous commits is lost.
    common_content = [
        ("monitor-changes.json", json_dumpb(monitor_changeset)),
    ]

    # Store the broadcast version in `common` branch.
    print("Fetching broadcasts content")
    resp = requests.get(f"{SERVER_URL}/__broadcasts__")
    resp.raise_for_status()
    broadcasts = resp.json()
    common_content.append(("broadcasts.json", json_dumpb(broadcasts)))

    new_changesets = [
        entry
        for entry in monitor_changeset["changes"]
        if entry["last_modified"] > latest_timestamp
    ]
    print(f"Fetch {len(new_changesets)} changesets")
    all_changesets = await fetch_all_changesets(
        client, [(entry["bucket"], entry["collection"]) for entry in new_changesets]
    )

    # Store the certificate chains.
    print("Fetching certificate chains")
    for url, pem in fetch_all_cert_chains(client, all_changesets):
        parsed = urllib.parse.urlparse(url)
        common_content.append((f"cert-chains/{parsed.path.lstrip('/')}", pem.encode()))

    # Store all the attachments as LFS pointers.
    # NOTE: This writes the pointer files, not the large object content itself.
    common_content.append(
        (".gitattributes", b"attachments/** filter=lfs diff=lfs merge=lfs -text\n")
    )
    for changeset in all_changesets:
        for record in changeset["changes"]:
            if "attachment" not in record:
                continue

            attachment = record["attachment"]
            location = attachment["location"].lstrip("/")
            pointer_blob = make_lfs_pointer(attachment["hash"], attachment["size"])
            common_content.extend(
                [
                    (f"attachments/{location}", pointer_blob),
                    (f"attachments/{location}.meta.json", json_dumpb(record)),
                ]
            )

    # Also store the bundles as LFS pointers.
    print("Fetching attachments bundles")
    attachments_base_url = (await client.server_info())["capabilities"]["attachments"][
        "base_url"
    ].rstrip("/")
    bundles_locations: list[str] = ["bundles/startup.json.mozlz4"]
    for changeset in all_changesets:
        if not changeset["metadata"].get("attachment", {}).get("bundle", False):
            continue
        metadata = changeset["metadata"]
        bundles_locations.append(
            f"bundles/{metadata['bucket']}--{metadata['id']}.zip"
        )
    for location in bundles_locations:
        url = attachments_base_url + "/" + location
        hash, size = fetch_attachment(url)
        blob = make_lfs_pointer(hash, size)
        common_content.append((location, blob))

    monitor_tree_id = upsert_blobs(repo, common_content, base_tree=common_base_tree)

    if common_base_tree is not None and monitor_tree_id == common_base_tree.id:
        print("No changes for common branch, skipping commit.")
    else:
        commit_oid = repo.create_commit(
            common_branch,
            author,
            committer,
            "Add monitor-changes and x5u certificate chains",
            monitor_tree_id,
            parents,
        )
        print(f"Created commit common: {commit_oid}")

        # Tag with current timestamp for next runs
        tag_name = f"timestamps/common/{monitor_changeset['timestamp']}"
        try:
            repo.create_tag(
                tag_name,
                commit_oid,
                pygit2.GIT_OBJECT_COMMIT,
                author,
                f"Common changes @ {monitor_changeset['timestamp']}",
            )
            print(f"Created tag common: {tag_name}")
        except pygit2.AlreadyExistsError:
            print(f"Tag {tag_name} already exists, skipping.")

    print("")
    for changeset in all_changesets:
        bid = changeset["metadata"]["bucket"]
        cid = changeset["metadata"]["id"]
        timestamp = changeset["timestamp"]
        refname = f"refs/heads/buckets/{bid}"
        commit_message = f"{bid}/{cid}@{timestamp}"

        # Find the bucket branch (changesets are not ordered by bucket)
        try:
            branch_tip = repo.lookup_reference(refname).target
            base_tree = repo.get(branch_tip).tree
            parents = [branch_tip]
        except KeyError:
            # Only first run, and first collection in the bucket.
            base_tree = None
            parents = []

        # Create one blob per record. We start a new tree for this collection
        # anything from previous commits is lost.
        branch_content = [(f"{cid}/metadata.json", json_dumpb(changeset["metadata"]))]
        records = sorted(changeset["changes"], key=lambda r: r["id"])
        for record in records:
            branch_content.append((f"{cid}/{record['id']}.json", json_dumpb(record)))

        files_tree_id = upsert_blobs(repo, branch_content, base_tree=base_tree)

        if base_tree is not None and files_tree_id == base_tree.id:
            print(f"No changes for {bid}/{cid}, skipping commit.")
        else:
            # Commit and tag.
            commit_oid = repo.create_commit(
                refname, author, committer, commit_message, files_tree_id, parents
            )
            print(f"Created commit {bid}/{cid} @ {timestamp}: {commit_oid}")
            # Tag the commit with the timestamp for traceability. If it already
            # exists, ignore the error (idempotent tagging behavior).
            tag_name = f"timestamps/{bid}/{cid}/{timestamp}"
            try:
                repo.create_tag(
                    tag_name,
                    commit_oid,
                    pygit2.GIT_OBJECT_COMMIT,
                    author,
                    f"{bid}/{cid}/{timestamp}",
                )
            except pygit2.AlreadyExistsError:
                print(f"Tag {tag_name} already exists, skipping.")
