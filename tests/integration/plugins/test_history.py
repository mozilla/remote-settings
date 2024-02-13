import pytest

from ...conftest import Auth, ClientFactory


pytestmark = pytest.mark.asyncio


async def test_history_plugin(
    setup_client: ClientFactory,
    editor_client: ClientFactory,
    editor_auth: Auth,
    keep_existing: bool,
    skip_server_setup: bool,
):
    if not skip_server_setup and not keep_existing:
        setup_client.purge_history()

    # Reset collection status.
    collection = editor_client.get_collection()
    timestamp_start = collection["data"]["last_modified"]
    if collection["data"]["status"] != "signed":
        editor_client.patch_collection(data={"status": "to-rollback"})

    # Create record, will set status to "work-in-progress"
    editor_client.create_record(data={"hola": "mundo"})
    # Request review, will set status and update collection attributes.
    editor_client.patch_collection(data={"status": "to-review"})

    history_entries = editor_client.get_history(
        resource_name="collection",
        collection_id=editor_client.collection_name,
        _since=timestamp_start,
    )

    history_entries.reverse()
    assert len(history_entries) >= 3, "History does not contain expected events"
    (
        event_wip,
        event_to_review,
        event_review_attrs,
    ) = history_entries[-3:]

    assert event_wip["action"] == "update"
    assert "kinto-signer" in event_wip["user_id"]
    assert event_wip["target"]["data"]["status"] == "work-in-progress"

    assert event_to_review["action"] == "update"
    assert event_to_review["user_id"] == f"account:{editor_auth[0]}"
    assert event_to_review["target"]["data"]["status"] == "to-review"

    assert event_review_attrs["action"] == "update"
    assert "kinto-signer" in event_review_attrs["user_id"]
    assert (
        event_review_attrs["target"]["data"]["last_review_request_by"]
        == f"account:{editor_auth[0]}"
    )
