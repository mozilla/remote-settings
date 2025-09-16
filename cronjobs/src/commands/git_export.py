import asyncio
import base64
import hashlib
import itertools
import json
import os
import tempfile
import time
import urllib
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Generator, Iterable, Optional

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
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


# Mandatory environment variables (default values)
SERVER_URL = config("SERVER", default="http://localhost:8888/v1")
GIT_AUTHOR = config("GIT_AUTHOR", default="User <user@example.com>")
REPO_OWNER = config("REPO_OWNER", default="leplatrem")
REPO_NAME = config("REPO_NAME", default="remote-settings-data")
GITHUB_USERNAME = config("GITHUB_USERNAME", default="")
GITHUB_TOKEN = config("GITHUB_TOKEN", default="")
SSH_PRIVKEY_PATH = config("SSH_PRIVKEY_PATH", default="~/.ssh/id_ed25519")
SSH_KEY_PASSPHRASE = config("SSH_KEY_PASSPHRASE", default="")

# Internal parameters
WORK_DIR = config("WORK_DIR", default="/tmp/git-export.git")
FORCE = config("FORCE", default=False, cast=bool)
MAX_PARALLEL_REQUESTS = config("MAX_PARALLEL_REQUESTS", default=10, cast=int)
LOG_LEVEL = config("LOG_LEVEL", default="INFO").upper()
HTTP_TIMEOUT_CONNECT_SECONDS = config(
    "HTTP_TIMEOUT_CONNECT_SECONDS", default=10, cast=int
)
HTTP_TIMEOUT_READ_SECONDS = config("HTTP_TIMEOUT_READ_SECONDS", default=60, cast=int)
HTTP_TIMEOUT_WRITE_SECONDS = config("HTTP_TIMEOUT_WRITE_SECONDS", default=600, cast=int)
HTTP_RETRY_MAX_COUNT = config("HTTP_RETRY_MAX_COUNT", default=10, cast=int)
HTTP_RETRY_DELAY_SECONDS = config("HTTP_RETRY_DELAY_SECONDS", default=1, cast=float)
GIT_SSH_USERNAME = config("GIT_SSH_USERNAME", default="git")
GIT_REMOTE_URL = config(
    "GIT_REMOTE_URL",
    default=f"{GIT_SSH_USERNAME}@github.com:{REPO_OWNER}/{REPO_NAME}.git",
)
GITHUB_MAX_LFS_BATCH_SIZE = config("GITHUB_MAX_LFS_BATCH_SIZE", default=100, cast=int)
SSH_PUBKEY_PATH = config("SSH_PUBKEY_PATH", default=f"{SSH_PRIVKEY_PATH}.pub")

# Constants
COMMON_BRANCH = "common"
REMOTE_NAME = "origin"
_user, _email = GIT_AUTHOR.split("<")
GIT_USER = _user.strip()
GIT_EMAIL = _email.rstrip(">")
HTTP_TIMEOUT_SECONDS = (HTTP_TIMEOUT_CONNECT_SECONDS, HTTP_TIMEOUT_READ_SECONDS)
HTTP_TIMEOUT_BATCH_SECONDS = (HTTP_TIMEOUT_CONNECT_SECONDS, HTTP_TIMEOUT_READ_SECONDS)
HTTP_TIMEOUT_UPLOAD_SECONDS = (HTTP_TIMEOUT_CONNECT_SECONDS, HTTP_TIMEOUT_WRITE_SECONDS)


def git_export(event, context):
    """
    Main entrypoint
    """
    print(f"Git remote URL {GIT_REMOTE_URL}")
    print(
        f"Use SSH key {SSH_PUBKEY_PATH} with {'*' * len(SSH_KEY_PASSPHRASE) if SSH_KEY_PASSPHRASE else 'empty'} passphrase"
    )
    credentials = Keypair(
        GIT_SSH_USERNAME,
        os.path.expanduser(SSH_PUBKEY_PATH),
        os.path.expanduser(SSH_PRIVKEY_PATH),
        SSH_KEY_PASSPHRASE,
    )
    callbacks = RemoteCallbacks(credentials=credentials)

    if os.path.exists(WORK_DIR):
        print(f"Work dir {WORK_DIR} already exists, skipping clone.")
        repo = pygit2.Repository(WORK_DIR)
        remote = repo.remotes[REMOTE_NAME]
        if remote.url != GIT_REMOTE_URL:
            raise ValueError(
                f"Remote URL {remote.url} of work dir {WORK_DIR} does not match {GIT_REMOTE_URL}"
            )
        print("Head was at", repo.head.target)
        print(f"Fetching from {GIT_REMOTE_URL}...")
        remote.fetch(callbacks=callbacks, prune=True)
    else:
        # Clone remote repository into work dir.
        print(f"Clone {GIT_REMOTE_URL} into {WORK_DIR}...")
        pygit2.clone_repository(GIT_REMOTE_URL, WORK_DIR, callbacks=callbacks)
        repo = pygit2.Repository(WORK_DIR)

    print("Head is now at", repo.head.target)

    # TODO: use PGP key to sign commits

    try:
        changed_attachments, changed_branches, changed_tags = asyncio.run(
            repo_sync_content(repo)
        )
        print(f"{len(changed_attachments)} attachments to upload.")
        github_lfs_batch_upload_many(objects=changed_attachments)

        push_mirror(repo, changed_branches, changed_tags, callbacks=callbacks)

        # TODO: delete old tags and old LFS objects.

        print("Done.")
    except Exception as exc:
        print("Error occurred:", exc)
        reset_repo(repo, callbacks=callbacks)
        raise exc


def reset_repo(repo: pygit2.Repository, callbacks: pygit2.RemoteCallbacks):
    print("Rolling back local changes...")
    # Reset all local branches to their remote
    for branch_name in repo.branches.local:
        remote_name = f"origin/{branch_name}"
        if remote_name not in repo.branches:
            continue
        local_branch = repo.branches[branch_name]
        remote_branch = repo.branches[remote_name]
        # Reset local branch to remote target
        print(f"Resetting local branch {branch_name} to remote {remote_name}")
        local_branch.set_target(remote_branch.target)
        # If it's the currently checked out branch, reset HEAD too
        if repo.head.shorthand == branch_name:
            repo.reset(remote_branch.target, pygit2.GIT_RESET_HARD)

    # Delete local tags that are not on remote
    origin = repo.remotes[REMOTE_NAME]
    remote_tags = {
        obj["name"]
        for obj in origin.ls_remotes(callbacks=callbacks)
        if obj["name"].startswith("refs/tags/") and not obj["local"]
    }
    for ref in repo.references:
        if ref.startswith("refs/tags/") or ref in remote_tags:
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


def json_dumpb(obj: Any) -> bytes:
    """
    Serialize an object to a JSON-formatted byte string.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


async def fetch_all_changesets(
    client: kinto_http.AsyncClient, collections: Iterable[tuple[str, str]]
):
    """
    Fetch the changesets of the specified collections using parallel requests.
    """
    sem = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)

    async def fetch(bid, cid):
        async with sem:
            print("Fetching %s/%s" % (bid, cid))
            return await client.get_changeset(
                bucket=bid, collection=cid, bust_cache=True
            )

    return await asyncio.gather(*[fetch(bid, cid) for bid, cid in collections])


def fetch_attachment(url, dest_file=None):
    """
    Fetch the attachment at the given URL and return its sha256 hash and size.
    """
    if dest_file is None:
        dest_file = os.devnull

    print("Fetch attachment %r" % url)
    h = hashlib.sha256()
    total = 0
    with open(dest_file, "wb") as f:
        with requests.get(url, stream=True, timeout=HTTP_TIMEOUT_SECONDS) as r:
            r.raise_for_status()
            for chunk in r.iter_content(1024 * 64):
                if not chunk:
                    continue
                f.write(chunk)
                h.update(chunk)
                total += len(chunk)
    return h.hexdigest(), total


def fetch_all_cert_chains(
    client: kinto_http.AsyncClient, changesets
) -> list[tuple[str, str]]:
    """
    Fetch all certificate chains for the given changesets, and return URL + PEM content.
    """
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
    """
    for entry in tree:
        path = f"{prefix}{entry.name}"
        if entry.type == pygit2.GIT_OBJECT_BLOB:
            yield path, entry.id  # file
        elif entry.type == pygit2.GIT_OBJECT_TREE:  # descend
            yield from iter_tree(repo, repo[entry.id], prefix=path + "/")


def _new_retrying_session() -> requests.Session:
    """
    Session tuned for GitHub LFS 'batch' and 'verify' calls.
    """
    session = requests.Session()
    retries = Retry(
        total=HTTP_RETRY_MAX_COUNT,
        connect=HTTP_RETRY_MAX_COUNT,
        read=HTTP_RETRY_MAX_COUNT,
        backoff_factor=1.5,
        status_forcelist=[408, 409, 425, 429, 500, 502, 503, 504],
        allowed_methods={"HEAD", "GET", "PUT", "POST", "DELETE", "OPTIONS", "TRACE"},
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries, pool_maxsize=MAX_PARALLEL_REQUESTS)
    session.mount("https://", adapter)
    return session


def github_lfs_batch_request(
    auth_header: str,
    objects: Iterable[dict[str, Any]],
    operation: str,  # "upload" or "download"
) -> dict[str, Any]:
    """
    Generic Git LFS Batch call.
    objects: [{"oid": "<sha256-hex>", "size": <int>}, ...]

    https://github.com/git-lfs/git-lfs/blob/main/docs/api/batch.md#requests
    """
    url = f"https://github.com/{REPO_OWNER}/{REPO_NAME}.git/info/lfs/objects/batch"
    headers = {
        "Accept": "application/vnd.git-lfs+json",
        "Content-Type": "application/vnd.git-lfs+json",
        "Authorization": auth_header,
    }
    payload = {
        "operation": operation,
        "transfers": ["basic"],
        "objects": list(objects),
    }
    session = _new_retrying_session()
    r = session.post(
        url, headers=headers, json=payload, timeout=HTTP_TIMEOUT_BATCH_SECONDS
    )
    if r.status_code != 200:
        print(f"LFS: batch failed with status {r.status_code}: {r.text}")
    r.raise_for_status()
    return r.json()


def _download_from_cdn_and_upload_to_lfs_volume(
    source: tuple[str, int, str],  # (sha256_hex, size, src_url)
    dest: tuple[str, str, dict[str, str]],  # (href, method, headers)
) -> None:
    """
    Downloads the file locally (verifies digest/size), then uploads to specified URL.
    """
    sha256_hex, size, src_url = source
    upload_href, upload_method, upload_headers = dest

    with tempfile.NamedTemporaryFile() as tmp:
        tmp_path = tmp.name
        retry = 0
        while retry < HTTP_RETRY_MAX_COUNT:
            # Download from CDN into temp file.
            downloaded_digest, downloaded_size = fetch_attachment(
                src_url, dest_file=tmp_path
            )
            if downloaded_size == size:
                if downloaded_digest == sha256_hex:
                    break
            retry += 1
            time.sleep(HTTP_RETRY_DELAY_SECONDS)
        else:
            raise RuntimeError(
                f"LFS: {src_url} failed to download after {HTTP_RETRY_MAX_COUNT} attempts"
            )
        # If we reach here, it means we successfully downloaded the file from the CDN.
        # Now, upload it to LFS volume.
        print(
            f"LFS: uploading {src_url} -> {upload_method} {upload_href} ({size} bytes)"
        )
        with open(tmp_path, "rb") as f:
            resp = requests.request(
                upload_method.upper(),
                upload_href,
                data=f,
                headers=upload_headers,
                timeout=HTTP_TIMEOUT_UPLOAD_SECONDS,
            )
        if resp.status_code not in (200, 201, 204):
            print(f"LFS: {src_url} upload failed with {resp.status_code}: {resp.text}")
        resp.raise_for_status()


def _github_lfs_verify_upload(
    source: tuple[str, str],  # (sha256_hex, size)
    dest: tuple[str, dict[str, str, str]],  # (href, method, headers)
) -> None:
    """
    The LFS upload API returns a verify action that the client has to call in
    order to complete the upload process.
    """
    oid, size = source
    verify_href, method, headers = dest
    payload = {"oid": oid, "size": size}
    r = requests.request(
        method, verify_href, json=payload, headers=headers, timeout=HTTP_TIMEOUT_SECONDS
    )
    if r.status_code not in (200, 201, 204):
        print(f"LFS: verify for {oid} failed with {r.status_code}: {r.text}")
    r.raise_for_status()


def github_lfs_batch_upload_many(
    objects: Iterable[tuple[str, int, str]],  # (sha256_hex, size, source_url)
) -> None:
    """
    Performs LFS batch 'upload' for up to GITHUB_MAX_LFS_BATCH_SIZE objects per batch,
    PUTs missing objects to the presigned destinations, and POSTs verify if provided.

    objects: iterable of (oid_hex:str, size:int, src_url:str)
    """
    creds = f"{GITHUB_USERNAME}:{GITHUB_TOKEN}".encode("utf-8")
    authz = f"Basic {base64.b64encode(creds).decode('ascii')}"

    chunks = list(itertools.batched(objects, GITHUB_MAX_LFS_BATCH_SIZE))
    total_chunks = len(chunks)

    # Single session for batch/verify calls (NOT reused for presigned PUTs/POSTs)
    for idx, chunk in enumerate(chunks, start=1):
        print(f"LFS: uploading chunk {idx}/{total_chunks} ({len(chunk)} objects)")

        batch_resp = github_lfs_batch_request(
            auth_header=authz,
            objects=[{"oid": oid, "size": size} for (oid, size, _url) in chunk],
            operation="upload",
        )

        # Map response objects by oid
        resp_objects = batch_resp.get("objects") or []
        api_objs_by_oid = {o.get("oid"): o for o in resp_objects if o.get("oid")}

        # Decide which to upload or/and verify
        to_upload: list[tuple[tuple[str, int, str], tuple[str, dict[str, str]]]] = []
        to_verify: list[tuple[tuple[str, int], tuple[str, str, dict[str, str]]]] = []
        for oid, size, url in chunk:
            api_obj = api_objs_by_oid.get(oid)
            if not api_obj:
                print(
                    f"LFS: warning: server omitted oid {oid} in batch response; skipping"
                )
                continue
            if err := api_obj.get("error"):
                print(
                    f"LFS: upload error for {oid}: {err.get('code')} {err.get('message')}"
                )
                continue
            act = api_obj.get("actions") or {}
            upload_action = act.get("upload")
            if upload_action:
                href = upload_action["href"]
                method = upload_action.get("method") or "PUT"
                headers = upload_action["header"]
                to_upload.append(((oid, size, url), (href, method, headers)))
            else:
                print(f"LFS: already present {url} ({oid}) on server, skipping upload.")

            # The server returns a verify endpoint with headers.
            verify_action = act.get("verify")
            if verify_action:
                href = verify_action["href"]
                headers = verify_action["header"]
                to_verify.append(((oid, size), (href, "POST", headers)))
            else:
                print(f"LFS: no verify action for {oid}, skipping verify.")

        # Parallel uploads
        if to_upload:
            with ThreadPoolExecutor(max_workers=MAX_PARALLEL_REQUESTS) as pool:
                futures = [
                    pool.submit(_download_from_cdn_and_upload_to_lfs_volume, src, dest)
                    for (src, dest) in to_upload
                ]
                for f in as_completed(futures):
                    f.result()  # propagate exceptions

        # Parallel verifications
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_REQUESTS) as pool:
            futures = [
                pool.submit(_github_lfs_verify_upload, src, dest)
                for (src, dest) in to_verify
            ]
            for f in as_completed(futures):
                f.result()  # propagate exceptions

        print(
            f"LFS: {len(to_upload)} uploaded and {len(to_verify)} verified in chunk {idx}/{total_chunks}"
        )


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


async def repo_sync_content(
    repo,
) -> tuple[list[tuple[str, int, str]], list[str], list[str]]:
    """
    Sync content from the remote server to the local git repository.
    Return the list of changed attachments to be uploaded to LFS, the list of changed branches, and the list of changed tags.
    """
    changed_attachments: list[tuple[str, int, str]] = []
    changed_branches: set[str] = set()
    changed_tags: list[str] = []

    author = pygit2.Signature(GIT_USER, GIT_EMAIL)
    committer = author

    common_branch = f"refs/heads/{COMMON_BRANCH}"

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
        print(
            f"Found latest tag: {latest_timestamp}.",
            "Ignoring (forced)" if FORCE else "",
        )
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
        return changed_attachments, changed_branches, changed_tags

    # Store the monitor changeset in `common` branch.
    # Anything from previous commits is lost.
    common_content = [
        ("monitor-changes.json", json_dumpb(monitor_changeset)),
    ]

    new_changesets = [
        entry
        for entry in monitor_changeset["changes"]
        if FORCE or entry["last_modified"] > latest_timestamp
    ]
    print(f"{len(new_changesets)} collections changed since last sync.")
    all_changesets = await fetch_all_changesets(
        client, [(entry["bucket"], entry["collection"]) for entry in new_changesets]
    )

    # Store the broadcast version in `common` branch.
    print("Fetching broadcasts content")
    resp = requests.get(f"{SERVER_URL}/__broadcasts__")
    resp.raise_for_status()
    broadcasts = resp.json()
    common_content.append(("broadcasts.json", json_dumpb(broadcasts)))

    # Store the certificate chains.
    print("Fetching certificate chains")
    for url, pem in fetch_all_cert_chains(client, all_changesets):
        parsed = urllib.parse.urlparse(url)
        common_content.append((f"cert-chains/{parsed.path.lstrip('/')}", pem.encode()))

    # Scan the existing LFS pointers in the repository, in order to detect changed attachments.
    existing_attachments = {}
    if common_base_tree is not None:
        for path, oid in iter_tree(repo, common_base_tree):
            if not path.startswith("attachments/"):
                continue
            blob = repo[oid]
            try:
                sha256_hex, size = parse_lfs_pointer(blob.data)
                existing_attachments[path] = (sha256_hex, size)
            except ValueError as exc:
                print(f"Failed to parse LFS pointer for {path}: {exc}")
    print(f"Found {len(existing_attachments)} attachments in tree")

    # Store all the attachments as LFS pointers.
    attachments_base_url = (await client.server_info())["capabilities"]["attachments"][
        "base_url"
    ].rstrip("/")

    # Mark the attachments/ folder as fully managed via LFS.
    common_content.append(
        (".gitattributes", b"attachments/** filter=lfs diff=lfs merge=lfs -text\n")
    )
    # Iterate through all records that have attachments, and compare their sha256
    # with the existing LFS pointer. If new or changed, keep track of it for upload.
    for changeset in all_changesets:
        for record in changeset["changes"]:
            if "attachment" not in record:
                continue

            attachment = record["attachment"]
            location = attachment["location"].lstrip("/")
            path = f"attachments/{location}"
            pointer_blob = make_lfs_pointer(attachment["hash"], attachment["size"])
            common_content.append((path, pointer_blob))

            existing_hash = existing_size = None
            if existing := existing_attachments.get(path):
                existing_hash, existing_size = existing
            if (
                existing_hash != attachment["hash"]
                or existing_size != attachment["size"]
            ):
                print(f"Attachment {path} is new or has changed")
                changed_attachments.append(
                    (
                        attachment["hash"],
                        attachment["size"],
                        f"{attachments_base_url}/{location}",
                    )
                )

    # Also store the bundles as LFS pointers. But since we don't know their sha256
    # and size, we have to fetch them first before being able to compare them
    # with existing LFS pointers.
    print("Fetching attachments bundles")
    bundles_locations: list[str] = ["bundles/startup.json.mozlz4"]
    for changeset in all_changesets:
        if not changeset["metadata"].get("attachment", {}).get("bundle", False):
            continue
        metadata = changeset["metadata"]
        bundles_locations.append(f"bundles/{metadata['bucket']}--{metadata['id']}.zip")
    for location in bundles_locations:
        url = f"{attachments_base_url}/{location}"
        path = f"attachments/{location}"
        hash, size = fetch_attachment(url)
        blob = make_lfs_pointer(hash, size)
        common_content.append((path, blob))

        existing_hash = existing_size = None
        if existing := existing_attachments.get(path):
            existing_hash, existing_size = existing
        if existing_hash != hash or existing_size != size:
            print(f"Bundle {path} is new or has changed")
            changed_attachments.append((hash, size, url))

    monitor_tree_id = tree_upsert_blobs(
        repo, common_content, base_tree=common_base_tree
    )

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
        changed_branches.add(common_branch)

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
            changed_tags.append(tag_name)
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

        files_tree_id = tree_upsert_blobs(repo, branch_content, base_tree=base_tree)

        if base_tree is not None and files_tree_id == base_tree.id:
            print(f"No changes for {bid}/{cid} branch, skipping commit.")
        else:
            # Commit and tag.
            commit_oid = repo.create_commit(
                refname, author, committer, commit_message, files_tree_id, parents
            )
            print(f"Created commit {bid}/{cid} @ {timestamp}: {commit_oid}")
            changed_branches.add(refname)

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
                print(f"Created {tag_name}")
                changed_tags.append(tag_name)
            except pygit2.AlreadyExistsError:
                print(f"Tag {tag_name} already exists, skipping.")

    return changed_attachments, changed_branches, changed_tags
