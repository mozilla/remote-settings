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

    preview_buckets = {
        "main-workspace": "main-preview",
        "security-state-staging": "security-state-preview",
        "staging": "blocklists-preview",
    }
    # do not bother intropsecting server info here...
    without_preview_collection = ["addons-bloomfilters"]

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

    only_workspace_attachments = all_workspace_attachments - all_preview_attachments
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

    storage_client = storage.Client()
    bucket = storage_client.bucket(STORAGE_BUCKET_NAME)
    to_remove_mark = []
    for blob in bucket.list_blobs():
        if not only_workspace_attachments:
            break
        if blob.name not in only_workspace_attachments:
            continue
        only_workspace_attachments.remove(blob.name)
        if blob.custom_time is not None:
            print(
                f"⚠️ Blob gs://{STORAGE_BUCKET_NAME}/{blob.name} is marked for deletion at {blob.custom_time}"
            )
            to_remove_mark.append(blob.name)
        else:
            print(
                f"✅ Blob gs://{STORAGE_BUCKET_NAME}/{blob.name} is NOT marked for deletion"
            )

    with storage_client.batch():
        for blob_name in to_remove_mark:
            blob = bucket.blob(blob_name)
            # Once set, custom_time cannot be removed. We set it to date in the future.
            blob.custom_time = datetime.datetime.now(
                datetime.timezone.utc
            ) + datetime.timedelta(days=365)
            blob.patch()
            print(f"Removed deletion mark of gs://{STORAGE_BUCKET_NAME}/{blob.name}")


if __name__ == "__main__":
    asyncio.run(main())
