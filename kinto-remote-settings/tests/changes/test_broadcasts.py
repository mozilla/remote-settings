import datetime
import unittest
from unittest import mock

from . import BaseWebTest


FAKE_NOW = datetime.datetime(2023, 10, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
DAY_IN_SECONDS = 24 * 60 * 60
FAKE_TIMESTAMP = int(FAKE_NOW.timestamp() * 1000)


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
        self.monitored_timestamps.return_value = [("main", "cid", FAKE_TIMESTAMP)]
        self.app.app.registry.cache.flush()

        assert self.get_broadcasted_version() == f'"{FAKE_TIMESTAMP}"'

    def test_returns_current_value_if_up_to_date(self):
        self.monitored_timestamps.return_value = [("main", "cid", FAKE_TIMESTAMP)]

        assert self.get_broadcasted_version() == f'"{FAKE_TIMESTAMP}"'
        assert self.get_broadcasted_version() == f'"{FAKE_TIMESTAMP}"'

    def test_database_is_not_hit_when_last_published_is_younger_than_min_debounce(self):
        old_timestamp = int(
            (FAKE_NOW - datetime.timedelta(minutes=3)).timestamp() * 1000
        )
        self.app.app.registry.cache.set(
            "remote-settings/monitor_changes/timestamp",
            old_timestamp,
            ttl=DAY_IN_SECONDS,
        )

        assert self.get_broadcasted_version() == f'"{old_timestamp}"'
        self.monitored_timestamps.assert_not_called()

    def test_return_current_version_if_last_publish_is_older_than_max_debounce(self):
        # Last timestamp is too old (> max debounce), new one should be published
        old_timestamp = int(
            (FAKE_NOW - datetime.timedelta(minutes=21)).timestamp() * 1000
        )
        self.app.app.registry.cache.set(
            "remote-settings/monitor_changes/timestamp",
            old_timestamp,
            ttl=DAY_IN_SECONDS,
        )
        self.monitored_timestamps.return_value = [("main", "cid", FAKE_TIMESTAMP)]

        assert self.get_broadcasted_version() == f'"{FAKE_TIMESTAMP}"'

    def test_return_current_version_if_last_publish_is_equal_to_current_even_if_old(
        self,
    ):
        latest_timestamp = int(
            (FAKE_NOW - datetime.timedelta(minutes=21)).timestamp() * 1000
        )
        self.app.app.registry.cache.set(
            "remote-settings/monitor_changes/timestamp",
            latest_timestamp,
            ttl=DAY_IN_SECONDS,
        )
        self.monitored_timestamps.return_value = [("main", "cid", latest_timestamp)]

        assert self.get_broadcasted_version() == f'"{latest_timestamp}"'

    def test_return_current_version_if_last_publish_is_equal_to_current_even_if_recent(
        self,
    ):
        latest_timestamp = int(
            (FAKE_NOW - datetime.timedelta(minutes=6)).timestamp() * 1000
        )
        self.app.app.registry.cache.set(
            "remote-settings/monitor_changes/timestamp",
            latest_timestamp,
            ttl=DAY_IN_SECONDS,
        )
        self.monitored_timestamps.return_value = [("main", "cid", latest_timestamp)]

        assert self.get_broadcasted_version() == f'"{latest_timestamp}"'

    def test_return_current_version_if_cached_and_current_are_older_than_min_debounce(
        self,
    ):
        latest_timestamp = int(
            (FAKE_NOW - datetime.timedelta(minutes=6)).timestamp() * 1000
        )
        cache_timestamp = latest_timestamp
        self.app.app.registry.cache.set(
            "remote-settings/monitor_changes/timestamp",
            cache_timestamp,
            ttl=DAY_IN_SECONDS,
        )
        self.monitored_timestamps.return_value = [("main", "cid", latest_timestamp)]

        assert self.get_broadcasted_version() == f'"{latest_timestamp}"'

    def test_return_cache_version_if_latest_changes_are_newer_than_min_debounce(
        self,
    ):
        latest_timestamp = int(
            (FAKE_NOW - datetime.timedelta(minutes=2)).timestamp() * 1000
        )
        cache_timestamp = int(
            (FAKE_NOW - datetime.timedelta(minutes=6)).timestamp() * 1000
        )
        self.app.app.registry.cache.set(
            "remote-settings/monitor_changes/timestamp",
            cache_timestamp,
            ttl=DAY_IN_SECONDS,
        )
        self.monitored_timestamps.return_value = [("main", "cid", latest_timestamp)]

        assert self.get_broadcasted_version() == f'"{cache_timestamp}"'

    def test_return_current_version_if_latest_changes_are_older_than_min_debounce(
        self,
    ):
        latest_timestamp = int(
            (FAKE_NOW - datetime.timedelta(minutes=6)).timestamp() * 1000
        )
        cache_timestamp = int(
            (FAKE_NOW - datetime.timedelta(minutes=8)).timestamp() * 1000
        )
        self.app.app.registry.cache.set(
            "remote-settings/monitor_changes/timestamp",
            cache_timestamp,
            ttl=DAY_IN_SECONDS,
        )
        self.monitored_timestamps.return_value = [("main", "cid", latest_timestamp)]

        assert self.get_broadcasted_version() == f'"{latest_timestamp}"'
