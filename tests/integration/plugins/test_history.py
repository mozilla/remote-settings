import pytest

from ...conftest import Auth, ClientFactory
from ..utils import setup_server


pytestmark = pytest.mark.asyncio


async def test_history_plugin(
    make_client: ClientFactory,
    setup_auth: Auth,
    editor_auth: Auth,
    keep_existing: bool,
    skip_server_setup: bool,
):
    editor_client = make_client(editor_auth)

    if not skip_server_setup:
        setup_client = make_client(setup_auth)
        await setup_server(setup_client, editor_client)

        if not keep_existing:
            await setup_client.purge_history()

    # Reset collection status.
    collection = await editor_client.get_collection()
    if collection["data"]["status"] != "signed":
        await editor_client.patch_collection(data={"status": "to-rollback"})

    # Create record, will set status to "work-in-progress"
    await editor_client.create_record(data={"hola": "mundo"})
    # Request review, will set status and update collection attributes.
    await editor_client.patch_collection(data={"status": "to-review"})

    history = await editor_client.get_history()

    history.reverse()
    collection_entries = [
        e
        for e in history
        if e["resource_name"] == "collection"
        and e["collection_id"] == editor_client.collection_name
    ]
    assert len(collection_entries) >= 3, "History does not contain expected events"
    (
        event_wip,
        event_to_review,
        event_review_attrs,
    ) = collection_entries[-3:]

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
