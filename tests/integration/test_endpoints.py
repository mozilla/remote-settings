import pytest
import requests

from ..conftest import Auth, ClientFactory
from .utils import setup_server


pytestmark = pytest.mark.asyncio


def test_heartbeat(server: str):
    resp = requests.get(f"{server}/__heartbeat__")
    resp.raise_for_status()


async def test_permissions_endpoint(
    make_client: ClientFactory,
    server: str,
    setup_auth: Auth,
    editor_auth: Auth,
    reviewer_auth: Auth,
    source_bucket: str,
    source_collection: str,
    skip_server_setup: bool,
):
    if not skip_server_setup:
        setup_client = make_client(setup_auth)
        editor_client = make_client(editor_auth)
        reviewer_client = make_client(reviewer_auth)
        setup_server(setup_client, editor_client, reviewer_client)

    for user in (editor_auth, reviewer_auth):
        resp = requests.get(
            f"{server}/permissions",
            auth=user,
        )
        resp.raise_for_status()
        permissions = resp.json()["data"]
        collection_perms = next(
            e["permissions"]
            for e in permissions
            if e["resource_name"] == "collection"
            and e["bucket_id"] == source_bucket
            and e["collection_id"] == source_collection
        )
        assert "write" in collection_perms
