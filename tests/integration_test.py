import os
import random
from string import hexdigits
from typing import Callable, Dict, List, Tuple

import pytest
import requests
from kinto_http import AsyncClient

from kinto_remote_settings.signer.backends.local_ecdsa import ECDSASigner
from kinto_remote_settings.signer.serializer import canonical_json


pytestmark = pytest.mark.asyncio


async def test_history_plugin(
    make_client: Callable[[Tuple[str, str]], AsyncClient], auth: Tuple[str, str]
):
    client = make_client(auth)
    await client.create_bucket(id="main-workspace", if_not_exists=True)
    await client.create_collection(
        id="product-integrity", bucket="main-workspace", if_not_exists=True
    )
    history = await client.get_history(bucket="main-workspace")

    assert history
    assert len(history) == 5
    assert "user_id" in history[0]
    assert "plugin:kinto-signer" == history[0]["user_id"]
    assert "collection_id" in history[-2]
    assert "product-integrity" == history[-2]["collection_id"]
    assert "bucket_id" in history[-1]
    assert "main-workspace" == history[-1]["bucket_id"]


async def test_email_plugin(
    make_client: Callable[[Tuple[str, str]], AsyncClient], auth: Tuple[str, str]
):
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
    make_client: Callable[[Tuple[str, str]], AsyncClient],
    auth: Tuple[str, str],
    server: str,
):
    client = make_client(auth)
    await client.create_bucket(id="main-workspace", if_not_exists=True)
    await client.create_collection(
        id="product-integrity", bucket="main-workspace", if_not_exists=True
    )

    with open("kinto-logo.svg", "rb") as attachment:
        assert requests.post(
            f"{server}/buckets/main-workspace/collections/product-integrity/records/logo/attachment",
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
    make_client: Callable[[Tuple[str, str]], AsyncClient],
    auth: Tuple[str, str],
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
            f"{server}/buckets/main-workspace/collections/product-integrity/records/logo/attachment",
            files={"attachment": attachment},
            auth=client.session.auth,
        ), "Issue updating an existing record to include an attachment"

    record = await client.get_record(
        id="logo", bucket="main-workspace", collection="product-integrity"
    )

    assert record
    assert "data" in record
    assert "attachment" in record["data"]


async def test_signer_plugin(
    make_client: Callable[[Tuple[str, str]], AsyncClient],
    auth: Tuple[str, str],
    editor_auth: Tuple[str, str],
    reviewer_auth: Tuple[str, str],
    server: str,
    source_bucket: str,
    source_collection: str,
    reset: bool,
):
    client = make_client(auth)
    editor_client = make_client(editor_auth)
    reviewer_client = make_client(reviewer_auth)

    # 0. initialize source bucket/collection (if necessary)
    server_info = await client.server_info()
    editor_id = (await editor_client.server_info())["user"]["id"]
    reviewer_id = (await reviewer_client.server_info())["user"]["id"]
    print("Server: {0}".format(server))
    print("Author: {user[id]}".format(**server_info))
    print("Editor: {0}".format(editor_id))
    print("Reviewer: {0}".format(reviewer_id))

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
    msg = (
        "Signoff: {source[bucket]}/{source[collection]} => "
        "{preview[bucket]}/{preview[collection]} => "
        "{destination[bucket]}/{destination[collection]} "
    )
    print(msg.format(**resource))
    print("_" * 80)

    await client.create_bucket(if_not_exists=True)
    await client.create_bucket(id=resource["preview"]["bucket"], if_not_exists=True)
    bucket = await client.create_bucket(
        id=resource["destination"]["bucket"], if_not_exists=True
    )

    await client.create_collection(
        permissions={
            "write": [editor_id, reviewer_id] + bucket["permissions"]["write"]
        },
        if_not_exists=True,
    )

    editors_group = (
        resource.get("editors_group") or signer_capabilities["editors_group"]
    )
    editors_group = editors_group.format(collection_id=source_collection)
    await client.patch_group(id=editors_group, data={"members": [editor_id]})

    reviewers_group = (
        resource.get("reviewers_group") or signer_capabilities["reviewers_group"]
    )
    reviewers_group = reviewers_group.format(collection_id=source_collection)
    await client.patch_group(id=reviewers_group, data={"members": [reviewer_id]})

    if reset:
        await client.delete_records()
        existing = 0
    else:
        existing_records = await client.get_records()
        existing = len(existing_records)

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

    # 1. upload data
    print("Author uploads 20 random records")
    records = await upload_records(client, 20)

    # 2. ask for a signature
    # 2.1 ask for review (noop on old versions)
    print("Editor asks for review")
    data = {"status": "to-review"}
    await editor_client.patch_collection(data=data)
    # 2.2 check the preview collection
    print("Check preview collection")
    preview_records = await preview_client.get_records()
    expected = existing + 20
    assert (
        len(preview_records) == expected
    ), f"{len(preview_records)} != {expected} records"
    metadata = (await preview_client.get_collection())["data"]
    preview_signature = metadata.get("signature")
    assert preview_signature, "Preview collection not signed"
    preview_timestamp = await preview_client.get_records_timestamp()
    # 2.3 approve the review
    print("Reviewer approves and triggers signature")
    data = {"status": "to-sign"}
    await reviewer_client.patch_collection(data=data)

    # 3. upload more data
    print("Author creates 20 others records")
    await upload_records(client, 20)

    print("Editor updates 5 random records")
    for toupdate in random.sample(records, 5):
        await editor_client.patch_record(data=dict(newkey=_rand(10), **toupdate))

    print("Author deletes 5 random records")
    for todelete in random.sample(records, 5):
        await client.delete_record(id=todelete["id"])

    expected = existing + 20 + 20 - 5

    # 4. ask again for a signature
    # 2.1 ask for review (noop on old versions)
    print("Editor asks for review")
    data = {"status": "to-review"}
    await editor_client.patch_collection(data=data)
    # 2.2 check the preview collection
    print("Check preview collection")
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
    print("Reviewer approves and triggers signature")
    data = {"status": "to-sign"}
    await reviewer_client.patch_collection(data=data)

    # 5. wait for the result

    # 6. obtain the destination records and serialize canonically.

    records = list(await dest_client.get_records())
    assert len(records) == expected, f"{len(records)} != {expected} records"
    timestamp = await dest_client.get_records_timestamp()
    serialized = canonical_json(records, timestamp)

    # 7. get back the signed hash

    signature = (await dest_client.get_collection())["data"]["signature"]

    with open("pub", "w") as f:
        f.write(signature["public_key"])

    # 8. verify the signature matches the hash
    signer = ECDSASigner(public_key="pub")
    try:
        signer.verify(serialized, signature)
        print("Signature OK")
    except Exception:
        print("Signature KO")
        raise


async def test_changes_plugin(
    make_client: Callable[[Tuple[str, str]], AsyncClient], auth: Tuple[str, str]
):
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
