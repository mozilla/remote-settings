"""
This command will iterate through the collections where Compression Dictionary Transport
is enabled, and create compressed files for the latest attachments.
It then uploads these `.dcz` files to Google Cloud Storage.
"""

import os
import tempfile
import typing
from compression.zstd import ZstdCompressor, ZstdDict
from pathlib import Path

from google.cloud import storage
from kinto_http.utils import Iterable

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

PREVIOUS_VERSIONS_COUNT = int(os.getenv("PREVIOUS_VERSIONS_COUNT", "5"))


def records_to_compress(
    changesets: list[dict[str, typing.Any]],
) -> list[tuple[str, str, list[str]]]:
    to_compress: list[tuple[str, str, list[str]]] = []
    for changeset in changesets:
        if "compression-dictionaries" not in changeset["metadata"].get("flags", []):
            continue
        bid = changeset["metadata"]["bucket"]
        cid = changeset["metadata"]["id"]
        rids = []
        for r in changeset["changes"]:
            if "attachment" in r:
                rids.append(r["id"])
        if rids:
            to_compress.append((bid, cid, rids))
    return to_compress


def scan_existing_attachments(
    bucket: storage.Bucket, collections: list[tuple[str, str, list[str]]]
) -> typing.Generator[tuple[str, str, list[str]]]:
    for bid, cid, records in collections:
        folder = f"{bid}/{cid}/"
        filenames_by_rid = {}
        blobs = bucket.list_blobs(prefix=folder)
        for blob in blobs:
            filename = blob.name
            # Extract {rid} from filename using pattern {{ datetime }}--{{ rid }}--{{ filename }}
            try:
                _, rid, _ = filename.split("--", maxsplit=2)
            except ValueError:
                print(
                    f"{filename} filename format is not compatible with compression dictionaries",
                    # We don't support attachments that were uploaded before
                    # this change: https://github.com/mozilla/webservices-infra/pull/10827
                )
                continue
            if rid not in records:
                # This attachment belongs to a record that was deleted.
                continue
            filenames_by_rid.setdefault(rid, []).append(filename)

        for filenames in filenames_by_rid.values():
            yield bid, cid, filenames


def find_missing_compressed_files(
    client: storage.Client,
    bucket: storage.Bucket,
    pairs: Iterable[tuple[str, str, str, str]],
) -> list[tuple[str, str, str, str]]:
    missing: list[tuple[str, str, str, str]] = []
    for bid, cid, old, new in pairs:
        dict_name = compressed_filename(bid, cid, old, new)
        exists = storage.Blob(bucket=bucket, name=dict_name).exists(client=client)
        if not exists:
            print(f"{dict_name} is missing from GCS.")
            missing.append((bid, cid, old, new))
    return missing


def compressed_filename(bid, cid, old, new):
    old_stem = Path(old).stem
    new_stem = Path(new).stem
    # /cdt/{bid}/{cid}/compressed/target-{new}/dcz/from-{old}.dcz"
    return f"{DESTINATION_FOLDER}/{bid}/{cid}/compressed/target-{new_stem}/dcz/from-{old_stem}.dcz"


def download_blob_to_file(
    client: storage.Client, bucket: storage.Bucket, blobname: str, path: Path
):
    print(f"Download {blobname} into {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fd:
        storage.Blob(bucket=bucket, name=blobname).download_to_file(fd, client=client)


def zstd_compress(dict_path: Path, file_path: Path, destination: typing.IO):
    print(f"Compress {file_path} using {dict_path} as dictionary")
    with (
        open(dict_path, "rb") as dict_fd,
        open(file_path, "rb") as file_fd,
    ):
        zdict = ZstdDict(dict_fd.read(), is_raw=True)
        zcomp = ZstdCompressor(zstd_dict=zdict)
        while chunk := file_fd.read(8192):
            destination.write(zcomp.compress(chunk))
        destination.write(zcomp.flush())


def build_compression_dictionaries():
    """
    Builds and publishes compressed attachments for the collections
    where compression dictionaries are enabled.

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
    workspace_changesets = fetch_all_changesets(
        kinto_client, with_workspace_buckets=True, with_preview_destination=False
    )
    to_compress = records_to_compress(workspace_changesets)

    gcs_client = storage.Client()
    dicts_bucket = gcs_client.bucket(STORAGE_BUCKET_NAME_DICTS)
    attachments_bucket = gcs_client.bucket(STORAGE_BUCKET_NAME_ATTACHMENTS)

    # Build list of all GCS attachments for these records.
    # We could rely on collection history, but scanning GCS to
    # look for all previous attachments of a record is simpler.
    all_files = scan_existing_attachments(attachments_bucket, to_compress)

    # Iterate each attachment and its previous versions.
    all_pairs = []
    for bid, cid, filenames in all_files:
        if len(filenames) < 2:
            # No history for this record. We need at least 2 files.
            continue
        # For each record, take the last N attachments
        latest_filenames = sorted(filenames, reverse=True)
        new = latest_filenames[0]
        for old in latest_filenames[1 : PREVIOUS_VERSIONS_COUNT + 1]:
            all_pairs.append((bid, cid, old, new))

    # Query the compression-dictionaries GCS bucket to see which are missing.
    missing_dictionaries = find_missing_compressed_files(
        gcs_client, dicts_bucket, all_pairs
    )

    if not missing_dictionaries:
        print(f"Up-to-date ({len(all_pairs)} existing compressed files).")
        return
    else:
        print(f"{len(missing_dictionaries)} files to compress.")

    # Now build all missing compression dictionaries, and upload them.
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)

        for bid, cid, old, new in missing_dictionaries:
            # Download actual files from attachments bucket.
            old_tmp_path = tmp_dir / old
            download_blob_to_file(gcs_client, attachments_bucket, old, old_tmp_path)
            new_tmp_path = tmp_dir / new
            download_blob_to_file(gcs_client, attachments_bucket, new, new_tmp_path)

            dest_name = compressed_filename(bid, cid, old, new)
            with tempfile.TemporaryFile() as compressed_fd:
                # Compress `new` using `old` as the compression dictionary.
                zstd_compress(
                    dict_path=old_tmp_path,
                    file_path=new_tmp_path,
                    destination=compressed_fd,
                )

                # Upload result to compression-dictionaries bucket.
                if SKIP_UPLOAD:
                    print(f"[skip] Upload to {dest_name}")
                else:
                    print(f"Upload {dest_name}...")
                    compressed_fd.seek(0)
                    storage.Blob(bucket=dicts_bucket, name=dest_name).upload_from_file(
                        compressed_fd,
                        content_type="application/zstd",
                        client=gcs_client,
                    )
