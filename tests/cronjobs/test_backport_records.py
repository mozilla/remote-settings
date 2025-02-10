import json
import unittest

import pytest
import responses
from commands.backport_records import backport_records


class TestRecordsBackport(unittest.TestCase):
    server = "https://fake-server.net/v1"
    auth = ("foo", "bar")
    source_bid = "main"
    source_cid = "one"
    dest_bid = "main-workspace"
    dest_cid = "other"

    def setUp(self):
        self.source_collection_uri = (
            f"{self.server}/buckets/{self.source_bid}/collections/{self.source_cid}"
        )
        self.source_records_uri = f"{self.source_collection_uri}/records"

        self.dest_collection_uri = (
            f"{self.server}/buckets/{self.dest_bid}/collections/{self.dest_cid}"
        )
        self.dest_records_uri = f"{self.dest_collection_uri}/records"

    @responses.activate
    def test_missing_records_are_backported(self):
        responses.add(
            responses.GET,
            self.server + "/",
            json={
                "settings": {"batch_max_requests": 10},
                "capabilities": {"signer": {"resources": []}},
            },
        )
        responses.add(
            responses.GET,
            self.source_records_uri,
            json={
                "data": [
                    {"id": "a", "age": 22, "last_modified": 1},
                    {"id": "b", "age": 30, "last_modified": 10},
                ]
            },
        )
        responses.add(
            responses.GET,
            self.dest_records_uri,
            json={"data": [{"id": "a", "age": 22, "last_modified": 2}]},
        )
        responses.add(responses.POST, self.server + "/batch", json={"responses": []})

        backport_records(
            event={
                "server": self.server,
                "backport_records_source_auth": self.auth,
                "backport_records_source_bucket": self.source_bid,
                "backport_records_source_collection": self.source_cid,
                "backport_records_source_filters": '{"min_age": 20}',
                "backport_records_dest_bucket": self.dest_bid,
                "backport_records_dest_collection": self.dest_cid,
            },
            context=None,
        )

        assert responses.calls[0].request.method == "GET"
        assert responses.calls[0].request.url.endswith("?min_age=20")

        assert responses.calls[1].request.method == "GET"
        assert responses.calls[2].request.method == "GET"

        assert responses.calls[3].request.method == "POST"
        posted_records = json.loads(responses.calls[3].request.body)
        assert posted_records["requests"] == [
            {
                "body": {"data": {"age": 30, "id": "b", "last_modified": 10}},
                "headers": {"If-None-Match": "*"},
                "method": "PUT",
                "path": "/buckets/main-workspace/collections/other/records/b",
            }
        ]

    @responses.activate
    def test_outdated_records_are_overwritten(self):
        responses.add(
            responses.GET,
            self.server + "/",
            json={
                "settings": {"batch_max_requests": 10},
                "capabilities": {"signer": {"resources": []}},
            },
        )
        responses.add(responses.HEAD, self.source_records_uri, headers={"ETag": '"42"'})
        responses.add(
            responses.GET,
            self.source_records_uri,
            json={"data": [{"id": "a", "age": 22, "last_modified": 2}]},
        )
        responses.add(responses.HEAD, self.dest_records_uri, headers={"ETag": '"41"'})
        responses.add(
            responses.GET,
            self.dest_records_uri,
            json={"data": [{"id": "a", "age": 20, "last_modified": 1}]},
        )
        responses.add(responses.POST, self.server + "/batch", json={"responses": []})

        backport_records(
            event={
                "server": self.server,
                "safe_headers": True,
                "backport_records_source_auth": self.auth,
                "backport_records_source_bucket": self.source_bid,
                "backport_records_source_collection": self.source_cid,
                "backport_records_dest_bucket": self.dest_bid,
                "backport_records_dest_collection": self.dest_cid,
            },
            context=None,
        )

        assert responses.calls[3].request.method == "POST"
        posted_records = json.loads(responses.calls[3].request.body)
        assert posted_records["requests"] == [
            {
                "body": {"data": {"age": 22, "id": "a"}},
                "headers": {"If-Match": '"1"'},
                "method": "PUT",
                "path": "/buckets/main-workspace/collections/other/records/a",
            }
        ]

    @responses.activate
    def test_nothing_to_do(self):
        responses.add(
            responses.GET,
            self.source_records_uri,
            json={
                "data": [
                    {"id": "a", "age": 22, "last_modified": 1},
                    {"id": "b", "age": 30, "last_modified": 10},
                ]
            },
        )
        responses.add(
            responses.GET,
            self.dest_collection_uri,
            json={
                "data": {
                    "status": "signed",
                },
            },
        )
        responses.add(
            responses.GET,
            self.dest_records_uri,
            json={
                "data": [
                    {"id": "a", "age": 22, "last_modified": 20},
                    {"id": "b", "age": 30, "last_modified": 30},
                ]
            },
        )

        backport_records(
            event={
                "server": self.server,
                "backport_records_source_auth": self.auth,
                "backport_records_source_bucket": self.source_bid,
                "backport_records_source_collection": self.source_cid,
                "backport_records_dest_bucket": self.dest_bid,
                "backport_records_dest_collection": self.dest_cid,
            },
            context=None,
        )

        assert len(responses.calls) == 3
        assert responses.calls[0].request.method == "GET"
        assert responses.calls[0].request.url.endswith(self.source_records_uri)
        assert responses.calls[1].request.method == "GET"
        assert responses.calls[1].request.url.endswith(self.dest_records_uri)
        # Check if the destination collection is signed.
        assert responses.calls[2].request.method == "GET"
        assert responses.calls[2].request.url.endswith(self.dest_collection_uri)

    @responses.activate
    def test_pending_changes(self):
        responses.add(
            responses.GET,
            self.server + "/",
            json={
                "settings": {"batch_max_requests": 10},
                "capabilities": {
                    "signer": {
                        "to_review_enabled": False,
                        "group_check_enabled": True,
                        "resources": [
                            {
                                "source": {
                                    "bucket": self.dest_bid,
                                    "collection": self.dest_cid,
                                }
                            }
                        ],
                    }
                },
            },
        )
        responses.add(
            responses.GET,
            self.source_records_uri,
            json={
                "data": [
                    {"id": "a", "age": 22, "last_modified": 1},
                    {"id": "b", "age": 30, "last_modified": 10},
                ]
            },
        )
        responses.add(
            responses.GET,
            self.dest_collection_uri,
            json={
                "data": {"status": "work-in-progress"},
            },
        )
        responses.add(
            responses.PATCH,
            self.dest_collection_uri,
            json={
                "data": {"status": "to-sign"},
            },
        )
        responses.add(
            responses.GET,
            self.dest_records_uri,
            json={
                "data": [
                    {"id": "a", "age": 22, "last_modified": 20},
                    {"id": "b", "age": 30, "last_modified": 30},
                ]
            },
        )

        backport_records(
            event={
                "server": self.server,
                "backport_records_source_auth": self.auth,
                "backport_records_source_bucket": self.source_bid,
                "backport_records_source_collection": self.source_cid,
                "backport_records_dest_bucket": self.dest_bid,
                "backport_records_dest_collection": self.dest_cid,
            },
            context=None,
        )

        assert len(responses.calls) == 6
        assert responses.calls[0].request.method == "GET"
        assert responses.calls[0].request.url.endswith(self.source_records_uri)
        assert responses.calls[1].request.method == "GET"
        assert responses.calls[1].request.url.endswith(self.dest_records_uri)
        # Check if the destination collection is signed.
        assert responses.calls[2].request.method == "GET"
        assert responses.calls[2].request.url.endswith(self.dest_collection_uri)
        # Fetch server info for batch requests size.
        assert responses.calls[3].request.method == "GET"
        assert responses.calls[3].request.url == self.server + "/"
        # Check if the destination has review enabled.
        assert responses.calls[4].request.method == "GET"
        assert responses.calls[4].request.url == self.server + "/"
        # Request signing.
        assert responses.calls[5].request.method == "PATCH"
        assert responses.calls[5].request.url.endswith(self.dest_collection_uri)
        sign_request = json.loads(responses.calls[5].request.body)
        assert sign_request == {"data": {"status": "to-sign"}}


@pytest.mark.parametrize(
    ("mapping_env", "expected_calls"),
    [
        (
            "ws/scid?field=value&key=data -> main/cid",
            [("ws", "scid", {"field": "value", "key": "data"}, "main", "cid")],
        ),
        (
            "ws/scid?key1=value1&key2=value2&key2=value3 -> main/cid",
            [
                (
                    "ws",
                    "scid",
                    {"key1": "value1", "key2": ["value2", "value3"]},
                    "main",
                    "cid",
                )
            ],
        ),
        (
            "ws/scid1 -> main/cid1\nws/scid2 -> main/cid2",
            [("ws", "scid1", {}, "main", "cid1"), ("ws", "scid2", {}, "main", "cid2")],
        ),
    ],
)
def test_correct_multiline_mappings(mapping_env, expected_calls):
    with unittest.mock.patch("commands.backport_records.execute_backport") as mocked:
        backport_records(
            event={
                "server": "http://server",
                "backport_records_source_auth": "admin:admin",
                "backport_records_mappings": mapping_env,
            },
            context=None,
        )
        for expected_params in expected_calls:
            mocked.assert_any_call(
                unittest.mock.ANY,
                unittest.mock.ANY,
                unittest.mock.ANY,
                unittest.mock.ANY,
                *expected_params,
            )


@pytest.mark.parametrize(
    "mapping_env",
    [
        "ws-scid -> main/cid",
        "ws-scid --> main/cid",
    ],
)
def test_incorrect_multiline_mappings(mapping_env):
    with unittest.mock.patch("commands.backport_records.execute_backport"):
        with pytest.raises(match="Invalid syntax"):
            backport_records(
                event={
                    "server": "http://server",
                    "backport_records_source_auth": "admin:admin",
                    "backport_records_mappings": mapping_env,
                },
                context=None,
            )
