import os
from datetime import datetime, timezone
from itertools import product
from unittest import mock

import pytest
import responses
from commands.purge_history import purge_history


SERVER_URL = "https://fake-server.net/v1"


@pytest.fixture(scope="module", autouse=True)
def set_env_var():
    with mock.patch.dict(
        os.environ,
        {
            "SERVER": SERVER_URL,
            "AUTH": "root:123",
            "BUCKETS": "bid1,bid2",
            "USER_IDS": "account:user1,account:user2",
            "MAX_AGE_DAYS": "3",
        },
    ):
        yield


@pytest.fixture
def mocked_now():
    with mock.patch("commands.purge_history.utcnow") as mocked:
        yield mocked


@responses.activate
def test_deletes_from_all_history_endpoints(mocked_now):
    fake_now = datetime(2024, 3, 27, 13, 37, tzinfo=timezone.utc)
    mocked_now.return_value = fake_now

    for bid in ("bid1", "bid2"):
        responses.add(
            responses.DELETE,
            f"{SERVER_URL}/buckets/{bid}/history",
            json={"data": []},
        )

    purge_history()

    assert len(responses.calls) == 4
    for i, (bid, user) in enumerate(
        product(("bid1", "bid2"), ("account:user1", "account:user2"))
    ):
        assert (
            responses.calls[i].request.headers["Authorization"] == "Basic cm9vdDoxMjM="
        )
        assert responses.calls[i].request.params["_before"] == '"1711287420000"'
        assert f"/buckets/{bid}/history" in responses.calls[i].request.path_url
        assert responses.calls[i].request.params["user_id"] == user
