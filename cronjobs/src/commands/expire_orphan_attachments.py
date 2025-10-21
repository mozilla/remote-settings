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


def expire_orphan_attachments(event, context):
    """
    This cronjob will mark all orphan attachments for deletion, using the
    `custom_time` field in GCS objects.

    We then have a Lifecycle Management rule in GCS that will actually delete
    files N days after they are marked.
    Our `git_export` job will also query GCS objects' `x-goog-meta-custom-time`
    in order to purge files from the tree.
    """
    client = KintoClient(server_url=SERVER)
    all_changesets = fetch_all_changesets(client)

    attachments = set()
    for changeset in all_changesets:
        for record in changeset["changes"]:
            if attachments_info := record.get("attachment"):
                attachments.add(attachments_info["location"])

    current_time = datetime.now(timezone.utc)

    storage_client = storage.Client()
    bucket = storage_client.bucket(STORAGE_BUCKET_NAME)
    blobs = bucket.list_blobs()  # Recursive by default
    for blob in blobs:
        if blob.name in attachments:
            continue  # This attachment is still referenced.

        # Skip "directory placeholders" (zero-length folder markers)
        if blob.name.endswith("/"):
            continue

        if blob.custom_time:
            if VERBOSE:
                print(
                    f"{blob.name} is already marked for deletion (age: {blob.custom_time})."
                )
            continue

        if DRY_RUN:
            print(
                f"[DRY RUN] Would mark orphan attachment gs://{STORAGE_BUCKET_NAME}/{blob.name} for deletion"
            )
            continue

        print(
            f"Marking orphan attachment gs://{STORAGE_BUCKET_NAME}/{blob.name} for deletion"
        )
        blob.custom_time = current_time
        blob.patch()
