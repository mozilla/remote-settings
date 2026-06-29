"""
This command will iterate through the collections where Compression Dictionary Transport
is enabled, and create compressed files for the latest attachments.
It then uploads these `.zst` files to Google Cloud Storage.
"""

import os
import tempfile
from pathlib import Path

from compression.zstd import ZstdCompressor, ZstdDict
from google.cloud import storage

from . import KintoClient, fetch_all_changesets


ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
REALM = os.getenv("REALM", "test")
SERVER = os.getenv("SERVER")
STORAGE_BUCKET_NAME_DICTS = os.getenv(
    "STORAGE_BUCKET_NAME_DICTS",
    f"remote-settings-{REALM}-{ENVIRONMENT}-compression-dictionaries",
)
STORAGE_BUCKET_NAME_ATTACHMENTS = os.getenv(
    "STORAGE_BUCKET_NAME_ATTACHMENTS",
    f"remote-settings-{REALM}-{ENVIRONMENT}-attachments",
)
DESTINATION_FOLDER = os.getenv("DESTINATION_FOLDER", "cdt")
# Flags for local development
SKIP_UPLOAD = os.getenv("SKIP_UPLOAD", "0") in "1yY"

PAIRS_COUNT = int(os.getenv("PAIRS_COUNT", "5"))


def compressed_filename(bid, cid, old, new):
    old_stem = Path(old).stem
    new_stem = Path(new).stem
    # /cdt/{bid}/{cid}/compressed/target-{new}/dcz/from-{old}.dcz"
    return f"{DESTINATION_FOLDER}/{bid}/{cid}/compressed/target-{new_stem}/dcz/from-{old_stem}.dcz"


def build_compression_dictionaries():
    """
    This command:
    - fetches all collections changesets
    - lists collections where compression-dictionaries are enabled
    - iterates all attachments on GCS and link them to records
    - builds the list of missing compressed dictionaries
    - fetches files from GCS, compress the latest using the N previous as dictionary
    - uploads the files to GCS
    """
    # Build list of records with attachments for the
    # collections where compression dictionaries are enabled.
    kinto_client = KintoClient(server_url=SERVER)
    latest_attachment_by_bid_cid_rid: dict[tuple[str, str], dict[str, str]] = {}
    workspace_changesets = fetch_all_changesets(
        kinto_client, with_workspace_buckets=True, with_preview_destination=False
    )
    for changeset in workspace_changesets:
        if "compression-dictionaries" not in changeset["metadata"].get("flags", []):
            continue

        bid = changeset["metadata"]["bucket"]
        cid = changeset["metadata"]["id"]
        for r in changeset["changes"]:
            rid = r["id"]
            if "attachment" in r:
                latest_attachment_by_bid_cid_rid.setdefault((bid, cid), {})[rid] = r[
                    "attachment"
                ]["location"]

    # Build list of GCS attachments for these records.
    gcs_client = storage.Client()
    dicts_bucket = gcs_client.bucket(STORAGE_BUCKET_NAME_DICTS)
    attachments_bucket = gcs_client.bucket(STORAGE_BUCKET_NAME_ATTACHMENTS)

    all_attachments_by_bid_cid_rid: dict[tuple[str, str], dict[str, list[str]]] = {}
    for (bid, cid), records in latest_attachment_by_bid_cid_rid.items():
        folder = f"{bid}/{cid}/"
        blobs = gcs_client.list_blobs(STORAGE_BUCKET_NAME_ATTACHMENTS, prefix=folder)
        for blob in blobs:
            filename = blob.name
            # Extract {rid} from filename using pattern {{ datetime }}--{{ rid }}--{{ filename }}
            fileparts = filename.split("--")
            if len(fileparts) != 3:
                # We don't support attachments that were uploaded before
                # this change: https://github.com/mozilla/webservices-infra/pull/10827
                print(
                    f"{filename} filename format is not compatible with compression dictionaries"
                )
                continue
            _, rid, _ = fileparts
            if rid not in records:
                # This attachment belongs to a record that was deleted.
                continue
            # Keep all versions of the attachments related to this record (sorted).
            all_attachments_by_bid_cid_rid.setdefault((bid, cid), {}).setdefault(
                rid, []
            ).append(filename)

    # For each record, take the last N attachments, and check that the compression
    # dictionary exists.
    missing_dictionaries = []
    total_count = 0
    for (bid, cid), records in all_attachments_by_bid_cid_rid.items():
        for rid, filenames in records.items():
            if len(filenames) < 2:
                # No history for this record. We need at least 2 files.
                continue

            latest_filenames = sorted(filenames, reverse=True)
            new = latest_filenames[0]
            for old in latest_filenames[1:PAIRS_COUNT]:
                total_count += 1
                dict_name = compressed_filename(bid, cid, old, new)
                exists = storage.Blob(bucket=dicts_bucket, name=dict_name).exists(
                    client=gcs_client
                )
                if not exists:
                    missing_dictionaries.append((bid, cid, old, new))

    if not missing_dictionaries:
        print(f"Up-to-date ({total_count} existing dictionaries).")
        return

    # Now build all missing compression dictionaries.
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)
        for bid, cid, old, new in missing_dictionaries:
            old_tmp_path = tmp_dir / old
            old_tmp_path.parent.mkdir(parents=True, exist_ok=True)
            with open(old_tmp_path, "wb") as old_fd:
                storage.Blob(bucket=attachments_bucket, name=old).download_to_file(
                    old_fd, client=gcs_client
                )

            new_tmp_path = tmp_dir / new
            new_tmp_path.parent.mkdir(parents=True, exist_ok=True)
            with open(new_tmp_path, "wb") as new_fd:
                storage.Blob(bucket=attachments_bucket, name=new).download_to_file(
                    new_fd, client=gcs_client
                )

            with (
                open(old_tmp_path, "rb") as old_fd,
                open(new_tmp_path, "rb") as new_fd,
                tempfile.TemporaryFile() as compressed_fd,
            ):
                # Compress `new` using `old` as the compression dictionary.
                zdict = ZstdDict(old_fd.read())
                zcomp = ZstdCompressor(zstd_dict=zdict)
                zcomp.copy_stream(new_fd, compressed_fd)
                compressed_fd.seek(0)

                dest_name = compressed_filename(bid, cid, old, new)
                if SKIP_UPLOAD:
                    print(f"[skip] Upload to {dest_name}")
                else:
                    storage.Blob(bucket=dicts_bucket, name=dest_name).upload_from_file(
                        compressed_fd,
                        content_type="application/zstd",
                        client=gcs_client,
                    )
