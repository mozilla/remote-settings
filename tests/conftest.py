import os
import random
from typing import Callable, Tuple

import pytest
import requests
from kinto_http import Client, KintoException
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


def asbool(s):
    return s.strip().lower() in ("true", "yes", "on", "1")


DEFAULT_SERVER = os.getenv("SERVER", "http://localhost:8888/v1")
DEFAULT_SETUP_AUTH = os.getenv("SETUP_AUTH", "user:pass")
DEFAULT_EDITOR_AUTH = os.getenv("EDITOR_AUTH", "editor:pass")
DEFAULT_REVIEWER_AUTH = os.getenv("REVIEWER_AUTH", "reviewer:pass")
DEFAULT_BUCKET = os.getenv("BUCKET", "main-workspace")
DEFAULT_COLLECTION = os.getenv("COLLECTION", "integration-tests")
DEFAULT_MAIL_DIR = os.getenv("MAIL_DIR", "mail")
DEFAULT_KEEP_EXISTING = asbool(os.getenv("KEEP_EXISTING", "false"))
DEFAULT_SKIP_SERVER_SETUP = asbool(os.getenv("SKIP_SERVER_SETUP", "false"))
DEFAULT_TO_REVIEW_ENABLED = asbool(os.getenv("TO_REVIEW_ENABLED", "true"))

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
        "--bucket",
        action="store",
        default=DEFAULT_BUCKET,
        help="Source bucket",
    )
    parser.addoption(
        "--collection",
        action="store",
        default=DEFAULT_COLLECTION,
        help="Source collection",
    )
    parser.addoption(
        "--mail-dir",
        action="store",
        default=DEFAULT_MAIL_DIR,
        help="Directory of debug email files (from server). Set as empty "
        "string to disable email tests. Should be disabled for integration "
        "tests",
    )
    parser.addoption(
        "--keep-existing",
        action="store_true",
        default=DEFAULT_KEEP_EXISTING,
        help="Keep existing collection data",
    )
    parser.addoption(
        "--skip-server-setup",
        action="store_true",
        default=DEFAULT_SKIP_SERVER_SETUP,
        help="Skip server setup operations. Should be set to `true` for remote "
        "server integration tests",
    )
    parser.addoption(
        "--to-review-enabled",
        action="store_true",
        default=DEFAULT_TO_REVIEW_ENABLED,
        help="Include tests and related to the to-review config option",
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
    return request.config.getoption("--bucket")


@pytest.fixture(scope="session")
def source_collection(request) -> str:
    return request.config.getoption("--collection")


@pytest.fixture(scope="session")
def mail_dir(request) -> str:
    directory = request.config.getoption("--mail-dir")
    if not directory:
        pytest.skip("MAIL_DIR set to empty string. Skipping email test.")
    return directory


@pytest.fixture(scope="session")
def keep_existing(request) -> bool:
    return request.config.getoption("--keep-existing")


@pytest.fixture(scope="session")
def skip_server_setup(request) -> bool:
    return request.config.getoption("--skip-server-setup")


@pytest.fixture(scope="session")
def to_review_enabled(request) -> bool:
    return request.config.getoption("--to-review-enabled")


@pytest.fixture()
def make_client(
    server: str, source_bucket: str, source_collection: str, skip_server_setup: bool
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
        request_session = requests.Session()
        retries = Retry(
            total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504]
        )
        request_session.mount(
            f"{server.split('://')[0]}://", HTTPAdapter(max_retries=retries)
        )

        if not skip_server_setup and auth:
            create_user(request_session, server, auth)

        return RemoteSettingsClient(
            server_url=server,
            auth=auth,
            bucket=source_bucket,
            collection=source_collection,
            retry=5,
        )

    return _make_client


@pytest.fixture(autouse=True)
def _flush_default_collection(
    make_client: ClientFactory,
    editor_auth: Auth,
):
    editor_client = make_client(editor_auth)
    try:
        editor_client.delete_records()
    except KintoException as e:
        # in the case where a user doesn't have permissions to delete
        print(e)


@pytest.fixture(scope="session", autouse=True)
def _verify_url(request: pytest.FixtureRequest, base_url: str):
    """Verifies the base URL"""
    verify = request.config.option.verify_base_url
    if base_url and verify:
        session = requests.Session()
        retries = Retry(backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
        session.mount(base_url, HTTPAdapter(max_retries=retries))
        session.get(base_url, verify=False)


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
