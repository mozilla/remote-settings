import datetime
import unittest
from unittest import mock

from kinto_remote_settings import __version__

from . import BaseWebTest

SAMPLE_RECORD = {"data": {"dev-edition": True}}
HOUR_AGO = int(datetime.datetime.now().timestamp() * 1000) - 3600


class UpdateChangesTest(BaseWebTest, unittest.TestCase):
    changes_uri = "/buckets/monitor/collections/changes/records"
    records_uri = "/buckets/blocklists/collections/certificates/records"

    def setUp(self):
        super(UpdateChangesTest, self).setUp()
        self.app.post_json(self.records_uri, SAMPLE_RECORD, headers=self.headers)

    def test_parent_bucket_and_collection_dont_have_to_exist(self):
        self.app.delete(
            "/buckets/monitor/collections/changes",
            headers=self.headers,
            status=(403, 404),
        )
        self.app.get(self.changes_uri)  # Not failing
        self.app.delete("/buckets/monitor", headers=self.headers, status=(403, 404))
        self.app.get(self.changes_uri)  # Not failing

    def test_parent_bucket_and_collection_can_exist(self):
        self.app.put("/buckets/monitor", headers=self.headers)
        resp = self.app.get(self.changes_uri)  # Not failing
        self.assertEqual(len(resp.json["data"]), 1)

        self.app.put("/buckets/monitor/collections/changes", headers=self.headers)
        resp = self.app.get(self.changes_uri)  # Not failing
        self.assertEqual(len(resp.json["data"]), 1)

    def test_a_change_record_is_updated_per_bucket_collection(self):
        resp = self.app.get(self.changes_uri)
        before_timestamp = resp.json["data"][0]["last_modified"]
        before_id = resp.json["data"][0]["id"]

        self.app.post_json(self.records_uri, SAMPLE_RECORD, headers=self.headers)

        resp = self.app.get(self.changes_uri)

        after_timestamp = resp.json["data"][0]["last_modified"]
        after_id = resp.json["data"][0]["id"]
        self.assertEqual(before_id, after_id)
        self.assertNotEqual(before_timestamp, after_timestamp)

    def test_only_collections_specified_in_settings_are_monitored(self):
        resp = self.app.get(self.changes_uri, headers=self.headers)
        change_record = resp.json["data"][0]
        records_uri = "/buckets/default/collections/certificates/records"

        self.app.post_json(records_uri, SAMPLE_RECORD, headers=self.headers)

        resp = self.app.get(self.changes_uri, headers=self.headers)
        after = resp.json["data"][0]
        self.assertEqual(change_record["id"], after["id"])
        self.assertEqual(change_record["last_modified"], after["last_modified"])

    def test_the_resource_configured_can_be_a_collection_uri(self):
        with mock.patch.dict(
            self.app.app.registry.settings,
            [("changes.resources", "/buckets/blocklists/collections/certificates")],
        ):
            resp = self.app.get(self.changes_uri)
        self.assertEqual(len(resp.json["data"]), 1)

    def test_returns_304_if_no_change_occured(self):
        resp = self.app.get(self.changes_uri)
        before_timestamp = resp.headers["ETag"]
        self.app.get(
            self.changes_uri, headers={"If-None-Match": before_timestamp}, status=304
        )

    def test_returns_412_with_if_none_match_star(self):
        self.app.get(self.changes_uri, headers={"If-None-Match": "*"}, status=412)

    def test_no_cache_control_is_returned_if_not_configured(self):
        resp = self.app.get(self.changes_uri)
        assert "max-age" not in resp.headers["Cache-Control"]

        resp = self.app.get(self.changes_uri + '?_expected="42"')
        assert "max-age" not in resp.headers["Cache-Control"]

    def test_returns_empty_list_if_no_resource_configured(self):
        with mock.patch.dict(
            self.app.app.registry.settings, [("changes.resources", "")]
        ):
            resp = self.app.get(self.changes_uri)
        self.assertEqual(resp.json["data"], [])

    def test_change_record_has_greater_last_modified_of_collection_of_records(self):
        resp = self.app.post_json(self.records_uri, SAMPLE_RECORD, headers=self.headers)
        last_modified = resp.json["data"]["last_modified"]
        resp = self.app.get(self.changes_uri, headers=self.headers)
        change_last_modified = resp.json["data"][0]["last_modified"]
        self.assertGreaterEqual(change_last_modified, last_modified)

    def test_record_with_old_timestamp_does_update_changes(self):
        resp = self.app.post_json(self.records_uri, SAMPLE_RECORD, headers=self.headers)
        old_record = SAMPLE_RECORD.copy()
        old_record["data"]["last_modified"] = 42
        self.app.post_json(self.records_uri, old_record, headers=self.headers)

        resp = self.app.get(self.changes_uri, headers=self.headers)
        change_last_modified = resp.json["data"][0]["last_modified"]
        self.assertNotEqual(change_last_modified, 42)

    def test_change_record_has_server_host_attribute(self):
        self.app.post_json(self.records_uri, SAMPLE_RECORD, headers=self.headers)

        resp = self.app.get(self.changes_uri, headers=self.headers)
        change = resp.json["data"][0]
        self.assertEqual(change["host"], "www.kinto-storage.org")

    def test_change_record_has_bucket_and_collection_attributes(self):
        self.app.post_json(self.records_uri, SAMPLE_RECORD, headers=self.headers)

        resp = self.app.get(self.changes_uri, headers=self.headers)
        change = resp.json["data"][0]
        self.assertEqual(change["bucket"], "blocklists")
        self.assertEqual(change["collection"], "certificates")

    def test_changes_capability_exposed(self):
        resp = self.app.get("/")
        capabilities = resp.json["capabilities"]
        self.assertIn("changes", capabilities)
        expected = {
            "description": "Track modifications of records in Kinto and store "
            "the collection timestamps into a specific bucket "
            "and collection.",
            "collections": ["/buckets/blocklists"],
            "url": "http://kinto.readthedocs.io/en/latest/tutorials/"
            "synchronisation.html#polling-for-remote-changes",
            "version": __version__,
        }
        self.assertEqual(expected, capabilities["changes"])


class CacheExpiresTest(BaseWebTest, unittest.TestCase):
    changes_uri = "/buckets/monitor/collections/changes/records"

    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super().get_app_settings(extras)
        settings["monitor.changes.record_cache_expires_seconds"] = "60"
        settings["monitor.changes.record_cache_maximum_expires_seconds"] = "3600"
        return settings

    def test_cache_expires_headers_are_supported(self):
        resp = self.app.get(self.changes_uri)
        assert "max-age=60" in resp.headers["Cache-Control"]

    def test_cache_expires_header_is_maximum_with_cache_busting(self):
        resp = self.app.get(self.changes_uri + f"?_since={HOUR_AGO}&_expected=42")
        assert "max-age=3600" in resp.headers["Cache-Control"]

    def test_cache_expires_header_is_default_with_filter(self):
        # The _since just filters on lower bound of timestamps, if data changes
        # we don't want to cache for too long.
        resp = self.app.get(self.changes_uri + f"?_since={HOUR_AGO}")
        assert "max-age=60" in resp.headers["Cache-Control"]

    def test_cache_expires_header_is_default_with_concurrency_control(self):
        # The `If-None-Match` header is just a way to obtain a 304 instead of a 200
        # with an empty list. In the client code [0] it is always used in conjonction
        # with _since={last-etag}
        # [0] https://searchfox.org/mozilla-central/rev/93905b66/services/settings/Utils.jsm#70-73 # noqa: 501
        headers = {"If-None-Match": f'"{HOUR_AGO}"'}
        resp = self.app.get(self.changes_uri + f'?_since="{HOUR_AGO}"', headers=headers)
        assert "max-age=60" in resp.headers["Cache-Control"]


class OldSinceRedirectTest(BaseWebTest, unittest.TestCase):
    changes_uri = "/buckets/monitor/collections/changes/records"

    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super().get_app_settings(extras)
        settings["kinto.changes.since_max_age_days"] = "2"
        settings["kinto.changes.http_host"] = "cdn-host"
        return settings

    def test_redirects_and_drops_since_if_too_old(self):
        resp = self.app.get(self.changes_uri + "?_since=42")
        self.assertEqual(resp.status_code, 307)
        self.assertEqual(
            resp.headers["Location"],
            "https://cdn-host/v1/buckets/monitor/collections/changes/records",
        )

        # Try again with a real timestamp older than allowed in settings.
        timestamp = int(
            (datetime.datetime.now() - datetime.timedelta(days=3)).timestamp() * 1000
        )
        resp = self.app.get(self.changes_uri + f"?_since={timestamp}")
        self.assertEqual(resp.status_code, 307)

    def test_redirects_keep_other_querystring_params(self):
        resp = self.app.get(self.changes_uri + "?_since=42&_expected=%22123456%22")
        self.assertEqual(resp.status_code, 307)
        self.assertIn("/records?_expected=%22123456%22", resp.headers["Location"])

    def test_does_not_redirect_if_not_old_enough(self):
        timestamp = int(
            (datetime.datetime.now() - datetime.timedelta(days=1)).timestamp() * 1000
        )
        resp = self.app.get(self.changes_uri + f"?_since={timestamp}")
        self.assertEqual(resp.status_code, 200)

    def test_redirects_sends_cache_control(self):
        response = self.app.get(self.changes_uri + "?_since=42")
        self.assertEqual(response.status_code, 307)
        self.assertIn("Expires", response.headers)
        self.assertIn("Cache-Control", response.headers)
        self.assertEqual(response.headers["Cache-Control"], "max-age=86400")
