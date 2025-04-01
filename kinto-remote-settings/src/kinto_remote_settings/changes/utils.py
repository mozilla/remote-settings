import hashlib
from typing import Optional
from uuid import UUID

from kinto.core import utils as core_utils
from pyramid.settings import aslist


def bound_limit(settings: dict, value: Optional[int]) -> int:
    """
    ``_limit`` querystring value has to be within what is configured as
    pagination size and max storage fetching size (respectively defaults
    as `None` and 10000 in `kinto.core.DEFAULT_SETTINGS`)
    """
    max_fetch_size = settings["storage_max_fetch_size"]
    paginate_by = settings["paginate_by"] or max_fetch_size
    max_limit = min(paginate_by, max_fetch_size)
    return min(abs(value), max_limit) if value is not None else max_limit


def monitored_timestamps(request):
    """
    Return the list of collection timestamps based on the specified
    lists of resources in settings.

    :rtype: list[tuple[str,str,int]]
    """
    settings = request.registry.settings
    storage = request.registry.storage

    included_resources_uri = aslist(settings.get("changes.resources", ""))
    excluded_collections_uri = aslist(settings.get("changes.excluded_collections", ""))

    all_resources_timestamps = storage.all_resources_timestamps("record")

    results = []
    for parent_id, timestamp in all_resources_timestamps.items():
        matches_included = any(
            parent_id.startswith(uri) for uri in included_resources_uri
        )
        if not matches_included:
            continue
        matches_excluded = any(
            parent_id.startswith(uri) for uri in excluded_collections_uri
        )
        if matches_excluded:
            continue

        _, matchdict = core_utils.view_lookup_registry(request.registry, parent_id)
        bucket_id, collection_id = matchdict["bucket_id"], matchdict["id"]

        results.append((bucket_id, collection_id, timestamp))
    return results


_CHANGES_ENTRIES_ID_CACHE = {}


def change_entry_id(request, http_host, bucket_id, collection_id):
    """Generates a deterministic UUID based on input parameters
    and keeps it in cache.

    :rtype: str
    """
    global _CHANGES_ENTRIES_ID_CACHE

    cache_key = (http_host, bucket_id, collection_id)
    if cache_key not in _CHANGES_ENTRIES_ID_CACHE:
        collection_uri = core_utils.instance_uri(
            request, "collection", bucket_id=bucket_id, id=collection_id
        )
        uniqueid = http_host + collection_uri
        identifier = hashlib.md5(uniqueid.encode("utf-8")).hexdigest()
        entry_id = str(UUID(identifier))
        _CHANGES_ENTRIES_ID_CACHE[cache_key] = entry_id
    return _CHANGES_ENTRIES_ID_CACHE[cache_key]
