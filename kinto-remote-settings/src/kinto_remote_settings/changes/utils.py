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


def monitored_collections(registry):
    storage = registry.storage
    resources_uri = aslist(registry.settings.get("changes.resources", ""))

    excluded_collections_uri = aslist(
        registry.settings.get("changes.excluded_collections", "")
    )
    excluded_collections = []
    for uri in excluded_collections_uri:
        _, matchdict = core_utils.view_lookup_registry(registry, uri)
        excluded_collections.append((matchdict["bucket_id"], matchdict["id"]))

    collections = []

    for resource_uri in resources_uri:
        resource_name, matchdict = core_utils.view_lookup_registry(
            registry, resource_uri
        )
        if resource_name == "bucket":
            # Every collections in this bucket.
            result = storage.list_all(
                resource_name="collection", parent_id=resource_uri
            )
            collections.extend([(matchdict["id"], obj["id"]) for obj in result])

        elif resource_name == "collection":
            collections.append((matchdict["bucket_id"], matchdict["id"]))

    return [c for c in collections if c not in excluded_collections]


def changes_object(request, bucket_id, collection_id, timestamp):
    """Generate an object for /buckets/monitor/collections/changes."""
    http_host = request.registry.settings.get("http_host") or ""
    collection_uri = core_utils.instance_uri(
        request, "collection", bucket_id=bucket_id, id=collection_id
    )
    uniqueid = http_host + collection_uri
    identifier = hashlib.md5(uniqueid.encode("utf-8")).hexdigest()
    entry_id = str(UUID(identifier))

    return dict(
        id=entry_id,
        last_modified=timestamp,
        bucket=bucket_id,
        collection=collection_id,
        host=http_host,
    )
