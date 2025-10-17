import os
from datetime import datetime, timedelta, timezone

from decouple import config
from google.cloud import storage

from . import KintoClient, fetch_all_changesets


SERVER = config("SERVER", default="http://localhost:8888/v1")
DRY_RUN = config("DRY_RUN", default=False, cast=bool)
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
REALM = os.getenv("REALM", "test")
STORAGE_BUCKET_NAME = os.getenv(
    "STORAGE_BUCKET_NAME", f"remote-settings-{REALM}-{ENVIRONMENT}-attachments"
)
DELTA_DAYS = config("DELTA_DAYS", default=365, cast=int)


def delete_older_files(bucket_name: str, folders: dict[str, datetime]):
    """
    Recursively deletes all files older than the given datetime from the specified
    folders in a GCS bucket.

    @param bucket_name (str): Name of the GCS bucket.
    @param folders (list[str]): List of folder prefixes (e.g., ['main-workspace/world/', 'security-state/intermediates']).
    @param cutoff_datetime (datetime): Datetime threshold — files older than this are deleted.
    """
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    freed_mb = 0.0

    for folder, cutoff_datetime in folders.items():
        blobs = bucket.list_blobs(prefix=folder)  # Recursive by default
        deleted_count = 0
        checked_count = 0

        for blob in blobs:
            checked_count += 1
            # Skip "directory placeholders" (zero-length folder markers)
            if blob.name.endswith("/"):
                continue

            if blob.updated < cutoff_datetime:
                if not DRY_RUN:
                    print(
                        f"Deleting gs://{bucket_name}/{blob.name} (last updated: {blob.updated})"
                    )
                    blob.delete()
                deleted_count += 1
                freed_mb += blob.size / (1024 * 1024)
        print(f"Finished folder '{folder}': {deleted_count}/{checked_count} deleted.")

    print(f"Total space freed: {freed_mb:.2f} MB")


def purge_old_attachments(event, context):
    """
    Purge old files from Google Cloud Storage, older than 1 year than the
    oldest record in each collection by default (see `DELTA_DAYS`).
    """
    client = KintoClient(server_url=SERVER)
    all_changesets = fetch_all_changesets(client)

    folders: dict[str, datetime] = {}
    for changeset in all_changesets:
        if not changeset["changes"]:
            continue
        # Oldest record's last_modified in the changeset.
        oldest_timestamp = changeset["changes"][-1]["last_modified"]
        oldest_datetime = datetime.fromtimestamp(
            oldest_timestamp / 1000, tz=timezone.utc
        )
        # Delete files 1 year older than the oldest record.
        # We don't even try to be smart, to look at attachments etc.
        cutoff_datetime = oldest_datetime - timedelta(days=DELTA_DAYS)
        # Attachments use workspace bucket as parent folder.
        bid = {
            "main": "main-workspace",
            "security-state": "security-state-staging",
            "blocklists": "staging",
        }[changeset["metadata"]["bucket"]]
        cid = changeset["metadata"]["id"]
        folders[f"{bid}/{cid}/"] = cutoff_datetime

    delete_older_files(STORAGE_BUCKET_NAME, folders)
