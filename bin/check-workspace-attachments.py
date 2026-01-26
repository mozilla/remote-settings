"""
This script will list all attachments that are only referenced in workspace
buckets, and check if they are missing from the server. It will also check if they are marked
for deletion in the GCS bucket, and if so, it will set the deletion mark in the future.

Context: https://mozilla-hub.atlassian.net/browse/RMST-281
"""

import asyncio
import itertools
import os
import tempfile

import kinto_http
import requests
from google.cloud import storage


ENV = os.getenv("ENV", "prod").lower()
SERVER_URL = {
    "prod": "https://remote-settings.mozilla.org/v1",
    "stage": "https://remote-settings.allizom.org/v1",
    "dev": "https://remote-settings-dev.allizom.org/v1",
    "local": "http://localhost:8888/v1",
}[ENV]
AUTH = os.getenv("AUTH")
REALMS = {
    "dev": "nonprod",
    "stage": "nonprod",
    "prod": "prod",
}
STORAGE_BUCKET_NAME = os.getenv(
    "STORAGE_BUCKET_NAME", f"remote-settings-{REALMS[ENV]}-{ENV}-attachments"
)
POSTPONE_DELETION_MARK_DAYS = int(os.getenv("POSTPONE_DELETION_MARK_DAYS", "365"))


async def fetch_collections(client, bid):
    """Fetch collections for a given bucket."""
    collections = await client.get_collections(bucket=bid)
    return [(bid, c["id"]) for c in collections]


async def check_urls(urls, max_concurrent=10):
    """Test fetching URLs in parallel with a limit on concurrency."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch(url):
        async with semaphore:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, requests.head, url)
            return response.status_code == 200

    tasks = [fetch(url) for url in urls]
    results = await asyncio.gather(*tasks)
    return [url for url, success in zip(urls, results) if not success]


def rewrite_from_scratch(bucket, blob_name):
    """
    Since GCS does not let us remove the `custom_time` field which
    is used in the retention policy rule, we rewrite the object from
    scratch.

    Note: `custom_time` is not overridable during `rewrite()`.
    """
    with tempfile.NamedTemporaryFile(dir="/tmp", delete=False) as tmp:
        tmp_path = tmp.name
    print(
        f"Rewrite gs://{STORAGE_BUCKET_NAME}/{blob_name} using backup at {tmp_path}",
        end=" ",
    )
    # Download
    blob = bucket.blob(blob_name)
    blob.download_to_filename(tmp_path)
    print(".", end="")
    # Delete all generations
    versions = bucket.list_blobs(prefix=blob_name, versions=True)
    print(".", end="")
    bucket.delete_blobs(list(versions))
    print(".", end="")
    # Re-upload (same object name, new generation)
    new_blob = bucket.blob(blob_name)
    new_blob.metadata = blob.metadata
    new_blob.content_type = blob.content_type
    new_blob.upload_from_filename(tmp_path)
    print(".", end="")
    new_blob.reload()
    assert new_blob.custom_time is None, (
        f"{blob_name} has custom time as {new_blob.custom_time}"
    )
    print(". Done.")


async def list_all_attachments(client, collections):
    records = await asyncio.gather(
        *(client.get_records(bucket=bid, collection=cid) for bid, cid in collections)
    )
    return set(
        [
            r["attachment"]["location"]
            for records in records
            for r in records
            if "attachment" in r
        ]
    )


async def main():
    client = kinto_http.AsyncClient(server_url=SERVER_URL, auth=AUTH)

    # Fetch all changesets of all workspace buckets.
    bucket_ids = ["main-workspace", "security-state-staging", "staging"]
    results = await asyncio.gather(
        *(fetch_collections(client, bid) for bid in bucket_ids)
    )
    all_collections = list(itertools.chain.from_iterable(results))
    print(len(all_collections), "collections to analyze")

    all_workspace_attachments = await list_all_attachments(client, all_collections)
    print(f"Found {len(all_workspace_attachments)} draft attachments in total")

    # Now list all attachments in preview buckets.
    preview_buckets = {
        "main-workspace": "main-preview",
        "security-state-staging": "security-state-preview",
        "staging": "blocklists-preview",
    }
    # do not bother intropsecting server info here...
    without_preview_collection = ["addons-bloomfilters"]
    all_preview_collections = [
        (preview_buckets[bid], cid)
        for bid, cid in all_collections
        if cid not in without_preview_collection
    ]
    all_preview_attachments = await list_all_attachments(
        client, all_preview_collections
    )

    # Now list attachments in main buckets.
    main_buckets = {
        "main-workspace": "main",
        "security-state-staging": "security-state",
        "staging": "blocklists",
    }
    all_main_collections = [(main_buckets[bid], cid) for bid, cid in all_collections]
    all_main_attachments = await list_all_attachments(client, all_main_collections)

    # Check which of the only_workspace_attachments are missing from the server.
    # We only check these since they are not checked by our Telescope attachments checks.
    only_workspace_attachments = (
        all_workspace_attachments - all_preview_attachments - all_main_attachments
    )
    print(
        f"{len(only_workspace_attachments)} attachments are only referenced in workspace buckets"
    )
    server_info = await client.server_info()
    base_url = server_info["capabilities"]["attachments"]["base_url"]
    missing = await check_urls(
        [f"{base_url}{location}" for location in only_workspace_attachments]
    )
    print(f"{len(missing)} missing attachments found.")
    print("\n".join(missing))

    # Now check which GCS attachments are marked for deletion. And make sure that we do not
    # have attachments referenced in buckets that are marked for deletion.
    print("Checking GCS for deletion marks...")
    storage_client = storage.Client()
    bucket = storage_client.bucket(STORAGE_BUCKET_NAME)
    marked_for_deletion = set()
    for blob in bucket.list_blobs():
        if blob.custom_time is not None:
            marked_for_deletion.add(blob.name)
    print(f"{len(marked_for_deletion)} attachments are marked for deletion in GCS.")

    # Now check which of the only_workspace_attachments are marked for deletion.
    to_reset = set()
    for live_attachments in (
        all_workspace_attachments,
        all_preview_attachments,
        all_main_attachments,
    ):
        if marked := (marked_for_deletion & live_attachments):
            to_reset.update(marked)

    if to_reset:
        print(
            f"⚠️ {len(to_reset)} attachments referenced in workspace/preview/main buckets are marked for deletion in GCS."
        )
        for blob_name in to_reset:
            rewrite_from_scratch(bucket, blob_name)
            print(f"Removed deletion mark of gs://{STORAGE_BUCKET_NAME}/{blob_name}")
    else:
        print(
            "✅ No attachment referenced in workspace/preview/main buckets is marked for deletion in GCS."
        )


if __name__ == "__main__":
    asyncio.run(main())
