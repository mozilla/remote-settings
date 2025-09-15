import asyncio
import concurrent
import hashlib
import json
import os
import subprocess
import tempfile
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
HTTP_TIMEOUT_BATCH_SECONDS = (10, 180)  # (connect, read) seconds for requests
HTTP_TIMEOUT_UPLOAD_SECONDS = (10, 600)  # (connect, read) seconds for requests
HTTP_RETRY_MAX_COUNT = config("HTTP_RETRY_MAX_COUNT", default=10, cast=int)

SERVER_URL = config("SERVER", default="http://localhost:8888/v1")
GIT_AUTHOR = config("GIT_AUTHOR", default="User <user@example.com>")
user, email = GIT_AUTHOR.split("<")
GIT_AUTHOR_USER = user.strip()
GIT_AUTHOR_EMAIL = email.rstrip(">")
WORK_DIR = config("WORK_DIR", default="/tmp/git-export.git")
REPO_OWNER = config("REPO_OWNER", default="leplatrem")
REPO_NAME = config("REPO_NAME", default="remote-settings-data")
GIT_SSH_USERNAME = config("GIT_SSH_USERNAME", default="git")
GIT_REMOTE_URL = config(
    "GIT_REMOTE_URL",
    default=f"{GIT_SSH_USERNAME}@github.com:{REPO_OWNER}/{REPO_NAME}.git",
)
GITHUB_TOKEN = config("GITHUB_TOKEN", default="")
GITHUB_MAX_LFS_BATCH_SIZE = config("GITHUB_MAX_LFS_BATCH_SIZE", default=100, cast=int)
GIT_PUBKEY_PATH = config("GIT_PUBKEY_PATH", default="~/.ssh/id_ed25519.pub")
GIT_PRIVKEY_PATH = config("GIT_PRIVKEY_PATH", default="~/.ssh/id_ed25519")
GIT_PASSPHRASE = config("GIT_PASSPHRASE", default="")
COMMON_BRANCH = "common"
FORCE = config("FORCE", default=False, cast=bool)


def git_export(event, context):
    credentials = Keypair(
        GIT_SSH_USERNAME,
        os.path.expanduser(GIT_PUBKEY_PATH),
        os.path.expanduser(GIT_PRIVKEY_PATH),
        GIT_PASSPHRASE,
    )
    callbacks = RemoteCallbacks(credentials=credentials)

    if os.path.exists(WORK_DIR):
        print(f"Work dir {WORK_DIR} already exists, skipping clone.")
        repo = pygit2.Repository(WORK_DIR)
        fetch_prune(repo, callbacks=callbacks)
    else:
        # Clone remote repository into work dir.
        callbacks = RemoteCallbacks(credentials=credentials)
        print(
            f"Clone {GIT_REMOTE_URL} into {WORK_DIR} using {GIT_PUBKEY_PATH} with passphrase '{'*' * len(GIT_PASSPHRASE)}'..."
        )
        pygit2.clone_repository(GIT_REMOTE_URL, WORK_DIR, callbacks=callbacks)
        repo = pygit2.Repository(WORK_DIR)

    # TODO: use PGP key to sign commits

    collected_attachments = asyncio.run(sync_git_content(repo))
    print(f"Collected {len(collected_attachments)} attachments.")

    sync_attachments(collected_attachments)

    push_mirror()

    print("Done.")


def fetch_prune(repo, callbacks):
    remote = repo.remotes["origin"]
    if remote.url != GIT_REMOTE_URL:
        raise ValueError(
            f"Remote URL {remote.url} of work dir {WORK_DIR} does not match {GIT_REMOTE_URL}"
        )
    # Fetch from remote and reset local content with remote.
    print("Fetch remote")
    remote.fetch(callbacks=callbacks, prune=True)


def push_mirror():
    print("Authenticate using SSH agent...")
    agent_output = subprocess.check_output(["ssh-agent", "-s"], text=True)
    agent_env = {}
    for line in agent_output.splitlines():
        if line.startswith(("SSH_AUTH_SOCK", "SSH_AGENT_PID")):
            instruction, _ = line.split(";", 1)
            k, v = instruction.split("=", 1)
            agent_env[k] = v
    env = {**os.environ, **agent_env}

    # Create a tiny askpass helper that just prints the passphrase
    askpass_path = None
    if GIT_PASSPHRASE:
        fd, askpass_path = tempfile.mkstemp(prefix="askpass-", text=True)
        os.chmod(askpass_path, 0o700)
        os.write(fd, f'#!/usr/bin/env bash\necho "{GIT_PASSPHRASE}"\n'.encode())
        os.close(fd)

    try:
        add_env = dict(env)
        if askpass_path:
            add_env["SSH_ASKPASS"] = askpass_path
            add_env["SSH_ASKPASS_REQUIRE"] = "force"
            # Some ssh-add builds require DISPLAY to be set (any value)
            add_env.setdefault("DISPLAY", ":0")

        # Add key (don't rely on stdin)
        res = subprocess.run(
            ["ssh-add", os.path.expanduser(GIT_PRIVKEY_PATH)],
            text=True,
            capture_output=True,
            env=add_env,
        )
        if res.returncode != 0:
            raise RuntimeError(
                f"Failed to add SSH key: {res.stderr.strip() or res.stdout.strip() or 'unknown error'}"
            )

        print("Push to remote...")
        env_for_git = {
            **env,
            "GIT_SSH_COMMAND": "ssh -o IdentitiesOnly=yes -o StrictHostKeyChecking=no",
        }
        subprocess.run(
            ["git", "-C", WORK_DIR, "push", "--mirror"], env=env_for_git, check=True
        )
        subprocess.run(
            ["git", "-C", WORK_DIR, "push", "--tags"], env=env_for_git, check=True
        )
    finally:
        if askpass_path:
            try:
                os.remove(askpass_path)
            except OSError:
                pass
        subprocess.run(
            ["ssh-agent", "-k"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


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


def fetch_attachment(session, url, dest_file=None):
    """
    Fetch the attachment at the given URL and return its sha256 hash and size.
    """
    if dest_file is None:
        dest_file = os.devnull

    print("Fetch %r" % url)
    h = hashlib.sha256()
    total = 0
    with open(dest_file, "wb") as f:
        with session.get(url, stream=True, timeout=HTTP_TIMEOUT_SECONDS) as r:
            r.raise_for_status()
            for chunk in r.iter_content(1024 * 64):
                if not chunk:
                    continue
                f.write(chunk)
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


def parse_lfs_pointer(data: bytes) -> Tuple[str, int]:
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


def iter_tree(repo: pygit2.Repository, tree: pygit2.Tree, prefix=""):
    for entry in tree:
        path = f"{prefix}{entry.name}"
        if entry.type == pygit2.GIT_OBJECT_BLOB:
            yield path, entry.id  # file
        elif entry.type == pygit2.GIT_OBJECT_TREE:  # descend
            yield from iter_tree(repo, repo[entry.id], prefix=path + "/")


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


async def sync_git_content(repo) -> list[tuple[str, int, str]]:
    """
    Sync content from the remote server to the local git repository.
    Return the list of collected attachments to be uploaded to LFS.
    """
    author = pygit2.Signature(GIT_AUTHOR_USER, GIT_AUTHOR_EMAIL)
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
    if not FORCE and monitor_changeset["timestamp"] == latest_timestamp:
        print("No new changes since last run.")
        return []

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
        if FORCE or entry["last_modified"] > latest_timestamp
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

    # Tell Git LFS that files in attachments/ folder will be sent using LFS.
    common_content.append(
        (".gitattributes", b"attachments/** filter=lfs diff=lfs merge=lfs -text\n")
    )

    # Scan the existing LFS pointers in the repository, in order to detect changed attachments.
    lfs_pointers = {}
    if common_base_tree is not None:
        for path, oid in iter_tree(repo, common_base_tree):
            if path.startswith("attachments/"):
                blob = repo[oid]
                try:
                    sha256_hex, size = parse_lfs_pointer(blob.data)
                    lfs_pointers[path] = (sha256_hex, size)
                except ValueError as exc:
                    print(f"Failed to parse LFS pointer for {path}: {exc}")

    collected_attachments: list[tuple[str, int, str, str]] = []
    attachments_base_url = (await client.server_info())["capabilities"]["attachments"][
        "base_url"
    ].rstrip("/")

    # Now compare with the server content.
    unchanged = 0
    for changeset in all_changesets:
        for record in changeset["changes"]:
            if "attachment" not in record:
                continue

            attachment = record["attachment"]
            location = attachment["location"].lstrip("/")
            path = f"attachments/{location}"

            # And we evaluate whether it's necessary to create/update the attachment.
            existing = lfs_pointers.pop(path, None)
            upload = False
            if existing:
                # If we have a matching LFS pointer, compare it.
                sha256_hex, size = existing
                if sha256_hex != attachment["hash"] or size != attachment["size"]:
                    print(
                        f"Attachment {location} has changed (was: {sha256_hex[:4]}, {size}, is: {attachment['hash'][:4]}, {attachment['size']})"
                    )
                    # Attachment has changed, need to update it.
                    upload = True
                else:
                    unchanged += 1
            else:
                # Attachment is new, need to upload it.
                print(f"attachments/{location} is new.")
                upload = True

            if upload:
                # We keep track of the attachment to download.
                collected_attachments.append(
                    (
                        attachment["hash"],
                        attachment["size"],
                        path,
                        f"{attachments_base_url}/{location}",
                    )
                )
            else:
                # We leave the LFS pointer as is.
                common_content.append(
                    (
                        path,
                        make_lfs_pointer(attachment["hash"], attachment["size"]),
                    )
                )

    # Same for attachments bundles. But since we don't know their hash and size a priori,
    # we need to download them first in order to compare with previous runs content.
    print("Fetching attachments bundles")
    bundles_locations: list[str] = ["bundles/startup.json.mozlz4"]
    for changeset in all_changesets:
        if not changeset["metadata"].get("attachment", {}).get("bundle", False):
            continue
        metadata = changeset["metadata"]
        bundles_locations.append(f"bundles/{metadata['bucket']}--{metadata['id']}.zip")
    # Download the bundles and compare with previous LFS pointers.
    session = requests.Session()
    for location in bundles_locations:
        path = f"attachments/{location}"
        url = f"{attachments_base_url}/{location}"
        hash, size = fetch_attachment(session, url)
        existing = lfs_pointers.pop(path, None)
        if existing:
            previous_hash, previous_size = existing
            if previous_hash != hash or previous_size != size:
                collected_attachments.append((hash, size, path, url))

    # The LFS pointers that remain are deleted attachments.
    # Since they were not included in the common branch content, they
    # will be marked as deleted in the commit.
    print("Unchanged attachments", unchanged)
    print("Updated attachments", len(collected_attachments))
    print("Deleted attachments", len(lfs_pointers))

    monitor_tree_id = upsert_blobs(repo, common_content, base_tree=common_base_tree)

    if common_base_tree is not None and monitor_tree_id == common_base_tree.id:
        print("No changes for common branch, skipping commit.")
    else:
        commit_oid = repo.create_commit(
            common_branch,
            author,
            committer,
            f"Common branch content @ {monitor_changeset['timestamp']}",
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
                f"Common branch content @ {monitor_changeset['timestamp']}",
            )
            print(f"Created tag common: {tag_name}")
        except pygit2.AlreadyExistsError:
            print(f"Tag {tag_name} already exists, skipping.")

    # Now update the bucket branches, create a commit for each collection
    # that has changed since last run.
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

    return collected_attachments


def sync_attachments(attachments: list[tuple[str, int, str, str]]):
    # Make sure LFS is install (idempotent)
    subprocess.run(["git", "-C", WORK_DIR, "lfs", "install", "--local"], check=True)
    # Configure identity
    subprocess.run(
        ["git", "-C", WORK_DIR, "config", "user.name", GIT_AUTHOR_USER], check=True
    )
    subprocess.run(
        ["git", "-C", WORK_DIR, "config", "user.email", GIT_AUTHOR_EMAIL], check=True
    )

    def _download_one(session, expected_hash, expected_size, path, url):
        if os.path.exists(path):
            # Avoid redownloading if the file is here.
            filesize = os.path.getsize(path)
            if filesize == expected_size:
                sha256 = hashlib.sha256()
                with open(path, "rb") as f:
                    while chunk := f.read(1024 * 64):
                        sha256.update(chunk)
                sha256_hex = sha256.hexdigest()
                if sha256_hex == expected_hash:
                    print(
                        f"Attachment {url} already exists at {path}, skipping download."
                    )
                    return
        # Download the attachment into the git repo and retry if the file is not valid.
        retry_count = 0
        while retry_count < HTTP_RETRY_MAX_COUNT:
            fetched_hash, fetched_size = fetch_attachment(session, url, dest_file=path)
            if fetched_hash != expected_hash or fetched_size != expected_size:
                print(
                    f"Attachment content mismatch. Retry {retry_count + 1}/{HTTP_RETRY_MAX_COUNT}"
                )
                retry_count += 1
                continue
            return  # success
        # if we drop out of the loop, all retries failed
        raise ValueError(f"Attachment content mismatch after retries for {url}")

    with requests.Session() as session:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_PARALLEL_REQUESTS
        ) as executor:
            futures = [
                executor.submit(
                    _download_one,
                    session,
                    expected_hash,
                    expected_size,
                    os.path.join(WORK_DIR, location),
                    url,
                )
                for expected_hash, expected_size, location, url in attachments
            ]
            for future in concurrent.futures.as_completed(futures):
                # will raise if any worker raised
                future.result()

    # Now rely on git LFS hooks to commit changes.
    # We cannot use pygit for that, since it does not call LFS hooks and filters for us.
    # The alternative implementation would be to use the Github LFS batch upload API, but
    # it appeared to not be reliable enough to detect existing files and skip reuploads.
    subprocess.run(
        ["git", "-C", WORK_DIR, "add", os.path.join(WORK_DIR, "attachments")],
        check=True,
    )

    # Commit changes.
    subprocess.run(
        ["git", "-C", WORK_DIR, "commit", "-m", "Sync attachments"], check=True
    )
