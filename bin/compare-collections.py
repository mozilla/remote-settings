"""
Show the records differences between the staging, preview and published
versions of a collection.

Usage:

    SERVER=https://remote-settings.mozilla.org/v1 AUTH="Bearer abc" \
        python bin/compare-collections.py security-state/onecrl
"""

import os
import sys

from kinto_http import Client
from kinto_http.utils import collection_diff


SERVER = os.getenv("SERVER", "https://remote-settings.mozilla.org/v1")
AUTH = os.getenv("AUTH")


def main(bid_cid):
    bid, cid = bid_cid.split("/")
    client = Client(server_url=SERVER, auth=AUTH)

    buckets = {
        "main": ("main-workspace", "main-preview", "main"),
        "security-state": ("security-state-staging", "security-state-preview", "security-state"),
        "blocklists": ("blocklists-staging", "blocklists-preview", "blocklists"),
    }[bid]

    records = {}
    for bucket in buckets:
        records[bucket] = client.get_records(bucket=bucket, collection=cid)
        print(f"{bucket}/{cid}: {len(records[bucket])} records")

    for src, dest in zip(buckets, buckets[1:]):
        to_create, to_update, to_delete = collection_diff(records[src], records[dest])
        print(f"\n## {src} vs {dest}")
        if not (to_create or to_update or to_delete):
            print("Identical")
            continue
        for r in to_create:
            print(f"+ {r['id']} (only in {src})")
        for r in to_delete:
            print(f"- {r['id']} (only in {dest})")
        for old, new in to_update:
            print(f"~ {new['id']}")
            for field in sorted((set(old) | set(new)) - {"last_modified", "schema"}):
                if old.get(field) != new.get(field):
                    print(f"    {field}: {old.get(field)!r} -> {new.get(field)!r}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])
