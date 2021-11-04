from collections import OrderedDict
from enum import Enum

from kinto.core.events import ACTIONS
from kinto.core.storage.exceptions import UnicityError
from kinto.core.utils import build_request, instance_uri
from kinto.views import NameGenerator
from pyramid.exceptions import ConfigurationError

PLUGIN_USERID = "plugin:kinto-signer"
FIELD_LAST_MODIFIED = "last_modified"


class STATUS(Enum):
    WORK_IN_PROGRESS = "work-in-progress"
    TO_SIGN = "to-sign"
    TO_REFRESH = "to-resign"
    TO_REVIEW = "to-review"
    TO_ROLLBACK = "to-rollback"
    SIGNED = "signed"

    def __eq__(self, other):
        if not hasattr(other, "value"):
            return self.value == other
        return super(STATUS, self).__eq__(other)

    def __ne__(self, other):
        return not self.__eq__(other)


def _get_resource(resource):
    # Use the default NameGenerator in Kinto resources to check if the resource
    # URIs seem valid.
    # XXX: if a custom ID generator is specified in settings, this verification would
    # not result as expected.
    name_generator = NameGenerator()

    parts = resource.split("/")
    if len(parts) == 2:
        bucket, collection = parts
    elif len(parts) == 3 and parts[1] == "buckets":
        # /buckets/bid
        _, _, bucket = parts
        collection = None
    elif len(parts) == 5 and parts[1] == "buckets" and parts[3] == "collections":
        # /buckets/bid/collections/cid
        _, _, bucket, _, collection = parts
    else:
        raise ValueError("should be a bucket or collection URI")
    valid_ids = name_generator.match(bucket) and (
        collection is None or name_generator.match(collection)
    )
    if not valid_ids:
        raise ValueError("bucket or collection id is invalid")
    return {"bucket": bucket, "collection": collection}


def parse_resources(raw_resources):
    resources = OrderedDict()

    lines = [line.strip() for line in raw_resources.strip().splitlines()]
    for res in lines:
        error_msg = "Malformed resource: %%s (in %r). See kinto-signer README." % res
        if "->" not in res and ";" not in res:
            raise ConfigurationError(error_msg % "not separated with '->'")

        try:
            triplet = [
                r.strip() for r in res.replace(";", " ").replace("->", " ").split()
            ]
            if len(triplet) == 2:
                source_uri, destination_uri = triplet
                preview_uri = None
            else:
                source_uri, preview_uri, destination_uri = triplet
        except ValueError:
            raise ConfigurationError(error_msg % "should be a pair or a triplet")

        try:
            source = _get_resource(source_uri)
            destination = _get_resource(destination_uri)
            preview = _get_resource(preview_uri) if preview_uri else None
        except ValueError as e:
            raise ConfigurationError(error_msg % e)

        # Raise if mix-up of per-bucket/specific collection.
        sections = (source, destination) + ((preview,) if preview else tuple())
        all_per_bucket = all([x["collection"] is None for x in sections])
        all_explicit = all([x["collection"] is not None for x in sections])
        if not all_per_bucket and not all_explicit:
            raise ConfigurationError(
                error_msg % "cannot mix bucket and collection URIs"
            )

        # Repeated source/preview/destination.
        if (
            len(set([tuple(s.items()) for s in (source, preview or {}, destination)]))
            != 3
        ):
            raise ConfigurationError(
                error_msg % "cannot have same value for source, "
                " preview or destination"
            )

        # Resources info is returned as a mapping by bucket/collection URI.
        bid = source["bucket"]
        if source["collection"] is None:
            # Per bucket.
            key = f"/buckets/{bid}"
        else:
            cid = source["collection"]
            # For a specific collection.
            key = f"/buckets/{bid}/collections/{cid}"

        # We can't have the same source twice.
        if key in resources:
            raise ConfigurationError(error_msg % "cannot repeat resource")

        resources[key] = {"source": source, "destination": destination}
        if preview is not None:
            resources[key]["preview"] = preview

    # Raise if same bid/cid twice/thrice.
    # Theoretically we could support it, but since we never said it was possible
    # and have no test at all for that, prefer safety.
    sources = [tuple(r["source"].items()) for r in resources.values()]
    destinations = [tuple(r["destination"].items()) for r in resources.values()]
    previews = [
        tuple(r["preview"].items()) for r in resources.values() if "preview" in r
    ]

    if len(set(destinations)) != len(destinations):
        raise ConfigurationError("Resources setting has repeated destination URI")
    if len(set(previews)) != len(previews):
        raise ConfigurationError("Resources setting has repeated preview URI")

    intersects = (
        set(sources).intersection(set(previews))
        or set(sources).intersection(set(destinations))
        or set(destinations).intersection(set(previews))
    )
    if intersects:
        raise ConfigurationError("cannot repeat URIs across resources")

    return resources


def get_first_matching_setting(setting_name, settings, prefixes, default=None):
    for prefix in prefixes:
        prefixed_setting_name = prefix + setting_name
        if prefixed_setting_name in settings:
            return settings[prefixed_setting_name]
    return default


def ensure_resource_exists(
    request, resource_name, parent_id, obj, permissions, matchdict
):
    storage = request.registry.storage
    permission = request.registry.permission
    try:
        created = storage.create(
            resource_name=resource_name, parent_id=parent_id, obj=obj
        )
        object_uri = instance_uri(request, resource_name, **matchdict)
        permission.replace_object_permissions(object_uri, permissions)
        notify_resource_event(
            request,
            {"method": "PUT", "path": object_uri},
            matchdict=matchdict,
            resource_name=resource_name,
            parent_id=parent_id,
            obj=created,
            action=ACTIONS.CREATE,
        )
    except UnicityError:
        pass


def notify_resource_event(
    request, request_options, matchdict, resource_name, parent_id, obj, action, old=None
):
    """Helper that triggers resource events as real requests."""
    fakerequest = build_request(request, request_options)
    fakerequest.matchdict = matchdict
    fakerequest.bound_data = request.bound_data
    fakerequest.authn_type, fakerequest.selected_userid = PLUGIN_USERID.split(":")
    fakerequest.current_resource_name = resource_name

    # When kinto-signer copies record from one place to another,
    # it simulates a resource event. Since kinto-attachment
    # prevents from updating attachment fields, it throws an error.
    # The following flag will disable the kinto-attachment check.
    # See https://github.com/Kinto/kinto-signer/issues/256
    # and https://bugzilla.mozilla.org/show_bug.cgi?id=1470812
    has_changed_attachment = (
        resource_name == "record"
        and action == ACTIONS.UPDATE
        and "attachment" in old
        and old["attachment"] != obj.get("attachment")
    )
    if has_changed_attachment:
        fakerequest._attachment_auto_save = True

    fakerequest.notify_resource_event(
        parent_id=parent_id,
        timestamp=obj[FIELD_LAST_MODIFIED],
        data=obj,
        action=action,
        old=old,
    )


def records_equal(a, b):
    ignore_fields = ("last_modified", "schema")
    ac = {k: v for k, v in a.items() if k not in ignore_fields}
    bc = {k: v for k, v in b.items() if k not in ignore_fields}
    return ac == bc


def records_diff(left, right):
    left_by_id = {r["id"]: r for r in left}
    results = []
    for r in right:
        rid = r["id"]
        left_record = left_by_id.pop(rid, None)
        if left_record is None:
            # In right, but not in left (deleted!)
            results.append({**r, "deleted": True})
        elif not records_equal(left_record, r):
            # Differ between left and right
            results.append(left_record)
    # In left, but not in right.
    results.extend(left_by_id.values())
    return results
