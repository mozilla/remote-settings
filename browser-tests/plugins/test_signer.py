import asyncio
import operator
import random
import threading

import aiohttp
import canonicaljson
import pytest
from autograph_utils import MemoryCache, SignatureVerifier
from kinto_http import KintoException
from kinto_http.patch_type import JSONPatch

from ..conftest import RemoteSettingsClient, signed_resource
from ..utils import _rand, upload_records


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


def verify_signature(records, timestamp, signature):
    thread = threading.Thread(
        target=verify_signature_sync, args=(records, timestamp, signature)
    )
    thread.start()
    thread.join()


def verify_signature_sync(records, timestamp, signature):
    """Runs the async verification function in a separate thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_verify_signature(records, timestamp, signature))
    loop.close()


async def _verify_signature(records, timestamp, signature):
    x5u = signature["x5u"]
    serialized = canonical_json(records, timestamp).encode("utf-8")

    async with aiohttp.ClientSession() as session:
        verifier = SignatureVerifier(session, MemoryCache(), FakeRootHash())
        await verifier.verify(serialized, signature["signature"], x5u)


def test_signer_plugin_capabilities(anonymous_client: RemoteSettingsClient):
    capability = (anonymous_client.server_info())["capabilities"]["signer"]
    assert capability["group_check_enabled"]


def test_signer_plugin_full_workflow(
    editor_client: RemoteSettingsClient,
    reviewer_client: RemoteSettingsClient,
    to_review_enabled: bool,
):
    if not to_review_enabled:
        pytest.skip("to-review disabled")

    resource = signed_resource(editor_client)

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

    existing_records = editor_client.get_records()
    existing = len(existing_records)
    if existing > 0:
        editor_client.delete_records()
        existing = 0

        # Status is now WIP.
        status = (editor_client.get_collection())["data"]["status"]
        assert status == "work-in-progress", f"{status} != work-in-progress"

        # Re-sign and verify.
        editor_client.patch_collection(data={"status": "to-review"})
        reviewer_client.patch_collection(data={"status": "to-sign"})
        changeset = dest_client.fetch_changeset()
        timestamp = changeset["timestamp"]
        signature = changeset["metadata"]["signature"]
        verify_signature([], timestamp, signature)

    # 1. upload data
    records = upload_records(editor_client, 20)

    # 2. ask for a signature
    # 2.1 ask for review
    editor_client.patch_collection(data={"status": "to-review"})
    # 2.2 check the preview collection
    changeset = preview_client.fetch_changeset()
    preview_records = changeset["changes"]
    expected = existing + 20
    assert len(preview_records) == expected, (
        f"{len(preview_records)} != {expected} records"
    )
    preview_timestamp = changeset["timestamp"]
    preview_signature = changeset["metadata"]["signature"]
    assert preview_signature, "Preview collection not signed"
    # Verify the preview collection
    verify_signature(preview_records, preview_timestamp, preview_signature)

    # 2.3 approve the review
    reviewer_client.patch_collection(data={"status": "to-sign"})

    # 3. upload more data
    upload_records(editor_client, 20)

    for toupdate in random.sample(records, 5):
        editor_client.patch_record(data=dict(newkey=_rand(10), **toupdate))

    for todelete in random.sample(records, 5):
        editor_client.delete_record(id=todelete["id"])

    expected = existing + 20 + 20 - 5

    # 4. ask again for a signature
    # 2.1 ask for review (noop on old versions)
    editor_client.patch_collection(data={"status": "to-review"})
    # 2.2 check the preview collection
    preview_records = preview_client.get_records()
    assert len(preview_records) == expected, (
        f"{len(preview_records)} != {expected} records"
    )
    # Diff size is 20 + 5 if updated records are also all deleted,
    # or 30 if deletions and updates apply to different records.
    diff_since_last = preview_client.get_records(_since=preview_timestamp)
    assert 25 <= len(diff_since_last) <= 30, (
        "Changes since last signature are not consistent"
    )

    metadata = (preview_client.get_collection())["data"]
    assert preview_signature != metadata["signature"], "Preview collection not updated"

    # 2.3 approve the review
    reviewer_client.patch_collection(data={"status": "to-sign"})

    # 5. verify signature
    changeset = dest_client.fetch_changeset()
    records = changeset["changes"]
    assert len(records) == expected, f"{len(records)} != {expected} records"
    timestamp = changeset["timestamp"]
    signature = changeset["metadata"]["signature"]
    assert signature, "Preview collection not signed"

    try:
        verify_signature(records, timestamp, signature)
    except Exception:
        print("Signature KO")
        raise


def test_workflow_without_review(
    editor_client: RemoteSettingsClient,
    reviewer_client: RemoteSettingsClient,
    to_review_enabled: bool,
):
    if to_review_enabled:
        pytest.skip("to-review enabled")

    resource = signed_resource(editor_client)

    dest_col = resource["destination"].get("collection")
    dest_client = editor_client.clone(
        bucket=resource["destination"]["bucket"],
        collection=dest_col or editor_client.collection_name,
        auth=tuple(),
    )

    upload_records(editor_client, 1)
    reviewer_client.patch_collection(data={"status": "to-sign"})
    changeset = dest_client.fetch_changeset()
    records = changeset["changes"]
    timestamp = changeset["timestamp"]
    signature = changeset["metadata"]["signature"]

    try:
        verify_signature(records, timestamp, signature)
    except Exception:
        print("Signature KO")
        raise


def test_signer_plugin_rollback(
    editor_client: RemoteSettingsClient,
):
    editor_client.patch_collection(data={"status": "to-rollback"})
    before_records = editor_client.get_records()

    upload_records(editor_client, 1)

    records = editor_client.get_records()
    assert len(records) == len(before_records) + 1
    editor_client.patch_collection(data={"status": "to-rollback"})
    records = editor_client.get_records()
    assert len(records) == len(before_records)


def test_signer_plugin_refresh(
    editor_client: RemoteSettingsClient,
    reviewer_client: RemoteSettingsClient,
    to_review_enabled: bool,
):
    resource = signed_resource(editor_client)
    preview_bucket = resource["preview"]["bucket"]
    dest_bucket = resource["destination"]["bucket"]
    upload_records(editor_client, 5)

    editor_client.patch_collection(data={"status": "to-review"})

    reviewer_client.patch_collection(data={"status": "to-sign"})
    signature_preview_before = (editor_client.get_collection(bucket=preview_bucket))[
        "data"
    ]["signature"]

    signature_before = (editor_client.get_collection(bucket=dest_bucket))["data"][
        "signature"
    ]

    reviewer_client.patch_collection(data={"status": "to-resign"})

    signature = (editor_client.get_collection(bucket=dest_bucket))["data"]["signature"]
    signature_preview = (editor_client.get_collection(bucket=dest_bucket))["data"][
        "signature"
    ]

    assert signature_before != signature
    assert signature_preview_before != signature_preview


def test_cannot_skip_to_review(
    editor_client: RemoteSettingsClient,
    reviewer_client: RemoteSettingsClient,
    to_review_enabled: bool,
):
    if not to_review_enabled:
        pytest.skip("to-review disabled")

    upload_records(editor_client, 1)

    with pytest.raises(KintoException):
        reviewer_client.patch_collection(data={"status": "to-sign"})


def test_same_editor_cannot_review(
    setup_client: RemoteSettingsClient,
    editor_client: RemoteSettingsClient,
    reviewer_client: RemoteSettingsClient,
    to_review_enabled: bool,
):
    if not to_review_enabled:
        pytest.skip("to-review disabled")

    if setup_client:
        # Add reviewer to editors, and vice-versa.
        reviewer_id = (reviewer_client.server_info())["user"]["id"]
        data = JSONPatch(
            [{"op": "add", "path": "/data/members/0", "value": reviewer_id}]
        )
        setup_client.patch_group(
            id=f"{setup_client.collection_name}-editors", changes=data
        )
        editor_id = (editor_client.server_info())["user"]["id"]
        data = JSONPatch([{"op": "add", "path": "/data/members/0", "value": editor_id}])
        setup_client.patch_group(
            id=f"{setup_client.collection_name}-reviewers", changes=data
        )

    upload_records(editor_client, 1)

    reviewer_client.patch_collection(data={"status": "to-review"})
    with pytest.raises(KintoException):
        reviewer_client.patch_collection(data={"status": "to-sign"})


def test_rereview_after_cancel(
    setup_client: RemoteSettingsClient,
    editor_client: RemoteSettingsClient,
    reviewer_client: RemoteSettingsClient,
    to_review_enabled: bool,
):
    if not to_review_enabled:
        pytest.skip("to-review disabled")

    # Add reviewer to editors, and vice-versa.
    if setup_client:
        reviewer_id = (reviewer_client.server_info())["user"]["id"]
        data = JSONPatch(
            [{"op": "add", "path": "/data/members/0", "value": reviewer_id}]
        )
        setup_client.patch_group(
            id=f"{setup_client.collection_name}-editors", changes=data
        )
        editor_id = (editor_client.server_info())["user"]["id"]
        data = JSONPatch([{"op": "add", "path": "/data/members/0", "value": editor_id}])
        setup_client.patch_group(
            id=f"{setup_client.collection_name}-reviewers", changes=data
        )

    upload_records(editor_client, 1)

    reviewer_client.patch_collection(data={"status": "to-review"})

    reviewer_client.patch_collection(data={"status": "work-in-progress"})
    with pytest.raises(KintoException):
        reviewer_client.patch_collection(data={"status": "to-sign"})
