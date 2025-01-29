import os
import asyncio
import re
import kinto_http

SERVER_URL = os.getenv("SERVER_URL", "https://firefox.settings.services.mozilla.com/v1")

client = kinto_http.AsyncClient(server_url=SERVER_URL)

async def fetch_collections(bucket_id):
    """Fetch collections for a given bucket."""
    collections = await client.get_collections(bucket=bucket_id)
    return [(bucket_id, c["id"]) for c in collections]

async def fetch_records(bucket_id, collection_id):
    """Fetch records for a given bucket and collection."""
    records = await client.get_records(bucket=bucket_id, collection=collection_id)
    return [record.get("filter_expression") for record in records]

async def main():
    # """Main async function to fetch collections and records in parallel."""

    # Fetch all collections in parallel
    bucket_ids = ["main", "security-state", "blocklists"]
    all_collections = await asyncio.gather(*(fetch_collections(bid) for bid in bucket_ids))

    # Flatten the list of collections
    all_collections = [item for sublist in all_collections for item in sublist]

    # Fetch all records in parallel
    all_records = await asyncio.gather(*(fetch_records(bid, cid) for bid, cid in all_collections))

    # Flatten and filter the records, removing None values
    target_filters = set(filter(None, [record for sublist in all_records for record in sublist]))
    fields = {match.group(1) for expr in target_filters for match in re.finditer(r'env.([a-zA-Z0-9_.]+)', expr)}
    transforms = {match.group(1) for expr in target_filters for match in re.finditer(r'\|(\w+)\(', expr)}

    print("\n".join(target_filters))
    print("\nFields used:")
    print(sorted(fields))

    print("\nTransforms used:")
    print(sorted(transforms))

# Run the asyncio event loop
asyncio.run(main())
