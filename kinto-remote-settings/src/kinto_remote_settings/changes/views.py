import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import colander
import kinto.core
from kinto.authorization import RouteFactory
from kinto.core import Service, resource
from kinto.core import utils as core_utils
from kinto.core.cornice.validators import colander_validator
from kinto.core.storage import Filter, Sort
from kinto.core.storage import exceptions as storage_exceptions
from kinto.core.storage.memory import extract_object_set
from kinto.core.utils import COMPARISON, instance_uri
from pyramid import httpexceptions
from pyramid.security import NO_PERMISSION_REQUIRED, IAuthorizationPolicy
from zope.interface import implementer

from . import (
    BROADCASTER_ID,
    CHANGES_COLLECTION,
    CHANGES_COLLECTION_PATH,
    CHANGES_RECORDS_PATH,
    CHANGESET_PATH,
    CHANNEL_ID,
    MONITOR_BUCKET,
)
from .utils import bound_limit, change_entry_id, monitored_timestamps


DAY_IN_SECONDS = 24 * 60 * 60
POSTGRESQL_MAX_INTEGER_VALUE = 2**63
positive_big_integer = colander.Range(min=0, max=POSTGRESQL_MAX_INTEGER_VALUE)


logger = logging.getLogger(__name__)


def utcnow():
    return datetime.now(datetime.timezone.utc)


class ChangesModel(object):
    id_field = "id"
    modified_field = "last_modified"
    deleted_field = "deleted"
    permissions_field = "__permissions__"

    def __init__(self, request):
        self.request = request
        self.storage = request.registry.storage

        self.__entries = None

    def timestamp(self):
        if not self._entries():
            return core_utils.msec_time()
        max_value = max([e["last_modified"] for e in self._entries()])
        return max_value

    def get_objects(
        self,
        filters=None,
        sorting=None,
        pagination_rules=None,
        limit=None,
        include_deleted=False,
        parent_id=None,
    ):
        objs, _ = extract_object_set(
            objects=self._entries(),
            filters=filters,
            sorting=sorting,
            pagination_rules=pagination_rules,
            limit=limit,
        )
        return objs

    def _entries(self):
        http_host = self.request.registry.settings.get("http_host") or ""

        if self.__entries is None:
            entries = [
                dict(
                    id=change_entry_id(self.request, http_host, bid, cid),
                    last_modified=timestamp,
                    bucket=bid,
                    collection=cid,
                    host=http_host,
                )
                for bid, cid, timestamp in monitored_timestamps(self.request)
            ]
            self.__entries = entries
        return self.__entries


class ChangesSchema(resource.ResourceSchema):
    host = colander.SchemaNode(colander.String())
    bucket = colander.SchemaNode(colander.String())
    collection = colander.SchemaNode(colander.String())

    class Options:
        preserve_unknown = False


@implementer(IAuthorizationPolicy)
class AnonymousRoute(RouteFactory):
    def check_permission(self, principals, bound_perms):
        # Bypass permissions check on /buckets/monitor.
        return True


@resource.register(
    name="changes",
    description="List of changes",
    plural_path=CHANGES_RECORDS_PATH,
    object_path=None,
    plural_methods=("GET",),
    factory=AnonymousRoute,
)
class Changes(resource.Resource):
    """
    This Kinto **resource** gets hit by old clients (Firefox <88)
    See https://bugzilla.mozilla.org/show_bug.cgi?id=1666511

    Recent clients reach the `/changeset` endpoints (see Kinto **service** below).
    """

    schema = ChangesSchema

    def __init__(self, request, context=None):
        # Bypass call to storage if _since is too old.
        _handle_old_since_redirect(request)
        # Inject custom model.
        self.model = ChangesModel(request)
        super(Changes, self).__init__(request, context)

    def plural_get(self):
        try:
            result = super().plural_get()
        except httpexceptions.HTTPNotModified:
            # Since the Google Cloud Platform CDN does not cache ``304 Not Modified``
            # responses, we return a ``200 Ok`` with an empty list of changes to the
            # clients. The two are strictly equivalent in the client implementation:
            # https://searchfox.org/mozilla-esr78/rev/3c633b1a0994f380032/services/settings/Utils.jsm#170-208
            result = self.postprocess([])

        _handle_cache_expires(self.request, MONITOR_BUCKET, CHANGES_COLLECTION)
        return result


def _handle_cache_expires(request, bid, cid):
    # If the client sends cache busting query parameters, then we can cache more
    # aggressively.
    settings = request.registry.settings
    prefix = f"{bid}.{cid}.record_cache"
    default_expires = settings.get(f"{prefix}_expires_seconds")
    maximum_expires = settings.get(f"{prefix}_maximum_expires_seconds", default_expires)

    has_cache_busting = "_expected" in request.GET
    cache_expires = maximum_expires if has_cache_busting else default_expires

    if cache_expires is not None:
        request.response.cache_expires(seconds=int(cache_expires))

    elif bucket_expires := settings.get(f"{bid}.record_cache_expires_seconds"):
        request.response.cache_expires(seconds=int(bucket_expires))

    elif global_expires := settings.get("record_cache_expires_seconds"):
        request.response.cache_expires(seconds=int(global_expires))


def _handle_old_since_redirect(request):
    """
    In order to limit the number of possible combinations
    of `_since` and `_expected` querystring parameters,
    and thus maximize the effect of caching, we redirect the clients
    that arrive here with a very old `_since` value.

    This simply means that these clients will have to iterate
    and compare the local timestamps of the whole list of changes
    instead of a filtered subset.

    https://searchfox.org/mozilla-central/rev/b58ca450/services/settings/remote-settings.js#299

    See https://bugzilla.mozilla.org/show_bug.cgi?id=1529685
    and https://bugzilla.mozilla.org/show_bug.cgi?id=1665319#c2
    """
    try:
        # request.validated is not populated yet (resource was not instantiated yet,
        # we want to bypass storage).
        qs_since_str = request.GET.get("_since", "")
        qs_since = int(qs_since_str.strip('"'))
    except ValueError:
        # Will fail later during resource querystring validation.
        return

    settings = request.registry.settings
    max_age_since = int(settings.get("changes.since_max_age_days", 21))
    if max_age_since < 0:
        # Redirect is disabled.
        return

    min_since_dt = datetime.now() - timedelta(days=max_age_since)
    min_since = min_since_dt.timestamp() * 1000

    if qs_since >= min_since:
        # Since value is recent. No redirect.
        return

    http_scheme = settings.get("http_scheme") or "https"
    http_host = settings.get(
        "changes.http_host", request.registry.settings.get("http_host")
    )
    host_uri = f"{http_scheme}://{http_host}"
    redirect = host_uri + request.matched_route.generate(request.matchdict)

    queryparams = request.GET.copy()
    del queryparams["_since"]
    if queryparams:
        redirect += "?" + urlencode(queryparams)

    # Serve a redirection, with optional cache control headers.
    response = httpexceptions.HTTPTemporaryRedirect(redirect)
    cache_seconds = int(
        settings.get("changes.since_max_age_redirect_ttl_seconds", 86400)
    )
    if cache_seconds >= 0:
        response.cache_expires(cache_seconds)
    raise response


@implementer(IAuthorizationPolicy)
class ChangeSetRoute(RouteFactory):
    """The changeset endpoint should have the same permissions as the collection
    metadata.

    The permission to read records is implicit when metadata are readable.
    """

    def __init__(self, request):
        super().__init__(request)
        bid = request.matchdict["bucket_id"]
        cid = request.matchdict["collection_id"]
        collection_uri = instance_uri(request, "collection", bucket_id=bid, id=cid)
        # This route context will be the same as when reaching the collection URI.
        self.permission_object_id = collection_uri
        self.required_permission = "read"

    def check_permission(self, principals, bound_perms):
        # The monitor/changes changeset endpoint is publicly accesible.
        if self.permission_object_id == CHANGES_COLLECTION_PATH:
            return True
        # Otherwise rely on the collection permissions.
        return super().check_permission(principals, bound_perms)


changeset = kinto.core.Service(
    name="collection-changeset", path=CHANGESET_PATH, factory=ChangeSetRoute
)


class QuotedTimestamp(colander.SchemaNode):
    """Integer between "" used in _since querystring."""

    schema_type = colander.String
    error_message = "The value should be integer between double quotes."
    validator = colander.Regex('^"([0-9]+?)"(?!\n)$', msg=error_message)

    def deserialize(self, cstruct=colander.null):
        param = super(QuotedTimestamp, self).deserialize(cstruct)
        if param is colander.drop:
            return param
        return int(param.strip('"'))


class ChangeSetQuerystring(colander.MappingSchema):
    _since = QuotedTimestamp(missing=colander.drop)
    _expected = colander.SchemaNode(colander.String())
    _limit = colander.SchemaNode(
        colander.Integer(), missing=colander.drop, validator=positive_big_integer
    )
    # Query parameters used on monitor/changes endpoint.
    bucket = colander.SchemaNode(colander.String(), missing=colander.drop)
    collection = colander.SchemaNode(colander.String(), missing=colander.drop)


class ChangeSetSchema(colander.MappingSchema):
    querystring = ChangeSetQuerystring()


@changeset.get(
    schema=ChangeSetSchema(), permission="read", validators=(colander_validator,)
)
def get_changeset(request):
    bid = request.matchdict["bucket_id"]
    cid = request.matchdict["collection_id"]

    storage = request.registry.storage

    queryparams = request.validated["querystring"]
    limit = bound_limit(request.registry.settings, queryparams.get("_limit"))
    filters = []
    include_deleted = False
    if "_since" in queryparams:
        filters = [Filter("last_modified", queryparams["_since"], COMPARISON.GT)]
        # Include tombstones when querying with _since
        include_deleted = True

    if (bid, cid) == (MONITOR_BUCKET, CHANGES_COLLECTION):
        # Redirect old since, on monitor/changes only.
        _handle_old_since_redirect(request)

        if "bucket" in queryparams:
            filters.append(Filter("bucket", queryparams["bucket"], COMPARISON.EQ))

        if "collection" in queryparams:
            filters.append(
                Filter("collection", queryparams["collection"], COMPARISON.EQ)
            )

        model = ChangesModel(request)
        metadata = {}
        records_timestamp = model.timestamp()
        last_modified = (
            records_timestamp  # The collection 'monitor/changes' is virtual.
        )
        # Mimic records endpoint and sort by timestamp desc.
        sorting = [Sort("last_modified", -1)]
        changes = model.get_objects(
            filters=filters,
            limit=limit,
            include_deleted=include_deleted,
            sorting=sorting,
        )

    else:
        bucket_uri = instance_uri(request, "bucket", id=bid)
        collection_uri = instance_uri(request, "collection", bucket_id=bid, id=cid)

        try:
            # We'll make sure that data isn't changed while we read metadata, changes,
            # etc.
            before = storage.resource_timestamp(
                resource_name="record", parent_id=collection_uri
            )
            # Fetch collection metadata.
            metadata = storage.get(
                resource_name="collection", parent_id=bucket_uri, object_id=cid
            )

        except storage_exceptions.ObjectNotFoundError:
            raise httpexceptions.HTTPNotFound()

        except storage_exceptions.BackendError as e:
            # The call to `resource_timestamp()` on an empty collection will try
            # initialize it. If the instance is read-only, it fails with a backend
            # error. Raise 404 in this case otherwise raise the original backend error.
            if "when running in readonly" in str(e):
                raise httpexceptions.HTTPNotFound()
            raise

        # Fetch list of changes.
        changes = storage.list_all(
            resource_name="record",
            parent_id=collection_uri,
            filters=filters,
            limit=limit,
            id_field="id",
            modified_field="last_modified",
            deleted_field="deleted",
            sorting=[Sort("last_modified", -1)],
            include_deleted=include_deleted,
        )
        # Fetch current collection timestamp.
        records_timestamp = storage.resource_timestamp(
            resource_name="record", parent_id=collection_uri
        )
        # We use the timestamp from the collection metadata, because we want it to
        # be bumped when the signature is refreshed. Indeed, the CDN will revalidate
        # the origin's response, only if the `Last-Modified` header has changed.
        # Side note: We are sure that the collection timestamp is always higher
        # than the records timestamp, because we have fields like `last_edit_date`
        # in the collection metadata that are automatically bumped when records change.
        last_modified = metadata["last_modified"]

        # Do not serve inconsistent data.
        if before != records_timestamp:  # pragma: no cover
            raise storage_exceptions.IntegrityError(message="Inconsistent data. Retry.")

    # Cache control.
    _handle_cache_expires(request, bid, cid)

    # Set Last-Modified response header (Pyramid takes care of converting).
    request.response.last_modified = last_modified / 1000.0

    data = {
        "metadata": {
            **metadata,
            "bucket": bid,
        },
        "timestamp": records_timestamp,
        "changes": changes,
    }
    return data


class BroadcastResponseSchema(colander.MappingSchema):
    body = colander.SchemaNode(colander.Mapping())


broadcasts_response_schemas = {
    "200": BroadcastResponseSchema(
        description="Return the current version number to be broadcasted via Push."
    )
}


broadcasts = Service(name="broadcast", path="/__broadcasts__", description="broadcast")


@broadcasts.get(
    permission=NO_PERMISSION_REQUIRED,
    tags=["Utilities"],
    operation_id="broadcast_view",
    response_schemas=broadcasts_response_schemas,
)
def broadcasts_view(request):
    """
    Implement the old Megaphone broacast endpoint,that the Push service will pull.

    See https://github.com/mozilla-services/megaphone?tab=readme-ov-file#get-v1broadcasts
    """
    settings = request.registry.settings
    min_debounce_interval = int(
        settings.get(
            "push_broadcast_min_debounce_interval_seconds", "300"
        )  # 5 min by default.
    )
    max_debounce_interval = int(
        settings.get(
            "push_broadcast_max_debounce_interval_seconds", "1200"
        )  # 20 min by default.
    )

    # Current highest timestamp in the monitored collections:
    rs_timestamp = max(ts for _, _, ts in monitored_timestamps(request))
    rs_age_seconds = (
        utcnow() - datetime.fromtimestamp(rs_timestamp / 1000, timezone.utc)
    ).total_seconds()

    # Last published timestamp (from cache).
    cache_key = f"{BROADCASTER_ID}/{CHANNEL_ID}/timestamp"
    last_timestamp = request.registry.cache.get(cache_key)
    if last_timestamp is None:
        # If no timestamp was published ever, we use the current timestamp.
        debounced_timestamp = rs_timestamp
        logger.info(
            "No previous timestamp found in cache. Publishing current timestamp."
        )
    else:
        # Avoid publishing too many Push notifications in a short time:
        # - if changes are published too close together (eg. < 5min), then we don't update the exposed timestamp
        # - but if changes are published continuously for too long (eg. > 20min), then we update the exposed timestamp

        last_timestamp_age_seconds = (
            utcnow() - datetime.fromtimestamp(last_timestamp / 1000, timezone.utc)
        ).total_seconds()

        diff = min_debounce_interval - rs_age_seconds
        if diff > 0:
            log_msg = f"A change was published recently (<{min_debounce_interval}). "
            if last_timestamp_age_seconds < max_debounce_interval:
                log_msg += f"Last timestamp is {last_timestamp_age_seconds} seconds old (<{max_debounce_interval}). Can wait {diff} more seconds."
                # Do not publish a new timestamp yet.
                debounced_timestamp = last_timestamp
            else:
                log_msg += f"Last timestamp is {last_timestamp_age_seconds} seconds old (>{max_debounce_interval}). Publish!"
                # Publish a new timestamp.
                debounced_timestamp = rs_timestamp
        else:
            log_msg = f"Last timestamp is {last_timestamp_age_seconds} seconds old (>{min_debounce_interval}). Publish!"
            debounced_timestamp = rs_timestamp

        logger.info(
            log_msg,
            extra={
                "min_debounce_interval": min_debounce_interval,
                "max_debounce_interval": max_debounce_interval,
                "rs_age_seconds": rs_age_seconds,
                "last_timestamp_age_seconds": last_timestamp_age_seconds,
                "wait_seconds": max(0, diff),
            },
        )

    # Store the published timestamp in the cache for next calls (skip write if unchanged).
    if debounced_timestamp != last_timestamp:
        request.registry.cache.set(cache_key, debounced_timestamp, ttl=DAY_IN_SECONDS)
    # Expose it for the Push service to pull.
    return {
        "broadcasts": {f"{BROADCASTER_ID}/{CHANNEL_ID}": f'"{debounced_timestamp}"'},
        "code": 200,
    }
