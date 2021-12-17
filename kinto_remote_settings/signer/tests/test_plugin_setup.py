import unittest
import uuid
from unittest import mock

import pytest
from kinto import main as kinto_main
from kinto.core.events import ResourceChanged
from pyramid import testing
from pyramid.exceptions import ConfigurationError
from requests import exceptions as requests_exceptions

from kinto_remote_settings import __version__
from kinto_remote_settings.signer import includeme, utils
from kinto_remote_settings.signer.backends.autograph import AutographSigner
from kinto_remote_settings.signer.listeners import sign_collection_data

from .support import BaseWebTest, get_user_headers


class HelloViewTest(BaseWebTest, unittest.TestCase):
    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super().get_app_settings(extras)
        settings["signer.reviewers_group"] = "{bucket_id}-{collection_id}-reviewers"
        settings["signer.alice.reviewers_group"] = "revoyeurs"
        settings["signer.alice.source.to_review_enabled"] = "true"

        settings["signer.stage.normandy.to_review_enabled"] = "false"
        return settings

    def test_capability_is_exposed(self):
        self.maxDiff = None
        resp = self.app.get("/")
        capabilities = resp.json["capabilities"]
        self.assertIn("signer", capabilities)
        expected = {
            "description": "Digital signatures for integrity and authenticity of records.",  # NOQA
            "url": ("https://github.com/Kinto/kinto-signer#kinto-signer"),
            "version": __version__,
            "group_check_enabled": True,
            "to_review_enabled": False,
            "editors_group": "editors",
            "reviewers_group": "{bucket_id}-{collection_id}-reviewers",
            "resources": [
                {
                    "destination": {"bucket": "alice", "collection": "destination"},
                    "source": {"bucket": "alice", "collection": "source"},
                    "reviewers_group": "revoyeurs",
                    "to_review_enabled": True,
                },
                {
                    "destination": {"bucket": "alice", "collection": "to"},
                    "preview": {"bucket": "alice", "collection": "preview"},
                    "source": {"bucket": "alice", "collection": "from"},
                    "reviewers_group": "revoyeurs",
                },
                {
                    "destination": {"bucket": "bob", "collection": "destination"},
                    "source": {"bucket": "bob", "collection": "source"},
                    "reviewers_group": "bob-source-reviewers",
                },
                {
                    "source": {"bucket": "stage", "collection": None},
                    "preview": {"bucket": "preview", "collection": None},
                    "destination": {"bucket": "prod", "collection": None},
                    "reviewers_group": "stage-{collection_id}-reviewers",
                },
                {
                    "source": {"bucket": "stage", "collection": "normandy"},
                    "preview": {"bucket": "preview", "collection": "normandy"},
                    "destination": {"bucket": "prod", "collection": "normandy"},
                    "reviewers_group": "stage-normandy-reviewers",
                },
            ],
        }
        self.assertEqual(expected, capabilities["signer"])


class HeartbeatTest(BaseWebTest, unittest.TestCase):
    def setUp(self):
        patch = mock.patch("kinto_remote_settings.signer.backends.autograph.requests")
        self.mock = patch.start()
        self.addCleanup(patch.stop)
        self.signature = {"signature": "", "x5u": "", "mode": "", "ref": "abc"}
        self.mock.post.return_value.json.return_value = [self.signature]

    def test_heartbeat_is_exposed(self):
        resp = self.app.get("/__heartbeat__")
        assert "signer" in resp.json

    def test_heartbeat_fails_if_unreachable(self):
        self.mock.post.side_effect = requests_exceptions.ConnectTimeout()
        resp = self.app.get("/__heartbeat__", status=503)
        assert resp.json["signer"] is False

    def test_heartbeat_fails_if_missing_attributes(self):
        invalid = self.signature.copy()
        invalid.pop("signature")
        self.mock.post.return_value.json.return_value = [invalid]
        resp = self.app.get("/__heartbeat__", status=503)
        assert resp.json["signer"] is False


class IncludeMeTest(unittest.TestCase):
    def includeme(self, settings):
        config = testing.setUp(settings=settings)
        kinto_main(None, config=config)
        includeme(config)
        return config

    def test_includeme_raises_value_error_if_no_resource_defined(self):
        with pytest.raises(ConfigurationError):
            self.includeme(
                settings={"signer.ecdsa.private_key": "", "signer.ecdsa.public_key": ""}
            )

    def test_defines_a_signer_per_bucket(self):
        settings = {
            "signer.resources": (
                "/buckets/sb1/collections/sc1 -> /buckets/db1/collections/dc1\n"
            ),
            "signer.sb1.signer_backend": "kinto_remote_settings.signer.backends.local_ecdsa",  # noqa: 501
            "signer.sb1.ecdsa.public_key": "/path/to/key",
            "signer.sb1.ecdsa.private_key": "/path/to/private",
        }
        config = self.includeme(settings)
        (signer,) = config.registry.signers.values()
        assert signer.public_key == "/path/to/key"

    def test_includeme_doesnt_fail_when_expanding_collection(self):
        settings = {
            "signer.resources": (
                "/buckets/sb1 -> /buckets/db1\n" "/buckets/sb2 -> /buckets/db2\n"
            ),
            "signer.signer_backend": "kinto_remote_settings.signer.backends.local_ecdsa",
            "signer.ecdsa.public_key": "/path/to/key",
            "signer.ecdsa.private_key": "/path/to/private",
            "signer.sb1.sc1.signer_backend": "kinto_remote_settings.signer.backends.local_ecdsa",  # noqa: 501
            "signer.sb1.sc1.ecdsa.public_key": "/path/to/key",
            "signer.sb1.sc1.ecdsa.private_key": "/path/to/private",
        }
        self.includeme(settings)

    def test_includeme_sanitizes_exposed_settings(self):
        settings = {
            "signer.resources": (
                "/buckets/sb1 -> /buckets/db1\n" "/buckets/sb2 -> /buckets/db2\n"
            ),
            "signer.signer_backend": "kinto_remote_settings.signer.backends.local_ecdsa",
            "signer.ecdsa.public_key": "/path/to/key",
            "signer.ecdsa.private_key": "/path/to/private",
            "signer.sb1.sc1.signer_backend": "kinto_remote_settings.signer.backends.local_ecdsa",  # noqa: 501
            "signer.sb1.sc1.ecdsa.public_key": "/path/to/key",
            "signer.sb1.sc1.ecdsa.private_key": "/path/to/private",
            "signer.sb2.signer_backend": "kinto_remote_settings.signer.backends.local_ecdsa",  # noqa: 501
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
            "signer.sb1.signer_backend": "kinto_remote_settings.signer.backends.local_ecdsa",  # noqa: 501
            "signer.sb1.ecdsa.public_key": "/path/to/key",
            "signer.sb1.ecdsa.private_key": "/path/to/private",
            "signer.sb1.sc1.signer_backend": "kinto_remote_settings.signer.backends.autograph",  # noqa: 501
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

    def test_a_statsd_timer_is_used_for_signature_if_configured(self):
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
        statsd_client = config.registry.statsd._client
        with mock.patch.object(statsd_client, "timing") as mocked:
            config.registry.notify(event)
            timers = set(c[0][0] for c in mocked.call_args_list)
            assert "plugins.signer" in timers

    def test_includeme_raises_value_error_if_unknown_placeholder(self):
        settings = {
            "signer.resources": "/buckets/sb1/collections/sc1 -> /buckets/db1/collections/dc1",  # noqa: 501
            "signer.editors_group": "{datetime}_group",
            "signer.ecdsa.public_key": "/path/to/key",
            "signer.ecdsa.private_key": "/path/to/private",
        }
        with pytest.raises(ConfigurationError) as excinfo:
            self.includeme(settings=settings)
        assert "Unknown group placeholder 'datetime'" in repr(excinfo.value)


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


class BatchTest(BaseWebTest, unittest.TestCase):
    def setUp(self):
        super(BatchTest, self).setUp()
        self.headers = get_user_headers("me")

        resp = self.app.get("/", headers=self.headers)
        self.userid = resp.json["user"]["id"]

        self.app.put_json("/buckets/alice", headers=self.headers)
        self.app.put_json("/buckets/bob", headers=self.headers)

        self.app.put_json(
            "/buckets/alice/groups/reviewers",
            {"data": {"members": [self.userid]}},
            headers=self.headers,
        )
        self.app.put_json(
            "/buckets/bob/groups/reviewers",
            {"data": {"members": [self.userid]}},
            headers=self.headers,
        )

        # Patch calls to Autograph.
        patch = mock.patch("kinto_remote_settings.signer.backends.autograph.requests")
        self.mock = patch.start()
        self.addCleanup(patch.stop)
        self.mock.post.return_value.json.return_value = [
            {
                "signature": "",
                "hash_algorithm": "",
                "signature_encoding": "",
                "content-signature": "",
                "x5u": "",
                "ref": "",
            }
        ]

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
            "/buckets/alice/groups/reviewers",
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
        ]
        for data, path in parameters:
            body = {"data": data}
            resp = self.app.post_json(
                self.records_uri, body, headers=self.headers, status=400
            )
            assert path in resp.json["message"]


class SourceCollectionDeletion(BaseWebTest, unittest.TestCase):
    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super(cls, SourceCollectionDeletion).get_app_settings(extras)
        settings["signer.to_review_enabled"] = "true"
        settings["signer.stage.editors_group"] = "something"
        return settings

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

        self.headers = get_user_headers("me")
        resp = self.app.get("/", headers=self.headers)
        self.userid = resp.json["user"]["id"]

        self.other_headers = get_user_headers("Sam:Wan Heilss")
        resp = self.app.get("/", headers=self.other_headers)
        self.other_userid = resp.json["user"]["id"]

        self.app.put_json("/buckets/stage", headers=self.headers)

        self.app.put_json(
            "/buckets/stage/groups/something",
            {"data": {"members": [self.other_userid]}},
            headers=self.headers,
        )
        self.app.put_json(
            "/buckets/stage/groups/reviewers",
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
            "kinto_remote_settings.signer.updater.LocalUpdater.sign_and_update_destination"  # noqa: 501
        )
        mocked = patch.start()
        self.addCleanup(patch.stop)

        self.app.delete("/buckets/bid/collections/a", headers=self.headers)

        assert not mocked.called

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
