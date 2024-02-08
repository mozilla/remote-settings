import pytest

from ...conftest import Auth, ClientFactory, signed_resource
from ..utils import setup_server, upload_records


pytestmark = pytest.mark.asyncio


def find_changes_record(records: list[dict], bucket: str, collection: str):
    return next(
        (
            record
            for record in records
            if record["collection"] == collection and record["bucket"] == bucket
        )
    )


async def test_changes_plugin(
    make_client: ClientFactory,
    setup_auth: Auth,
    editor_auth: Auth,
    reviewer_auth: Auth,
    source_collection: str,
    skip_server_setup: bool,
):
    if not skip_server_setup:
        setup_client = make_client(setup_auth)
        setup_server(setup_client)

    anonymous_client = make_client(tuple())
    editor_client = make_client(editor_auth)
    reviewer_client = make_client(reviewer_auth)

    # 1. Inspect the content of monitor/changes to get some reference timestamp
    records = anonymous_client.get_records(bucket="monitor", collection="changes")
    resource = signed_resource(editor_client)

    initial_preview = find_changes_record(
        records=records,
        bucket=resource["preview"]["bucket"],
        collection=source_collection,
    )
    initial_destination = find_changes_record(
        records=records,
        bucket=resource["destination"]["bucket"],
        collection=source_collection,
    )

    # 2. Upload records and request review
    upload_records(editor_client, 1)
    editor_client.patch_collection(data={"status": "to-review"})

    # 3. Compare timestamps and assert that preview timestamp was bumped,
    #    and destination wasn't
    records = anonymous_client.get_records(bucket="monitor", collection="changes")
    preview = find_changes_record(
        records=records,
        bucket=resource["preview"]["bucket"],
        collection=source_collection,
    )
    destination = find_changes_record(
        records=records,
        bucket=resource["destination"]["bucket"],
        collection=source_collection,
    )

    assert preview["last_modified"] > initial_preview["last_modified"]
    assert destination["last_modified"] == initial_destination["last_modified"]

    # 4. We approve the changes, and then assert that destination timestamp was bumped
    reviewer_client.patch_collection(data={"status": "to-sign"})
    records = anonymous_client.get_records(bucket="monitor", collection="changes")
    preview = find_changes_record(
        records=records,
        bucket=resource["preview"]["bucket"],
        collection=source_collection,
    )
    destination = find_changes_record(
        records=records,
        bucket=resource["destination"]["bucket"],
        collection=source_collection,
    )
    assert preview["last_modified"] > initial_preview["last_modified"]
    assert destination["last_modified"] > initial_destination["last_modified"]
