import unittest

from .support import BaseWebTest


class AutocreateTest(BaseWebTest, unittest.TestCase):
    @classmethod
    def get_app_settings(cls, extras=None):
        settings = super().get_app_settings(extras)
        settings["signer.auto_create_resources"] = True
        settings["signer.auto_create_resources_principals"] = (
            "account:admin",
            "system.Authenticated",
        )
        return settings

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
