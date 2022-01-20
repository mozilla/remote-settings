import unittest

from .support import BaseWebTest


class AutocreateTest(BaseWebTest, unittest.TestCase):
    config = "config/autocreate.ini"

    def test_resources_were_created(self):
        write_perms = sorted(["system.Authenticated", "account:admin"])

        r = self.app.get("/buckets/main-workspace", headers=self.headers)
        assert sorted(r.json["permissions"]["write"]) == write_perms

        r = self.app.get("/buckets/security-state-workspace", headers=self.headers)
        assert sorted(r.json["permissions"]["write"]) == write_perms

        r = self.app.get(
            "/buckets/security-state-workspace/collections/onecrl", headers=self.headers
        )
        assert sorted(r.json["permissions"]["write"]) == write_perms
