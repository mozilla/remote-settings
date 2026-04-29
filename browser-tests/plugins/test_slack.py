import json
import os


def test_slack_plugin(
    setup_client,
    editor_client,
    slack_dir: str,
):
    existing_files = set(os.listdir(slack_dir))

    if setup_client:
        setup_client.patch_bucket(
            data={
                "kinto-slack": {
                    "hooks": [
                        {
                            "event": "kinto_remote_settings.signer.events.ReviewRequested",
                            "channel": "#reviews",
                            "template": "{user_id} requested review for {changes_count} changes ({comment}) on {bucket_id}/{collection_id}.",
                        }
                    ]
                }
            },
        )

    bucket_metadata = editor_client.get_bucket()
    slack_hooks = bucket_metadata["data"]["kinto-slack"]["hooks"]
    assert [h for h in slack_hooks if "ReviewRequested" in h["event"]], (
        "Slack hook not found"
    )

    # Create record, will set status to "work-in-progress"
    editor_client.create_record(data={"hola": "mundo"})
    # Request review!
    editor_client.patch_collection(
        data={"status": "to-review", "last_editor_comment": "looks good"}
    )

    files_created = set(os.listdir(slack_dir)) - existing_files
    assert files_created, "No Slack notifications sent"
    assert len(files_created) == 1, "Too many Slack notifications sent"

    notification_file = files_created.pop()
    assert notification_file.endswith(".json")

    with open(os.path.join(slack_dir, notification_file)) as f:
        payload = json.load(f)

    assert payload["channel"] == "#reviews"
    assert "integration-tests" in payload["text"]
    assert "looks good" in payload["text"]
    assert "1 changes" in payload["text"]
