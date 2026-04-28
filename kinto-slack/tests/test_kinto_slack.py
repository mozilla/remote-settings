import unittest
from unittest import mock

from kinto_slack import _validate_slack_settings, get_messages


COLLECTION_METADATA = {
    "kinto-slack": {
        "hooks": [
            {
                "resource_name": "record",
                "action": "create",
                "channel": "#security-alerts",
                "template": "New record {record_id} in {collection_id}",
            },
            {
                "resource_name": "collection",
                "action": "update",
                "channel": "#ops",
                "template": "Collection {collection_id} was updated",
            },
        ]
    }
}

CONTEXT = {
    "bucket_id": "main-workspace",
    "collection_id": "my-collection",
    "resource_name": "record",
    "action": "create",
    "id": "abc123",
    "record_id": "abc123",
    "impacted_objects": [{"new": {"id": "abc123"}}],
}


class GetMessagesTest(unittest.TestCase):
    def setUp(self):
        self.storage = mock.MagicMock()
        self.storage.get.return_value = COLLECTION_METADATA

    def test_returns_message_for_matching_hook(self):
        (msg,) = get_messages(self.storage, CONTEXT)
        assert msg["channel"] == "#security-alerts"
        assert msg["text"] == "New record abc123 in my-collection"

    def test_interpolates_context_in_template(self):
        context = {**CONTEXT, "collection_id": "blocklist"}
        (msg,) = get_messages(self.storage, context)
        assert "blocklist" in msg["text"]

    def test_filters_by_action(self):
        context = {**CONTEXT, "action": "update"}
        assert get_messages(self.storage, context) == []

    def test_filters_by_resource_name(self):
        context = {**CONTEXT, "resource_name": "collection"}
        assert get_messages(self.storage, context) == []

    def test_filters_by_record_id(self):
        metadata = {
            "kinto-slack": {
                "hooks": [
                    {
                        "resource_name": "record",
                        "record_id": "specific-id",
                        "channel": "#alerts",
                        "template": "hit",
                    }
                ]
            }
        }
        self.storage.get.return_value = metadata
        context = {**CONTEXT, "record_id": "other-id", "id": "other-id"}
        assert get_messages(self.storage, context) == []

        context = {**CONTEXT, "record_id": "specific-id", "id": "specific-id"}
        assert len(get_messages(self.storage, context)) == 1

    def test_regex_filter(self):
        metadata = {
            "kinto-slack": {
                "hooks": [
                    {
                        "resource_name": "record",
                        "collection_id": "^prefix-.*",
                        "channel": "#alerts",
                        "template": "hit",
                    }
                ]
            }
        }
        self.storage.get.return_value = metadata
        assert (
            get_messages(self.storage, {**CONTEXT, "collection_id": "prefix-abc"}) != []
        )
        assert get_messages(self.storage, {**CONTEXT, "collection_id": "other"}) == []

    def test_falls_back_to_bucket_metadata(self):
        self.storage.get.side_effect = [
            {},  # collection metadata — no kinto-slack key
            COLLECTION_METADATA,  # bucket metadata
        ]
        (msg,) = get_messages(self.storage, CONTEXT)
        assert msg["channel"] == "#security-alerts"

    def test_no_hooks_returns_empty(self):
        self.storage.get.return_value = {}
        assert get_messages(self.storage, CONTEXT) == []

    def test_collection_resource_reads_from_impacted_object(self):
        context = {
            **CONTEXT,
            "resource_name": "collection",
            "action": "update",
            "impacted_objects": [
                {"new": {**COLLECTION_METADATA, "id": "my-collection"}}
            ],
        }
        (msg,) = get_messages(self.storage, context)
        assert msg["channel"] == "#ops"


class ValidateSlackSettingsTest(unittest.TestCase):
    def _make_event(self, hooks, action="update"):
        obj = {"kinto-slack": {"hooks": hooks}}
        event = mock.MagicMock()
        event.payload = {"action": action}
        event.impacted_objects = [{"new": obj}]
        return event

    def test_valid_hook_does_not_raise(self):
        event = self._make_event(
            [{"channel": "#alerts", "template": "msg", "action": "create"}]
        )
        _validate_slack_settings(event)  # no exception

    def test_missing_channel_raises(self):
        event = self._make_event([{"template": "msg"}])
        with mock.patch("kinto_slack.raise_invalid") as patched:
            _validate_slack_settings(event)
        patched.assert_called_once()
        assert "channel" in patched.call_args.kwargs["description"]

    def test_missing_template_raises(self):
        event = self._make_event([{"channel": "#alerts"}])
        with mock.patch("kinto_slack.raise_invalid") as patched:
            _validate_slack_settings(event)
        patched.assert_called_once()
        assert "template" in patched.call_args.kwargs["description"]

    def test_delete_action_skips_validation(self):
        event = self._make_event([], action="delete")
        event.impacted_objects = [
            {"old": {"kinto-slack": {"hooks": [{"bad": "hook"}]}}}
        ]
        _validate_slack_settings(event)  # no exception
