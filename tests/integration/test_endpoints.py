import requests

from ..conftest import Auth


def test_heartbeat(server: str):
    resp = requests.get(f"{server}/__heartbeat__")
    resp.raise_for_status()


def test_permissions_endpoint(
    server: str,
    editor_auth: Auth,
    reviewer_auth: Auth,
    source_bucket: str,
    source_collection: str,
    skip_server_setup: bool,
):
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
