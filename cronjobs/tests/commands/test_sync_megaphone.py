import os
from unittest import mock

import pytest
import responses
from commands.sync_megaphone import sync_megaphone


SERVER_URL = "https://fake-server.net/v1"
MEGAPHONE_URL = "https://megaphone.tld/v1"
BROADCAST_ID = "remote-settings"
CHANNEL_ID = "monitor_changes"
MONITOR_CHANGES_URI = f"{SERVER_URL}/buckets/monitor/collections/changes/changeset"
MEGAPHONE_BROADCASTS_URI = f"{MEGAPHONE_URL}/broadcasts"
MEGAPHONE_BROADCAST_URI = f"{MEGAPHONE_URL}/broadcasts/{BROADCAST_ID}/{CHANNEL_ID}"


@pytest.fixture(scope="module", autouse=True)
def set_env_var():
    with mock.patch.dict(
        os.environ,
        {
            "SERVER": SERVER_URL,
            "MEGAPHONE_URL": MEGAPHONE_URL,
            "MEGAPHONE_READER_AUTH": "reader-token",
            "MEGAPHONE_BROADCASTER_AUTH": "broadcaster-token",
        },
    ):
        yield


@responses.activate
def test_does_nothing_if_up_to_date():
    responses.add(
        responses.GET,
        MONITOR_CHANGES_URI,
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
        MEGAPHONE_BROADCASTS_URI,
        json={
            "code": 200,
            "broadcasts": {
                "remote-settings/monitor_changes": '"7"',
                "test/broadcast2": "v0",
            },
        },
    )

    sync_megaphone(
        event={},
        context=None,
    )

    # No PUT on Megaphone API was sent.
    assert len(responses.calls) == 2
    assert responses.calls[0].request.method == "GET"
    assert responses.calls[1].request.method == "GET"


@responses.activate
def test_does_nothing_if_megaphone_is_newer():
    responses.add(
        responses.GET,
        MONITOR_CHANGES_URI,
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
        MEGAPHONE_BROADCASTS_URI,
        json={
            "code": 200,
            "broadcasts": {
                "remote-settings/monitor_changes": '"8"',
            },
        },
    )

    sync_megaphone(
        event={},
        context=None,
    )

    # No PUT on Megaphone API was sent.
    assert len(responses.calls) == 2
    assert responses.calls[0].request.method == "GET"
    assert responses.calls[1].request.method == "GET"


@responses.activate
def test_sends_version_if_differs():
    responses.add(
        responses.GET,
        MONITOR_CHANGES_URI,
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
        MEGAPHONE_BROADCASTS_URI,
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
        MEGAPHONE_BROADCAST_URI,
    )

    sync_megaphone(
        event={},
        context=None,
    )

    assert len(responses.calls) == 3
    assert responses.calls[0].request.method == "GET"
    assert responses.calls[1].request.method == "GET"
    assert responses.calls[2].request.body == '"10"'
    assert responses.calls[1].request.headers["authorization"] == "Bearer reader-token"
    assert (
        responses.calls[2].request.headers["authorization"]
        == "Bearer broadcaster-token"
    )
