"""
This script will list all attachments that are only referenced in workspace
buckets, and check if they are missing from the server. It will also check if they are marked
for deletion in the GCS bucket, and if so, it will set the deletion mark in the future.

Context: https://mozilla-hub.atlassian.net/browse/RMST-281
"""

import asyncio
import datetime
import itertools
import os

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


async def main():
    client = kinto_http.AsyncClient(server_url=SERVER_URL, auth=AUTH)

    # Fetch all changesets of all workspace buckets.
    bucket_ids = ["main-workspace", "security-state-staging", "staging"]
    results = await asyncio.gather(
        *(fetch_collections(client, bid) for bid in bucket_ids)
    )
    all_collections = list(itertools.chain.from_iterable(results))
    print(len(all_collections), "collections to analyze")

    # List all attachments in workspace buckets.
    all_workspace_records = await asyncio.gather(
        *(
            client.get_records(bucket=bid, collection=cid)
            for bid, cid in all_collections
        )
    )
    all_workspace_attachments = set(
        [
            r["attachment"]["location"]
            for records in all_workspace_records
            for r in records
            if "attachment" in r
        ]
    )
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
    all_preview_records = await asyncio.gather(
        *(
            client.get_records(bucket=bid, collection=cid)
            for bid, cid in all_preview_collections
        )
    )
    all_preview_attachments = set(
        [
            r["attachment"]["location"]
            for records in all_preview_records
            for r in records
            if "attachment" in r
        ]
    )

    # Now list attachments in main buckets.
    main_buckets = {
        "main-workspace": "main",
        "security-state-staging": "security-state",
        "staging": "blocklists",
    }
    all_main_collections = [
        (main_buckets[bid], cid)
        for bid, cid in all_collections
        if cid not in without_preview_collection
    ]
    all_main_records = await asyncio.gather(
        *(
            client.get_records(bucket=bid, collection=cid)
            for bid, cid in all_main_collections
        )
    )
    all_main_attachments = set(
        [
            r["attachment"]["location"]
            for records in all_main_records
            for r in records
            if "attachment" in r
        ]
    )

    only_workspace_attachments = (
        all_workspace_attachments - all_preview_attachments - all_main_attachments
    )
    print(
        f"{len(only_workspace_attachments)} attachments are only referenced in workspace buckets"
    )

    # Check which of the only_workspace_attachments are missing from the server.
    server_info = await client.server_info()
    base_url = server_info["capabilities"]["attachments"]["base_url"]
    missing = await check_urls(
        [f"{base_url}{location}" for location in only_workspace_attachments]
    )
    print(f"{len(missing)} missing attachments found.")
    print("\n".join(missing))

    # Now check which GCS attachments are marked for deletion. And make sure that we do not
    # have attachments referenced in preview and main buckets that are marked for deletion.
    print("Checking GCS for deletion marks...")
    storage_client = storage.Client()
    bucket = storage_client.bucket(STORAGE_BUCKET_NAME)
    marked_for_deletion = set()
    for blob in bucket.list_blobs():
        if blob.custom_time is not None:
            marked_for_deletion.add(blob.name)
    print(f"{len(marked_for_deletion)} attachments are marked for deletion in GCS.")

    # Now check which of the only_workspace_attachments are marked for deletion.
    to_postpone_deletion = []
    for live_attachments in (
        all_workspace_attachments,
        all_preview_attachments,
        all_main_attachments,
    ):
        if marked := marked_for_deletion & live_attachments:
            to_postpone_deletion.extend(marked)

    if to_postpone_deletion:
        print(
            f"⚠️ {len(to_postpone_deletion)} attachments referenced in workspace/preview/main buckets are marked for deletion in GCS."
        )
        with storage_client.batch():
            for blob_name in to_postpone_deletion:
                blob = bucket.blob(blob_name)
                # Once set, custom_time cannot be removed. We set it to date in the future.
                blob.custom_time = datetime.datetime.now(
                    datetime.timezone.utc
                ) + datetime.timedelta(days=POSTPONE_DELETION_MARK_DAYS)
                blob.patch()
                print(
                    f"Postponed deletion mark of gs://{STORAGE_BUCKET_NAME}/{blob.name} to {blob.custom_time}"
                )
    else:
        print(
            "✅ No attachment referenced in workspace/preview/main buckets is marked for deletion in GCS."
        )


if __name__ == "__main__":
    asyncio.run(main())
