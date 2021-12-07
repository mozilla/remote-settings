import json
from typing import Tuple

import pytest
import requests
from kinto_http import Client
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_SERVER = "http://localhost:8888/v1"
DEFAULT_AUTH = "user:pass"
DEFAULT_BUCKET = "default"
DEFAULT_COLLECTION = "source"


def pytest_addoption(parser):
    parser.addoption(
        "--server",
        action="store",
        default=DEFAULT_SERVER,
        help="Kinto server (in form 'http(s)://<host>:<port>/v1')",
    )
    parser.addoption(
        "--auth",
        action="store",
        default=DEFAULT_AUTH,
        help="Basic authentication",
    )
    parser.addoption(
        "--editor-auth",
        action="store",
        default=None,
        help="Basic authentication for editor",
    )
    parser.addoption(
        "--reviewer-auth",
        action="store",
        default=None,
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
        "--reset",
        action="store_true",
        default=False,
        help="Reset collection data",
    )


@pytest.fixture(scope="session")
def server(request):
    return request.config.getoption("--server")


@pytest.fixture(scope="session")
def auth(request):
    return tuple(request.config.getoption("--auth").split(":"))


@pytest.fixture(scope="session")
def editor_auth(request):
    return request.config.getoption("--editor-auth")


@pytest.fixture(scope="session")
def reviewer_auth(request):
    return request.config.getoption("--reviewer-auth")


@pytest.fixture(scope="session")
def bucket(request):
    return request.config.getoption("--bucket")


@pytest.fixture(scope="session")
def collection(request):
    return request.config.getoption("--collection")


@pytest.fixture(scope="session")
def reset(request):
    return request.config.getoption("--reset")


@pytest.fixture
def get_clients(
    flush_server,
    server: str,
    auth: Tuple[str, str],
    editor_auth: Tuple[str, str],
    reviewer_auth: Tuple[str, str],
    bucket: str,
    collection: str,
) -> Tuple[Client, Client, Client]:
    """Pytest fixture for creating Kinto Clients used for tests.

    Args:
        server (str): Kinto server (in form 'http(s)://<host>:<port>/v1')
        auth (Tuple[str, str]): Basic authentication where auth[0]=user, auth[1]=pass
        editor_auth (str): Basic authentication for editor
        reviewer_auth (str): Basic authentication for reviewer
        bucket (str): Source bucket
        collection (str): Source collection

    Returns:
        Tuple[Client, Client, Client]: User client, editor client, reviewer client
    """

    request_session = requests.Session()
    retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
    request_session.mount(
        f"{server.split('://')[0]}://", HTTPAdapter(max_retries=retries)
    )

    # check if user already exists before creating
    r = request_session.get(f"{server}/", auth=auth)
    if "user" not in r.json():
        create_account_url = f"{server}/accounts/{auth[0]}"
        assert request_session.put(
            create_account_url,
            data=json.dumps({"data": {"password": auth[1]}}),
            headers={"Content-Type": "application/json"},
        )

    client = Client(
        server_url=server,
        auth=auth,
        bucket=bucket,
        collection=collection,
        retry=5,
    )

    if editor_auth is None:
        editor_auth = auth

    if reviewer_auth is None:
        reviewer_auth = auth

    editor_client = Client(
        server_url=server,
        auth=editor_auth,
        bucket=bucket,
        collection=collection,
        retry=5,
    )
    reviewer_client = Client(
        server_url=server,
        auth=reviewer_auth,
        bucket=bucket,
        collection=collection,
        retry=5,
    )

    return client, editor_client, reviewer_client


@pytest.fixture
def flush_server(server: str):
    assert requests.post(f"{server}/__flush__")
