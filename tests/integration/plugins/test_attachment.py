import requests

from ...conftest import RemoteSettingsClient


def test_attachment_plugin_new_record(
    editor_client: RemoteSettingsClient,
):
    with open("kinto-logo.svg", "rb") as attachment:
        assert requests.post(
            f"{editor_client.session.server_url}{editor_client.get_endpoint('record', id='logo')}/attachment",
            files={"attachment": attachment},
            auth=editor_client.session.auth,
        ), "Issue creating a new record with an attachment"

    record = editor_client.get_record(id="logo")

    assert record
    assert "data" in record
    assert "attachment" in record["data"]


def test_attachment_plugin_existing_record(
    editor_client: RemoteSettingsClient,
):
    editor_client.create_record(
        id="logo",
        data={"type": "logo"},
        if_not_exists=True,
    )

    with open("kinto-logo.svg", "rb") as attachment:
        assert requests.post(
            f"{editor_client.session.server_url}{editor_client.get_endpoint('record', id='logo')}/attachment",
            files={"attachment": attachment},
            auth=editor_client.session.auth,
        ), "Issue updating an existing record to include an attachment"

    record = editor_client.get_record(id="logo")

    assert record
    assert "data" in record
    assert "attachment" in record["data"]
