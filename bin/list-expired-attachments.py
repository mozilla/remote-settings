import asyncio
import datetime
import os
from collections import Counter

from google.cloud import storage


ENV = os.getenv("ENV", "prod").lower()
AUTH = os.getenv("AUTH")
REALMS = {
    "dev": "nonprod",
    "stage": "nonprod",
    "prod": "prod",
}
STORAGE_BUCKET_NAME = os.getenv(
    "STORAGE_BUCKET_NAME", f"remote-settings-{REALMS[ENV]}-{ENV}-attachments"
)


def month_key(dt):
    return dt.strftime("%Y-%m")


async def main() -> None:
    print("Checking GCS for deletion marks...")
    storage_client = storage.Client()
    bucket = storage_client.bucket(STORAGE_BUCKET_NAME)

    marked_for_deletion = set()
    month_counts: Counter[str] = Counter()

    weird = set()
    utcnow = datetime.datetime.now(datetime.UTC)
    for blob in bucket.list_blobs():
        if blob.custom_time is not None:
            marked_for_deletion.add(blob.name)
            month_counts[month_key(blob.custom_time)] += 1
            if blob.custom_time > utcnow:
                weird.add(blob.name)

    if not month_counts:
        print("No attachments are marked for deletion in GCS.")
        return

    for month in sorted(month_counts):
        print(f"{month}: {month_counts[month]}")

    total = sum(month_counts.values())
    print(f"\nTotal marked for deletion: {total}")

    print(weird)


if __name__ == "__main__":
    asyncio.run(main())
