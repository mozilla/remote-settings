from playwright.sync_api import Browser, BrowserContext

from .conftest import Auth
from .utils import create_extra_headers


def test_heartbeat(server: str, context: BrowserContext):
    resp = context.request.get(f"{server}/__heartbeat__")
    assert resp.status == 200


def test_config(server_config, to_review_enabled):
    assert server_config["project_name"]
    assert server_config["project_version"]
    assert server_config["http_api_version"]
    assert server_config["url"]
    assert to_review_enabled == ("dev" not in server_config["project_name"].lower())


def test_permissions_endpoint(
    server: str,
    editor_auth: Auth,
    reviewer_auth: Auth,
    source_bucket: str,
    source_collection: str,
    browser: Browser,
):
    for user in (editor_auth, reviewer_auth):
        context = browser.new_context(
            base_url=server, extra_http_headers=create_extra_headers(user[0], user[1])
        )
        resp = context.request.get("/permissions")
        assert resp.status == 200
        permissions = resp.json()["data"]
        collection_perms = next(
            e["permissions"]
            for e in permissions
            if e["resource_name"] == "collection"
            and e["bucket_id"] == source_bucket
            and e["collection_id"] == source_collection
        )
        assert "write" in collection_perms
