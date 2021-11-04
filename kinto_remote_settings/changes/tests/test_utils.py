import unittest
from unittest import mock

from pyramid.request import Request

from kinto_remote_settings.changes.utils import changes_object


class ChangesRecordTest(unittest.TestCase):
    def test_single_hardcoded(self):
        request = Request.blank(path="/")
        request.route_path = mock.Mock()
        request.route_path.return_value = "/buckets/a/collections/b"
        request.registry = mock.Mock()
        request.registry.settings = {}
        timestamp = 1525457597166
        entry = changes_object(request, "a", "b", timestamp)

        self.assertEqual(
            entry,
            {
                "bucket": "a",
                "collection": "b",
                "host": "",
                "id": "9527d115-6191-fa49-a530-8fbfc4997755",
                "last_modified": timestamp,
            },
        )

    def test_another_hardcoded(self):
        request = Request.blank(path="/")
        request.route_path = mock.Mock()
        request.route_path.return_value = "/buckets/a/collections/b"
        request.registry = mock.Mock()
        request.registry.settings = {"http_host": "https://localhost:443"}
        timestamp = 1525457597166
        entry = changes_object(request, "a", "b", timestamp)

        self.assertEqual(
            entry,
            {
                "bucket": "a",
                "collection": "b",
                "host": "https://localhost:443",
                "id": "fa48a96d-1600-f561-8645-3395acb08a5a",
                "last_modified": timestamp,
            },
        )
