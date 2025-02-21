import os

from ..conftest import Auth


def test_email_plugin(
    setup_client: Auth,
    editor_client: Auth,
    mail_dir: str,
):
    mail_dir = os.path.abspath(mail_dir)
    existing_email_files = set(os.listdir(mail_dir))
    print(f"Read emails from {mail_dir} ({len(existing_email_files)} file(s) present)")

    if setup_client:
        setup_client.patch_bucket(
            data={
                "kinto-emailer": {
                    "hooks": [
                        {
                            "event": "kinto_remote_settings.signer.events.ReviewRequested",
                            "subject": "{user_id} requested review on {bucket_id}/{collection_id}.",
                            "template": "Review changes at {root_url}admin/#/buckets/{bucket_id}/collections/{collection_id}/records",
                            "recipients": [
                                "me@you.com",
                                f"/buckets/{setup_client.bucket_name}/groups/reviewers",
                            ],
                        }
                    ]
                }
            },
        )

    bucket_metadata = editor_client.get_bucket()
    email_hooks = bucket_metadata["data"]["kinto-emailer"]["hooks"]
    assert [h for h in email_hooks if "ReviewRequested" in h["event"]], (
        "Email hook not found"
    )

    # Create record, will set status to "work-in-progress"
    editor_client.create_record(data={"hola": "mundo"})
    # Request review!
    editor_client.patch_collection(data={"status": "to-review"})

    email_files_created = set(os.listdir(mail_dir)) - existing_email_files
    assert email_files_created, "No emails created"
    assert len(email_files_created) == 1, "Too many emails created"
    email_file = email_files_created.pop()
    assert email_file.endswith(".eml")

    with open(os.path.join(mail_dir, email_file), "r") as f:
        mail_contents = f.read()
        assert mail_contents.find("Subject: account") >= 0
        assert mail_contents.find("To: me@you.com") >= 0
