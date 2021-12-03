import datetime
import logging
from enum import Enum

from kinto.core.events import ACTIONS
from kinto.core.storage.exceptions import RecordNotFoundError
from pyramid.security import Everyone

from .serializer import canonical_json
from .utils import STATUS, ensure_resource_exists, notify_resource_event, records_diff

logger = logging.getLogger(__name__)


FIELD_ID = "id"
FIELD_LAST_MODIFIED = "last_modified"
# Source collection fields to be copied to destination.
PUBLISHED_COLLECTION_FIELDS = ("schema", "sort", "displayFields", "attachment")


class TRACKING_FIELDS(Enum):
    LAST_EDIT_BY = "last_edit_by"
    LAST_EDIT_DATE = "last_edit_date"
    LAST_REVIEW_REQUEST_BY = "last_review_request_by"
    LAST_REVIEW_REQUEST_DATE = "last_review_request_date"
    LAST_REVIEW_BY = "last_review_by"
    LAST_REVIEW_DATE = "last_review_date"
    LAST_SIGNATURE_BY = "last_signature_by"
    LAST_SIGNATURE_DATE = "last_signature_date"


def _ensure_resource(resource):
    if not set(resource.keys()).issuperset({"bucket", "collection"}):
        msg = "Resources should contain both bucket and collection"
        raise ValueError(msg)
    return resource


class LocalUpdater(object):
    """Sign items in the source and push them to the destination.

    Triggers a signature of all records in the source destination, and
    eventually update the destination with the new signature and the updated
    records.

    :param source:
        Python dictionary containing the bucket and collection of the source.

    :param destination:
        Python dictionary containing the bucket and collection of the
        destination.

    :param signer:
        The instance of the signer that will be used to generate the signature
        on the collection.

    :param storage:
        The instance of kinto.core.storage that will be used to retrieve
        records from the source and add new items to the destination.
    """

    def __init__(self, source, destination, signer, storage, permission):
        self._source = None
        self._destination = None

        self.source = source
        self.destination = destination
        self.signer = signer
        self.storage = storage
        self.permission = permission

    @property
    def source(self):
        return self._source

    @source.setter
    def source(self, source):
        self._source = _ensure_resource(source)
        self.source_bucket_uri = "/buckets/%s" % source["bucket"]
        self.source_collection_uri = "/buckets/%s/collections/%s" % (
            source["bucket"],
            source["collection"],
        )

    @property
    def destination(self):
        return self._destination

    @destination.setter
    def destination(self, destination):
        self._destination = _ensure_resource(destination)
        self.destination_bucket_uri = "/buckets/%s" % (self.destination["bucket"])
        self.destination_collection_uri = "/buckets/%s/collections/%s" % (
            self.destination["bucket"],
            self.destination["collection"],
        )

    def sign_and_update_destination(
        self,
        request,
        source_attributes,
        next_source_status=STATUS.SIGNED,
        previous_source_status=None,
        push_records=True,
    ):
        """Sign the specified collection.

        0. Create the destination bucket / collection
        1. Get all the records of the collection
        2. Send all records since the last_modified of the destination
        3. Compute a hash of these records
        4. Ask the signer for a signature
        5. Send the signature to the destination.
        """
        changes_count = 0

        self.create_destination(request)

        if push_records:
            changes_count = self.push_records_to_destination(request)

        records, timestamp = self.get_destination_records(empty_none=False)
        serialized_records = canonical_json(records, timestamp)
        logger.debug(f"{self.source_collection_uri}:\t'{serialized_records}'")
        signature = self.signer.sign(serialized_records)

        self.set_destination_signature(signature, source_attributes, request)
        if next_source_status is not None:
            self.update_source_status(
                next_source_status, request, previous_source_status
            )

        return changes_count

    def refresh_signature(self, request, next_source_status=None):
        """Refresh the signature without moving records."""
        records, timestamp = self.get_destination_records(empty_none=False)
        serialized_records = canonical_json(records, timestamp)
        logger.debug(f"{self.source_collection_uri}:\t'{serialized_records}'")
        signature = self.signer.sign(serialized_records)
        self.set_destination_signature(signature, request=request, source_attributes={})

        if next_source_status is not None:
            current_userid = request.prefixed_userid
            current_date = datetime.datetime.now(datetime.timezone.utc).isoformat()
            attrs = {"status": next_source_status}
            attrs[TRACKING_FIELDS.LAST_SIGNATURE_BY.value] = current_userid
            attrs[TRACKING_FIELDS.LAST_SIGNATURE_DATE.value] = current_date
            self._update_source_attributes(request, **attrs)

    def rollback_changes(
        self, request, refresh_last_edit=True, refresh_signature=False
    ):
        """Restore the contents of *destination* to *source* (delete extras, recreate deleted,
        and restore changes) (eg. destination -> preview, or preview -> source).
        """
        dest_records, _ = self.get_destination_records(empty_none=False)
        dest_by_id = {r["id"]: r for r in dest_records}
        source_records, _ = self.get_source_records()

        changes_since_approval = records_diff(source_records, dest_records)

        storage_kwargs = {
            "parent_id": self.source_collection_uri,
            "resource_name": "record",
        }

        changed_count = 0
        for record in changes_since_approval:
            action = None
            record_before = None
            impacted = None

            dest_record = dest_by_id.get(record[FIELD_ID])
            if dest_record is None:
                # In source, but not in destination. Must be deleted.
                if not record.get("deleted"):
                    tombstone = self.storage.delete(
                        object_id=record[FIELD_ID],
                        last_modified=record[FIELD_LAST_MODIFIED],
                        **storage_kwargs,
                    )
                    action = ACTIONS.DELETE
                    record_before = record
                    impacted = tombstone

            # In dest_records, but not in source_records. Must be re-created.
            elif record.get("deleted"):
                self.storage.create(obj=dest_record, **storage_kwargs)
                action = ACTIONS.CREATE
                record_before = None
                impacted = dest_record

            # Differ, restore attributes of dest_record in source.
            else:
                self.storage.update(
                    object_id=record[FIELD_ID], obj=dest_record, **storage_kwargs
                )
                action = ACTIONS.UPDATE
                record_before = record
                impacted = dest_record

            if action is not None:
                changed_count += 1
                # Notify resource event, in order to leave a trace in the history.
                matchdict = {
                    "bucket_id": self.destination["bucket"],
                    "collection_id": self.destination["collection"],
                    FIELD_ID: record[FIELD_ID],
                }
                record_uri = (
                    "/buckets/{bucket_id}/collections/{collection_id}/records/{id}"
                ).format(**matchdict)

                notify_resource_event(
                    request,
                    {
                        "method": "DELETE" if action == ACTIONS.DELETE else "PUT",
                        "path": record_uri,
                    },
                    matchdict=matchdict,
                    resource_name="record",
                    parent_id=self.source_collection_uri,
                    obj=impacted,
                    action=action,
                    old=record_before,
                )

        if refresh_last_edit:
            current_userid = request.prefixed_userid
            current_date = datetime.datetime.now(datetime.timezone.utc).isoformat()
            attrs = {
                "status": STATUS.SIGNED.value,
                "last_editor_comment": "",
                "last_reviewer_comment": "",
            }
            attrs[TRACKING_FIELDS.LAST_EDIT_BY.value] = current_userid
            attrs[TRACKING_FIELDS.LAST_EDIT_DATE.value] = current_date
            self._update_source_attributes(request, **attrs)

        return changed_count

    def create_destination(self, request):
        """Create the destination bucket/collection if they don't already exist."""
        # With the current implementation, the destination is not writable by
        # anyone and readable by everyone.
        # https://github.com/Kinto/kinto-signer/issues/55
        bucket_name = self.destination["bucket"]
        collection_name = self.destination["collection"]

        # Destination bucket will be writable by current user.
        perms = {"write": [request.prefixed_userid]}
        ensure_resource_exists(
            request=request,
            resource_name="bucket",
            parent_id="",
            obj={FIELD_ID: bucket_name},
            permissions=perms,
            matchdict={"id": bucket_name},
        )

        # Destination collection will be publicly readable.
        readonly_perms = {"read": (Everyone,)}
        ensure_resource_exists(
            request=request,
            resource_name="collection",
            parent_id=self.destination_bucket_uri,
            obj={FIELD_ID: collection_name},
            permissions=readonly_perms,
            matchdict={"bucket_id": bucket_name, "id": collection_name},
        )

    def _get_records(self, resource, empty_none=True):
        bid = resource["bucket"]
        cid = resource["collection"]
        parent_id = f"/buckets/{bid}/collections/{cid}"

        records = self.storage.list_all(parent_id=parent_id, resource_name="record")

        if len(records) == 0 and empty_none:
            # When the collection empty (no records and no tombstones)
            collection_timestamp = None
        else:
            collection_timestamp = self.storage.resource_timestamp(
                parent_id=parent_id, resource_name="record"
            )

        return records, collection_timestamp

    def get_source_records(self, **kwargs):
        return self._get_records(self.source, **kwargs)

    def get_destination_records(self, **kwargs):
        return self._get_records(self.destination, **kwargs)

    def push_records_to_destination(self, request):
        dest_records, dest_timestamp = self.get_destination_records()
        source_records, source_timestamp = self.get_source_records()
        new_records = records_diff(source_records, dest_records)
        changes_count = len(new_records)

        if len(new_records) == 0:
            return

        # Update the destination collection.
        for record in new_records:
            storage_kwargs = {
                "parent_id": self.destination_collection_uri,
                "resource_name": "record",
            }
            try:
                before = self.storage.get(object_id=record[FIELD_ID], **storage_kwargs)
            except RecordNotFoundError:
                before = None

            # Timestamp should be bumped in destination.
            record = {**record}
            del record[FIELD_LAST_MODIFIED]

            deleted = record.get("deleted", False)
            if deleted:
                try:
                    pushed = self.storage.delete(
                        object_id=record[FIELD_ID],
                        **storage_kwargs,
                    )
                    action = ACTIONS.DELETE
                except RecordNotFoundError:
                    # If the record doesn't exists in the destination
                    # we are good and can ignore it.
                    continue
            else:
                if before is None:
                    pushed = self.storage.create(obj=record, **storage_kwargs)
                    action = ACTIONS.CREATE
                else:
                    pushed = self.storage.update(
                        object_id=record[FIELD_ID], obj=record, **storage_kwargs
                    )
                    action = ACTIONS.UPDATE

            matchdict = {
                "bucket_id": self.destination["bucket"],
                "collection_id": self.destination["collection"],
                FIELD_ID: record[FIELD_ID],
            }
            bid = matchdict["bucket_id"]
            cid = matchdict["collection_id"]
            rid = matchdict["id"]
            record_uri = f"/buckets/{bid}/collections/{cid}/records/{rid}"

            notify_resource_event(
                request,
                {"method": "DELETE" if deleted else "PUT", "path": record_uri},
                matchdict=matchdict,
                resource_name="record",
                parent_id=self.destination_collection_uri,
                obj=pushed,
                action=action,
                old=before,
            )

        return changes_count

    def set_destination_signature(self, signature, source_attributes, request):
        # Push the new signature to the destination collection.
        parent_id = "/buckets/%s" % self.destination["bucket"]
        collection_id = "collection"

        collection_record = self.storage.get(
            parent_id=parent_id,
            resource_name=collection_id,
            object_id=self.destination["collection"],
        )

        # Update the collection_record
        new_collection = dict(**collection_record)
        new_collection.pop(FIELD_LAST_MODIFIED, None)
        new_collection["signature"] = signature
        for attr in PUBLISHED_COLLECTION_FIELDS:
            if attr in source_attributes:
                new_collection.setdefault(attr, source_attributes[attr])

        updated = self.storage.update(
            parent_id=parent_id,
            resource_name=collection_id,
            object_id=self.destination["collection"],
            obj=new_collection,
        )

        matchdict = dict(
            bucket_id=self.destination["bucket"], id=self.destination["collection"]
        )
        notify_resource_event(
            request,
            {"method": "PUT", "path": self.destination_collection_uri},
            matchdict=matchdict,
            resource_name="collection",
            parent_id=self.destination_bucket_uri,
            obj=updated,
            action=ACTIONS.UPDATE,
            old=collection_record,
        )

    def update_source_review_request_by(self, request):
        current_date = datetime.datetime.now(datetime.timezone.utc).isoformat()
        attrs = {
            TRACKING_FIELDS.LAST_REVIEW_REQUEST_BY.value: request.prefixed_userid,
            TRACKING_FIELDS.LAST_REVIEW_REQUEST_DATE.value: current_date,
        }
        return self._update_source_attributes(request, **attrs)

    def update_source_status(self, status, request, old_status=None):
        current_userid = request.prefixed_userid
        current_date = datetime.datetime.now(datetime.timezone.utc).isoformat()
        attrs = {"status": status.value}
        if status == STATUS.WORK_IN_PROGRESS:
            attrs[TRACKING_FIELDS.LAST_EDIT_BY.value] = current_userid
            attrs[TRACKING_FIELDS.LAST_EDIT_DATE.value] = current_date
        if status == STATUS.TO_REVIEW:
            attrs[TRACKING_FIELDS.LAST_REVIEW_REQUEST_BY.value] = current_userid
            attrs[TRACKING_FIELDS.LAST_REVIEW_REQUEST_DATE.value] = current_date
            # Make sure we reset the review comments if none is specified.
            if "last_editor_comment" not in request.validated["body"].get("data", {}):
                attrs["last_editor_comment"] = ""
        if status == STATUS.SIGNED:
            if old_status != STATUS.SIGNED:
                # Do not keep track of reviewer when refreshing signature.
                attrs[TRACKING_FIELDS.LAST_REVIEW_BY.value] = current_userid
                attrs[TRACKING_FIELDS.LAST_REVIEW_DATE.value] = current_date
            attrs[TRACKING_FIELDS.LAST_SIGNATURE_BY.value] = current_userid
            attrs[TRACKING_FIELDS.LAST_SIGNATURE_DATE.value] = current_date
        return self._update_source_attributes(request, **attrs)

    def _update_source_attributes(self, request, **kwargs):
        parent_id = "/buckets/%s" % self.source["bucket"]
        resource_name = "collection"

        collection_record = self.storage.get(
            parent_id=parent_id,
            resource_name=resource_name,
            object_id=self.source["collection"],
        )

        # Update the collection_record
        new_collection = dict(**collection_record)
        new_collection.update(**kwargs)

        # Remove last_modified to be sure it's bumped.
        new_collection.pop("last_modified", None)

        updated = self.storage.update(
            parent_id=parent_id,
            resource_name=resource_name,
            object_id=self.source["collection"],
            obj=new_collection,
        )

        matchdict = dict(bucket_id=self.source["bucket"], id=self.source["collection"])
        notify_resource_event(
            request,
            {"method": "PUT", "path": self.source_collection_uri},
            matchdict=matchdict,
            resource_name="collection",
            parent_id=self.source_bucket_uri,
            obj=updated,
            action=ACTIONS.UPDATE,
            old=collection_record,
        )
