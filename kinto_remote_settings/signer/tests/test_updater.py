import datetime
import unittest
from unittest import mock

import pytest
from kinto.core.storage.exceptions import RecordNotFoundError

from kinto_remote_settings.signer.updater import LocalUpdater
from kinto_remote_settings.signer.utils import STATUS

from .support import DummyRequest


class LocalUpdaterTest(unittest.TestCase):
    def setUp(self):
        self.storage = mock.MagicMock()
        self.permission = mock.MagicMock()
        self.signer_instance = mock.MagicMock()
        self.updater = LocalUpdater(
            source={"bucket": "sourcebucket", "collection": "sourcecollection"},
            destination={"bucket": "destbucket", "collection": "destcollection"},
            signer=self.signer_instance,
            storage=self.storage,
            permission=self.permission,
        )

        # Resource events are bypassed completely in this test suite.
        patcher = mock.patch("kinto_remote_settings.signer.utils.build_request")
        self.addCleanup(patcher.stop)
        patcher.start()

    def patch(self, obj, *args, **kwargs):
        patcher = mock.patch.object(obj, *args, **kwargs)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def test_updater_raises_if_resources_are_not_set_properly(self):
        with pytest.raises(ValueError) as excinfo:
            LocalUpdater(
                source={"bucket": "source"},
                destination={},
                signer=self.signer_instance,
                storage=self.storage,
                permission=self.permission,
            )
        assert str(excinfo.value) == (
            "Resources should contain both " "bucket and collection"
        )

    def test_get_source_records_asks_storage_for_records(self):
        self.storage.list_all.return_value = []

        self.updater.get_source_records()
        self.storage.list_all.assert_called_with(
            resource_name="record",
            parent_id="/buckets/sourcebucket/collections/sourcecollection",
        )

    def test_get_destination_records(self):
        # We want to test get_destination_records with some records.
        records = [
            {"id": idx, "foo": "bar %s" % idx, "last_modified": 42 - idx}
            for idx in range(1, 4)
        ]
        self.storage.list_all.return_value = records
        self.updater.get_destination_records()
        self.storage.resource_timestamp.assert_called_with(
            resource_name="record",
            parent_id="/buckets/destbucket/collections/destcollection",
        )
        self.storage.list_all.assert_called_with(
            resource_name="record",
            parent_id="/buckets/destbucket/collections/destcollection",
        )

    def test_push_records_to_destination(self):
        self.patch(self.updater, "get_destination_records", return_value=([], 1324))
        records = [
            {"id": idx, "foo": "bar %s" % idx, "last_modified": 42 - idx}
            for idx in range(1, 4)
        ]
        self.patch(self.updater, "get_source_records", return_value=(records, 1325))
        self.updater.push_records_to_destination(DummyRequest())
        assert self.storage.update.call_count == 3
        assert self.storage.update.call_args_list[0][1] == {
            "obj": {"id": 1, "foo": "bar 1"},
            "object_id": 1,
            "parent_id": "/buckets/destbucket/collections/destcollection",
            "resource_name": "record",
        }

    def test_push_records_removes_deleted_records(self):
        self.patch(self.updater, "get_destination_records", return_value=([], 1324))
        records = [
            {"id": idx, "foo": "bar %s" % idx, "last_modified": 42 - idx}
            for idx in range(0, 2)
        ]
        records.extend(
            [{"id": idx, "deleted": True, "last_modified": 42} for idx in range(3, 5)]
        )
        self.patch(self.updater, "get_source_records", return_value=(records, 1325))
        self.updater.push_records_to_destination(DummyRequest())
        assert self.updater.get_source_records.call_count == 1
        assert self.storage.update.call_count == 2
        assert self.storage.delete.call_count == 2

    def test_push_records_skip_already_deleted_records(self):
        # In case the record doesn't exists in the destination
        # a RecordNotFoundError is raised.
        self.storage.delete.side_effect = RecordNotFoundError()
        self.patch(self.updater, "get_destination_records", return_value=([], 1324))
        records = [
            {"id": idx, "foo": "bar %s" % idx, "last_modified": 42 - idx}
            for idx in range(0, 2)
        ]
        records.extend(
            [{"id": idx, "deleted": True, "last_modified": 42} for idx in range(3, 5)]
        )
        self.patch(self.updater, "get_source_records", return_value=(records, 1325))
        # Calling the updater should not raise the RecordNotFoundError.
        self.updater.push_records_to_destination(DummyRequest())

    def test_push_records_to_destination_with_no_destination_changes(self):
        self.patch(self.updater, "get_destination_records", return_value=([], None))
        records = [
            {"id": idx, "foo": "bar %s" % idx, "last_modified": 42 - idx}
            for idx in range(1, 4)
        ]
        self.patch(self.updater, "get_source_records", return_value=(records, 1325))
        self.updater.push_records_to_destination(DummyRequest())
        assert self.updater.get_source_records.call_count == 1
        assert self.storage.update.call_count == 3

    def test_set_destination_signature_modifies_the_destination_collection(self):
        self.storage.get.return_value = {"id": 1234, "last_modified": 1234}
        self.updater.set_destination_signature(
            mock.sentinel.signature, {}, DummyRequest()
        )

        self.storage.update.assert_called_with(
            resource_name="collection",
            object_id="destcollection",
            parent_id="/buckets/destbucket",
            obj={"id": 1234, "signature": mock.sentinel.signature},
        )

    def test_set_destination_signature_copies_kinto_admin_ui_fields(self):
        self.storage.get.return_value = {
            "id": 1234,
            "sort": "-age",
            "last_modified": 1234,
        }
        self.updater.set_destination_signature(
            mock.sentinel.signature,
            {"displayFields": ["name"], "sort": "size"},
            DummyRequest(),
        )

        self.storage.update.assert_called_with(
            resource_name="collection",
            object_id="destcollection",
            parent_id="/buckets/destbucket",
            obj={
                "id": 1234,
                "signature": mock.sentinel.signature,
                "sort": "-age",
                "displayFields": ["name"],
            },
        )

    def test_update_source_status_modifies_the_source_collection(self):
        self.storage.get.return_value = {
            "id": 1234,
            "last_modified": 1234,
            "status": "to-sign",
        }

        with mock.patch("kinto_remote_settings.signer.updater.datetime") as mocked:
            mocked.datetime.now().isoformat.return_value = "2018-04-09"
            self.updater.update_source_status(STATUS.SIGNED, DummyRequest())

        self.storage.update.assert_called_with(
            resource_name="collection",
            object_id="sourcecollection",
            parent_id="/buckets/sourcebucket",
            obj={
                "id": 1234,
                "last_review_by": "basicauth:bob",
                "last_review_date": "2018-04-09",
                "last_signature_by": "basicauth:bob",
                "last_signature_date": "2018-04-09",
                "status": "signed",
            },
        )

    def test_create_destination_updates_collection_permissions(self):
        collection_uri = "/buckets/destbucket/collections/destcollection"
        request = DummyRequest()
        request.route_path.return_value = collection_uri
        self.updater.create_destination(request)
        request.registry.permission.replace_object_permissions.assert_called_with(
            collection_uri, {"read": ("system.Everyone",)}
        )

    def test_create_destination_creates_bucket(self):
        request = DummyRequest()
        self.updater.create_destination(request)
        request.registry.storage.create.assert_any_call(
            resource_name="bucket", parent_id="", obj={"id": "destbucket"}
        )

    def test_create_destination_creates_collection(self):
        bucket_id = "/buckets/destbucket"
        request = DummyRequest()
        self.updater.create_destination(request)
        request.registry.storage.create.assert_any_call(
            resource_name="collection",
            parent_id=bucket_id,
            obj={"id": "destcollection"},
        )

    def test_sign_and_update_destination(self):
        records = [
            {"id": idx, "foo": "bar %s" % idx, "last_modified": idx}
            for idx in range(1, 3)
        ]
        self.storage.list_all.return_value = records

        self.patch(self.storage, "update_records")
        self.patch(self.updater, "get_destination_records", return_value=([], "0"))
        self.patch(self.updater, "push_records_to_destination")
        self.patch(self.updater, "set_destination_signature")

        self.updater.sign_and_update_destination(DummyRequest(), {"id": "source"})

        assert self.updater.get_destination_records.call_count == 1
        assert self.updater.push_records_to_destination.call_count == 1
        assert self.updater.set_destination_signature.call_count == 1

    def test_refresh_signature_does_not_push_records(self):
        self.storage.list_all.return_value = []
        self.patch(self.updater, "set_destination_signature")
        self.patch(self.updater, "push_records_to_destination")

        self.updater.refresh_signature(DummyRequest(), "signed")

        assert self.updater.set_destination_signature.call_count == 1
        assert self.updater.push_records_to_destination.call_count == 0

    def test_refresh_signature_restores_status_on_source(self):
        self.storage.list_all.return_value = []
        with mock.patch("kinto_remote_settings.signer.updater.datetime") as mocked:
            mocked.datetime.now.return_value = datetime.datetime(2010, 10, 31)

            self.updater.refresh_signature(DummyRequest(), "work-in-progress")

        new_attrs = {
            "status": "work-in-progress",
            "last_signature_by": "basicauth:bob",
            "last_signature_date": "2010-10-31T00:00:00",
        }
        self.storage.update.assert_any_call(
            resource_name="collection",
            parent_id="/buckets/sourcebucket",
            object_id="sourcecollection",
            obj=new_attrs,
        )
