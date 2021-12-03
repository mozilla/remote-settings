import random
import re
import string
import unittest
from unittest import mock

from kinto.core.errors import ERRORS
from kinto.core.testing import FormattedErrorMixin

from .support import BaseWebTest, get_user_headers

RE_ISO8601 = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}\+00:00")


class PostgresWebTest(BaseWebTest):
    source_bucket = "/buckets/alice"
    source_collection = "/buckets/alice/collections/scid"
    destination_bucket = "/buckets/alice"
    destination_collection = "/buckets/alice/collections/dcid"

    def setUp(self):
        super(PostgresWebTest, self).setUp()
        # Patch calls to Autograph.
        patch = mock.patch("kinto_remote_settings.signer.backends.autograph.requests")
        self.addCleanup(patch.stop)
        self.mocked_autograph = patch.start()

        def fake_sign():
            fake_signature = "".join(random.sample(string.ascii_lowercase, 10))
            return [
                {
                    "signature": fake_signature,
                    "hash_algorithm": "",
                    "signature_encoding": "",
                    "x5u": "",
                    "ref": "",
                }
            ]

        self.mocked_autograph.post.return_value.json.side_effect = fake_sign

    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super().get_app_settings(extras)

        settings["storage_backend"] = "kinto.core.storage.postgresql"
        db = "postgresql://postgres:postgres@localhost/testdb"
        settings["storage_url"] = db
        settings["permission_backend"] = "kinto.core.permission.postgresql"
        settings["permission_url"] = db
        settings["cache_backend"] = "kinto.core.cache.memory"

        settings["statsd_url"] = "udp://127.0.0.1:8125"

        settings["kinto.signer.resources"] = "%s -> %s" % (
            cls.source_collection,
            cls.destination_collection,
        )
        return settings


class SignoffWebTest(PostgresWebTest):
    def setUp(self):
        super(SignoffWebTest, self).setUp()
        self.headers = get_user_headers("tarte:en-pion")
        resp = self.app.get("/", headers=self.headers)
        self.userid = resp.json["user"]["id"]

        self.other_headers = get_user_headers("Sam:Wan Heilss")
        resp = self.app.get("/", headers=self.other_headers)
        self.other_userid = resp.json["user"]["id"]

        # Source bucket
        self.app.put_json(
            self.source_bucket,
            {"permissions": {"write": ["system.Authenticated"]}},
            headers=self.headers,
        )

        # Editors and reviewers group
        self.app.put_json(
            self.source_bucket + "/groups/editors",
            {"data": {"members": [self.userid, self.other_userid]}},
            headers=self.headers,
        )
        self.app.put_json(
            self.source_bucket + "/groups/reviewers",
            {"data": {"members": [self.userid, self.other_userid]}},
            headers=self.headers,
        )

        # Source collection with 2 records
        self.app.put_json(self.source_collection, headers=self.headers)
        self.app.post_json(
            self.source_collection + "/records",
            {"data": {"title": "hello"}},
            headers=self.headers,
        )
        self.app.post_json(
            self.source_collection + "/records",
            {"data": {"id": "in-french", "title": "bonjour"}},
            headers=self.headers,
        )


class CollectionStatusTest(SignoffWebTest, FormattedErrorMixin, unittest.TestCase):
    def test_status_can_be_refreshed_even_if_never_signed(self):
        resp = self.app.get(self.source_collection, headers=self.headers)
        before = resp.json["data"]["last_signature_date"]

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-resign"}},
            headers=self.headers,
        )
        resp = self.app.get(self.source_collection, headers=self.headers)

        assert resp.json["data"]["status"] == "work-in-progress"
        after = resp.json["data"]["last_signature_date"]
        assert before < after
        # The review request / approval field are not set.
        assert "last_review_date" not in resp.json["data"]
        assert "last_review_request_date" not in resp.json["data"]

    def test_status_cannot_be_set_to_unknown_value(self):
        resp = self.app.patch_json(
            self.source_collection,
            {"data": {"status": "married"}},
            headers=self.headers,
            status=400,
        )
        self.assertFormattedError(
            response=resp,
            code=400,
            errno=ERRORS.INVALID_POSTED_DATA,
            error="Bad Request",
            message="Invalid status 'married'",
        )
        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "work-in-progress"

    def test_status_cannot_be_set_to_signed_manually(self):
        resp = self.app.patch_json(
            self.source_collection,
            {"data": {"status": "signed"}},
            headers=self.headers,
            status=400,
        )
        assert resp.json["message"] == "Cannot set status to 'signed'"
        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "work-in-progress"

    def test_status_can_be_set_to_work_in_progress_manually(self):
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.headers,
        )
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "work-in-progress"}},
            headers=self.headers,
        )

    def test_status_can_be_maintained_as_signed_manually(self):
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.headers,
        )
        # Signature occured, the source collection will be signed.
        self.app.patch_json(
            self.source_collection, {"data": {"status": "signed"}}, headers=self.headers
        )
        self.app.patch_json(
            self.source_collection, {"data": {"author": "dali"}}, headers=self.headers
        )

    def test_status_cannot_be_removed_once_it_was_set(self):
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.headers,
        )
        self.app.put_json(
            self.source_collection, {"data": {}}, headers=self.headers, status=400
        )

    def test_status_cannot_be_emptied_once_it_was_set(self):
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.headers,
        )
        self.app.put_json(
            self.source_collection,
            {"data": {"status": ""}},
            headers=self.headers,
            status=400,
        )

    def test_status_can_be_reset(self):
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.headers,
        )
        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "signed"

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.headers,
        )
        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "to-review"

    def test_status_is_set_to_work_in_progress_when_records_are_posted(self):
        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "work-in-progress"

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.headers,
        )
        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "signed"

        self.app.post_json(
            self.source_collection + "/records",
            {"data": {"title": "Hallo"}},
            headers=self.headers,
        )
        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "work-in-progress"

    def test_statsd_reports_number_of_records_approved(self):
        # Publish the changes to reset the setup.
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.headers,
        )
        # Make some changes.
        self.app.post(self.source_collection + "/records", headers=self.headers)
        self.app.delete(
            self.source_collection + "/records/in-french", headers=self.headers
        )

        # Publish the changes again.
        statsd_client = self.app.app.registry.statsd
        with mock.patch.object(statsd_client, "count") as mocked:
            self.app.patch_json(
                self.source_collection,
                {"data": {"status": "to-sign"}},
                headers=self.headers,
            )
        call_args = mocked.call_args_list[0][0]

        # One creation and one deletion.
        assert call_args == ("plugins.signer.approved_changes", 2)


class ForceReviewTest(SignoffWebTest, unittest.TestCase):
    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super().get_app_settings(extras)
        settings["signer.to_review_enabled"] = "true"
        return settings

    def test_status_cannot_be_set_to_to_sign_without_review(self):
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.headers,
            status=400,
        )
        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "work-in-progress"

    def test_passing_from_signed_to_to_sign_is_not_allowed(self):
        """This is useful when the x5u certificate changed and you want
        to retrigger a new signature."""
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.headers,
        )
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.other_headers,
        )
        resp = self.app.get(self.source_collection, headers=self.other_headers)
        assert resp.json["data"]["status"] == "signed"

        resp = self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.other_headers,
            status=400,
        )
        assert resp.json["message"] == "Collection already signed"

    def test_editor_cannot_be_reviewer(self):
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.headers,
        )

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.headers,
            status=403,
        )
        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "to-review"

        # Try again as someone else
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.other_headers,
        )
        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "signed"


class RefreshSignatureTest(SignoffWebTest, unittest.TestCase):
    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super().get_app_settings(extras)
        settings["signer.to_review_enabled"] = "true"
        return settings

    def setUp(self):
        super().setUp()
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.headers,
        )
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.other_headers,
        )
        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "signed"

    def test_resign_does_not_bump_destination_timestamp(self):
        resp = self.app.head(
            self.destination_collection + "/records", headers=self.headers
        )
        before = resp.headers["ETag"]

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-resign"}},
            headers=self.headers,
        )

        resp = self.app.head(
            self.destination_collection + "/records", headers=self.headers
        )
        after = resp.headers["ETag"]
        assert before == after

    def test_request_review_and_re_sign_does_not_bump_destination_timestamp(self):
        resp = self.app.head(
            self.destination_collection + "/records", headers=self.headers
        )
        before = resp.headers["ETag"]

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.other_headers,
        )
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.headers,
        )

        resp = self.app.head(
            self.destination_collection + "/records", headers=self.headers
        )
        after = resp.headers["ETag"]
        assert before == after

    def test_editor_can_retrigger_a_signature(self):
        # Editor retriggers a signature, without going through review.
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-resign"}},
            headers=self.headers,
        )

        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "signed"

    def test_reviewer_can_retrigger_a_signature(self):
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-resign"}},
            headers=self.other_headers,
        )
        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "signed"

    def test_if_resign_fails_signature_is_rolledback(self):
        self.mocked_autograph.post.side_effect = ValueError("Boom!")

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-resign"}},
            headers=self.other_headers,
            status=500,
        )

        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "signed"

    def test_non_reviewer_can_retrigger_a_signature(self):
        writer_headers = get_user_headers("walter:white")
        resp = self.app.get("/", headers=writer_headers)
        writer_userid = resp.json["user"]["id"]
        self.app.patch_json(
            self.source_bucket,
            {"permissions": {"write": [writer_userid]}},
            headers=self.headers,
        )

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-resign"}},
            headers=writer_headers,
        )
        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "signed"

    def test_signature_can_be_refreshed_with_pending_changes(self):
        self.app.post_json(
            self.source_collection + "/records",
            {"data": {"title": "pending change"}},
            headers=self.headers,
        )

        resp = self.app.get(self.destination_collection, headers=self.headers)
        before_signature = resp.json["data"]["signature"]["signature"]

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-resign"}},
            headers=self.headers,
        )
        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "work-in-progress"

        resp = self.app.get(self.destination_collection, headers=self.headers)
        assert resp.json["data"]["signature"]["signature"] != before_signature


class TrackingFieldsTest(SignoffWebTest, unittest.TestCase):
    def last_edit_by_and_date_are_tracked(self):
        self.app.post_json(
            self.source_collection + "/records",
            {"data": {"title": "Hallo"}},
            headers=self.headers,
        )
        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["last_edit_by"] == self.userid
        assert RE_ISO8601.match(resp.json["data"]["last_edit_date"])

    def test_last_review_request_by_and_date_are_tracked(self):
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.headers,
        )
        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["last_review_request_by"] == self.userid
        assert RE_ISO8601.match(resp.json["data"]["last_review_request_date"])

    def test_last_review_by_and_date_are_tracked(self):
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.headers,
        )
        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "signed"
        assert resp.json["data"]["last_review_by"] == self.userid
        assert RE_ISO8601.match(resp.json["data"]["last_review_date"])
        assert resp.json["data"]["last_signature_by"] == self.userid
        assert RE_ISO8601.match(resp.json["data"]["last_signature_date"])

    def test_last_review_differs_from_last_signature_on_refresh_signature(self):
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.headers,
        )
        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "signed"
        last_reviewer = resp.json["data"]["last_review_by"]

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-resign"}},
            headers=self.headers,
        )
        metadata = self.app.get(self.source_collection, headers=self.headers).json[
            "data"
        ]
        assert metadata["status"] == "signed"

        assert metadata["last_signature_date"] != metadata["last_review_date"]
        assert last_reviewer == metadata["last_review_by"]

    def test_editor_can_be_reviewer(self):
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.headers,
        )

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.headers,
        )
        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "signed"

    def test_editor_reviewer_editor_cannot_be_changed_nor_removed(self):
        self.app.post_json(
            self.source_collection + "/records",
            {"data": {"title": "Hallo"}},
            headers=self.headers,
        )
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.headers,
        )
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.other_headers,
        )

        resp = self.app.get(self.source_collection, headers=self.headers)
        source_collection = resp.json["data"]
        assert source_collection["status"] == "signed"

        # All tracking fields are here.
        expected = (
            "last_edit_by",
            "last_edit_date",
            "last_review_request_by",
            "last_review_request_date",
            "last_review_by",
            "last_review_date",
            "last_signature_by",
            "last_signature_date",
        )
        assert all([f in source_collection for f in expected])

        # They cannot be changed nor removed.
        for f in expected:
            self.app.patch_json(
                self.source_collection,
                {"data": {f: "changed"}},
                headers=self.headers,
                status=400,
            )
            changed = source_collection.copy()
            changed.pop(f)
            self.app.put_json(
                self.source_collection,
                {"data": changed},
                headers=self.headers,
                status=400,
            )


class RollbackChangesTest(SignoffWebTest, unittest.TestCase):
    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super().get_app_settings(extras)

        cls.preview_bucket = "/buckets/preview"
        cls.preview_collection = cls.preview_bucket + "/collections/pcid"

        settings["signer.to_review_enabled"] = "true"
        settings["kinto.signer.resources"] = " -> ".join(
            [cls.source_collection, cls.preview_collection, cls.destination_collection]
        )
        return settings

    def setUp(self):
        super().setUp()
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.headers,
        )
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.other_headers,
        )
        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "signed"

        self.app.put_json(
            self.source_collection + "/records/r1",
            {"data": {"title": "Hallo"}},
            headers=self.headers,
        )
        self.app.put_json(
            self.source_collection + "/records/r2",
            {"data": {"title": "Bon dia"}},
            headers=self.headers,
        )
        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "work-in-progress"

    def test_return_400_if_status_is_signed(self):
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.headers,
        )
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.other_headers,
        )

        resp = self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-rollback"}},
            headers=self.headers,
            status=400,
        )

        assert resp.json["message"] == "Collection has no work-in-progress"

    def test_rollbacks_if_no_pending_changes(self):
        self.app.delete(self.source_collection + "/records/r1", headers=self.headers)
        self.app.delete(self.source_collection + "/records/r2", headers=self.headers)

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-rollback"}},
            headers=self.headers,
        )

        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "signed"

    def test_rollbacks_if_review_already_requested(self):
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.headers,
        )

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-rollback"}},
            headers=self.headers,
        )

        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "signed"

    def test_tracking_fields_are_updated(self):
        resp = self.app.get(self.source_collection, headers=self.headers)
        before_date = resp.json["data"]["last_edit_date"]

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-rollback"}},
            headers=self.headers,
        )

        resp = self.app.get(self.source_collection, headers=self.headers)
        after_date = resp.json["data"]["last_edit_date"]
        assert before_date != after_date

    def test_comments_are_reset(self):
        self.app.patch_json(
            self.source_collection,
            {
                "data": {
                    "last_editor_comment": "please check that",
                    "last_reviewer_comment": "looks good",
                }
            },
            headers=self.headers,
        )

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-rollback"}},
            headers=self.headers,
        )

        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["last_editor_comment"] == ""
        assert resp.json["data"]["last_reviewer_comment"] == ""

    def test_recreates_deleted_record(self):
        resp = self.app.delete(
            self.source_collection + "/records?_limit=1&_sort=last_modified",
            headers=self.headers,
        )
        deleted_id = resp.json["data"][0]["id"]

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-rollback"}},
            headers=self.headers,
        )

        resp = self.app.get(
            self.source_collection + f"/records/{deleted_id}",
            headers=self.headers,
            status=200,
        )
        assert resp.json["data"]["title"] == "hello"

    def test_reverts_updated_records(self):
        resp = self.app.get(
            self.source_collection + "/records?_limit=1&_sort=last_modified",
            headers=self.headers,
        )
        update_id = resp.json["data"][0]["id"]
        self.app.put_json(
            self.source_collection + f"/records/{update_id}",
            {"data": {"title": "Ave"}},
            headers=self.headers,
        )

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-rollback"}},
            headers=self.headers,
        )

        resp = self.app.get(
            self.source_collection + f"/records/{update_id}",
            headers=self.headers,
            status=200,
        )
        assert resp.json["data"]["title"] == "hello"

    def test_removes_created_records(self):
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-rollback"}},
            headers=self.headers,
        )

        self.app.get(
            self.source_collection + "/records/r1", headers=self.headers, status=404
        )
        self.app.get(
            self.source_collection + "/records/r2", headers=self.headers, status=404
        )

    def test_also_resets_changes_on_preview(self):
        resp = self.app.get(self.preview_collection + "/records", headers=self.headers)
        size_setup = len(resp.json["data"])
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.headers,
        )
        resp = self.app.get(self.preview_collection + "/records", headers=self.headers)
        size_before = len(resp.json["data"])
        assert size_setup != size_before

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-rollback"}},
            headers=self.headers,
        )

        resp = self.app.get(self.preview_collection + "/records", headers=self.headers)
        size_after = len(resp.json["data"])
        assert size_before != size_after
        assert size_setup == size_after

    def test_preview_signature_is_refreshed(self):
        resp = self.app.get(self.preview_collection, headers=self.headers)
        sign_before = resp.json["data"]["signature"]["signature"]

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-rollback"}},
            headers=self.headers,
        )

        resp = self.app.get(self.preview_collection, headers=self.headers)
        sign_after = resp.json["data"]["signature"]["signature"]
        assert sign_before != sign_after

    def test_does_not_recreate_tombstones(self):
        # Approve creation of r1 and r2.
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.headers,
        )
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.other_headers,
        )
        # Delete r1.
        self.app.delete(
            self.source_collection + "/records/r1",
            headers=self.headers,
        )
        # Approve deletion of r1.
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.headers,
        )
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.other_headers,
        )
        # Recreate r1.
        self.app.put_json(
            self.source_collection + "/records/r1",
            {"data": {"title": "Servus"}},
            headers=self.headers,
        )
        # Rollback.
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-rollback"}},
            headers=self.headers,
        )
        # r1 should be deleted again.
        self.app.get(
            self.source_collection + "/records/r1", headers=self.headers, status=404
        )
        self.app.get(
            self.preview_collection + "/records/r1", headers=self.headers, status=404
        )
        self.app.get(
            self.destination_collection + "/records/r1",
            headers=self.headers,
            status=404,
        )


class UserGroupsTest(SignoffWebTest, FormattedErrorMixin, unittest.TestCase):
    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super().get_app_settings(extras)
        return settings

    def setUp(self):
        super(UserGroupsTest, self).setUp()
        self.editor_headers = get_user_headers("edith:her")
        resp = self.app.get("/", headers=self.editor_headers)
        self.editor = resp.json["user"]["id"]

        self.editor_headers = get_user_headers("emo:billier")
        resp = self.app.get("/", headers=self.editor_headers)
        self.editor = resp.json["user"]["id"]

        self.reviewer_headers = get_user_headers("ray:weaver")
        resp = self.app.get("/", headers=self.reviewer_headers)
        self.reviewer = resp.json["user"]["id"]

        self.app.put_json(
            "/buckets/alice/groups/editors",
            {"data": {"members": [self.editor]}},
            headers=self.headers,
        )

        self.app.put_json(
            "/buckets/alice/groups/reviewers",
            {"data": {"members": [self.reviewer]}},
            headers=self.headers,
        )

    def test_only_editors_can_ask_to_review(self):
        resp = self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.reviewer_headers,
            status=403,
        )
        self.assertFormattedError(
            response=resp,
            code=403,
            errno=ERRORS.FORBIDDEN,
            error="Forbidden",
            message="Not in editors group",
        )

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.editor_headers,
        )

    def test_only_reviewers_can_ask_to_sign(self):
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.editor_headers,
        )

        resp = self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.editor_headers,
            status=403,
        )
        self.assertFormattedError(
            response=resp,
            code=403,
            errno=ERRORS.FORBIDDEN,
            error="Forbidden",
            message="Not in reviewers group",
        )

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.reviewer_headers,
        )


class SpecificUserGroupsTest(SignoffWebTest, FormattedErrorMixin, unittest.TestCase):
    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super().get_app_settings(extras)

        cls.source_collection1 = "/buckets/alice/collections/cid1"
        cls.source_collection2 = "/buckets/alice/collections/cid2"

        settings["kinto.signer.resources"] = "%s -> %s\n%s -> %s" % (
            cls.source_collection1,
            cls.source_collection1.replace("alice", "destination"),
            cls.source_collection2,
            cls.source_collection2.replace("alice", "destination"),
        )

        settings["signer.alice.cid1.editors_group"] = "editeurs"
        settings["signer.alice.cid1.reviewers_group"] = "revoyeurs"
        return settings

    def setUp(self):
        super(SpecificUserGroupsTest, self).setUp()

        self.app.put_json(self.source_collection1, headers=self.headers)
        self.app.put_json(self.source_collection2, headers=self.headers)

        self.someone_headers = get_user_headers("sam:wan")

        self.editor_headers = get_user_headers("emo:billier")
        resp = self.app.get("/", headers=self.editor_headers)
        self.editor = resp.json["user"]["id"]

        self.app.put_json(
            "/buckets/alice/groups/editeurs",
            {"data": {"members": [self.editor]}},
            headers=self.headers,
        )

    def test_editors_cannot_ask_to_review_if_not_specifically_configured(self):
        resp = self.app.patch_json(
            self.source_collection2,
            {"data": {"status": "to-review"}},
            headers=self.someone_headers,
            status=403,
        )
        self.assertFormattedError(
            response=resp,
            code=403,
            errno=ERRORS.FORBIDDEN,
            error="Forbidden",
            message="Not in editors group",
        )

    def test_only_specific_editors_can_ask_to_review(self):
        resp = self.app.patch_json(
            self.source_collection1,
            {"data": {"status": "to-review"}},
            headers=self.someone_headers,
            status=403,
        )
        self.assertFormattedError(
            response=resp,
            code=403,
            errno=ERRORS.FORBIDDEN,
            error="Forbidden",
            message="Not in editeurs group",
        )

    def test_only_reviewers_can_ask_to_sign(self):
        self.app.patch_json(
            self.source_collection1,
            {"data": {"status": "to-review"}},
            headers=self.editor_headers,
        )
        resp = self.app.patch_json(
            self.source_collection1,
            {"data": {"status": "to-sign"}},
            headers=self.editor_headers,
            status=403,
        )
        self.assertFormattedError(
            response=resp,
            code=403,
            errno=ERRORS.FORBIDDEN,
            error="Forbidden",
            message="Not in revoyeurs group",
        )


class PreviewCollectionTest(SignoffWebTest, unittest.TestCase):
    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super().get_app_settings(extras)

        cls.preview_bucket = "/buckets/preview"
        cls.preview_collection = cls.preview_bucket + "/collections/pcid"

        settings["signer.to_review_enabled"] = "true"
        settings["kinto.signer.resources"] = "%s -> %s -> %s" % (
            cls.source_collection,
            cls.preview_collection,
            cls.destination_collection,
        )
        return settings

    def test_the_preview_collection_is_updated_and_signed(self):
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.headers,
        )

        self.app.get(self.preview_bucket, headers=self.headers)

        resp = self.app.get(self.preview_collection, headers=self.headers)
        assert "signature" in resp.json["data"]

        resp = self.app.get(self.preview_collection + "/records", headers=self.headers)
        assert len(resp.json["data"]) == 2

    def test_the_preview_collection_receives_kinto_admin_ui_attributes(self):
        self.app.patch_json(
            self.source_collection,
            {
                "data": {
                    "status": "to-review",
                    "displayFields": ["age"],
                    "schema": {"type": "object"},
                }
            },
            headers=self.headers,
        )

        resp = self.app.get(self.preview_collection, headers=self.headers)
        assert resp.json["data"]["displayFields"] == ["age"]
        assert "schema" in resp.json["data"]

    def test_the_preview_collection_is_also_resigned(self):
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.headers,
        )
        resp = self.app.get(self.preview_collection, headers=self.headers)
        signature_preview_before = resp.json["data"]["signature"]
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.other_headers,
        )
        resp = self.app.get(self.destination_collection, headers=self.headers)
        signature_destination_before = resp.json["data"]["signature"]
        # status is signed.
        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["status"] == "signed"

        # Resign.
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-resign"}},
            headers=self.headers,
        )

        resp = self.app.get(self.destination_collection, headers=self.headers)
        signature_destination_after = resp.json["data"]["signature"]
        assert signature_destination_before != signature_destination_after
        resp = self.app.get(self.preview_collection, headers=self.headers)
        signature_preview_after = resp.json["data"]["signature"]
        assert signature_preview_before != signature_preview_after

    def test_the_preview_collection_is_emptied_when_source_records_are_deleted(self):
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.headers,
        )
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.other_headers,
        )

        resp = self.app.get(self.source_collection + "/records", headers=self.headers)
        records = resp.json["data"]
        for r in records:
            self.app.delete(
                self.source_collection + "/records/" + r["id"], headers=self.headers
            )
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.headers,
        )

        resp = self.app.get(self.preview_collection + "/records", headers=self.headers)
        records = resp.json["data"]
        assert len(records) == 0

    def test_the_preview_collection_is_emptied_when_source_is_deleted(self):
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.headers,
        )
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.other_headers,
        )

        self.app.delete(self.source_collection + "/records", headers=self.headers).json[
            "data"
        ]
        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.headers,
        )

        resp = self.app.get(self.preview_collection + "/records", headers=self.headers)
        records = resp.json["data"]
        assert len(records) == 0

    def test_last_editor_comment_are_reset_on_review(self):
        self.app.patch_json(
            self.source_collection,
            {
                "data": {
                    "last_editor_comment": "please check that",
                    "last_reviewer_comment": "looks good",
                }
            },
            headers=self.headers,
        )

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-review"}},
            headers=self.headers,
        )

        resp = self.app.get(self.source_collection, headers=self.headers)
        assert resp.json["data"]["last_editor_comment"] == ""


class CollectionDelete(SignoffWebTest, unittest.TestCase):
    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super().get_app_settings(extras)

        cls.source_bucket = "/buckets/source"
        cls.source_collection = cls.source_bucket + "/collections/cid"
        cls.preview_bucket = "/buckets/preview"
        cls.preview_collection = cls.preview_bucket + "/collections/cid"
        cls.destination_bucket = "/buckets/destination"
        cls.destination_collection = cls.destination_bucket + "/collections/cid"

        settings["signer.to_review_enabled"] = "true"
        settings["kinto.signer.resources"] = (
            "%s -> %s -> %s"
            % (cls.source_bucket, cls.preview_bucket, cls.destination_bucket)
            + "\n %s -> %s"
            % (
                cls.source_bucket + "/collections/no-preview",
                cls.destination_bucket + "/collections/no-preview",
            )
            + "\n /buckets/some-bucket -> /buckets/some-other"
        )
        return settings

    def setUp(self):
        super(CollectionDelete, self).setUp()

        self.app.put(
            self.source_bucket + "/collections/no-preview", headers=self.headers
        )
        self.app.put(
            self.destination_bucket + "/collections/extra", headers=self.headers
        )
        self.app.put(
            self.preview_bucket + "/collections/no-preview", headers=self.headers
        )

    def test_cannot_delete_preview_collection_if_used(self):
        self.app.delete(self.preview_collection, headers=self.headers, status=403)

    def test_cannot_delete_destination_collection_if_used(self):
        self.app.delete(self.destination_collection, headers=self.headers, status=403)
        self.app.delete(
            self.destination_bucket + "/collections/no-preview",
            headers=self.headers,
            status=403,
        )

    def test_can_delete_preview_if_source_is_deleted(self):
        self.app.delete(self.source_collection, headers=self.headers)
        self.app.delete(self.preview_collection, headers=self.headers)

    def test_can_delete_preview_if_unused(self):
        self.app.delete(
            self.preview_bucket + "/collections/no-preview", headers=self.headers
        )

    def test_can_delete_destination_if_unused(self):
        self.app.delete(
            self.destination_bucket + "/collections/extra", headers=self.headers
        )


class NoReviewTest(SignoffWebTest, unittest.TestCase):
    """
    If preview collection is set in config, we create it
    and copy the records there, even if review is disabled.
    """

    source_bucket = "/buckets/dev"
    source_collection = "/buckets/dev/collections/normandy"
    preview_bucket = "/buckets/stage"
    preview_collection = "/buckets/stage/collections/normandy"
    destination_bucket = "/buckets/prod"
    destination_collection = "/buckets/prod/collections/normandy"

    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super().get_app_settings(extras)

        # preview collection exists.
        settings["kinto.signer.resources"] = " -> ".join(
            (cls.source_bucket, cls.preview_bucket, cls.destination_bucket)
        )
        # dev/onecrl has review enabled.
        settings["signer.to_review_enabled"] = "true"
        # dev/normandy has review disabled.
        settings["signer.dev.normandy.to_review_enabled"] = "false"

        return settings

    def setUp(self):
        super().setUp()
        # Make the preview bucket readable (to obtain explicit 404 when collections
        # don't exist instead of ambiguous 403)
        self.app.put_json(
            self.preview_bucket,
            {"permissions": {"read": ["system.Everyone"]}},
            headers=self.headers,
        )
        self.app.put(self.source_bucket + "/collections/onecrl", headers=self.headers)
        self.app.put(self.source_collection, headers=self.headers)

    def test_the_preview_collection_is_created_when_review_enabled(self):
        self.app.get(self.preview_bucket + "/collections/onecrl", headers=self.headers)

    def test_the_preview_collection_is_created_when_review_disabled(self):
        self.app.get(self.preview_collection, headers=self.headers)

    def test_the_preview_collection_is_updated_when_review_enabled(self):
        before = len(
            self.app.get(
                self.preview_bucket + "/collections/onecrl/records",
                headers=self.headers,
            ).json["data"]
        )
        self.app.post_json(
            self.source_bucket + "/collections/onecrl/records",
            {"data": {"title": "Hallo"}},
            headers=self.headers,
        )

        self.app.patch_json(
            self.source_bucket + "/collections/onecrl",
            {"data": {"status": "to-review"}},
            headers=self.headers,
        )

        after = len(
            self.app.get(
                self.preview_bucket + "/collections/onecrl/records",
                headers=self.headers,
            ).json["data"]
        )
        assert after > before, "Preview was not updated when review enabled"

    def test_the_preview_collection_is_updated_when_review_disabled(self):
        before = len(
            self.app.get(
                self.preview_collection + "/records", headers=self.headers
            ).json["data"]
        )
        self.app.post_json(
            self.source_collection + "/records",
            {"data": {"title": "Hallo"}},
            headers=self.headers,
        )

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.headers,
        )

        after = len(
            self.app.get(
                self.preview_collection + "/records", headers=self.headers
            ).json["data"]
        )
        assert after > before, "Preview was not updated when review disabled"


class NoPreviewTest(SignoffWebTest, unittest.TestCase):
    """
    If preview collection is not set in config, we don't create it
    even if review is enabled.
    """

    source_bucket = "/buckets/dev"
    source_collection = "/buckets/dev/collections/normandy"
    preview_bucket = "/buckets/preview"
    destination_bucket = "/buckets/prod"
    destination_collection = "/buckets/prod/collections/normandy"

    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super().get_app_settings(extras)

        # No preview collection.
        settings["kinto.signer.resources"] = " -> ".join(
            (cls.source_bucket, cls.destination_bucket)
        )
        # dev/onecrl has review enabled.
        settings["signer.to_review_enabled"] = "true"
        # dev/normandy has review disabled.
        settings["signer.dev.normandy.to_review_enabled"] = "false"

        return settings

    def setUp(self):
        super().setUp()
        self.app.put(self.preview_bucket, headers=self.headers)
        self.app.put(self.source_bucket + "/collections/onecrl", headers=self.headers)
        self.app.put_json(self.source_collection, headers=self.headers)

    def test_the_preview_collection_is_not_created_when_review_enabled(self):
        self.app.get(
            self.preview_bucket + "/collections/onecrl",
            status=404,
            headers=self.headers,
        )

    def test_the_preview_collection_is_not_created_when_review_disabled(self):
        self.app.get(
            self.preview_bucket + "/collections/normandy",
            status=404,
            headers=self.headers,
        )

    def test_the_preview_collection_is_not_updated_when_review_enabled(self):
        self.app.post_json(
            self.source_bucket + "/collections/onecrl/records",
            {"data": {"title": "Hallo"}},
            headers=self.headers,
        )

        self.app.patch_json(
            self.source_bucket + "/collections/onecrl",
            {"data": {"status": "to-review"}},
            headers=self.headers,
        )

        # The preview still doesn't exist
        self.app.get(
            self.preview_bucket + "/collections/onecrl",
            status=404,
            headers=self.headers,
        )
        # Destination will updated on review approval.

    def test_the_preview_collection_is_not_updated_when_review_disabled(self):
        before = len(
            self.app.get(
                self.destination_collection + "/records", headers=self.headers
            ).json["data"]
        )
        self.app.post_json(
            self.source_collection + "/records",
            {"data": {"title": "Hallo"}},
            headers=self.headers,
        )

        self.app.patch_json(
            self.source_collection,
            {"data": {"status": "to-sign"}},
            headers=self.headers,
        )

        # The preview still doesn't exist
        self.app.get(
            self.preview_bucket + "/collections/normandy",
            status=404,
            headers=self.headers,
        )
        # And destination was updated.
        after = len(
            self.app.get(
                self.destination_collection + "/records", headers=self.headers
            ).json["data"]
        )
        assert after > before, "Destination was not updated when review enabled"


class PerBucketTest(SignoffWebTest, unittest.TestCase):
    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super().get_app_settings(extras)

        cls.source_bucket = "/buckets/stage"
        cls.source_collection = cls.source_bucket + "/collections/cid"
        cls.preview_bucket = "/buckets/preview"
        cls.preview_collection = cls.preview_bucket + "/collections/cid"
        cls.destination_bucket = "/buckets/prod"
        cls.destination_collection = cls.destination_bucket + "/collections/cid"

        settings["kinto.signer.resources"] = " -> ".join(
            [cls.source_bucket, cls.preview_bucket, cls.destination_bucket]
        )

        settings["signer.to_review_enabled"] = "true"
        settings["signer.stage.specific.to_review_enabled"] = "false"

        settings["signer.stage.specific.autograph.hawk_id"] = "for-specific"
        return settings

    def test_destination_and_preview_collections_are_created_and_signed(self):
        col_uri = "/collections/pim"
        self.app.put(self.source_bucket + col_uri, headers=self.headers)

        data = self.app.get(self.preview_bucket + col_uri, headers=self.headers).json[
            "data"
        ]
        assert "signature" in data

        data = self.app.get(
            self.destination_bucket + col_uri, headers=self.headers
        ).json["data"]
        assert "signature" in data

        # Source status was set to signed.
        data = self.app.get(self.source_bucket + col_uri, headers=self.headers).json[
            "data"
        ]
        assert data["status"] == "signed"

    def test_review_settings_can_be_overriden_for_a_specific_collection(self):
        # review is not enabled for this particular one, sign directly!
        self.app.put_json(
            self.source_bucket + "/collections/specific",
            {"data": {"status": "to-sign"}},
            headers=self.headers,
        )

    def test_signer_can_be_specified_per_collection(self):
        self.mocked_autograph.post.reset_mock()
        self.app.put_json(
            self.source_bucket + "/collections/specific",
            {"data": {"status": "to-sign"}},
            headers=self.headers,
        )

        args, kwargs = self.mocked_autograph.post.call_args_list[0]
        assert args[0].startswith("http://localhost:8000")  # global.
        assert kwargs["auth"].credentials["id"] == "for-specific"
        assert (
            kwargs["auth"].credentials["key"].startswith("fs5w")
        )  # global in signer.ini


class GroupCreationTest(PostgresWebTest, unittest.TestCase):
    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super().get_app_settings(extras)

        cls.source_bucket = "/buckets/stage"
        cls.preview_bucket = "/buckets/preview"
        cls.destination_bucket = "/buckets/prod"

        settings["signer.to_review_enabled"] = "true"

        settings["kinto.signer.editors_group"] = "best-editors"
        settings["kinto.signer.reviewers_group"] = "{collection_id}-reviewers"
        settings["kinto.signer.resources"] = ";".join(
            [cls.source_bucket, cls.preview_bucket, cls.destination_bucket]
        )

        cls.editors_group = cls.source_bucket + "/groups/best-editors"
        cls.reviewers_group = cls.source_bucket + "/groups/good-reviewers"
        cls.source_collection = cls.source_bucket + "/collections/good"

        return settings

    def setUp(self):
        super(GroupCreationTest, self).setUp()

        resp = self.app.get("/", headers=self.headers)
        self.userid = resp.json["user"]["id"]

        self.app.put(self.source_bucket, headers=self.headers)

        self.other_headers = get_user_headers("otra:persona")
        resp = self.app.get("/", headers=self.other_headers)
        self.other_userid = resp.json["user"]["id"]

    def test_groups_are_not_touched_if_existing(self):
        resp = self.app.put(self.editors_group, headers=self.headers)
        before = resp.json["data"]["last_modified"]

        self.app.put(self.source_collection, headers=self.headers)

        resp = self.app.get(self.editors_group, headers=self.headers)
        after = resp.json["data"]["last_modified"]

        assert before == after

    def test_groups_are_created_if_missing(self):
        self.app.get(self.editors_group, headers=self.headers, status=404)
        self.app.get(self.reviewers_group, headers=self.headers, status=404)

        self.app.put(self.source_collection, headers=self.headers)

        self.app.get(self.editors_group, headers=self.headers)
        self.app.get(self.reviewers_group, headers=self.headers)

    def test_groups_are_allowed_to_write_the_source_collection(self):
        body = {"data": {"members": [self.other_userid]}}
        self.app.put_json(self.editors_group, body, headers=self.headers)

        self.app.put(self.source_collection, headers=self.headers)

        self.app.post_json(
            self.source_collection + "/records", headers=self.other_headers, status=201
        )

    def test_events_are_sent(self):
        patch = mock.patch("kinto_remote_settings.signer.utils.notify_resource_event")
        mocked = patch.start()
        self.addCleanup(patch.stop)

        self.app.put(self.source_collection, headers=self.headers)

        args, kwargs = mocked.call_args_list[0]
        _, fakerequest = args
        assert fakerequest["method"] == "PUT"
        assert fakerequest["path"] == "/buckets/stage/groups/best-editors"
        assert kwargs["resource_name"] == "group"

    def test_groups_permissions_include_current_user_only(self):
        self.app.put(self.source_collection, headers=self.headers)

        r = self.app.get(self.editors_group, headers=self.headers).json
        assert r["permissions"]["write"] == [self.userid]
        r = self.app.get(self.reviewers_group, headers=self.headers).json
        assert r["permissions"]["write"] == [self.userid]

    def test_editors_contains_current_user_as_member_by_default(self):
        self.app.put(self.source_collection, headers=self.headers)

        r = self.app.get(self.editors_group, headers=self.headers).json
        assert r["data"]["members"] == [self.userid]
        r = self.app.get(self.reviewers_group, headers=self.headers).json
        assert r["data"]["members"] == []

    def test_groups_are_not_touched_if_already_exist(self):
        resp = self.app.put(self.editors_group, headers=self.headers)
        editors_timetamp = resp.json["data"]["last_modified"]
        resp = self.app.put(self.reviewers_group, headers=self.headers)
        reviewers_timetamp = resp.json["data"]["last_modified"]

        self.app.put(self.source_collection, headers=self.headers)

        r = self.app.get(self.editors_group, headers=self.headers).json
        assert r["data"]["last_modified"] == editors_timetamp
        r = self.app.get(self.reviewers_group, headers=self.headers).json
        assert r["data"]["last_modified"] == reviewers_timetamp

    def test_groups_are_not_created_if_not_allowed(self):
        # Allow this other user to create collections.
        body = {"permissions": {"collection:create": [self.other_userid]}}
        self.app.patch_json(self.source_bucket, body, headers=self.headers)

        # Create the collection.
        self.app.put(self.source_collection, headers=self.other_headers)

        # Groups were not created.
        self.app.get(self.editors_group, headers=self.headers, status=404)
        self.app.get(self.reviewers_group, headers=self.headers, status=404)

    def test_groups_are_created_if_allowed_via_group_create_perm(self):
        # Allow this other user to create collections and groups.
        body = {
            "permissions": {
                "collection:create": [self.other_userid],
                "group:create": [self.other_userid],
            }
        }
        self.app.patch_json(self.source_bucket, body, headers=self.headers)

        # Create the collection.
        self.app.put(self.source_collection, headers=self.other_headers)

        self.app.get(self.editors_group, headers=self.headers)
        self.app.get(self.reviewers_group, headers=self.headers)
