import itertools
import os
from datetime import datetime, timezone

from decouple import config
from google.cloud import storage

from . import KintoClient, fetch_all_changesets


SERVER = config("SERVER", default="http://localhost:8888/v1")
DRY_RUN = config("DRY_RUN", default=False, cast=bool)
VERBOSE = config("VERBOSE", default=False, cast=bool)
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
REALM = os.getenv("REALM", "test")
STORAGE_BUCKET_NAME = os.getenv(
    "STORAGE_BUCKET_NAME", f"remote-settings-{REALM}-{ENVIRONMENT}-attachments"
)
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))
AUTH = os.getenv("AUTH")


def expire_orphan_attachments():
    """
    This cronjob will set the custom time field on orphaned attachments to the current time.
    We then have a retention policy on GCS bucket that will
    soft-delete these objects after N days.

    Our `git_export` job will then also query GCS objects in order
    to purge files from the tree that 404s on the server.
    """
    client = KintoClient(server_url=SERVER, auth=AUTH)
    all_changesets = fetch_all_changesets(client, with_workspace_buckets=True)

    attachments = set()
    total_size = 0
    for changeset in all_changesets:
        for record in changeset["changes"]:
            if attachments_info := record.get("attachment"):
                attachments.add(attachments_info["location"])
                total_size += attachments_info["size"]
    print(
        f"Found {len(attachments)} referenced attachments. Total size: {total_size / (1024 * 1024):.2f}MB"
    )

    storage_client = storage.Client()
    bucket = storage_client.bucket(STORAGE_BUCKET_NAME)

    to_update = []
    for blob in bucket.list_blobs():
        if blob.name in attachments or blob.name.startswith("bundles/"):
            continue
        if blob.custom_time is not None:
            if VERBOSE:
                print(
                    f"Skipping blob gs://{STORAGE_BUCKET_NAME}/{blob.name} already marked for deletion at {blob.custom_time}"
                )
            continue
        if DRY_RUN:
            print(
                f"[DRY RUN] Would mark orphan attachment gs://{STORAGE_BUCKET_NAME}/{blob.name} for deletion"
            )
        to_update.append(blob)
    print(f"Found {len(to_update)} orphan attachments to mark for deletion.")

    if DRY_RUN:
        return

    for chunk in itertools.batched(to_update, BATCH_SIZE):
        with storage_client.batch():
            for blob in chunk:
                print(
                    f"Marking orphan attachment gs://{STORAGE_BUCKET_NAME}/{blob.name} for deletion"
                )
                blob.custom_time = datetime.now(timezone.utc)
                blob.patch()
