import random
import re
import string
import unittest
from unittest import mock

from .support import BaseWebTest, get_user_headers

RE_ISO8601 = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}\+00:00")


class SignerAttachmentsTest(BaseWebTest, unittest.TestCase):
    def setUp(self):
        super().setUp()
        # Patch calls to Autograph.
        patch = mock.patch("kinto_remote_settings.signer.backends.autograph.requests")
        self.addCleanup(patch.stop)
        self.mocked_autograph = patch.start()

        def fake_sign():
            fake_signature = "".join(random.sample(string.ascii_lowercase, 10))
            return [
                {
                    "signature": "",
                    "hash_algorithm": "",
                    "signature_encoding": "",
                    "content-signature": fake_signature,
                    "x5u": "",
                    "ref": "",
                }
            ]

        self.mocked_autograph.post.return_value.json.side_effect = fake_sign

        self.headers = get_user_headers("tarte:en-pion")
        resp = self.app.get("/", headers=self.headers)
        self.userid = resp.json["user"]["id"]

        self.other_headers = get_user_headers("Sam:Wan Heilss")
        resp = self.app.get("/", headers=self.other_headers)
        self.other_userid = resp.json["user"]["id"]

        self.app.put_json(self.source_bucket, headers=self.headers)
        self.app.put_json(self.source_collection, headers=self.headers)
        self.app.put_json(
            self.source_bucket + "/groups/reviewers",
            {"data": {"members": [self.other_userid]}},
            headers=self.headers,
        )

    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super().get_app_settings(extras)

        settings["kinto.includes"] += " kinto_attachment"

        cls.source_bucket = "/buckets/alice"
        cls.source_collection = cls.source_bucket + "/collections/scid"
        cls.destination_bucket = "/buckets/alice"
        cls.destination_collection = cls.destination_bucket + "/collections/dcid"

        settings["kinto.signer.resources"] = "%s -> %s" % (
            cls.source_collection,
            cls.destination_collection,
        )

        settings["signer.to_review_enabled"] = "false"

        settings["attachment.base_path"] = "/tmp"

        return settings

    def initialize(self):
        r = self.app.post_json(
            self.source_collection + "/records",
            {"data": {"title": "hello"}},
            headers=self.headers,
        )
        r = r.json["data"]
        uri = self.source_collection + "/records/" + r["id"] + "/attachment"
        self.upload_file(
            uri=uri,
            files=[("attachment", "image.jpg", b"--fake--")],
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

    def upload_file(self, uri, files, params=[], headers={}):
        content_type, body = self.app.encode_multipart(params, files)
        headers = headers.copy()
        headers["Content-Type"] = content_type
        resp = self.app.post(uri, body, headers=headers)
        return resp

    def test_attachment_is_enabled(self):
        r = self.app.get("/")
        assert "attachments" in r.json["capabilities"]

    def test_attachment_is_published_on_final_collection(self):
        self.initialize()

        r = self.app.get(self.destination_collection + "/records", headers=self.headers)
        record = r.json["data"][0]

        assert "attachment" in record

    def test_attachment_can_be_replaced(self):
        self.initialize()

        r = self.app.get(self.destination_collection + "/records", headers=self.headers)
        record = r.json["data"][0]

        attachment_before = record["attachment"]["hash"]

        uri = self.source_collection + "/records/" + record["id"] + "/attachment"
        self.upload_file(
            uri=uri,
            files=[("attachment", "image.jpg", b"--other-fake--")],
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

        r = self.app.get(self.destination_collection + "/records", headers=self.headers)
        record = r.json["data"][0]
        attachment_after = record["attachment"]["hash"]

        assert attachment_before != attachment_after
