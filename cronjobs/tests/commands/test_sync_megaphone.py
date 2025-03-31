import os
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest
import responses
from commands.sync_megaphone import sync_megaphone


SERVER_URL = "https://fake-server.net/v1"
MEGAPHONE_URL = "https://megaphone.tld/v1"
BROADCAST_ID = "remote-settings"
CHANNEL_ID = "monitor_changes"
MIN_SYNC_INTERVAL_SECONDS = 100
MAX_SYNC_INTERVAL_SECONDS = 300
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
            "MIN_SYNC_INTERVAL_SECONDS": str(MIN_SYNC_INTERVAL_SECONDS),
            "MAX_SYNC_INTERVAL_SECONDS": str(MAX_SYNC_INTERVAL_SECONDS),
        },
    ):
        yield


@pytest.fixture
def mocked_now():
    with mock.patch("commands.sync_megaphone.utcnow") as mocked:
        yield mocked


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
def test_sends_version_if_less_than_debounce_seconds_and_megaphone_recent(mocked_now):
    fake_now = datetime(2024, 3, 27, 13, 37, tzinfo=timezone.utc)
    recent_timestamp = int(
        (fake_now - timedelta(seconds=MIN_SYNC_INTERVAL_SECONDS - 10)).timestamp()
        * 1000
    )
    mocked_now.return_value = fake_now
    responses.add(
        responses.GET,
        MONITOR_CHANGES_URI,
        json={
            "changes": [
                {
                    "id": "a",
                    "bucket": "main",
                    "collection": "cid",
                    "last_modified": recent_timestamp,
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
                "remote-settings/monitor_changes": f'"{recent_timestamp - 1100}"',
                "test/broadcast2": "v0",
            },
        },
    )

    sync_megaphone(
        event={},
        context=None,
    )

    assert len(responses.calls) == 2
    assert responses.calls[0].request.method == "GET"


@responses.activate
def test_sends_version_if_older_than_debounce_seconds(mocked_now):
    fake_now = datetime(2024, 3, 27, 13, 37, tzinfo=timezone.utc)
    old_timestamp = int(
        (fake_now - timedelta(seconds=MIN_SYNC_INTERVAL_SECONDS + 10)).timestamp()
        * 1000
    )
    mocked_now.return_value = fake_now
    responses.add(
        responses.GET,
        MONITOR_CHANGES_URI,
        json={
            "changes": [
                {
                    "id": "a",
                    "bucket": "main",
                    "collection": "cid",
                    "last_modified": old_timestamp + 42,
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
                "remote-settings/monitor_changes": f'"{old_timestamp}"',
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
    assert responses.calls[2].request.method == "PUT"
    assert responses.calls[2].request.body == f'"{old_timestamp + 42}"'
    assert responses.calls[1].request.headers["authorization"] == "Bearer reader-token"
    assert (
        responses.calls[2].request.headers["authorization"]
        == "Bearer broadcaster-token"
    )


@responses.activate
def test_sends_version_if_less_than_debounce_seconds_but_megaphone_is_old(mocked_now):
    fake_now = datetime(2024, 3, 27, 13, 37, tzinfo=timezone.utc)
    recent_timestamp = int(
        (fake_now - timedelta(seconds=MIN_SYNC_INTERVAL_SECONDS - 10)).timestamp()
        * 1000
    )
    outdated_timestamp = int(
        (fake_now - timedelta(seconds=MAX_SYNC_INTERVAL_SECONDS + 10)).timestamp()
        * 1000
    )
    mocked_now.return_value = fake_now
    responses.add(
        responses.GET,
        MONITOR_CHANGES_URI,
        json={
            "changes": [
                {
                    "id": "a",
                    "bucket": "main",
                    "collection": "cid",
                    "last_modified": recent_timestamp,
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
                "remote-settings/monitor_changes": f'"{outdated_timestamp}"',
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
    assert responses.calls[2].request.method == "PUT"
