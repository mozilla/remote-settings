import asyncio
import datetime
import json
import os
import traceback
import urllib
from typing import Any, Iterable

import kinto_http
import pygit2
import requests
from decouple import config
from pygit2 import (
    Keypair,
    RemoteCallbacks,
)

from ._git_export_git_tools import (
    clone_or_fetch,
    delete_old_tags,
    delete_unreferenced_commits,
    iter_tree,
    make_lfs_pointer,
    parse_lfs_pointer,
    push_mirror,
    reset_repo,
    tree_upsert_blobs,
)
from ._git_export_lfs import (
    fetch_and_hash,
    github_lfs_batch_upload_many,
    github_lfs_validate_credentials,
    list_unreachable_paths,
)


# Mandatory environment variables (default values)
SERVER_URL = config("SERVER", default="http://localhost:8888/v1")
GIT_AUTHOR = config("GIT_AUTHOR", default="User <user@example.com>")
REPO_OWNER = config("REPO_OWNER", default="mozilla")
REPO_NAME = config("REPO_NAME", default="remote-settings-data")
SSH_PRIVKEY_PATH = os.path.expanduser(
    config("SSH_PRIVKEY_PATH", default="~/.ssh/id_ed25519")
)
SSH_KEY_PASSPHRASE = config("SSH_KEY_PASSPHRASE", default="")

# LFS GitHub authentication
# Option A: Personal Access Token (PAT)
GITHUB_USERNAME = config("GITHUB_USERNAME", default=None)
GITHUB_TOKEN = config("GITHUB_TOKEN", default=None)
# Option B: GitHub App authentication
GITHUB_APP_ID = config("GITHUB_APP_ID", default=None)
GITHUB_APP_PRIVATE_KEY_PATH = config("GITHUB_APP_PRIVATE_KEY_PATH", default=None)

# Internal parameters
WORK_DIR = config("WORK_DIR", default="/tmp/git-export.git")
MAX_PARALLEL_REQUESTS = config("MAX_PARALLEL_REQUESTS", default=10, cast=int)
LOG_LEVEL = config("LOG_LEVEL", default="INFO").upper()
GIT_SSH_USERNAME = config("GIT_SSH_USERNAME", default="git")
GIT_REMOTE_URL = config(
    "GIT_REMOTE_URL",
    default=f"{GIT_SSH_USERNAME}@github.com:{REPO_OWNER}/{REPO_NAME}.git",
)
SSH_PUBKEY_PATH = os.path.expanduser(
    config("SSH_PUBKEY_PATH", default=f"{SSH_PRIVKEY_PATH}.pub")
)
TAGS_MAX_AGE_DAYS = config("TAGS_MAX_AGE_DAYS", default=90, cast=int)
MIN_TAGS_PER_COLLECTION_COUNT = config(
    "MIN_TAGS_PER_COLLECTION_COUNT", default=2, cast=int
)

# By default, we delete unreachable attachments only once every 2days between 12:00 and 12:15 UTC
# This avoids running this potentially expensive operation on every cronjob run.
# And to avoid duplicating the cronjob definition twice just to set this env var.
_now = datetime.datetime.now(datetime.timezone.utc)
_IS_EVEN_DAY = _now.day % 2 == 0
_SHOULD_DELETE_UNREACHABLE = _IS_EVEN_DAY and _now.hour == 12 and 0 < _now.minute < 15

DELETE_UNREACHABLE_ATTACHMENTS = config(
    "DELETE_UNREACHABLE_ATTACHMENTS", default=_SHOULD_DELETE_UNREACHABLE, cast=bool
)

# By default, we only synchronize if there are data changes.
# But once a day, we run a full sync in order to synchronize collections whose data
# didn't change but whose metadata did (e.g., signature refreshed, new certs, etc.).
_SHOULD_FORCE = _now.hour == 0 and 0 < _now.minute < 15
FORCE = config("FORCE", default=_SHOULD_FORCE, cast=bool)

# Constants
GIT_REF_PREFIX = "v1/"
COMMON_BRANCH = "common"
_user, _email = GIT_AUTHOR.split("<")
GIT_USER = _user.strip()
GIT_EMAIL = _email.rstrip(">")


def git_export(event, context):
    """
    Export Remote Settings data to a Git repository.
    """
    print(f"Git remote URL {GIT_REMOTE_URL}")
    print(
        f"Use SSH key {SSH_PUBKEY_PATH} with {'*' * len(SSH_KEY_PASSPHRASE) if SSH_KEY_PASSPHRASE else 'empty'} passphrase"
    )
    for key in (SSH_PUBKEY_PATH, SSH_PRIVKEY_PATH):
        open(key, "rb").read()
    credentials = Keypair(
        GIT_SSH_USERNAME,
        SSH_PUBKEY_PATH,
        SSH_PRIVKEY_PATH,
        SSH_KEY_PASSPHRASE,
    )
    callbacks = RemoteCallbacks(credentials=credentials)
    # TODO: use PGP key to sign commits

    print(
        f"Testing GitHub Token for {GITHUB_USERNAME or GITHUB_APP_ID} on {REPO_OWNER}/{REPO_NAME}..."
    )
    auth_header = github_lfs_validate_credentials(
        repo_owner=REPO_OWNER,
        repo_name=REPO_NAME,
        github_username=GITHUB_USERNAME,
        github_token=GITHUB_TOKEN,
        github_app_id=GITHUB_APP_ID,
        github_app_private_key_path=GITHUB_APP_PRIVATE_KEY_PATH,
    )

    repo = clone_or_fetch(GIT_REMOTE_URL, WORK_DIR, callbacks=callbacks)
    if not repo.raw_listall_references():
        print("No branches or tags found in the repository.")
    else:
        print("Head is now at", repo.head.target)

    try:
        changed_attachments, changed_branches, created_tags = asyncio.run(
            repo_sync_content(repo)
        )

        deleted_tags = delete_old_tags(
            repo,
            max_age_days=TAGS_MAX_AGE_DAYS,
            min_tags_per_collection=MIN_TAGS_PER_COLLECTION_COUNT,
        )
        print(f"{len(deleted_tags)} old tags to delete.")

        # Now that we deleted old tags, delete all commits that are no longer
        # referenced by any tag.
        # This will required checkout to use `--force` since we rewrite history.
        # We do this to keep a reasonable number of objects, and most importantly
        # to delete LFS files from remote storage (Github keeps LFS files as long as
        # there is a reference to them in the git history).
        delete_unreferenced_commits(repo)

        print(f"{len(changed_attachments)} attachments to upload.")
        github_lfs_batch_upload_many(
            objects=changed_attachments,
            repo_owner=REPO_OWNER,
            repo_name=REPO_NAME,
            auth_header=auth_header,
        )

        changed_tags = [f"+{tag}" for tag in created_tags] + [
            f"-{tag}" for tag in deleted_tags
        ]
        push_mirror(repo, changed_branches, changed_tags, callbacks=callbacks)

        print("Done.")
    except Exception as exc:
        print("Error occurred:", exc)
        traceback.print_exc()
        print("Rolling back local changes...")
        reset_repo(repo, callbacks=callbacks)
        raise exc


def json_dumpb(obj: Any) -> bytes:
    """
    Serialize an object to a JSON-formatted byte string.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


async def fetch_all_changesets(
    client: kinto_http.AsyncClient, collections: Iterable[tuple[str, str]]
) -> list[dict[str, Any]]:
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


async def repo_sync_content(
    repo,
    delete_unreachable_attachments=DELETE_UNREACHABLE_ATTACHMENTS,
) -> tuple[list[tuple[str, int, str]], list[str], list[str]]:
    """
    Sync content from the remote server to the local git repository.
    Return the list of changed attachments to be uploaded to LFS, the list of changed branches, and the list of changed tags.
    """
    changed_attachments: list[tuple[str, int, str]] = []
    changed_branches: set[str] = set()
    created_tags: list[str] = []

    author = pygit2.Signature(GIT_USER, GIT_EMAIL)
    committer = author

    common_branch = f"refs/heads/{GIT_REF_PREFIX}{COMMON_BRANCH}"

    # The repo may exist without the 'common' ref (first run).
    try:
        common_tip = repo.lookup_reference(common_branch).target
        common_base_tree = repo.get(common_tip).tree
        parents = [common_tip]
    except KeyError:  # pragma: no cover
        common_base_tree = None
        parents = []

    # Previous run timestamp, find latest tag starting with `timestamps/common/*`
    refs = [ref.decode() for ref in repo.raw_listall_references()]
    timestamps = [
        int(t.split("/")[-1])
        for t in refs
        if t.startswith(f"refs/tags/{GIT_REF_PREFIX}timestamps/common/")
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
        return changed_attachments, changed_branches, created_tags

    server_info = await client.server_info()

    # Store the server info and monitor changeset in `common` branch.
    # Anything from previous commits is lost.
    common_content = [
        ("server-info.json", json_dumpb(server_info)),
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
        cert_path = f"cert-chains/{parsed.path.lstrip('/')}"
        print(f"Storing cert chain {cert_path}")
        common_content.append((cert_path, pem.encode()))

    # Scan the existing LFS pointers in the repository, in order to detect changed attachments.
    existing_attachments = {}
    if common_base_tree is not None:
        try:
            attachment_tree = common_base_tree / "attachments"
            objs = iter_tree(repo, attachment_tree)
        except KeyError:
            # No attachments/ folder yet.
            objs = []
        for path, oid in objs:
            blob = repo[oid]
            try:
                sha256_hex, size = parse_lfs_pointer(blob.data)
            except ValueError as exc:
                print(f"Failed to parse LFS pointer for {path}: {exc}")
            existing_attachments[path] = (sha256_hex, size)
    print(f"Found {len(existing_attachments)} attachments in tree")

    # Store all the attachments as LFS pointers.
    attachments_base_url = server_info["capabilities"]["attachments"][
        "base_url"
    ].rstrip("/")

    # Delete unreachable attachments. Since this operation creates a lot of
    # hits, we do it only if the flag is enabled (less frequent than normal cronjob run).
    if delete_unreachable_attachments:
        attachments_paths = existing_attachments.keys()
        obsolete_attachments = list_unreachable_paths(
            attachments_base_url, attachments_paths
        )
        for path in obsolete_attachments:
            print(f"Attachment {path} is unreachable, deleting from tree")
            common_content.append((f"attachments/{path}", None))  # Delete from tree

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
        has_attachment = any(r.get("attachment") for r in changeset["changes"])
        if not has_attachment:
            continue
        metadata = changeset["metadata"]
        bundles_locations.append(f"bundles/{metadata['bucket']}--{metadata['id']}.zip")
    for location in bundles_locations:
        url = f"{attachments_base_url}/{location}"
        path = f"attachments/{location}"
        hash, size = fetch_and_hash(url)
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
        tag_name = f"{GIT_REF_PREFIX}timestamps/common/{monitor_changeset['timestamp']}"
        try:
            repo.create_tag(
                tag_name,
                commit_oid,
                pygit2.GIT_OBJECT_COMMIT,
                author,
                f"Common branch content @ {monitor_changeset['timestamp']}",
            )
            print(f"Created tag common: {tag_name}")
            created_tags.append(tag_name)
        except pygit2.AlreadyExistsError:
            print(f"Tag {tag_name} already exists, skipping.")

    print("")
    for changeset in all_changesets:
        bid = changeset["metadata"]["bucket"]
        cid = changeset["metadata"]["id"]
        timestamp = changeset["timestamp"]
        refname = f"refs/heads/{GIT_REF_PREFIX}buckets/{bid}"
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
            print(f"Created commit {bid}/{cid}@{timestamp}: {commit_oid}")
            changed_branches.add(refname)

            # Tag the commit with the timestamp for traceability. If it already
            # exists, ignore the error (idempotent tagging behavior).
            tag_name = f"{GIT_REF_PREFIX}timestamps/{bid}/{cid}/{timestamp}"
            try:
                repo.create_tag(
                    tag_name,
                    commit_oid,
                    pygit2.GIT_OBJECT_COMMIT,
                    author,
                    f"{bid}/{cid}/{timestamp}",
                )
                print(f"Created tag {tag_name}")
                created_tags.append(tag_name)
            except pygit2.AlreadyExistsError:  # pragma: no cover
                print(f"Tag {tag_name} already exists, skipping.")

    return changed_attachments, changed_branches, created_tags
