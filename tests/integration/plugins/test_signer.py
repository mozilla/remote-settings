import operator
import random

import aiohttp
import canonicaljson
import pytest
from autograph_utils import MemoryCache, SignatureVerifier
from kinto_http import KintoException
from kinto_http.patch_type import JSONPatch

from ...conftest import Auth, ClientFactory, signed_resource
from ..utils import _rand, setup_server, upload_records


class FakeRootHash:
    def __eq__(self, val):
        return True


def canonical_json(records, last_modified):
    # This code is import from `kinto_remote_settings.signer.serializer`.
    # Duplicating it here prevents us from installing the plugin and the
    # whole Kinto / Pyramid chain of dependance.
    # Note that this serialization code won't change since millions of
    # clients depend on it.
    records = (r for r in records if not r.get("deleted", False))
    records = sorted(records, key=operator.itemgetter("id"))
    payload = {"data": records, "last_modified": "%s" % last_modified}
    dump = canonicaljson.dumps(payload)
    return dump


async def verify_signature(records, timestamp, signature):
    x5u = signature["x5u"].replace("file:///tmp/autograph/", "http://certchains/")
    serialized = canonical_json(records, timestamp).encode("utf-8")

    async with aiohttp.ClientSession() as session:
        verifier = SignatureVerifier(session, MemoryCache(), FakeRootHash())
        await verifier.verify(serialized, signature["signature"], x5u)


pytestmark = pytest.mark.asyncio


async def test_signer_plugin_capabilities(make_client: ClientFactory):
    anonymous_client = make_client(tuple())
    capability = (await anonymous_client.server_info())["capabilities"]["signer"]
    assert capability["group_check_enabled"]
    assert capability["to_review_enabled"]


async def test_signer_plugin_full_workflow(
    make_client: ClientFactory,
    setup_auth: Auth,
    editor_auth: Auth,
    reviewer_auth: Auth,
    server: str,
    keep_existing: bool,
    skip_server_setup: bool,
):
    editor_client = make_client(editor_auth)
    reviewer_client = make_client(reviewer_auth)

    resource = await signed_resource(editor_client)

    if not skip_server_setup:
        setup_client = make_client(setup_auth)
        await setup_server(setup_client, editor_client, reviewer_client)

    dest_col = resource["destination"].get("collection")
    dest_client = editor_client.clone(
        bucket=resource["destination"]["bucket"],
        collection=dest_col or editor_client.collection_name,
        auth=tuple(),
    )

    preview_bucket = resource["preview"]["bucket"]
    preview_collection = resource["preview"].get("collection")
    preview_client = editor_client.clone(
        bucket=preview_bucket,
        collection=preview_collection or editor_client.collection_name,
        auth=tuple(),
    )

    existing_records = await editor_client.get_records()
    existing = len(existing_records)
    if existing > 0 and not keep_existing:
        await editor_client.delete_records()
        existing = 0

        # Status is now WIP.
        status = (await editor_client.get_collection())["data"]["status"]
        assert status == "work-in-progress", f"{status} != work-in-progress"

        # Re-sign and verify.
        await editor_client.patch_collection(data={"status": "to-review"})
        await reviewer_client.patch_collection(data={"status": "to-sign"})
        timestamp = await dest_client.get_records_timestamp()
        signature = (await dest_client.get_collection())["data"]["signature"]
        await verify_signature([], timestamp, signature)

    # 1. upload data
    records = await upload_records(editor_client, 20)

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
    await upload_records(editor_client, 20)

    for toupdate in random.sample(records, 5):
        await editor_client.patch_record(data=dict(newkey=_rand(10), **toupdate))

    for todelete in random.sample(records, 5):
        await editor_client.delete_record(id=todelete["id"])

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


async def test_signer_plugin_rollback(
    make_client: ClientFactory,
    setup_auth: Auth,
    editor_auth: Auth,
    skip_server_setup: bool,
):
    if not skip_server_setup:
        setup_client = make_client(setup_auth)
        await setup_server(setup_client)

    editor_client = make_client(editor_auth)
    await editor_client.patch_collection(data={"status": "to-rollback"})
    before_records = await editor_client.get_records()

    await upload_records(editor_client, 5)

    records = await editor_client.get_records()
    assert len(records) == len(before_records) + 5
    await editor_client.patch_collection(data={"status": "to-rollback"})
    records = await editor_client.get_records()
    assert len(records) == len(before_records)


async def test_signer_plugin_refresh(
    make_client: ClientFactory,
    setup_auth: Auth,
    editor_auth: Auth,
    reviewer_auth: Auth,
    skip_server_setup: bool,
):
    reviewer_client = make_client(reviewer_auth)
    if not skip_server_setup:
        setup_client = make_client(setup_auth)
        await setup_server(setup_client, reviewer_client=reviewer_client)

    editor_client = make_client(editor_auth)
    resource = await signed_resource(editor_client)
    preview_bucket = resource["preview"]["bucket"]
    dest_bucket = resource["destination"]["bucket"]
    await upload_records(editor_client, 5)
    await editor_client.patch_collection(data={"status": "to-review"})
    await reviewer_client.patch_collection(data={"status": "to-sign"})
    signature_preview_before = (
        await editor_client.get_collection(bucket=preview_bucket)
    )["data"]["signature"]

    signature_before = (await editor_client.get_collection(bucket=dest_bucket))["data"][
        "signature"
    ]

    await reviewer_client.patch_collection(data={"status": "to-resign"})

    signature = (await editor_client.get_collection(bucket=dest_bucket))["data"][
        "signature"
    ]
    signature_preview = (await editor_client.get_collection(bucket=dest_bucket))[
        "data"
    ]["signature"]

    assert signature_before != signature
    assert signature_preview_before != signature_preview


async def test_signer_plugin_reviewer_verifications(
    make_client: ClientFactory,
    setup_auth: Auth,
    editor_auth: Auth,
    reviewer_auth: Auth,
    skip_server_setup: bool,
):
    editor_client = make_client(editor_auth)
    reviewer_client = make_client(reviewer_auth)

    if not skip_server_setup:
        setup_client = make_client(setup_auth)
        await setup_server(setup_client, editor_client, reviewer_client)
        # Add reviewer to editors, and vice-versa.
        reviewer_id = (await reviewer_client.server_info())["user"]["id"]
        data = JSONPatch(
            [{"op": "add", "path": "/data/members/0", "value": reviewer_id}]
        )
        await setup_client.patch_group(
            id=f"{setup_client.collection_name}-editors", changes=data
        )
        editor_id = (await editor_client.server_info())["user"]["id"]
        data = JSONPatch([{"op": "add", "path": "/data/members/0", "value": editor_id}])
        await setup_client.patch_group(
            id=f"{setup_client.collection_name}-reviewers", changes=data
        )

    await upload_records(editor_client, 5)

    # status cannot be set to to-sign
    with pytest.raises(KintoException):
        await reviewer_client.patch_collection(data={"status": "to-sign"})

    await reviewer_client.patch_collection(data={"status": "to-review"})
    # same editor cannot review
    with pytest.raises(KintoException):
        await reviewer_client.patch_collection(data={"status": "to-sign"})

    # review must be asked after cancelled
    await editor_client.patch_collection(data={"status": "to-review"})
    await reviewer_client.patch_collection(data={"status": "work-in-progress"})
    with pytest.raises(KintoException):
        await reviewer_client.patch_collection(data={"status": "to-sign"})

    await reviewer_client.patch_collection(data={"status": "to-review"})
    # Client can now review because he is not the last_editor.
    await editor_client.patch_collection(data={"status": "to-sign"})
