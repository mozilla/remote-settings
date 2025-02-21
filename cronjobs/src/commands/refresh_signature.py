import os
from datetime import datetime, timezone

from kinto_http import KintoException

from . import KintoClient as Client


class RefreshError(Exception):
    pass


def timestamp_to_date(timestamp_milliseconds):
    timestamp_seconds = int(timestamp_milliseconds) / 1000
    return datetime.utcfromtimestamp(timestamp_seconds).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


def utcnow():
    return datetime.now(timezone.utc)


def get_signed_source(server_info, change):
    # Small helper to identify the source collection from a potential
    # signing destination collection, like those mentioned in the changes endpoint
    # (eg. blocklists/plugins -> staging/plugins).
    signed_resources = server_info["capabilities"]["signer"]["resources"]
    for r in signed_resources:
        match_destination = r["destination"]["bucket"] == change["bucket"] and (
            r["destination"]["collection"] is None
            or r["destination"]["collection"] == change["collection"]
        )
        if match_destination:
            return {
                "bucket": r["source"]["bucket"],
                # Per-bucket configuration.
                "collection": r["source"]["collection"] or change["collection"],
            }


def refresh_signature(event, context, **kwargs):
    """Refresh the signatures of each collection."""
    server_url = event["server"]
    auth = event.get("refresh_signature_auth") or os.getenv("REFRESH_SIGNATURE_AUTH")
    max_signature_age = int(
        event.get("max_signature_age", os.getenv("MAX_SIGNATURE_AGE", 7))
    )

    # Look at the collections in the changes endpoint.
    bucket = event.get("bucket", "monitor")
    collection = event.get("collection", "changes")
    client = Client(server_url=server_url, bucket=bucket, collection=collection)
    print("Looking at %s: " % client.get_endpoint("collection"))
    changes = client.get_records()

    # Look at the signer configuration on the server.
    server_info = client.server_info()

    errors = []

    for change in changes:
        # 0. Figure out which was the source collection of this signed collection.
        source = get_signed_source(server_info, change)
        if source is None:
            # Skip if change is no kinto-signer destination (eg. review collection)
            continue

        client = Client(
            server_url=server_url,
            bucket=source["bucket"],
            collection=source["collection"],
            auth=auth,
        )

        try:
            print("Looking at %s:" % client.get_endpoint("collection"), end=" ")

            # 1. Grab collection information
            collection_metadata = client.get_collection()["data"]
            last_modified = collection_metadata["last_modified"]
            status = collection_metadata.get("status")
            last_signature_date = collection_metadata.get("last_signature_date")

            # Skip signature refresh if the collection was signed recently.
            if last_signature_date:
                last_signature_dt = datetime.fromisoformat(last_signature_date)
                last_signature_age = (utcnow() - last_signature_dt).days
                if last_signature_age < max_signature_age:
                    print("SKIP (only %s days old)" % last_signature_age)
                    continue

            # 2. Refresh!
            print("Refresh signature: ", end="")
            new_metadata = client.patch_collection(data={"status": "to-resign"})
            last_modified = new_metadata["data"]["last_modified"]

            # 3. Display the status of the collection
            last_modified_dt = timestamp_to_date(last_modified)
            print("status=", status, "at", last_modified_dt, "(", last_modified, ")")

        except KintoException as e:
            print(e)
            errors.append(e)

    if len(errors) > 0:
        error_messages = [str(e) for e in errors]
        raise RefreshError("\n" + "\n\n".join(error_messages))
