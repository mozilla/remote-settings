import unittest

import responses
from commands.sync_megaphone import sync_megaphone


class TestSyncMegaphone(unittest.TestCase):
    server = "https://fake-server.net/v1"
    megaphone_url = "https://megaphone.tld/v1"
    megaphone_reader_auth = "reader-token"
    megaphone_broadcaster_auth = "broadcaster-token"
    broadcast_id = "remote-settings/monitor_changes"

    def setUp(self):
        self.source_monitor_changes_uri = (
            f"{self.server}/buckets/monitor/collections/changes/changeset"
        )
        self.megaphone_broadcasts_uri = f"{self.megaphone_url}/broadcasts"
        self.megaphone_broadcast_uri = (
            f"{self.megaphone_url}/broadcasts/{self.broadcast_id}"
        )
        self.event = {
            k: getattr(self, k)
            for k in [
                "server",
                "megaphone_url",
                "megaphone_reader_auth",
                "megaphone_broadcaster_auth",
            ]
        }

    @responses.activate
    def test_does_nothing_if_up_to_date(self):
        responses.add(
            responses.GET,
            self.source_monitor_changes_uri,
            json={
                "changes": [
                    {
                        "id": "a",
                        "bucket": "main-preview",
                        "collection": "cid",
                        "last_modified": 10,
                    },
                    {
                        "id": "b",
                        "bucket": "main",
                        "collection": "cid",
                        "last_modified": 7,
                    },
                ]
            },
        )
        responses.add(
            responses.GET,
            self.megaphone_broadcasts_uri,
            json={
                "code": 200,
                "broadcasts": {
                    "remote-settings/monitor_changes": '"7"',
                    "test/broadcast2": "v0",
                },
            },
        )

        sync_megaphone(
            event=self.event,
            context=None,
        )

        # No PUT on Megaphone API was sent.
        assert len(responses.calls) == 2
        assert responses.calls[0].request.method == "GET"
        assert responses.calls[1].request.method == "GET"

    @responses.activate
    def test_does_nothing_if_megaphone_is_newer(self):
        responses.add(
            responses.GET,
            self.source_monitor_changes_uri,
            json={
                "changes": [
                    {
                        "id": "b",
                        "bucket": "main",
                        "collection": "cid",
                        "last_modified": 7,
                    },
                ]
            },
        )
        responses.add(
            responses.GET,
            self.megaphone_broadcasts_uri,
            json={
                "code": 200,
                "broadcasts": {
                    "remote-settings/monitor_changes": '"8"',
                },
            },
        )

        sync_megaphone(
            event=self.event,
            context=None,
        )

        # No PUT on Megaphone API was sent.
        assert len(responses.calls) == 2
        assert responses.calls[0].request.method == "GET"
        assert responses.calls[1].request.method == "GET"

    @responses.activate
    def test_sends_version_if_differs(self):
        responses.add(
            responses.GET,
            self.source_monitor_changes_uri,
            json={
                "changes": [
                    {
                        "id": "a",
                        "bucket": "main",
                        "collection": "cid",
                        "last_modified": 10,
                    },
                ]
            },
        )
        responses.add(
            responses.GET,
            self.megaphone_broadcasts_uri,
            json={
                "code": 200,
                "broadcasts": {
                    "remote-settings/monitor_changes": '"5"',
                    "test/broadcast2": "v0",
                },
            },
        )
        responses.add(
            responses.PUT,
            self.megaphone_broadcast_uri,
        )

        sync_megaphone(
            event=self.event,
            context=None,
        )

        assert len(responses.calls) == 3
        assert responses.calls[0].request.method == "GET"
        assert responses.calls[1].request.method == "GET"
        assert responses.calls[2].request.body == '"10"'
        assert (
            responses.calls[1].request.headers["authorization"] == "Bearer reader-token"
        )
        assert (
            responses.calls[2].request.headers["authorization"]
            == "Bearer broadcaster-token"
        )
