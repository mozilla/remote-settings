from unittest.mock import MagicMock, patch

from commands.consumption_movers import (
    MIN_AVG_BYTES,
    consumption_movers,
)


BIG_SIZE = MIN_AVG_BYTES * 2  # clearly above threshold
SMALL_SIZE = MIN_AVG_BYTES / 10  # clearly below threshold


def run_movers(
    previous: dict[str, float],
    last: dict[str, float],
    webhook_url="https://hooks.slack.com/test",
):
    with patch("commands.consumption_movers.bigquery.Client") as mock_client:
        mock_client.return_value.query.return_value.result.side_effect = [
            previous,
            last,
        ]
        with patch("commands.consumption_movers.SLACK_WEBHOOK_URL", webhook_url):
            with patch("commands.consumption_movers.requests.post") as mock_post:
                mock_post.return_value = MagicMock()
                consumption_movers()
                return mock_post


def slack_text(mock_post) -> str:
    return mock_post.call_args.kwargs["json"]["text"]


def test_new_collections_are_ignored():
    mock_post = run_movers(
        previous={"known": BIG_SIZE},
        last={"known": BIG_SIZE * 1.5, "brand-new": BIG_SIZE * 2},
    )
    assert "brand-new" not in slack_text(mock_post)


def test_small_collections_are_filtered():
    mock_post = run_movers(
        previous={"tiny": SMALL_SIZE},
        last={"tiny": SMALL_SIZE * 2},
    )
    assert "tiny" not in slack_text(mock_post)


def test_previously_large_collection_kept():
    mock_post = run_movers(
        previous={"shrinking": BIG_SIZE},
        last={"shrinking": SMALL_SIZE},
    )
    assert "shrinking" in slack_text(mock_post)


def test_previously_small_collection_kept():
    mock_post = run_movers(
        previous={"growing": SMALL_SIZE},
        last={"growing": BIG_SIZE},
    )
    assert "growing" in slack_text(mock_post)


def test_no_increase_section_when_none():
    mock_post = run_movers(
        previous={"down": BIG_SIZE},
        last={"down": BIG_SIZE * 0.5},
    )
    text = slack_text(mock_post)
    assert "Top increases" not in text
    assert "Top decreases" in text


def test_increases_sorted_by_delta_descending():
    mock_post = run_movers(
        previous={"big-delta": BIG_SIZE, "small-delta": BIG_SIZE},
        last={"big-delta": BIG_SIZE * 3, "small-delta": BIG_SIZE * 1.1},
    )
    text = slack_text(mock_post)
    assert text.index("big-delta") < text.index("small-delta")


def test_decreases_sorted_by_delta_ascending():
    mock_post = run_movers(
        previous={"big-drop": BIG_SIZE * 3, "small-drop": BIG_SIZE},
        last={"big-drop": BIG_SIZE, "small-drop": BIG_SIZE * 0.9},
    )
    text = slack_text(mock_post)
    assert text.index("big-drop") < text.index("small-drop")


def test_slack_payload_shape():
    mock_post = run_movers(
        previous={"cid": BIG_SIZE},
        last={"cid": BIG_SIZE * 2},
    )
    mock_post.assert_called_once()
    payload = mock_post.call_args.kwargs["json"]
    assert "channel" in payload
    assert "text" in payload
