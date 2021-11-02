import json
from typing import Tuple

import pytest
import requests
from kinto_http import Client, KintoException
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def test_changes_endpoint(get_clients: Tuple[Client, Client, Client, str]):
    client, editor_client, reviewer_client, server = get_clients
    buckets = client.get_buckets()

    # create default collection if it doesn't exist
    try:
        client.create_collection()
    except KintoException as e:
        print(e)

    col = client.get_collections(bucket=buckets[0]["id"])
    print(col)
    server_info = client.server_info()
    editor_id = editor_client.server_info()["user"]["id"]
    reviewer_id = reviewer_client.server_info()["user"]["id"]
    print("Server: {0}".format(server))
    print("Author: {user[id]}".format(**server_info))
    print("Editor: {0}".format(editor_id))
    print("Reviewer: {0}".format(reviewer_id))
    assert True


@pytest.fixture(scope="module")
def get_clients(
    server: str,
    auth: Tuple[str, str],
    editor_auth: Tuple[str, str],
    reviewer_auth: Tuple[str, str],
    bucket: str,
    collection: str,
) -> Tuple[Client, Client, Client, str]:
    """Pytest fixture for creating Kinto Clients used for tests.

    Args:
        server (str): Kinto server (in form 'http(s)://<host>:<port>/v1')
        auth (Tuple[str, str]): Basic authentication where auth[0]=user, auth[1]=pass
        editor_auth (str): Basic authentication for editor
        reviewer_auth (str): Basic authentication for reviewer
        bucket (str): Source bucket
        collection (str): Source collection

    Returns:
        Tuple[Client, Client, Client, str]: User client, editor client, reviewer client, server
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

    return client, editor_client, reviewer_client, server
