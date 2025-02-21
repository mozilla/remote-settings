import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import responses
from commands.refresh_signature import refresh_signature


SERVER_INFO = {
    "settings": {"batch_max_requests": 10},
    "capabilities": {
        "signer": {
            "resources": [
                {
                    "source": {
                        "bucket": "main-workspace",
                        "collection": None,
                    },
                    "destination": {"bucket": "main", "collection": None},
                }
            ]
        }
    },
}


MONITOR_CHANGES = {
    "data": [
        {"id": "a", "bucket": "main", "collection": "search-config"},
        {"id": "b", "bucket": "main", "collection": "top-sites"},
    ]
}


class TestSignatureRefresh(unittest.TestCase):
    server = "https://fake-server.net/v1"
    auth = ("foo", "bar")

    @responses.activate
    def test_skip_recently_signed(self):
        responses.add(
            responses.GET,
            self.server + "/",
            json=SERVER_INFO,
        )

        responses.add(
            responses.GET,
            self.server + "/buckets/monitor/collections/changes/records",
            json=MONITOR_CHANGES,
        )

        for cid, date in [
            ("search-config", "2019-01-11T15:11:07.807323+00:00"),
            ("top-sites", "2019-01-18T15:11:07.807323+00:00"),
        ]:
            responses.add(
                responses.GET,
                self.server + "/buckets/main-workspace/collections/" + cid,
                json={
                    "data": {"last_modified": 42, "last_signature_date": date},
                },
            )
            responses.add(
                responses.PATCH,
                self.server + "/buckets/main-workspace/collections/" + cid,
                json={
                    "data": {
                        "last_modified": 43,
                    }
                },
            )

        patch = mock.patch("commands.refresh_signature.utcnow")
        self.addCleanup(patch.stop)
        mocked = patch.start()

        mocked.return_value = datetime(2019, 1, 20).replace(tzinfo=timezone.utc)

        refresh_signature(
            event={
                "server": self.server,
            },
            context=None,
        )

        patch_requests = [r for r in responses.calls if r.request.method == "PATCH"]

        assert len(patch_requests) == 1

    @responses.activate
    def test_force_refresh_with_max_age_zero(self):
        responses.add(responses.GET, self.server + "/", json=SERVER_INFO)

        responses.add(
            responses.GET,
            self.server + "/buckets/monitor/collections/changes/records",
            json=MONITOR_CHANGES,
        )

        yesterday = (
            (datetime.now() - timedelta(days=1))
            .replace(tzinfo=timezone.utc)
            .isoformat()
        )
        day_before = (
            (datetime.now() - timedelta(days=2))
            .replace(tzinfo=timezone.utc)
            .isoformat()
        )

        for cid, date in [
            ("search-config", yesterday),
            ("top-sites", day_before),
        ]:
            responses.add(
                responses.GET,
                self.server + "/buckets/main-workspace/collections/" + cid,
                json={
                    "data": {"last_modified": 42, "last_signature_date": date},
                },
            )
            responses.add(
                responses.PATCH,
                self.server + "/buckets/main-workspace/collections/" + cid,
                json={
                    "data": {
                        "last_modified": 43,
                    }
                },
            )

        refresh_signature(
            event={
                "server": self.server,
                "max_signature_age": 0,
            },
            context=None,
        )

        patch_requests = [r for r in responses.calls if r.request.method == "PATCH"]

        assert len(patch_requests) == 2
