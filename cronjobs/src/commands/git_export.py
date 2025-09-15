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
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


MAX_PARALLEL_REQUESTS = config("MAX_PARALLEL_REQUESTS", default=10, cast=int)
LOG_LEVEL = config("LOG_LEVEL", default="INFO").upper()
HTTP_TIMEOUT_SECONDS = (5, 60)  # (connect, read) seconds for requests
HTTP_TIMEOUT_BATCH_SECONDS = (10, 180)  # (connect, read) seconds for requests
HTTP_TIMEOUT_UPLOAD_SECONDS = (10, 600)  # (connect, read) seconds for requests
HTTP_RETRY_MAX_COUNT = config("HTTP_RETRY_MAX_COUNT", default=10, cast=int)

SERVER_URL = config("SERVER", default="http://localhost:8888/v1")
GIT_AUTHOR = config("GIT_AUTHOR", default="User <user@example.com>")
WORK_DIR = config("WORK_DIR", default="/tmp/git-export.git")
REPO_OWNER = config("REPO_OWNER", default="leplatrem")
REPO_NAME = config("REPO_NAME", default="remote-settings-data")
GIT_SSH_USERNAME = config("GIT_SSH_USERNAME", default="git")
GIT_REMOTE_URL = config(
    "GIT_REMOTE_URL",
    default=f"{GIT_SSH_USERNAME}@github.com:{REPO_OWNER}/{REPO_NAME}.git",
)
GITHUB_USERNAME = config("GITHUB_USERNAME", default="")
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

    github_lfs_batch_upload_many(objects=collected_attachments)

    push_mirror(repo, callbacks=callbacks)

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


def push_mirror(repo: pygit2.Repository, callbacks=None) -> None:
    """
    An equivalent of `git push --mirror` for branches + tags only.
    """
    remote = repo.remotes["origin"]
    remote_refs = {
        ref.split("/", 1)[1]
        for ref in repo.branches.remote
        if ref.startswith("origin/")
    }
    remote_tag_names = {
        r.replace("refs/tags", "") for r in remote_refs if r.startswith("refs/tags/")
    }

    local_head_names = {b for b in repo.branches.local}  # e.g. {'main', 'dev'}
    local_tag_names = {
        refname.replace("refs/tags/", "")
        for refname in repo.listall_references()
        if refname.startswith("refs/tags/")
    }

    to_push = []

    # 1) Force update all local branches
    for b in sorted(local_head_names):
        to_push.append(f"+refs/heads/{b}:refs/heads/{b}")
    # 2) Force update all local tags
    for t in sorted(local_tag_names):
        to_push.append(f"+refs/tags/{t}:refs/tags/{t}")
    # 3) Delete stale remote tags
    for t in sorted(remote_tag_names - local_tag_names):
        to_push.append(f":refs/tags/{t}")

    if to_push:
        print("Pushing refspecs:", to_push)
        # This is the critical bit: non-fast-forward updates require the '+' force.
        # The deletions use the ':refs/...'; '+' is ignored for deleted refspecs.
        remote.push(to_push, callbacks=callbacks)
    else:
        print("Nothing to push.")


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


def fetch_attachment(url, dest_file=None):
    """
    Fetch the attachment at the given URL and return its sha256 hash and size.
    """
    if dest_file is None:
        dest_file = os.devnull

    print("Fetch %r" % url)
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


def _new_retrying_session() -> requests.Session:
    """
    Session tuned for GitHub LFS 'batch' and 'verify' calls.
    (Presigned uploads use plain requests in each thread; see below.)
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
    adapter = HTTPAdapter(
        max_retries=retries, pool_maxsize=max(16, MAX_PARALLEL_REQUESTS)
    )
    session.mount("https://", adapter)
    return session


def github_lfs_batch_request(
    session: requests.Session,
    *,
    auth_header: str,
    objects: Iterable[Dict[str, Any]],
    operation: str,  # "upload" or "download"
) -> Dict[str, Any]:
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
    r = session.post(
        url, headers=headers, json=payload, timeout=HTTP_TIMEOUT_BATCH_SECONDS
    )
    if r.status_code != 200:
        print(f"LFS: batch failed with status {r.status_code}: {r.text}")
    r.raise_for_status()
    return r.json()


def _download_and_upload_file(
    source: Tuple[str, int, str],  # (sha256_hex, size, src_url)
    dest: Tuple[str, str, Dict[str, str]],  # (href, method, headers)
) -> None:
    """
    Downloads the file locally (verifies digest/size), then uploads to presigned URL.
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
            time.sleep(0.5)
        else:
            raise RuntimeError(
                f"LFS: {src_url} failed to download after {HTTP_RETRY_MAX_COUNT} attempts"
            )
        # If we reach here, it means we successfully downloaded the file.
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


def _verify_if_needed(
    session: requests.Session,
    *,
    auth_header: str,
    api_obj: Dict[str, Any],
    oid: str,
    size: int,
) -> None:
    verify_action = (api_obj.get("actions") or {}).get("verify")
    if not verify_action:
        return
    href = verify_action["href"]
    headers = dict(verify_action.get("header") or {})
    # Verify is an authenticated call; make sure Authorization is present.
    headers.setdefault("Authorization", auth_header)
    payload = {"oid": oid, "size": size}
    r = session.post(href, json=payload, headers=headers, timeout=HTTP_TIMEOUT_SECONDS)
    if r.status_code not in (200, 201, 204):
        print(f"LFS: verify for {oid} failed with {r.status_code}: {r.text}")
    r.raise_for_status()


def github_lfs_batch_upload_many(
    objects: Iterable[Tuple[str, int, str]],  # (sha256_hex, size, source_url)
) -> None:
    """
    Performs LFS batch 'upload' for up to GITHUB_MAX_LFS_BATCH_SIZE objects per batch,
    PUTs missing objects to the presigned destinations, and POSTs verify if provided.

    objects: iterable of (oid_hex:str, size:int, src_url:str)
    """
    creds = f"{GITHUB_USERNAME}:{GITHUB_TOKEN}".encode("utf-8")
    authz = f"Basic {base64.b64encode(creds).decode('ascii')}"

    objs_all = list(objects)
    if not objs_all:
        print("LFS: nothing to upload")
        return

    chunks = list(itertools.batched(objs_all, GITHUB_MAX_LFS_BATCH_SIZE))
    total_chunks = len(chunks)

    # Single session for batch/verify calls (NOT reused for presigned PUTs)
    ctl_session = _new_retrying_session()

    for idx, chunk in enumerate(chunks, start=1):
        api_objs = [{"oid": oid, "size": size} for (oid, size, _url) in chunk]
        print(f"LFS: uploading chunk {idx}/{total_chunks} ({len(chunk)} objects)")

        batch_resp = github_lfs_batch_request(
            ctl_session,
            auth_header=authz,
            objects=api_objs,
            operation="upload",
        )

        # Defensive: map response objects by oid (do NOT assume order)
        resp_objects = batch_resp.get("objects") or []
        api_by_oid = {o.get("oid"): o for o in resp_objects if o.get("oid")}

        # Decide which to upload + prepare verify data
        to_upload: list[
            Tuple[Tuple[str, int, str], Tuple[str, str, Dict[str, str]]]
        ] = []
        for oid, size, url in chunk:
            api_obj = api_by_oid.get(oid)
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
                method = upload_action.get("method", "PUT")
                headers = upload_action.get("header") or {}
                to_upload.append(((oid, size, url), (href, method, headers)))
            else:
                print(f"LFS: already present {url} ({oid}) on server, skipping upload.")

        # Parallel uploads
        if to_upload:
            with ThreadPoolExecutor(max_workers=MAX_PARALLEL_REQUESTS) as pool:
                futures = [
                    pool.submit(_download_and_upload_file, src, dest)
                    for (src, dest) in to_upload
                ]
                for f in as_completed(futures):
                    f.result()  # propagate exceptions

        # Verify (sequential or light parallel is fine; verify endpoints are fast)
        # Use the same api_by_oid map so we verify exactly what the server asked us to.
        to_verify = [(oid, size) for (oid, size, _url) in chunk if api_by_oid.get(oid)]
        for oid, size in to_verify:
            _verify_if_needed(
                ctl_session,
                auth_header=authz,
                api_obj=api_by_oid[oid],
                oid=oid,
                size=size,
            )

        print(
            f"LFS: uploaded {len(to_upload)} new objects in chunk {idx}/{total_chunks}"
        )


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

    # Store all the attachments as LFS pointers.

    collected_attachments: list[tuple[str, int, str]] = []
    attachments_base_url = (await client.server_info())["capabilities"]["attachments"][
        "base_url"
    ].rstrip("/")

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
            common_content.append((f"attachments/{location}", pointer_blob))
            collected_attachments.append(
                (
                    attachment["hash"],
                    attachment["size"],
                    f"{attachments_base_url}/{location}",
                )
            )

    # Also store the bundles as LFS pointers.
    print("Fetching attachments bundles")

    bundles_locations: list[str] = ["bundles/startup.json.mozlz4"]
    for changeset in all_changesets:
        if not changeset["metadata"].get("attachment", {}).get("bundle", False):
            continue
        metadata = changeset["metadata"]
        bundles_locations.append(f"bundles/{metadata['bucket']}--{metadata['id']}.zip")
    for location in bundles_locations:
        url = f"{attachments_base_url}/{location}"
        hash, size = fetch_attachment(url)
        blob = make_lfs_pointer(hash, size)
        common_content.append((f"attachments/{location}", blob))
        collected_attachments.append((hash, size, url))

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
