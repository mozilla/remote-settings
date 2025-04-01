import unittest
from unittest import mock

from kinto_remote_settings.changes.utils import change_entry_id
from pyramid.request import Request


class ChangesEntryIdTest(unittest.TestCase):
    def test_single_hardcoded(self):
        request = Request.blank(path="/")
        request.route_path = mock.Mock()
        request.route_path.return_value = "/buckets/a/collections/b"

        entry = change_entry_id(request, "", "a", "b")

        assert entry == "9527d115-6191-fa49-a530-8fbfc4997755"

    def test_another_hardcoded(self):
        request = Request.blank(path="/")
        request.route_path = mock.Mock()
        request.route_path.return_value = "/buckets/a/collections/b"

        entry = change_entry_id(request, "https://localhost:443", "a", "b")

        assert entry == "fa48a96d-1600-f561-8645-3395acb08a5a"
