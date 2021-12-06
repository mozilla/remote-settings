import json
import os
from typing import Tuple

import pytest
import requests
from kinto_http import Client
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def test_history_plugin(get_clients: Tuple[Client, Client, Client, str]):
    client, _, _, _ = get_clients
    client.create_bucket(id="blog")
    client.create_collection(id="articles", bucket="blog", if_not_exists=True)
    history = client.get_history(bucket="blog")

    assert history
    assert len(history) == 2
    assert "collection_id" in history[0]
    assert "articles" in history[0]["collection_id"]
    assert "bucket_id" in history[1]
    assert "blog" in history[1]["bucket_id"]


def test_email_plugin(get_clients: Tuple[Client, Client, Client, str]):
    # remove any existing .eml files in mail directory
    try:
        for file in os.listdir("mail"):
            os.remove(f"mail/{file}")
    except FileNotFoundError:
        pass

    client, editor_client, _, _ = get_clients
    client.create_bucket(id="source")
    client.create_collection(id="email", bucket="source")
    client.patch_bucket(
        id="source",
        data={
            "kinto-emailer": {
                "hooks": [
                    {
                        "event": "kinto_remote_settings.signer.events.ReviewRequested",
                        "subject": "{user_id} requested review on {bucket_id}/{collection_id}.",
                        "template": "Review changes at {root_url}admin/#/buckets/{bucket_id}/collections/{collection_id}/records",
                        "recipients": [
                            "me@you.com",
                            "/buckets/source/groups/reviewers",
                        ],
                    }
                ]
            }
        },
    )
    editor_client.patch_collection(
        id="email", bucket="source", data={"status": "to-review"}
    )

    mail = os.listdir("mail")
    assert mail
    assert len(mail) == 1
    assert mail[0].endswith(".eml")

    with open(f"mail/{mail[0]}", "r") as f:
        mail_contents = f.read()
        assert mail_contents.find("Subject: account") >= 0
        assert mail_contents.find("To: me@you.com") >= 0


@pytest.fixture
def get_clients(
    flush_server,
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


@pytest.fixture
def flush_server(server: str):
    assert requests.post(f"{server}/__flush__")
