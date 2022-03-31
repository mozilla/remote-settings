import pytest

from ...conftest import Auth, ClientFactory, signed_resource
from ..utils import setup_server, upload_records


pytestmark = pytest.mark.asyncio


async def test_changes_plugin(
    make_client: ClientFactory,
    setup_auth: Auth,
    editor_auth: Auth,
    skip_server_setup: bool,
):
    if not skip_server_setup:
        setup_client = make_client(setup_auth)
        await setup_server(setup_client)

    anonymous_client = make_client(tuple())
    records = await anonymous_client.get_records(bucket="monitor", collection="changes")

    editor_client = make_client(editor_auth)
    resource = await signed_resource(editor_client)

    assert records
    assert len(records) == 2
    assert "bucket" in records[0]
    assert records[0]["bucket"] == resource["destination"]["bucket"]
    assert records[1]["bucket"] == resource["preview"]["bucket"]

    initial_last_modified = records[0]["last_modified"]

    await upload_records(editor_client, 10)
    await editor_client.patch_collection(data={"status": "to-review"})

    records = await anonymous_client.get_records(bucket="monitor", collection="changes")

    updated_last_modified = records[0]["last_modified"]
    assert records[0]["bucket"] == resource["preview"]["bucket"]

    assert updated_last_modified > initial_last_modified
