import os
import random
from string import hexdigits
from typing import Dict, List

import aiohttp
import pytest
import requests
from autograph_utils import MemoryCache, SignatureVerifier
from kinto_http import AsyncClient, KintoException
from kinto_http.patch_type import JSONPatch
from kinto_remote_settings.signer.serializer import canonical_json

from .conftest import Auth, ClientFactory


def test_heartbeat(server: str):
    resp = requests.get(f"{server}/__heartbeat__")
    resp.raise_for_status()


async def test_history_plugin(make_client: ClientFactory, auth: Auth):
    client = make_client(auth)
    client_id = (await client.server_info())["user"]["id"]
    await client.create_bucket(id="main-workspace", if_not_exists=True)
    await client.purge_history(bucket="main-workspace")
    await client.create_collection(
        id="product-integrity", bucket="main-workspace", if_not_exists=True
    )
    data = JSONPatch([{"op": "add", "path": "/data/members/0", "value": client_id}])
    await client.patch_group(id="product-integrity-editors", changes=data)
    await client.create_record(data={"hola": "mundo"})
    await client.patch_collection(data={"status": "to-review"})

    history = await client.get_history(bucket="main-workspace")

    history.reverse()
    collection_entries = [
        e
        for e in history
        if e["resource_name"] == "collection"
        and e["collection_id"] == "product-integrity"
    ]
    assert len(collection_entries) == 5

    (
        event_creation,
        event_signed,
        event_wip,
        event_to_review,
        event_review_attrs,
    ) = collection_entries

    assert event_creation["action"] == "create"
    assert event_creation["user_id"] == "account:user"

    assert event_signed["action"] == "update"
    assert "kinto-signer" in event_signed["user_id"]
    assert event_signed["target"]["data"]["status"] == "signed"

    assert event_wip["action"] == "update"
    assert "kinto-signer" in event_wip["user_id"]
    assert event_wip["target"]["data"]["status"] == "work-in-progress"

    assert event_to_review["action"] == "update"
    assert event_to_review["user_id"] == "account:user"
    assert event_to_review["target"]["data"]["status"] == "to-review"

    assert event_review_attrs["action"] == "update"
    assert "kinto-signer" in event_review_attrs["user_id"]
    assert (
        event_review_attrs["target"]["data"]["last_review_request_by"] == "account:user"
    )


async def test_email_plugin(make_client: ClientFactory, auth: Auth):
    # remove any existing .eml files in mail directory
    try:
        for file in os.listdir("mail"):
            os.remove(f"mail/{file}")
    except FileNotFoundError:
        pass

    client = make_client(auth)
    await client.create_bucket(id="main-workspace", if_not_exists=True)
    await client.create_collection(
        id="product-integrity", bucket="main-workspace", if_not_exists=True
    )
    await client.patch_bucket(
        id="main-workspace",
        data={
            "kinto-emailer": {
                "hooks": [
                    {
                        "event": "kinto_remote_settings.signer.events.ReviewRequested",
                        "subject": "{user_id} requested review on {bucket_id}/{collection_id}.",
                        "template": "Review changes at {root_url}admin/#/buckets/{bucket_id}/collections/{collection_id}/records",
                        "recipients": [
                            "me@you.com",
                            "/buckets/main-workspace/groups/reviewers",
                        ],
                    }
                ]
            }
        },
    )
    await client.patch_collection(
        id="product-integrity", bucket="main-workspace", data={"status": "to-review"}
    )

    mail = os.listdir("mail")
    assert mail, "No emails created"
    assert len(mail) == 1
    assert mail[0].endswith(".eml")

    with open(f"mail/{mail[0]}", "r") as f:
        mail_contents = f.read()
        assert mail_contents.find("Subject: account") >= 0
        assert mail_contents.find("To: me@you.com") >= 0


async def test_attachment_plugin_new_record(
    make_client: ClientFactory,
    auth: Auth,
    server: str,
):
    client = make_client(auth)
    await client.create_bucket(id="main-workspace", if_not_exists=True)
    await client.create_collection(
        id="product-integrity", bucket="main-workspace", if_not_exists=True
    )

    with open("kinto-logo.svg", "rb") as attachment:
        assert requests.post(
            f"{server}{await client.get_endpoint('record', bucket='main-workspace', collection='product-integrity', id='logo')}/attachment",
            files={"attachment": attachment},
            auth=client.session.auth,
        ), "Issue creating a new record with an attachment"

    record = await client.get_record(
        id="logo", bucket="main-workspace", collection="product-integrity"
    )

    assert record
    assert "data" in record
    assert "attachment" in record["data"]


async def test_attachment_plugin_existing_record(
    make_client: ClientFactory,
    auth: Auth,
    server: str,
):
    client = make_client(auth)
    await client.create_bucket(id="main-workspace", if_not_exists=True)
    await client.create_collection(
        id="product-integrity", bucket="main-workspace", if_not_exists=True
    )
    await client.create_record(
        id="logo",
        bucket="main-workspace",
        collection="product-integrity",
        data={"type": "logo"},
        if_not_exists=True,
    )

    with open("kinto-logo.svg", "rb") as attachment:
        assert requests.post(
            f"{server}{await client.get_endpoint('record', bucket='main-workspace', collection='product-integrity', id='logo')}/attachment",
            files={"attachment": attachment},
            auth=client.session.auth,
        ), "Issue updating an existing record to include an attachment"

    record = await client.get_record(
        id="logo", bucket="main-workspace", collection="product-integrity"
    )

    assert record
    assert "data" in record
    assert "attachment" in record["data"]


async def test_signer_plugin_capabilities(make_client: ClientFactory, auth: Auth):
    client = make_client(auth)
    capability = (await client.server_info())["capabilities"]["signer"]
    assert capability["group_check_enabled"]
    assert capability["to_review_enabled"]


async def test_signer_plugin_full_workflow(
    make_client: ClientFactory,
    auth: Auth,
    editor_auth: Auth,
    reviewer_auth: Auth,
    server: str,
    source_bucket: str,
    source_collection: str,
    keep_existing: bool,
):
    client = make_client(auth)
    editor_client = make_client(editor_auth)
    reviewer_client = make_client(reviewer_auth)

    # 0. initialize source bucket/collection (if necessary)
    server_info = await client.server_info()
    editor_id = (await editor_client.server_info())["user"]["id"]
    reviewer_id = (await reviewer_client.server_info())["user"]["id"]

    # 0. check that this collection is well configured.
    signer_capabilities = server_info["capabilities"]["signer"]

    resources = [
        r
        for r in signer_capabilities["resources"]
        if (source_bucket, source_collection)
        == (r["source"]["bucket"], r["source"]["collection"])
        or (source_bucket, None) == (r["source"]["bucket"], r["source"]["collection"])
    ]
    assert resources, "Specified source not configured to be signed"
    resource = resources[0]

    await client.create_bucket(if_not_exists=True)
    await client.create_bucket(id=resource["preview"]["bucket"], if_not_exists=True)
    await client.create_bucket(id=resource["destination"]["bucket"], if_not_exists=True)

    await client.create_collection(
        permissions={"write": [editor_id, reviewer_id]},
        if_not_exists=True,
    )

    editors_group = (
        resource.get("editors_group") or signer_capabilities["editors_group"]
    )
    editors_group = editors_group.format(collection_id=source_collection)
    data = JSONPatch([{"op": "add", "path": "/data/members/0", "value": editor_id}])
    await client.patch_group(id=editors_group, changes=data)

    reviewers_group = (
        resource.get("reviewers_group") or signer_capabilities["reviewers_group"]
    )
    reviewers_group = reviewers_group.format(collection_id=source_collection)
    data = JSONPatch([{"op": "add", "path": "/data/members/0", "value": reviewer_id}])
    await client.patch_group(id=reviewers_group, changes=data)

    dest_col = resource["destination"].get("collection") or source_collection
    dest_client = AsyncClient(
        server_url=server,
        bucket=resource["destination"]["bucket"],
        collection=dest_col,
    )

    preview_bucket = resource["preview"]["bucket"]
    preview_collection = resource["preview"].get("collection") or source_collection
    preview_client = AsyncClient(
        server_url=server,
        bucket=preview_bucket,
        collection=preview_collection,
    )

    existing_records = await client.get_records()
    existing = len(existing_records)
    if existing > 0 and not keep_existing:
        await client.delete_records()
        existing = 0

        # Status is now WIP.
        status = (await dest_client.get_collection())["data"]["status"]
        assert status == "work-in-progress", f"{status} != work-in-progress"

        # Re-sign and verify.
        await editor_client.patch_collection(data={"status": "to-review"})
        await reviewer_client.patch_collection(data={"status": "to-sign"})
        timestamp = await dest_client.get_records_timestamp()
        signature = (await dest_client.get_collection())["data"]["signature"]
        await verify_signature([], timestamp, signature)

    # 1. upload data
    records = await upload_records(client, 20)

    # 2. ask for a signature
    # 2.1 ask for review
    data = {"status": "to-review"}
    await editor_client.patch_collection(data=data)
    # 2.2 check the preview collection
    preview_records = await preview_client.get_records()
    expected = existing + 20
    assert (
        len(preview_records) == expected
    ), f"{len(preview_records)} != {expected} records"
    metadata = (await preview_client.get_collection())["data"]
    preview_signature = metadata.get("signature")
    assert preview_signature, "Preview collection not signed"
    preview_timestamp = await preview_client.get_records_timestamp()
    # Verify the preview collection
    await verify_signature(preview_records, preview_timestamp, preview_signature)

    # 2.3 approve the review
    data = {"status": "to-sign"}
    await reviewer_client.patch_collection(data=data)

    # 3. upload more data
    await upload_records(client, 20)

    for toupdate in random.sample(records, 5):
        await editor_client.patch_record(data=dict(newkey=_rand(10), **toupdate))

    for todelete in random.sample(records, 5):
        await client.delete_record(id=todelete["id"])

    expected = existing + 20 + 20 - 5

    # 4. ask again for a signature
    # 2.1 ask for review (noop on old versions)
    data = {"status": "to-review"}
    await editor_client.patch_collection(data=data)
    # 2.2 check the preview collection
    preview_records = await preview_client.get_records()
    assert (
        len(preview_records) == expected
    ), f"{len(preview_records)} != {expected} records"
    # Diff size is 20 + 5 if updated records are also all deleted,
    # or 30 if deletions and updates apply to different records.
    diff_since_last = await preview_client.get_records(_since=preview_timestamp)
    assert (
        25 <= len(diff_since_last) <= 30
    ), "Changes since last signature are not consistent"

    metadata = (await preview_client.get_collection())["data"]
    assert preview_signature != metadata["signature"], "Preview collection not updated"

    # 2.3 approve the review
    data = {"status": "to-sign"}
    await reviewer_client.patch_collection(data=data)

    # 5. verify signature

    records = list(await dest_client.get_records())
    assert len(records) == expected, f"{len(records)} != {expected} records"
    timestamp = await dest_client.get_records_timestamp()
    signature = (await dest_client.get_collection())["data"]["signature"]

    try:
        await verify_signature(records, timestamp, signature)
    except Exception:
        print("Signature KO")
        raise


async def test_signer_plugin_rollback(make_client: ClientFactory, auth: Auth):
    client = make_client(auth)
    await client.create_bucket(id="main-workspace", if_not_exists=True)
    await client.create_collection(
        id="product-integrity", bucket="main-workspace", if_not_exists=True
    )
    before_records = await client.get_records()

    await upload_records(client, 5)

    records = await client.get_records()
    assert len(records) == len(before_records) + 5
    await client.patch_collection(data={"status": "to-rollback"})
    records = await client.get_records()
    assert len(records) == len(before_records)


async def test_signer_plugin_refresh(
    make_client: ClientFactory,
    auth: Auth,
    reviewer_auth: Auth,
):
    cid = "product-integrity"
    client = make_client(auth)
    reviewer_client = make_client(reviewer_auth)
    reviewer_id = (await reviewer_client.server_info())["user"]["id"]
    await client.create_bucket(id="main-workspace", if_not_exists=True)
    await client.create_collection(id=cid, bucket="main-workspace", if_not_exists=True)
    data = JSONPatch([{"op": "add", "path": "/data/members/0", "value": reviewer_id}])
    await client.patch_group(id="product-integrity-reviewers", changes=data)
    await upload_records(client, 5)
    await client.patch_collection(data={"status": "to-review"})
    await reviewer_client.patch_collection(id=cid, data={"status": "to-sign"})
    signature_preview_before = (await client.get_collection(bucket="main-preview"))[
        "data"
    ]["signature"]
    signature_before = (await client.get_collection(bucket="main"))["data"]["signature"]

    await reviewer_client.patch_collection(id=cid, data={"status": "to-resign"})

    signature = (await client.get_collection(bucket="main"))["data"]["signature"]
    signature_preview = (await client.get_collection(bucket="main"))["data"][
        "signature"
    ]

    assert signature_before != signature
    assert signature_preview_before != signature_preview


async def test_signer_plugin_reviewer_verifications(
    make_client: ClientFactory,
    auth: Auth,
    reviewer_auth: Auth,
):
    client = make_client(auth)
    client_id = (await client.server_info())["user"]["id"]
    reviewer_client = make_client(reviewer_auth)
    reviewer_id = (await reviewer_client.server_info())["user"]["id"]
    await client.create_bucket(id="main-workspace", if_not_exists=True)
    await client.create_collection(
        id="product-integrity", bucket="main-workspace", if_not_exists=True
    )
    await client.patch_group(
        id="product-integrity-editors", data={"members": [client_id]}
    )
    await client.patch_group(
        id="product-integrity-reviewers", data={"members": [client_id, reviewer_id]}
    )
    await upload_records(client, 5)

    # status cannot be set to to-sign
    with pytest.raises(KintoException):
        await reviewer_client.patch_collection(data={"status": "to-sign"})

    # reviewer cannot ask review
    with pytest.raises(KintoException):
        await reviewer_client.patch_collection(data={"status": "to-review"})

    # Add reviewer to editors
    await client.patch_group(
        id="product-integrity-editors", data={"members": [reviewer_id]}
    )
    await reviewer_client.patch_collection(data={"status": "to-review"})
    # same editor cannot review
    with pytest.raises(KintoException):
        await reviewer_client.patch_collection(data={"status": "to-sign"})

    # review must be asked after cancelled
    await client.patch_collection(data={"status": "to-review"})
    await reviewer_client.patch_collection(data={"status": "work-in-progress"})
    with pytest.raises(KintoException):
        await reviewer_client.patch_collection(data={"status": "to-sign"})

    await reviewer_client.patch_collection(data={"status": "to-review"})
    # Client can now review because he is not the last_editor.
    await client.patch_collection(data={"status": "to-sign"})


class FakeRootHash:
    def __eq__(self, val):
        return True


async def verify_signature(records, timestamp, signature):
    x5u = signature["x5u"].replace("file:///tmp/autograph/", "http://certchains/")
    serialized = canonical_json(records, timestamp).encode("utf-8")

    async with aiohttp.ClientSession() as session:
        verifier = SignatureVerifier(session, MemoryCache(), FakeRootHash())
        await verifier.verify(serialized, signature["signature"], x5u)


async def test_changes_plugin(make_client: ClientFactory, auth: Auth):
    client = make_client(auth)
    await client.create_bucket(id="main-workspace", if_not_exists=True)
    await client.create_collection(
        id="product-integrity", bucket="main-workspace", if_not_exists=True
    )
    records = await client.get_records(bucket="monitor", collection="changes")

    assert records
    assert len(records) == 1
    assert "bucket" in records[0]
    assert records[0]["bucket"] == "main-workspace"

    initial_last_modified = records[0]["last_modified"]

    await upload_records(client, 10, "main-workspace", "product-integrity")
    records = await client.get_records(bucket="monitor", collection="changes")

    updated_last_modified = records[0]["last_modified"]

    assert updated_last_modified > initial_last_modified


def _rand(size: int = 10) -> str:
    return "".join(random.choices(hexdigits, k=size))


async def upload_records(
    client: AsyncClient, num: int, bucket: str = None, collection: str = None
) -> List[Dict]:
    records = []
    for _ in range(num):
        data = {"one": _rand(1000)}
        record = await client.create_record(
            data=data, bucket=bucket, collection=collection
        )
        records.append(record["data"])
    return records
