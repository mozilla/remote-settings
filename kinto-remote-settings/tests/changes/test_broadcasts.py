import datetime
import unittest
from unittest import mock

from . import BaseWebTest


FAKE_NOW = datetime.datetime(2023, 10, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
DAY_IN_SECONDS = 24 * 60 * 60


class BroadcastsTest(BaseWebTest, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.app = self.make_app()

        utcnow = mock.patch("kinto_remote_settings.changes.views.utcnow")
        self.utcnow = utcnow.start()
        self.utcnow.return_value = FAKE_NOW
        self.addCleanup(utcnow.stop)

        monitored_timestamps = mock.patch(
            "kinto_remote_settings.changes.views.monitored_timestamps"
        )
        self.monitored_timestamps = monitored_timestamps.start()
        self.addCleanup(monitored_timestamps.stop)

    def get_broadcasted_version(self):
        response = self.app.get("/__broadcasts__")
        return response.json["broadcasts"]["remote-settings/monitor_changes"]

    def test_first_call_returns_current_version(self):
        self.monitored_timestamps.return_value = [("main", "cid", 42)]
        self.app.app.registry.cache.flush()

        assert self.get_broadcasted_version() == '"42"'

    def test_returns_current_value_if_up_to_date(self):
        self.monitored_timestamps.return_value = [("main", "cid", 42)]

        assert self.get_broadcasted_version() == '"42"'
        assert self.get_broadcasted_version() == '"42"'

    def test_return_current_version_if_last_is_older_than_debounce_seconds(self):
        # Last timestamp is too old (> max debounce), new one should be published
        old_timestamp = int(
            (FAKE_NOW - datetime.timedelta(minutes=25)).timestamp() * 1000
        )
        self.app.app.registry.cache.set(
            "remote-settings/monitor_changes/timestamp",
            old_timestamp,
            ttl=DAY_IN_SECONDS,
        )
        new_timestamp = int(
            (FAKE_NOW - datetime.timedelta(minutes=3)).timestamp() * 1000
        )
        self.monitored_timestamps.return_value = [("main", "cid", new_timestamp)]

        assert self.get_broadcasted_version() == f'"{new_timestamp}"'

    def test_return_last_version_if_newer_than_debounce_seconds_and_last_is_recent(
        self,
    ):
        # New timestamp is too fresh (< debounce), and last timestamp is still valid
        latest_timestamp = int(
            (FAKE_NOW - datetime.timedelta(minutes=3)).timestamp() * 1000
        )
        self.monitored_timestamps.return_value = [("main", "cid", latest_timestamp)]
        last_published = int(
            (FAKE_NOW - datetime.timedelta(minutes=19)).timestamp() * 1000
        )
        self.app.app.registry.cache.set(
            "remote-settings/monitor_changes/timestamp",
            last_published,
            ttl=DAY_IN_SECONDS,
        )

        assert self.get_broadcasted_version() == f'"{last_published}"'

    def test_return_current_version_if_newer_than_debounce_seconds_but_last_is_old(
        self,
    ):
        old_timestamp = int(
            (FAKE_NOW - datetime.timedelta(minutes=21)).timestamp() * 1000
        )
        self.app.app.registry.cache.set(
            "remote-settings/monitor_changes/timestamp",
            old_timestamp,
            ttl=DAY_IN_SECONDS,
        )
        recent_timestamp = int(
            (FAKE_NOW - datetime.timedelta(minutes=3)).timestamp() * 1000
        )
        self.monitored_timestamps.return_value = [("main", "cid", recent_timestamp)]

        assert self.get_broadcasted_version() == f'"{recent_timestamp}"'
