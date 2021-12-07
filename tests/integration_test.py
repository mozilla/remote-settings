import os
from typing import Tuple

import requests
from kinto_http import Client


def test_history_plugin(get_clients: Tuple[Client, Client, Client]):
    client, _, _ = get_clients
    client.create_bucket(id="blog")
    client.create_collection(id="articles", bucket="blog")
    history = client.get_history(bucket="blog")

    assert history
    assert len(history) == 2
    assert "collection_id" in history[0]
    assert "articles" in history[0]["collection_id"]
    assert "bucket_id" in history[1]
    assert "blog" in history[1]["bucket_id"]


def test_email_plugin(get_clients: Tuple[Client, Client, Client]):
    # remove any existing .eml files in mail directory
    try:
        for file in os.listdir("mail"):
            os.remove(f"mail/{file}")
    except FileNotFoundError:
        pass

    client, editor_client, _ = get_clients
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


def test_attachment_plugin_new_record(
    get_clients: Tuple[Client, Client, Client], server: str
):
    client, _, _ = get_clients
    client.create_bucket(id="blog")
    client.create_collection(id="articles", bucket="blog")

    with open("kinto-logo.svg", "rb") as attachment:
        assert requests.post(
            f"{server}/buckets/blog/collections/articles/records/logo/attachment",
            files={"attachment": attachment},
            auth=client.session.auth,
        )


def test_attachment_plugin_existing_record(
    get_clients: Tuple[Client, Client, Client], server: str
):
    client, _, _ = get_clients
    client.create_bucket(id="blog")
    client.create_collection(id="articles", bucket="blog")
    client.create_record(
        id="logo", bucket="blog", collection="articles", data={"type": "logo"}
    )

    with open("kinto-logo.svg", "rb") as attachment:
        assert requests.post(
            f"{server}/buckets/blog/collections/articles/records/logo/attachment",
            files={"attachment": attachment},
            auth=client.session.auth,
        )
