import asyncio
import hashlib
import json
import urllib

import kinto_http
import pygit2
import requests
from decouple import config


MAX_PARALLEL_REQUESTS = config("MAX_PARALLEL_REQUESTS", default=10, cast=int)
LOG_LEVEL = config("LOG_LEVEL", default="INFO").upper()

SERVER_URL = config("SERVER", default="http://localhost:8888/v1")
GIT_AUTHOR = config("GIT_AUTHOR", default="User <user@example.com>")
OUTPUT_FOLDER = config(
    "OUTPUT", default="/tmp/git-export.git"
)  # TODO: replace with clone --bare of existing repo


def git_export(event, context):
    asyncio.run(poc_git_export())
    # TODO: clone existing repo instead of init
    # TODO: use PGP key to sign commits
    # TODO: use SSH key to authenticate with remote
    # TODO: push to remote
    # TODO: download attachments actual files and add them to LFS volume


async def fetch_all_changesets(client: kinto_http.AsyncClient):
    monitor_changeset = await client.get_changeset(
        bucket="monitor", collection="changes", bust_cache=True
    )

    sem = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)

    async def fetch(entry):
        async with sem:
            print("Fetching %s/%s" % (entry["bucket"], entry["collection"]))
            return await client.get_changeset(
                bucket=entry["bucket"], collection=entry["collection"], bust_cache=True
            )

    return monitor_changeset, await asyncio.gather(
        *[fetch(entry) for entry in monitor_changeset["changes"]]
    )


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


def make_lfs_pointer_blob(
    repo: pygit2.Repository, sha256_hex: str, size: int
) -> pygit2.Oid:
    """
    Create a Git LFS pointer blob with the given object id and size.
    """
    pointer = (
        "version https://git-lfs.github.com/spec/v1\n"
        f"oid sha256:{sha256_hex}\n"
        f"size {size}\n"
    )
    return repo.create_blob(pointer.encode("ascii"))


def fetch_attachment(url):
    """
    Fetch the attachment at the given URL and return its sha256 hash and size.
    """
    print("Fetch %r" % url)
    resp = requests.get(url)
    resp.raise_for_status()
    h = hashlib.sha256()
    total = 0
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        for chunk in r.iter_content(1024 * 64):
            if not chunk:
                continue
            h.update(chunk)
            total += len(chunk)
    return h.hexdigest(), total


async def poc_git_export():
    client = kinto_http.AsyncClient(server_url=SERVER_URL)

    attachments_base_url = (await client.server_info())["capabilities"]["attachments"][
        "base_url"
    ].rstrip("/")

    monitor_changeset, all_changesets = await fetch_all_changesets(client)

    user, email = GIT_AUTHOR.split("<")
    user = user.strip()
    email = email.rstrip(">")
    author = pygit2.Signature(user, email)
    committer = author

    common_branch = "refs/heads/common"
    repo = pygit2.init_repository(OUTPUT_FOLDER, bare=True, initial_head=common_branch)

    for changeset in all_changesets:
        bid = changeset["metadata"]["bucket"]
        cid = changeset["metadata"]["id"]
        timestamp = changeset["timestamp"]
        refname = f"refs/heads/buckets/{bid}"
        commit_message = f"{bid}/{cid}@{timestamp}"

        # Find the bucket branch (changesets are not ordered by bucket)
        try:
            common_tip = repo.lookup_reference(refname).target
            base_tree = repo.get(common_tip).tree
            parents = [common_tip]
        except KeyError:
            base_tree = None
            parents = []

        # Create one blob per record. We start a new tree for this collection
        # anything from previous commits is lost.
        files_builder = repo.TreeBuilder()
        blob_id = repo.create_blob(
            json.dumps(changeset["metadata"], sort_keys=True).encode("utf-8")
        )
        files_builder.insert("metadata.json", blob_id, pygit2.GIT_FILEMODE_BLOB)

        records = sorted(changeset["changes"], key=lambda r: r["id"])
        for record in records:
            blob_id = repo.create_blob(
                json.dumps(record, sort_keys=True).encode("utf-8")
            )
            files_builder.insert(
                f"{record['id']}.json", blob_id, pygit2.GIT_FILEMODE_BLOB
            )
        files_tree_id = files_builder.write()

        # Check if it would change the branch snapshot
        is_new_branch = base_tree is None
        if is_new_branch:
            # Only happens on first run, for the first collection in the bucket.
            folder_builder = repo.TreeBuilder()
        else:
            folder_builder = repo.TreeBuilder(base_tree)
            if cid in base_tree:
                prev_oid = base_tree[cid].id
                if prev_oid == files_tree_id:
                    print(f"No changes for {bid}/{cid}, skipping commit.")
                    continue
                # Replace the previous collection folder with the new one.
                folder_builder.remove(cid)

        folder_builder.insert(cid, files_tree_id, pygit2.GIT_FILEMODE_TREE)
        folder_tree_id = folder_builder.write()

        # Commit and tag.
        commit_oid = repo.create_commit(
            refname, author, committer, commit_message, folder_tree_id, parents
        )
        print(f"Created commit {bid}/{cid} @ {timestamp}: {commit_oid}")
        tag_name = f"timestamps/{bid}/{cid}/{timestamp}"
        repo.create_tag(
            tag_name,
            commit_oid,
            pygit2.GIT_OBJECT_COMMIT,
            author,
            f"{bid}/{cid}/{timestamp}",
        )

    # Store the monitor changeset in `common` branch.
    # Anything from previous commits is lost.
    common_builder = repo.TreeBuilder()
    blob_id = repo.create_blob(
        json.dumps(monitor_changeset, sort_keys=True).encode("utf-8")
    )
    common_builder.insert("monitor-changes.json", blob_id, pygit2.GIT_FILEMODE_BLOB)

    # Store the broadcast version in `common` branch.
    print("Fetching broadcasts content")
    resp = requests.get(f"{SERVER_URL}/__broadcasts__")
    resp.raise_for_status()
    broadcasts = resp.json()
    blob_id = repo.create_blob(
        json.dumps(broadcasts, sort_keys=True).encode("utf-8")
    )
    common_builder.insert("broadcasts.json", blob_id, pygit2.GIT_FILEMODE_BLOB)

    # Store the certificate chains. Anything from previous commits is lost.
    x5u_builder = repo.TreeBuilder()
    for url, pem in fetch_all_cert_chains(client, all_changesets):
        parsed = urllib.parse.urlparse(url)
        filename = parsed.path.lstrip("/").replace("/", "--")  # TODO: better with folders
        blob_id = repo.create_blob(pem.encode("utf-8"))
        x5u_builder.insert(filename, blob_id, pygit2.GIT_FILEMODE_BLOB)
    x5u_tree_id = x5u_builder.write()
    common_builder.insert("cert-chains", x5u_tree_id, pygit2.GIT_FILEMODE_TREE)

    # Store all the attachments as LFS pointers.
    with_attachments = []
    for changeset in all_changesets:
        for record in changeset["changes"]:
            if "attachment" not in record:
                continue
            with_attachments.append(record)
    attachments_builder = repo.TreeBuilder()
    for record in with_attachments:
        attachment = record["attachment"]
        location = attachment["location"]
        filename = location.replace("/", "--")  # TODO: better with folders
        # Attachment as LFS pointer.
        blob_id = make_lfs_pointer_blob(repo, attachment["hash"], attachment["size"])
        attachments_builder.insert(filename, blob_id, pygit2.GIT_FILEMODE_BLOB)
        # Record attributes.
        blob_id = repo.create_blob(json.dumps(record, sort_keys=True).encode("utf-8"))
        attachments_builder.insert(
            f"{filename}.meta.json", blob_id, pygit2.GIT_FILEMODE_BLOB
        )

    # Also store the bundles as LFS pointers.
    bundles_locations = []
    bundles_locations.append(f"bundles/startup.json.mozlz4")
    for changeset in all_changesets:
        if not changeset["metadata"].get("bundles", False):
            continue
        metadata = changeset["metadata"]
        bundles_locations.append(f"bundles/{metadata['bucket']}--{metadata['collection']}.zip")
    for location in bundles_locations:
        url = attachments_base_url + "/" + location
        hash, size = fetch_attachment(url)
        blob_id = make_lfs_pointer_blob(repo, hash, size)
        attachments_builder.insert(location.replace("/", "--"), blob_id, pygit2.GIT_FILEMODE_BLOB)

    attrachments_tree_id = attachments_builder.write()

    common_builder.insert("attachments", attrachments_tree_id, pygit2.GIT_FILEMODE_TREE)

    # Create .gitattributes file to mark attachments/ as LFS
    blob_id = repo.create_blob(b"attachments/** filter=lfs diff=lfs merge=lfs -text\n")
    common_builder.insert(".gitattributes", blob_id, pygit2.GIT_FILEMODE_BLOB)

    monitor_tree_id = common_builder.write()

    # Find the common branch tip
    try:
        common_tip = repo.lookup_reference(common_branch).target
        parents = [common_tip]
    except KeyError:
        parents = []
    commit_oid = repo.create_commit(
        common_branch,
        author,
        committer,
        "Add monitor-changes and x5u certificate chains",
        monitor_tree_id,
        parents,
    )
    print(f"Created commit common: {commit_oid}")
