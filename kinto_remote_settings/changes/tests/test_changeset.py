import unittest
from unittest import mock

from kinto.core.storage import exceptions as storage_exceptions
from kinto.core.testing import get_user_headers

from . import BaseWebTest

SAMPLE_RECORD = {"data": {"dev-edition": True}}


class ChangesetViewTest(BaseWebTest, unittest.TestCase):
    records_uri = "/buckets/blocklists/collections/certificates/records"
    changeset_uri = (
        "/buckets/blocklists/collections/certificates/changeset?_expected=42"
    )

    def setUp(self):
        super(ChangesetViewTest, self).setUp()
        self.app.post_json(self.records_uri, SAMPLE_RECORD, headers=self.headers)

    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super().get_app_settings(extras)
        settings["blocklists.certificates.record_cache_expires_seconds"] = 1234
        return settings

    def test_changeset_is_accessible(self):
        resp = self.app.head(self.records_uri, headers=self.headers)
        records_timestamp = int(resp.headers["ETag"][1:-1])

        resp = self.app.get(self.changeset_uri, headers=self.headers)
        data = resp.json

        assert "metadata" in data
        assert "timestamp" in data
        assert "changes" in data
        assert data["metadata"]["id"] == "certificates"
        assert len(data["changes"]) == 1
        assert data["changes"][0]["dev-edition"] is True
        assert data["timestamp"] == records_timestamp

    def test_changeset_can_be_filtered(self):
        resp = self.app.post_json(self.records_uri, {}, headers=self.headers)
        before = resp.json["data"]["last_modified"]
        self.app.post_json(self.records_uri, {}, headers=self.headers)

        resp = self.app.get(self.changeset_uri, headers=self.headers)
        assert len(resp.json["changes"]) == 3

        resp = self.app.get(
            self.changeset_uri + f'&_since="{before}"', headers=self.headers
        )
        assert len(resp.json["changes"]) == 1

    def test_tombstones_are_returned(self):
        resp = self.app.get(self.records_uri, headers=self.headers)
        before = resp.headers["ETag"]
        # Delete one record.
        self.app.delete(self.records_uri + "?_limit=1", headers=self.headers)

        resp = self.app.get(
            self.changeset_uri + f"&_since={before}", headers=self.headers
        )

        assert len(resp.json["changes"]) == 1
        assert "deleted" in resp.json["changes"][0]

    def test_changeset_is_not_publicly_accessible(self):
        # By default other users cannot read.
        user_headers = {
            **self.headers,
            **get_user_headers("some-user"),
        }
        self.app.get(self.changeset_uri, status=401)
        self.app.get(self.changeset_uri, headers=user_headers, status=403)

        # Add read permissions to everyone.
        self.app.patch_json(
            "/buckets/blocklists",
            {"permissions": {"read": ["system.Everyone"]}},
            headers=self.headers,
        )

        self.app.get(self.changeset_uri, headers=user_headers, status=200)
        self.app.get(self.changeset_uri, status=200)

    def test_changeset_returns_404_if_collection_is_unknown(self):
        changeset_uri = "/buckets/blocklists/collections/fjuvrb/changeset?_expected=42"
        self.app.get(changeset_uri, headers=self.headers, status=404)

    def test_timestamp_is_validated(self):
        self.app.get(
            self.changeset_uri + "&_since=abc", headers=self.headers, status=400
        )
        self.app.get(
            self.changeset_uri + "&_since=42", headers=self.headers, status=400
        )
        self.app.get(
            self.changeset_uri + "&_since=*)(!(objectClass=*)",
            headers=self.headers,
            status=400,
        )
        self.app.get(self.changeset_uri + '&_since="42"', headers=self.headers)

    def test_expected_param_is_mandatory(self):
        self.app.get(self.changeset_uri.split("?")[0], headers=self.headers, status=400)

    def test_limit_is_supported(self):
        self.app.post_json(self.records_uri, {}, headers=self.headers)

        resp = self.app.get(self.changeset_uri + "&_limit=1", headers=self.headers)
        assert len(resp.json["changes"]) == 1

    def test_extra_param_is_allowed(self):
        self.app.get(self.changeset_uri + "&_extra=abc", headers=self.headers)

    def test_cache_control_headers_are_set(self):
        resp = self.app.get(self.changeset_uri, headers=self.headers)
        assert resp.headers["Cache-Control"] == "max-age=1234"

    def test_raises_original_backend_errors(self):
        backend = self.app.app.registry.storage
        with mock.patch.object(backend, "resource_timestamp") as mocked:
            mocked.side_effect = storage_exceptions.BackendError
            changeset_uri = (
                "/buckets/blocklists/collections/certificates/changeset?_expected=42"
            )
            self.app.get(changeset_uri, headers=self.headers, status=503)


class ReadonlyTest(BaseWebTest, unittest.TestCase):
    changeset_uri = "/buckets/monitor/collections/changes/changeset?_expected=42"

    def setUp(self):
        super().setUp()
        # Mark storage as readonly.
        # We can't do it from test app settings because we need
        # the initial bucket and collection).
        self.app.app.registry.storage.readonly = True

    def test_changeset_returns_404_if_collection_is_unknown(self):
        changeset_uri = "/buckets/blocklists/collections/fjuvrb/changeset?_expected=42"
        self.app.get(changeset_uri, headers=self.headers, status=404)


class MonitorChangesetViewTest(BaseWebTest, unittest.TestCase):
    records_uri = "/buckets/blocklists/collections/{cid}/records"
    changeset_uri = "/buckets/monitor/collections/changes/changeset?_expected=42"

    def setUp(self):
        super().setUp()
        self.create_collection("blocklists", "cfr")
        self.app.post_json(
            self.records_uri.format(cid="cfr"), SAMPLE_RECORD, headers=self.headers
        )
        self.app.post_json(
            self.records_uri.format(cid="certificates"),
            SAMPLE_RECORD,
            headers=self.headers,
        )

    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super().get_app_settings(extras)
        settings["kinto.changes.since_max_age_days"] = 1
        return settings

    def test_changeset_exists_for_monitor_changes(self):
        resp = self.app.head(
            self.records_uri.format(cid="certificates"), headers=self.headers
        )
        records_timestamp = int(resp.headers["ETag"].strip('"'))

        resp = self.app.get(self.changeset_uri)
        data = resp.json

        assert data["timestamp"] == records_timestamp
        assert len(data["changes"]) == 2
        assert data["changes"][0]["collection"] == "certificates"

    def test_changeset_redirects_if_since_is_too_old(self):
        resp = self.app.get(self.changeset_uri + '&_since="42"')

        assert resp.status_code == 307
        assert resp.headers["Location"] == (
            "https://www.kinto-storage.org/v1"
            "/buckets/monitor/collections/changes/changeset?_expected=42"
        )

    def test_limit_is_supported(self):
        resp = self.app.get(self.changeset_uri + "&_limit=1", headers=self.headers)
        assert len(resp.json["changes"]) == 1

    def test_filter_by_collection(self):
        resp = self.app.get(
            self.changeset_uri + "&bucket=blocklists&collection=cfr",
            headers=self.headers,
        )
        assert len(resp.json["changes"]) == 1
