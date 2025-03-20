import asyncio
import os
import re

import kinto_http


SERVER_URL = os.getenv("SERVER_URL", "https://firefox.settings.services.mozilla.com/v1")

client = kinto_http.AsyncClient(server_url=SERVER_URL)


async def fetch_collections(bucket_id):
    """Fetch collections for a given bucket."""
    collections = await client.get_collections(bucket=bucket_id)
    return [(bucket_id, c["id"]) for c in collections]


async def fetch_jexl_expressions(bucket_id, collection_id):
    """Fetch records for a given bucket and collection."""
    records = await client.get_records(bucket=bucket_id, collection=collection_id)
    return [
        record["filter_expression"]
        for record in records
        if record.get("filter_expression")  # filter empty strings
    ]


async def main():
    # """Main async function to fetch collections and records in parallel."""

    # Fetch all collections in parallel
    bucket_ids = ["main", "security-state", "blocklists"]
    all_collections = await asyncio.gather(
        *(fetch_collections(bid) for bid in bucket_ids)
    )

    # Flatten the list of collections
    all_collections = [item for sublist in all_collections for item in sublist]

    # Fetch all records in parallel
    all_expressions = await asyncio.gather(
        *(fetch_jexl_expressions(bid, cid) for bid, cid in all_collections)
    )
    all_collections_expressions = []
    for (bid, cid), target_filters in zip(all_collections, all_expressions):
        if not target_filters:
            continue
        fields = {
            match.group(1)
            for expr in target_filters
            for match in re.finditer(r"env.([a-zA-Z0-9_.]+)", expr)
        }
        transforms = {
            match.group(1)
            for expr in target_filters
            for match in re.finditer(r"\|(\w+)\(", expr)
        }
        all_collections_expressions.append(
            (f"{bid}/{cid}", set(target_filters), fields, transforms)
        )

    def grab_all(ll, idx):
        return set([elt for row in ll for elt in row[idx]])

    print("\n".join(sorted(grab_all(all_collections_expressions, 1))))

    print("\nFields used:")
    print(sorted(grab_all(all_collections_expressions, 2)))

    print("\nTransforms used:")
    print(sorted(grab_all(all_collections_expressions, 3)))

    print(f"\n{'Collection':<35} {'Fields':<25} {'Transforms'}")
    print("=" * 80)
    for collection, _, fields, transforms in sorted(all_collections_expressions):
        fields_str = ", ".join(fields)
        transforms_str = ", ".join(transforms)
        print(f"{collection:<35} {fields_str:<25} {transforms_str}")


# Run the asyncio event loop
asyncio.run(main())
