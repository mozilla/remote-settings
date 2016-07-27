from kinto_admin import __version__ as admin_version
from . import BaseWebTest
from kinto.tests.support import unittest


class HelloViewTest(BaseWebTest, unittest.TestCase):

    def test_capability_is_exposed(self):
        self.maxDiff = None
        resp = self.app.get('/')
        capabilities = resp.json['capabilities']
        self.assertIn('admin', capabilities)
        expected = {
            "description": "Serve the admin console.",
            "url": ("https://github.com/Kinto/kinto-admin/"),
            "version": admin_version
        }
        self.assertEqual(expected, capabilities['admin'])
