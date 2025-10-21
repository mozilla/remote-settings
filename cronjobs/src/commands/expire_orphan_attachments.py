import os

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


def expire_orphan_attachments(event, context):
    """
    This cronjob will release holds on orphan attachments.
    See https://cloud.google.com/storage/docs/holding-objects
    And then GCS will start the count down, and when the retention
    period is over, it will soft-delete them.

    Our `git_export` job will then also query GCS objects in order
    to purge files from the tree that 404s on the server.
    """
    client = KintoClient(server_url=SERVER)
    all_changesets = fetch_all_changesets(client)

    attachments = set()
    for changeset in all_changesets:
        for record in changeset["changes"]:
            if attachments_info := record.get("attachment"):
                attachments.add(attachments_info["location"])

    storage_client = storage.Client()
    bucket = storage_client.bucket(STORAGE_BUCKET_NAME)

    if not bucket.default_event_based_hold:
        print(f"Default event-based hold is not enabled for {bucket.name}")
        return

    blobs = bucket.list_blobs()  # Recursive by default
    for blob in blobs:
        if blob.name in attachments:
            continue  # This attachment is still referenced.

        # Skip "directory placeholders" (zero-length folder markers)
        if blob.name.endswith("/"):
            continue

        if not blob.event_based_hold:
            if VERBOSE:
                print(f"{blob.name} has already been released from event-based hold")
            continue

        if DRY_RUN:
            print(
                f"[DRY RUN] Would mark orphan attachment gs://{STORAGE_BUCKET_NAME}/{blob.name} for deletion"
            )
            continue

        print(
            f"Marking orphan attachment gs://{STORAGE_BUCKET_NAME}/{blob.name} for deletion"
        )
        blob.event_based_hold = False
        blob.patch()
