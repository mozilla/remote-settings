from datetime import datetime, timedelta
from urllib.parse import urlencode

import colander
import kinto.core
from cornice.validators import colander_validator
from kinto.authorization import RouteFactory
from kinto.core import resource
from kinto.core import utils as core_utils
from kinto.core.storage import Filter, Sort
from kinto.core.storage import exceptions as storage_exceptions
from kinto.core.storage.memory import extract_object_set
from kinto.core.utils import COMPARISON, instance_uri
from pyramid import httpexceptions
from pyramid.security import IAuthorizationPolicy
from zope.interface import implementer

from . import (
    CHANGES_COLLECTION,
    CHANGES_COLLECTION_PATH,
    CHANGES_RECORDS_PATH,
    CHANGESET_PATH,
    MONITOR_BUCKET,
)
from .utils import changes_object, monitored_collections


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
        if self.__entries is None:
            self.__entries = {}

            for (bucket_id, collection_id) in monitored_collections(
                self.request.registry
            ):
                collection_uri = core_utils.instance_uri(
                    self.request, "collection", bucket_id=bucket_id, id=collection_id
                )
                timestamp = self.storage.resource_timestamp(
                    parent_id=collection_uri, resource_name="record"
                )
                entry = changes_object(
                    self.request, bucket_id, collection_id, timestamp
                )
                self.__entries[entry[self.id_field]] = entry

        return self.__entries.values()


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

    schema = ChangesSchema

    def __init__(self, request, context=None):
        # Bypass call to storage if _since is too old.
        _handle_old_since_redirect(request)
        # Inject custom model.
        self.model = ChangesModel(request)
        super(Changes, self).__init__(request, context)

    def plural_get(self):
        result = super().plural_get()
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
        bid = request.matchdict["bid"]
        cid = request.matchdict["cid"]
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
    validator = colander.Regex('^"([0-9]+?)"$', msg=error_message)

    def deserialize(self, cstruct=colander.null):
        param = super(QuotedTimestamp, self).deserialize(cstruct)
        if param is colander.drop:
            return param
        return int(param.strip('"'))


class ChangeSetQuerystring(colander.MappingSchema):
    _since = QuotedTimestamp(missing=colander.drop)
    _expected = colander.SchemaNode(colander.String())
    _limit = colander.SchemaNode(colander.Integer(), missing=colander.drop)
    # Query parameters used on monitor/changes endpoint.
    bucket = colander.SchemaNode(colander.String(), missing=colander.drop)
    collection = colander.SchemaNode(colander.String(), missing=colander.drop)


class ChangeSetSchema(colander.MappingSchema):
    querystring = ChangeSetQuerystring()


@changeset.get(
    schema=ChangeSetSchema(), permission="read", validators=(colander_validator,)
)
def get_changeset(request):
    bid = request.matchdict["bid"]
    cid = request.matchdict["cid"]

    storage = request.registry.storage

    queryparams = request.validated["querystring"]
    limit = queryparams.get("_limit")
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
        timestamp = model.timestamp()
        changes = model.get_objects(
            filters=filters, limit=limit, include_deleted=include_deleted
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
        timestamp = storage.resource_timestamp(
            resource_name="record", parent_id=collection_uri
        )

        # Do not serve inconsistent data.
        if before != timestamp:  # pragma: no cover
            raise storage_exceptions.IntegrityError(message="Inconsistent data. Retry.")

    # Cache control.
    _handle_cache_expires(request, bid, cid)

    # Set Last-Modified response header (Pyramid takes care of converting).
    request.response.last_modified = timestamp / 1000.0

    data = {
        "metadata": metadata,
        "timestamp": timestamp,
        "changes": changes,
    }
    return data
