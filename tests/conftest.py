import os
import random
from typing import Callable, Tuple

import pytest
import requests
from kinto_http import Client, KintoException
from kinto_http.patch_type import JSONPatch
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class RemoteSettingsClient(Client):
    def fetch_changeset(self, **kwargs) -> list[dict]:
        """
        Fetch from `/changeset` endpoint introduced by the kinto-remote-settings plugin.
        """
        bucket = self.bucket_name
        collection = self.collection_name
        endpoint = f"/buckets/{bucket}/collections/{collection}/changeset"
        kwargs.setdefault("_expected", random.randint(999999000000, 999999999999))
        body, _ = self.session.request("get", endpoint, params=kwargs)
        return body


DEFAULT_SERVER = os.getenv("SERVER", "http://localhost:8888/v1")
DEFAULT_SETUP_AUTH = os.getenv("SETUP_AUTH", "user:pass")
DEFAULT_EDITOR_AUTH = os.getenv("EDITOR_AUTH", "editor:pass")
DEFAULT_REVIEWER_AUTH = os.getenv("REVIEWER_AUTH", "reviewer:pass")
DEFAULT_MAIL_DIR = os.getenv("MAIL_DIR", "mail")


Auth = Tuple[str, str]
ClientFactory = Callable[[Auth], RemoteSettingsClient]


def pytest_addoption(parser):
    parser.addoption(
        "--server",
        action="store",
        default=DEFAULT_SERVER,
        help="Kinto server (in form 'http(s)://<host>:<port>/v1')",
    )
    parser.addoption(
        "--setup-auth",
        action="store",
        default=DEFAULT_SETUP_AUTH,
        help="Basic authentication for server setup",
    )
    parser.addoption(
        "--editor-auth",
        action="store",
        default=DEFAULT_EDITOR_AUTH,
        help="Basic authentication for editor",
    )
    parser.addoption(
        "--reviewer-auth",
        action="store",
        default=DEFAULT_REVIEWER_AUTH,
        help="Basic authentication for reviewer",
    )
    parser.addoption(
        "--mail-dir",
        action="store",
        default=DEFAULT_MAIL_DIR,
        help="Directory of debug email files (from server). Set as empty "
        "string to disable email tests. Should be disabled for browser/integration "
        "tests",
    )


@pytest.fixture(scope="session")
def server(request) -> str:
    return request.config.getoption("--server")


@pytest.fixture(scope="session")
def setup_auth(request) -> Auth:
    return tuple(request.config.getoption("--setup-auth").split(":"))


@pytest.fixture(scope="session")
def editor_auth(request) -> Auth:
    return tuple(request.config.getoption("--editor-auth").split(":"))


@pytest.fixture(scope="session")
def reviewer_auth(request) -> Auth:
    return tuple(request.config.getoption("--reviewer-auth").split(":"))


@pytest.fixture(scope="session")
def source_bucket(request) -> str:
    return "main-workspace"


@pytest.fixture(scope="session")
def source_collection(request) -> str:
    return "browser-tests"


@pytest.fixture(scope="session")
def server_config(browser, server) -> dict:
    resp = browser.new_context().request.get(server)
    return resp.json()


@pytest.fixture(scope="session")
def to_review_enabled(server_config) -> bool:
    return server_config["capabilities"]["signer"]["to_review_enabled"]


@pytest.fixture(scope="session")
def mail_dir(request) -> str:
    directory = request.config.getoption("--mail-dir")
    if not directory:
        pytest.skip("MAIL_DIR set to empty string. Skipping email test.")
    return directory


@pytest.fixture(scope="session")
def request_session(server) -> requests.Session:
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
    session.mount(f"{server.split('://')[0]}://", HTTPAdapter(max_retries=retries))
    return session


@pytest.fixture(scope="session")
def make_client(
    server: str,
    source_bucket: str,
    source_collection: str,
    request_session: requests.Session,
) -> ClientFactory:
    """Factory as fixture for creating a RemoteSettings Client used for tests.

    Args:
        server (str): Kinto server (in form 'http(s)://<host>:<port>/v1')
        source_bucket (str): Source bucket
        source_collection (str): Source collection

    Returns:
        RemoteSettingsClient: RemoteSettingsClient
    """

    def _make_client(auth: Auth) -> RemoteSettingsClient:
        if auth:
            create_user(request_session, server, auth)

        return RemoteSettingsClient(
            server_url=server,
            auth=auth,
            bucket=source_bucket,
            collection=source_collection,
            retry=5,
        )

    return _make_client


@pytest.fixture(scope="session")
def setup_client(setup_auth, make_client) -> RemoteSettingsClient:
    return make_client(setup_auth)


@pytest.fixture(scope="session")
def editor_client(editor_auth, make_client) -> RemoteSettingsClient:
    return make_client(editor_auth)


@pytest.fixture(scope="session")
def reviewer_client(reviewer_auth, make_client) -> RemoteSettingsClient:
    return make_client(reviewer_auth)


@pytest.fixture(scope="session")
def anonymous_client(make_client) -> RemoteSettingsClient:
    return make_client(tuple())


@pytest.fixture(scope="session", autouse=True)
def _setup_server(
    request,
    setup_client,
    editor_client,
    reviewer_client,
):
    setup_client.create_bucket(
        permissions={
            "collection:create": ["system.Authenticated"],
        },
        if_not_exists=True,
    )

    setup_client.create_collection(if_not_exists=True)

    editor_id = (editor_client.server_info())["user"]["id"]
    data = JSONPatch([{"op": "add", "path": "/data/members/0", "value": editor_id}])
    setup_client.patch_group(id=f"{setup_client.collection_name}-editors", changes=data)

    reviewer_id = (reviewer_client.server_info())["user"]["id"]
    data = JSONPatch([{"op": "add", "path": "/data/members/0", "value": reviewer_id}])
    setup_client.patch_group(
        id=f"{setup_client.collection_name}-reviewers", changes=data
    )


@pytest.fixture(autouse=True)
def _flush_default_collection(
    editor_client: RemoteSettingsClient,
    editor_auth: Auth,
):
    try:
        editor_client.delete_records()
    except KintoException as e:
        # in the case where a user doesn't have permissions to delete
        print(e)


@pytest.fixture(scope="session", autouse=True)
def _verify_url(
    request: pytest.FixtureRequest, base_url: str, request_session: requests.Session
):
    """Verifies the base URL"""
    verify = request.config.option.verify_base_url
    if base_url and verify:
        request_session.get(base_url, verify=False)


def create_user(request_session: requests.Session, server: str, auth: Auth):
    # check if user already exists before creating
    r = request_session.get(server, auth=auth)
    if "user" not in r.json():
        assert request_session.put(
            f"{server}/accounts/{auth[0]}",
            json={"data": {"password": auth[1]}},
        )


def signed_resource(client):
    bid, cid = client.bucket_name, client.collection_name
    signer_resources = (client.server_info())["capabilities"]["signer"]["resources"]
    signed_resource = [
        r
        for r in signer_resources
        if r["source"]["bucket"] == bid and r["source"]["collection"] == cid
    ]
    if len(signed_resource) == 0:
        # Not explicitly configured. Check if configured at bucket level.
        signed_resource = [
            r
            for r in signer_resources
            if r["source"]["bucket"] == bid and r["source"]["collection"] is None
        ]

    assert (
        signed_resource
    ), f"{source_bucket}/{source_collection} not configured to be signed"
    return signed_resource[0]
