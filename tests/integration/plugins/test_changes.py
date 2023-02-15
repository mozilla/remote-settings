import pytest

from ...conftest import Auth, ClientFactory, signed_resource
from ..utils import setup_server, upload_records


pytestmark = pytest.mark.asyncio


async def test_changes_plugin(
    make_client: ClientFactory,
    setup_auth: Auth,
    editor_auth: Auth,
    source_collection: str,
    skip_server_setup: bool,
):
    if not skip_server_setup:
        setup_client = make_client(setup_auth)
        await setup_server(setup_client)

    anonymous_client = make_client(tuple())
    records = await anonymous_client.get_records(bucket="monitor", collection="changes")
    assert records

    test_collection_records = [
        record for record in records if record["collection"] == source_collection
    ]
    assert len(test_collection_records) == 2

    editor_client = make_client(editor_auth)
    resource = await signed_resource(editor_client)
    assert "bucket" in test_collection_records[0]

    initial_last_modified = test_collection_records[0]["last_modified"]
    await upload_records(editor_client, 10)
    await editor_client.patch_collection(data={"status": "to-review"})

    records = await anonymous_client.get_records(bucket="monitor", collection="changes")
    test_collection_records = [
        record for record in records if record["collection"] == source_collection
    ]

    updated_last_modified = test_collection_records[0]["last_modified"]

    assert updated_last_modified > initial_last_modified
