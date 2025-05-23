import datetime
import os
import unittest
import uuid
from unittest import mock

from kinto import main as kinto_main
from kinto.core.events import ResourceChanged
from kinto_remote_settings import __version__
from kinto_remote_settings.signer import includeme, utils
from kinto_remote_settings.signer.backends.autograph import AutographSigner
from kinto_remote_settings.signer.listeners import sign_collection_data
from pyramid import testing
from requests import exceptions as requests_exceptions

from .support import BaseWebTest, get_user_headers


class HelloViewTest(BaseWebTest, unittest.TestCase):
    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super().get_app_settings(extras)
        settings["signer.alice.source.to_review_enabled"] = "true"
        settings["signer.stage.normandy.to_review_enabled"] = "false"
        return settings

    def test_capability_is_exposed(self):
        self.maxDiff = None
        resp = self.app.get("/")
        capabilities = resp.json["capabilities"]
        assert "signer" in capabilities
        expected = {
            "description": "Digital signatures for integrity and authenticity of records.",
            "url": "https://github.com/mozilla/remote-settings/tree/main/kinto-remote-settings",
            "version": __version__,
            "group_check_enabled": True,
            "to_review_enabled": False,
            "editors_group": "{collection_id}-editors",
            "reviewers_group": "{collection_id}-reviewers",
            "resources": [
                {
                    "destination": {"bucket": "alice", "collection": "destination"},
                    "source": {"bucket": "alice", "collection": "source"},
                    "to_review_enabled": True,
                },
                {
                    "destination": {"bucket": "alice", "collection": "to"},
                    "preview": {"bucket": "alice", "collection": "preview"},
                    "source": {"bucket": "alice", "collection": "from"},
                },
                {
                    "destination": {"bucket": "bob", "collection": "destination"},
                    "source": {"bucket": "bob", "collection": "source"},
                },
                {
                    "source": {"bucket": "stage", "collection": None},
                    "preview": {"bucket": "preview", "collection": None},
                    "destination": {"bucket": "prod", "collection": None},
                },
                {
                    "destination": {"bucket": "main", "collection": None},
                    "preview": {"bucket": "main-preview", "collection": None},
                    "source": {"bucket": "main-workspace", "collection": None},
                },
                {
                    "destination": {"bucket": "security-state", "collection": "onecrl"},
                    "source": {
                        "bucket": "security-state-workspace",
                        "collection": "onecrl",
                    },
                },
                {
                    "source": {"bucket": "stage", "collection": "normandy"},
                    "preview": {"bucket": "preview", "collection": "normandy"},
                    "destination": {"bucket": "prod", "collection": "normandy"},
                },
            ],
        }
        assert expected == capabilities["signer"]


class HeartbeatTest(BaseWebTest, unittest.TestCase):
    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super().get_app_settings(extras)
        settings["kinto.signer.autograph.server_url"] = "https://test.com"
        return settings

    def setUp(self):
        req_patch = mock.patch(
            "kinto_remote_settings.signer.backends.autograph.requests"
        )
        self.request_mock = req_patch.start()
        self.addCleanup(req_patch.stop)
        self.signature = {"signature": "", "x5u": "", "mode": "", "ref": "abc"}
        self.request_mock.post.return_value.json.return_value = [self.signature]

        fetch_cert_patch = mock.patch(
            "kinto_remote_settings.signer.backends.autograph.fetch_cert"
        )
        self.fetch_cert_mock = fetch_cert_patch.start()
        self.addCleanup(fetch_cert_patch.stop)
        utcnow = datetime.datetime.now(datetime.timezone.utc)
        next_year = utcnow + datetime.timedelta(days=365)
        fake_cert = mock.MagicMock(not_valid_before=utcnow, not_valid_after=next_year)
        self.fetch_cert_mock.return_value = fake_cert

    def test_heartbeat_is_exposed(self):
        resp = self.app.get("/__heartbeat__")
        assert "signer" in resp.json

    def test_heartbeat_fails_if_unreachable(self):
        self.request_mock.post.side_effect = requests_exceptions.ConnectTimeout()
        resp = self.app.get("/__heartbeat__", status=503)
        assert resp.json["signer"] is False

    def test_heartbeat_fails_if_missing_attributes(self):
        invalid = self.signature.copy()
        invalid.pop("signature")
        self.request_mock.post.return_value.json.return_value = [invalid]
        resp = self.app.get("/__heartbeat__", status=503)
        assert resp.json["signer"] is False

    def test_heartbeat_warns_if_certificate_expires_soon(self):
        utcnow = datetime.datetime.now(datetime.timezone.utc)
        thousands_days_ago = utcnow - datetime.timedelta(days=1000)
        in_ten_days = utcnow + datetime.timedelta(days=10)
        fake_cert = mock.MagicMock(
            not_valid_before=thousands_days_ago, not_valid_after=in_ten_days
        )
        self.fetch_cert_mock.return_value = fake_cert

        with mock.patch(
            "kinto_remote_settings.signer.backends.autograph.logger"
        ) as mocked_logger:
            resp = self.app.get("/__heartbeat__")

        assert resp.json["signer"] is True
        mocked_logger.warning.assert_called_with(
            "Only %s days before Autograph certificate expires (%s)", 9, in_ten_days
        )

    def test_heartbeat_warns_if_certificate_expires_on_clamped_limit(self):
        utcnow = datetime.datetime.now(datetime.timezone.utc)
        thousands_days_ago = utcnow - datetime.timedelta(days=1000)
        in_thirty_days = utcnow + datetime.timedelta(days=30)
        fake_cert = mock.MagicMock(
            not_valid_before=thousands_days_ago, not_valid_after=in_thirty_days
        )
        self.fetch_cert_mock.return_value = fake_cert

        with mock.patch(
            "kinto_remote_settings.signer.backends.autograph.logger"
        ) as mocked_logger:
            resp = self.app.get("/__heartbeat__")

        assert resp.json["signer"] is True
        mocked_logger.warning.assert_called_with(
            "Only %s days before Autograph certificate expires (%s)", 29, in_thirty_days
        )

    def test_heartbeat_succeeds_if_certificates_expires_before_threshold(self):
        utcnow = datetime.datetime.now(datetime.timezone.utc)
        thousands_days_ago = utcnow - datetime.timedelta(days=1000)
        in_thirty_one_days = utcnow + datetime.timedelta(days=32)
        fake_cert = mock.MagicMock(
            not_valid_before=thousands_days_ago, not_valid_after=in_thirty_one_days
        )
        self.fetch_cert_mock.return_value = fake_cert

        resp = self.app.get("/__heartbeat__", status=200)
        assert resp.json["signer"] is True


class IncludeMeTest(unittest.TestCase):
    def includeme(self, settings):
        config = testing.setUp(settings=settings)
        kinto_main(None, config=config)
        includeme(config)
        return config

    def test_defines_a_signer_per_bucket(self):
        settings = {
            "signer.resources": (
                "/buckets/sb1/collections/sc1 -> /buckets/db1/collections/dc1\n"
            ),
            "signer.sb1.signer_backend": "kinto_remote_settings.signer.backends.local_ecdsa",
            "signer.sb1.ecdsa.public_key": "/path/to/key",
            "signer.sb1.ecdsa.private_key": "/path/to/private",
        }
        config = self.includeme(settings)
        (signer,) = config.registry.signers.values()
        assert signer.public_key == "/path/to/key"

    def test_includeme_doesnt_fail_when_expanding_collection(self):
        settings = {
            "signer.resources": (
                "/buckets/sb1 -> /buckets/db1\n/buckets/sb2 -> /buckets/db2\n"
            ),
            "signer.signer_backend": "kinto_remote_settings.signer.backends.local_ecdsa",
            "signer.ecdsa.public_key": "/path/to/key",
            "signer.ecdsa.private_key": "/path/to/private",
            "signer.sb1.sc1.signer_backend": "kinto_remote_settings.signer.backends.local_ecdsa",
            "signer.sb1.sc1.ecdsa.public_key": "/path/to/key",
            "signer.sb1.sc1.ecdsa.private_key": "/path/to/private",
        }
        self.includeme(settings)

    def test_includeme_sanitizes_exposed_settings(self):
        settings = {
            "signer.resources": (
                "/buckets/sb1 -> /buckets/db1\n/buckets/sb2 -> /buckets/db2\n"
            ),
            "signer.signer_backend": "kinto_remote_settings.signer.backends.local_ecdsa",
            "signer.ecdsa.public_key": "/path/to/key",
            "signer.ecdsa.private_key": "/path/to/private",
            "signer.sb1.sc1.signer_backend": "kinto_remote_settings.signer.backends.local_ecdsa",
            "signer.sb1.sc1.ecdsa.public_key": "/path/to/key",
            "signer.sb1.sc1.ecdsa.private_key": "/path/to/private",
            "signer.sb2.signer_backend": "kinto_remote_settings.signer.backends.local_ecdsa",
            "signer.sb2.ecdsa.public_key": "/path/to/key",
            "signer.sb2.ecdsa.private_key": "/path/to/private",
        }
        config = self.includeme(settings)
        all_capabilities = config.registry.api_capabilities
        capabilities = all_capabilities["signer"]
        for resource in capabilities["resources"]:
            assert "ecdsa.private_key" not in resource
            assert "private_key" not in resource

    def test_defines_a_signer_per_bucket_and_collection(self):
        settings = {
            "signer.resources": (
                "/buckets/sb1/collections/sc1 -> /buckets/db1/collections/dc1\n"
                "/buckets/sb1/collections/sc2 -> /buckets/db1/collections/dc2"
            ),
            "signer.sb1.signer_backend": "kinto_remote_settings.signer.backends.local_ecdsa",
            "signer.sb1.ecdsa.public_key": "/path/to/key",
            "signer.sb1.ecdsa.private_key": "/path/to/private",
            "signer.sb1.sc1.signer_backend": "kinto_remote_settings.signer.backends.autograph",
            "signer.sb1.sc1.autograph.server_url": "http://localhost",
            "signer.sb1.sc1.autograph.hawk_id": "alice",
            "signer.sb1.sc1.autograph.hawk_secret": "a-secret",
        }
        config = self.includeme(settings)
        signer1, signer2 = config.registry.signers.values()
        if isinstance(signer1, AutographSigner):
            signer1, signer2 = signer2, signer1
        assert signer1.public_key == "/path/to/key"
        assert signer2.server_url == "http://localhost"

    def test_falls_back_to_global_settings_if_not_defined(self):
        settings = {
            "signer.resources": (
                "/buckets/sb1/collections/sc1 -> /buckets/db1/collections/dc1\n"
                "/buckets/sb1/collections/sc2 -> /buckets/db1/collections/dc2"
            ),
            "signer.signer_backend": "kinto_remote_settings.signer.backends.autograph",
            "signer.autograph.server_url": "http://localhost",
            "signer.sb1.autograph.hawk_id": "bob",
            "signer.sb1.autograph.hawk_secret": "a-secret",
            "signer.sb1.sc1.autograph.hawk_id": "alice",
            "signer.sb1.sc1.autograph.hawk_secret": "a-secret",
        }
        config = self.includeme(settings)

        signer1 = config.registry.signers["/buckets/sb1/collections/sc1"]
        assert isinstance(signer1, AutographSigner)
        assert signer1.server_url == "http://localhost"
        assert signer1.auth.credentials["id"] == "alice"

        signer2 = config.registry.signers["/buckets/sb1/collections/sc2"]
        assert isinstance(signer2, AutographSigner)
        assert signer2.server_url == "http://localhost"
        assert signer2.auth.credentials["id"] == "bob"

    def test_a_metrics_timer_is_used_for_signature_if_configured(self):
        settings = {
            "statsd_url": "udp://127.0.0.1:8125",
            "signer.resources": (
                "/buckets/sb1/collections/sc1 -> /buckets/db1/collections/dc1"
            ),
            "signer.ecdsa.public_key": "/path/to/key",
            "signer.ecdsa.private_key": "/path/to/private",
        }

        config = self.includeme(settings)

        payload = dict(resource_name="collection", action="update", bucket_id="foo")
        event = ResourceChanged(
            payload=payload, impacted_objects=[], request=mock.MagicMock()
        )

        with mock.patch.object(config.registry.metrics, "timer") as mocked:
            config.registry.notify(event)

            mocked.assert_called_with("plugins.signer.seconds")


class ConfigFromEnvironment(BaseWebTest, unittest.TestCase):
    def test_settings_are_read_from_environment_variables(self):
        with mock.patch.dict(
            os.environ,
            {
                "KINTO_SIGNER_RESOURCES": "/buckets/ready -> /buckets/steady -> /buckets/go",
                "KINTO_SIGNER_READY_TO_REVIEW_ENABLED": "true",
            },
        ):
            app = self.make_app()

        resp = app.get("/")
        signer_caps = resp.json["capabilities"]["signer"]

        assert not signer_caps["to_review_enabled"]
        assert signer_caps["resources"][0] == {
            "to_review_enabled": True,
            "source": {
                "bucket": "ready",
                "collection": None,
            },
            "preview": {"bucket": "steady", "collection": None},
            "destination": {"bucket": "go", "collection": None},
        }


class OnCollectionChangedTest(unittest.TestCase):
    def setUp(self):
        patch = mock.patch("kinto_remote_settings.signer.listeners.LocalUpdater")
        self.updater_mocked = patch.start()
        self.addCleanup(patch.stop)

    def test_nothing_happens_when_resource_is_not_configured(self):
        evt = mock.MagicMock(
            payload={"action": "update", "bucket_id": "a", "collection_id": "b"}
        )
        sign_collection_data(
            evt, resources=utils.parse_resources("c/d -> e/f"), to_review_enabled=True
        )
        assert not self.updater_mocked.called

    def test_nothing_happens_when_status_is_not_to_sign(self):
        evt = mock.MagicMock(
            payload={"action": "update", "bucket_id": "a", "collection_id": "b"},
            impacted_objects=[{"new": {"id": "b", "status": "signed"}}],
        )
        sign_collection_data(
            evt, resources=utils.parse_resources("a/b -> c/d"), to_review_enabled=True
        )
        assert not self.updater_mocked.sign_and_update_destination.called

    def test_updater_is_called_when_resource_and_status_matches(self):
        evt = mock.MagicMock(
            payload={"action": "update", "bucket_id": "a", "collection_id": "b"},
            impacted_objects=[{"new": {"id": "b", "status": "to-sign"}}],
        )
        evt.request.registry.storage = mock.sentinel.storage
        evt.request.registry.permission = mock.sentinel.permission
        evt.request.registry.signers = {
            "/buckets/a/collections/b": mock.sentinel.signer
        }
        evt.request.route_path.return_value = "/v1/buckets/a/collections/b"
        sign_collection_data(
            evt, resources=utils.parse_resources("a/b -> c/d"), to_review_enabled=True
        )
        self.updater_mocked.assert_called_with(
            signer=mock.sentinel.signer,
            storage=mock.sentinel.storage,
            permission=mock.sentinel.permission,
            source={"bucket": "a", "collection": "b"},
            destination={"bucket": "c", "collection": "d"},
        )

        mocked = self.updater_mocked.return_value
        assert mocked.sign_and_update_destination.called

    def test_kinto_attachment_property_is_set_to_allow_metadata_updates(self):
        evt = mock.MagicMock(
            payload={"action": "update", "bucket_id": "a", "collection_id": "b"},
            impacted_objects=[{"new": {"id": "b", "status": "to-sign"}}],
        )
        evt.request.registry.storage = mock.sentinel.storage
        evt.request.registry.permission = mock.sentinel.permission
        evt.request.registry.signers = {
            "/buckets/a/collections/b": mock.sentinel.signer
        }
        evt.request.route_path.return_value = "/v1/buckets/a/collections/b"
        sign_collection_data(
            evt, resources=utils.parse_resources("a/b -> c/d"), to_review_enabled=True
        )
        assert evt.request._attachment_auto_save is True

    def test_updater_does_not_fail_when_payload_is_inconsistent(self):
        # This happens with events on default bucket for kinto < 3.3
        evt = mock.MagicMock(
            payload={"action": "update", "subpath": "collections/boom"}
        )
        sign_collection_data(
            evt, resources=utils.parse_resources("a/b -> c/d"), to_review_enabled=True
        )


class PatchAutographMixin:
    def setUp(self):
        super().setUp()
        # Patch calls to Autograph.
        patch = mock.patch("kinto_remote_settings.signer.backends.autograph.requests")
        mocked = patch.start()
        self.addCleanup(patch.stop)
        mocked.post.return_value.json.side_effect = lambda: [
            {
                "signature": uuid.uuid4().hex,
                "hash_algorithm": "",
                "signature_encoding": "",
                "content-signature": "",
                "x5u": "",
                "ref": "",
            }
        ]


class BatchTest(BaseWebTest, PatchAutographMixin, unittest.TestCase):
    def setUp(self):
        super(BatchTest, self).setUp()
        self.headers = get_user_headers("me")

        resp = self.app.get("/", headers=self.headers)
        self.userid = resp.json["user"]["id"]

        self.app.put_json("/buckets/alice", headers=self.headers)
        self.app.put_json("/buckets/bob", headers=self.headers)

        self.app.put_json(
            "/buckets/alice/groups/source-reviewers",
            {"data": {"members": [self.userid]}},
            headers=self.headers,
        )
        self.app.put_json(
            "/buckets/alice/groups/from-reviewers",
            {"data": {"members": [self.userid]}},
            headers=self.headers,
        )
        self.app.put_json(
            "/buckets/bob/groups/source-reviewers",
            {"data": {"members": [self.userid]}},
            headers=self.headers,
        )

    def test_various_collections_can_be_signed_using_batch(self):
        self.app.put_json("/buckets/alice/collections/source", headers=self.headers)
        self.app.post_json(
            "/buckets/alice/collections/source/records", headers=self.headers
        )
        self.app.put_json("/buckets/bob/collections/source", headers=self.headers)
        self.app.post_json(
            "/buckets/bob/collections/source/records", headers=self.headers
        )

        self.app.post_json(
            "/batch",
            {
                "defaults": {
                    "method": "PATCH",
                    "body": {"data": {"status": "to-sign"}},
                },
                "requests": [
                    {"path": "/buckets/alice/collections/source"},
                    {"path": "/buckets/bob/collections/source"},
                ],
            },
            headers=self.headers,
        )

        resp = self.app.get("/buckets/alice/collections/source", headers=self.headers)
        assert resp.json["data"]["status"] == "signed"
        resp = self.app.get("/buckets/bob/collections/source", headers=self.headers)
        assert resp.json["data"]["status"] == "signed"

    def test_various_collections_can_be_signed_using_batch_creation(self):
        self.app.post_json(
            "/batch",
            {
                "defaults": {"method": "POST", "path": "/buckets/alice/collections"},
                "requests": [
                    {"body": {"data": {"id": "source", "status": "to-sign"}}},
                    {"body": {"data": {"id": "ignored", "status": "to-sign"}}},
                    {"body": {"data": {"id": "from", "status": "to-sign"}}},
                ],
            },
            headers=self.headers,
        )

        resp = self.app.get("/buckets/alice/collections/source", headers=self.headers)
        assert resp.json["data"]["status"] == "signed"
        resp = self.app.get("/buckets/alice/collections/from", headers=self.headers)
        assert resp.json["data"]["status"] == "signed"


class SigningErrorTest(BaseWebTest, unittest.TestCase):
    def test_returns_5xx_if_autograph_cannot_be_reached(self):
        collection_uri = "/buckets/alice/collections/source"
        self.app.app.registry.signers[collection_uri].server_url = "http://0.0.0.0:1234"

        self.app.put_json("/buckets/alice", headers=self.headers)

        resp = self.app.get("/", headers=self.headers)
        self.userid = resp.json["user"]["id"]
        self.app.put_json(
            "/buckets/alice/groups/source-reviewers",
            {"data": {"members": [self.userid]}},
            headers=self.headers,
        )

        self.app.put_json(
            collection_uri,
            {"data": {"status": "to-sign"}},
            headers=self.headers,
            status=500,
        )


class RecordChangedTest(BaseWebTest, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.headers = get_user_headers("me")

        patch = mock.patch("kinto_remote_settings.signer.backends.autograph.requests")
        self.mock = patch.start()
        self.addCleanup(patch.stop)

        self.collection_uri = "/buckets/alice/collections/source"
        self.records_uri = self.collection_uri + "/records"
        self.app.put_json("/buckets/alice", headers=self.headers)
        self.app.put_json(self.collection_uri, headers=self.headers)

    def test_returns_400_if_contains_float(self):
        self.headers = get_user_headers("me")
        parameters = [
            ({"a": 3.14}, "a"),
            ({"a": {"b": 41.0}}, "a.b"),
            ({"a": [{"b": 41.0}]}, "a.0.b"),
        ]
        for data, path in parameters:
            body = {"data": data}
            resp = self.app.post_json(
                self.records_uri, body, headers=self.headers, status=400
            )
            assert path in resp.json["message"]


class SourceCollectionSoftDeletion(BaseWebTest, PatchAutographMixin, unittest.TestCase):
    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super(cls, SourceCollectionSoftDeletion).get_app_settings(extras)
        settings["signer.to_review_enabled"] = "true"
        return settings

    def setUp(self):
        super().setUp()

        self.headers = get_user_headers("me")
        resp = self.app.get("/", headers=self.headers)
        self.userid = resp.json["user"]["id"]

        self.other_headers = get_user_headers("Sam:Wan Heilss")
        resp = self.app.get("/", headers=self.other_headers)
        self.other_userid = resp.json["user"]["id"]

        self.app.put_json("/buckets/stage", headers=self.headers)

        self.app.put_json(
            "/buckets/stage/groups/a-editors",
            {"data": {"members": [self.other_userid]}},
            headers=self.headers,
        )
        self.app.put_json(
            "/buckets/stage/groups/a-reviewers",
            {"data": {"members": [self.userid]}},
            headers=self.headers,
        )

        self.create_records_and_sign()

        resp = self.app.get("/buckets/prod/collections/a", headers=self.headers)
        signature_before = resp.json["data"]["signature"]["signature"]
        # Delete source collection.
        self.app.delete("/buckets/stage/collections/a", headers=self.headers)
        # Signature was refreshed.
        resp = self.app.get("/buckets/prod/collections/a", headers=self.headers)
        assert signature_before != resp.json["data"]["signature"]["signature"]

    def create_records_and_sign(self):
        body = {"permissions": {"write": [self.other_userid]}}
        self.app.put_json("/buckets/stage/collections/a", body, headers=self.headers)
        for i in range(5):
            self.app.post_json(
                "/buckets/stage/collections/a/records", headers=self.headers
            )
        self.app.patch_json(
            "/buckets/stage/collections/a",
            {"data": {"status": "to-review"}},
            headers=self.other_headers,
        )
        self.app.patch_json(
            "/buckets/stage/collections/a",
            {"data": {"status": "to-sign"}},
            headers=self.headers,
        )

    def test_unsigned_collection_are_not_affected(self):
        self.app.put_json("/buckets/bid", headers=self.headers)
        self.app.put_json("/buckets/bid/collections/a", headers=self.headers)

        patch = mock.patch(
            "kinto_remote_settings.signer.updater.LocalUpdater.sign_and_update_destination"
        )
        mocked = patch.start()
        self.addCleanup(patch.stop)

        self.app.delete("/buckets/bid/collections/a", headers=self.headers)

        assert not mocked.called

    def test_editors_reviewers_groups_are_deleted(self):
        self.app.get(
            "/buckets/stage/groups/a-editors", headers=self.headers, status=404
        )
        self.app.get(
            "/buckets/stage/groups/a-reviewers", headers=self.headers, status=404
        )

    def test_destination_content_is_deleted_when_source_is_deleted(self):
        # Destination is empty.
        resp = self.app.get("/buckets/prod/collections/a/records", headers=self.headers)
        assert len(resp.json["data"]) == 0
        # Tombstones were created.
        resp = self.app.get(
            "/buckets/prod/collections/a/records?_since=0", headers=self.headers
        )
        assert len(resp.json["data"]) == 5
        # Recreate source collection.
        self.create_records_and_sign()
        # Destination has 5 records.
        resp = self.app.get("/buckets/prod/collections/a/records", headers=self.headers)
        assert len(resp.json["data"]) == 5

    def test_preview_content_is_deleted_when_source_is_deleted(self):
        # Preview is empty.
        resp = self.app.get(
            "/buckets/preview/collections/a/records", headers=self.headers
        )
        assert len(resp.json["data"]) == 0
        # Tombstones were created.
        resp = self.app.get(
            "/buckets/preview/collections/a/records?_since=0", headers=self.headers
        )
        assert len(resp.json["data"]) == 5
        # Recreate source collection.
        self.create_records_and_sign()
        # Preview has 5 records.
        resp = self.app.get(
            "/buckets/preview/collections/a/records", headers=self.headers
        )
        assert len(resp.json["data"]) == 5


class SourceCollectionHardDeletion(BaseWebTest, PatchAutographMixin, unittest.TestCase):
    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super(cls, SourceCollectionHardDeletion).get_app_settings(extras)
        settings["signer.to_review_enabled"] = "true"
        settings["signer.hard_delete_destination_on_source_deletion"] = "true"
        return settings

    def setUp(self):
        super().setUp()

        self.headers = get_user_headers("me")
        resp = self.app.get("/", headers=self.headers)
        self.userid = resp.json["user"]["id"]

        self.other_headers = get_user_headers("Sam:Wan Heilss")
        resp = self.app.get("/", headers=self.other_headers)
        self.other_userid = resp.json["user"]["id"]

        self.app.put_json("/buckets/stage", headers=self.headers)

        self.app.put_json(
            "/buckets/stage/groups/a-editors",
            {"data": {"members": [self.other_userid]}},
            headers=self.headers,
        )
        self.app.put_json(
            "/buckets/stage/groups/a-reviewers",
            {"data": {"members": [self.userid]}},
            headers=self.headers,
        )

        self.create_records_and_sign()

        # oncrl doesn't have preview in config.ini
        self.app.put_json("/buckets/security-state-workspace", headers=self.headers)
        self.app.put_json(
            "/buckets/security-state-workspace/collections/onecrl", headers=self.headers
        )

    def create_records_and_sign(self):
        body = {"permissions": {"write": [self.other_userid]}}
        self.app.put_json("/buckets/stage/collections/a", body, headers=self.headers)
        for i in range(5):
            self.app.post_json(
                "/buckets/stage/collections/a/records", headers=self.headers
            )
        self.app.patch_json(
            "/buckets/stage/collections/a",
            {"data": {"status": "to-review"}},
            headers=self.other_headers,
        )
        self.app.patch_json(
            "/buckets/stage/collections/a",
            {"data": {"status": "to-sign"}},
            headers=self.headers,
        )

    def test_related_objects_are_all_deleted(self):
        self.app.get("/buckets/preview/collections/a", headers=self.headers)
        self.app.get("/buckets/prod/collections/a", headers=self.headers)
        self.app.get("/buckets/stage/groups/a-editors", headers=self.headers)
        self.app.get("/buckets/stage/groups/a-reviewers", headers=self.headers)

        self.app.delete("/buckets/stage/collections/a", headers=self.headers)

        self.app.get("/buckets/preview/collections/a", headers=self.headers, status=404)
        self.app.get("/buckets/prod/collections/a", headers=self.headers, status=404)
        self.app.get(
            "/buckets/stage/groups/a-editors", headers=self.headers, status=404
        )
        self.app.get(
            "/buckets/stage/groups/a-reviewers", headers=self.headers, status=404
        )

    def test_do_not_fail_if_group_already_deleted(self):
        self.app.delete("/buckets/stage/groups/a-editors", headers=self.headers)

        self.app.delete("/buckets/stage/collections/a", headers=self.headers)

        self.app.get(
            "/buckets/stage/groups/a-reviewers", headers=self.headers, status=404
        )

    def test_do_not_fail_if_collection_doesnt_have_preview(self):
        self.app.delete(
            "/buckets/security-state-workspace/collections/onecrl", headers=self.headers
        )

        self.app.get(
            "/buckets/security-state/collections/onecrl",
            headers=self.headers,
            status=404,
        )

    def test_deleted_collection_does_not_show_up_in_monitored_changes(self):
        monitored = self.app.get(
            "/buckets/monitor/collections/changes/changeset?_expected=0"
        )
        cids = set(
            f"{e['bucket']}/{e['collection']}" for e in monitored.json["changes"]
        )
        assert "preview/a" in cids
        assert "prod/a" in cids

        self.app.delete("/buckets/stage/collections/a", headers=self.headers)

        monitored = self.app.get(
            "/buckets/monitor/collections/changes/changeset?_expected=0"
        )
        cids = set(
            f"{e['bucket']}/{e['collection']}" for e in monitored.json["changes"]
        )
        assert "preview/a" not in cids
        assert "prod/a" not in cids


class ExpandedSettingsTest(BaseWebTest, PatchAutographMixin, unittest.TestCase):
    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super(cls, ExpandedSettingsTest).get_app_settings(extras)
        settings["signer.to_review_enabled"] = "true"
        settings["signer.main-workspace.magic-(\\w+).to_review_enabled"] = "false"
        return settings

    def setUp(self):
        super().setUp()
        self.app.put_json("/buckets/main-workspace", headers=self.headers)

    def test_expanded_settings_are_updated_on_collection_creation(self):
        server_info = self.app.get("/").json
        resources = server_info["capabilities"]["signer"]["resources"]
        source_collections = {entry["source"]["collection"] for entry in resources}
        assert "magic-word" not in source_collections
        assert "magic-(\\w+)" not in source_collections

        self.app.put_json(
            "/buckets/main-workspace/collections/magic-word", headers=self.headers
        )

        server_info = self.app.get("/").json
        resources = server_info["capabilities"]["signer"]["resources"]
        source_collections = {entry["source"]["collection"] for entry in resources}
        assert "magic-word" in source_collections
        assert "magic-(\\w+)" not in source_collections
