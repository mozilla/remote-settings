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

    def tearDown(self):
        super().tearDown()
        self.app.app.registry.cache.flush()

    def get_broadcasted_version(self):
        response = self.app.get("/__broadcasts__")
        return response.json["broadcasts"]["remote-settings/monitor_changes"]

    def test_first_call_returns_current_version(self):
        self.monitored_timestamps.return_value = [
            ("main", "cid", FAKE_TIMESTAMP),
            ("main", "cid2", FAKE_TIMESTAMP - 1000),
        ]
        self.app.app.registry.cache.flush()

        assert self.get_broadcasted_version() == f'"{FAKE_TIMESTAMP}"'

    def test_preview_buckets_and_collections_are_ignored(self):
        self.monitored_timestamps.return_value = [
            ("main-preview", "cid", FAKE_TIMESTAMP + 2000),
            ("main", "cid-preview", FAKE_TIMESTAMP + 1000),
            ("main", "cid", FAKE_TIMESTAMP),
        ]
        self.app.app.registry.cache.flush()

        assert self.get_broadcasted_version() == f'"{FAKE_TIMESTAMP}"'

    def test_returns_current_value_if_up_to_date(self):
        self.monitored_timestamps.return_value = [("main", "cid", FAKE_TIMESTAMP)]

        assert self.get_broadcasted_version() == f'"{FAKE_TIMESTAMP}"'
        assert self.get_broadcasted_version() == f'"{FAKE_TIMESTAMP}"'
        self.monitored_timestamps.assert_called_once()  # Only one call to the database, second call is cached

    def test_database_is_not_hit_when_last_published_is_younger_than_min_debounce(self):
        """
        ================o=>>>
                        |
                        +----> latest published (3 min ago < min debounce)
        """
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

    def test_ignores_intermediary_versions_aka_debounce(self):
        """
        ===o==x==x==x==o==========>>>
           |  |  |  |  |
           |  |  |  |  +-------------> latest timestamp published
           |  |  |  |
           |  +--+--+----------------> intermediary timestamps are ignored (aka. debounce)
           |
           +-------------------------> latest published
        """
        obtained = []
        for age in range(12, 5, -1):
            # Go back in time for each iteration to simulate the passage of time
            # and the publication of intermediary changes.
            self.utcnow.return_value = FAKE_NOW - datetime.timedelta(minutes=age)
            # One change every minute.
            latest_timestamp = int(
                (FAKE_NOW - datetime.timedelta(minutes=age + 1)).timestamp() * 1000
            )
            self.monitored_timestamps.return_value = [("main", "cid", latest_timestamp)]
            obtained.append(self.get_broadcasted_version())

        assert obtained == [obtained[0]] * 6 + [obtained[-1]]

    def test_return_cache_if_cached_and_current_are_older_than_min_debounce(
        self,
    ):
        """
        ===ox========>>>
           ||
           |+--> latest timestamp (6 min ago, but no change since then), return cache!
           |
           +-------------------> latest published
        """
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

        assert self.get_broadcasted_version() == f'"{cache_timestamp}"'

    def test_return_cache_version_if_latest_changes_are_newer_than_min_debounce(
        self,
    ):
        """
        ======o==x==>>>
              |  |
              |  +----> latest timestamp (2min ago but only 4 min diff with previous), return cache!
              |
              +--------> latest published (6min ago, > min )
        """
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

    def test_return_cache_version_if_latest_changes_are_older_than_min_debounce(
        self,
    ):
        """
        ===o======x=>>>
           |      |
           |      +--> latest timestamp (2min ago but 6 min diff with previous > min debounce), publish!
           |
           +---------> latest published (8 min ago > min debounce)
        """
        latest_timestamp = int(
            (FAKE_NOW - datetime.timedelta(minutes=2)).timestamp() * 1000
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

    def test_return_current_version_if_latest_changes_are_older_than_min_debounce(
        self,
    ):
        """
        ==o==x======>>>
          |  |
          |  +----> latest timestamp (6 min ago, but 2 min diff with previous, too close)
          |
          +-------> latest published (8 min ago > min debounce)
        """
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

        assert self.get_broadcasted_version() == f'"{cache_timestamp}"'
