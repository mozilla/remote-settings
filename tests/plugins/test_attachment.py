from playwright.sync_api import Browser

from ..conftest import Auth, RemoteSettingsClient
from ..utils import create_extra_headers


def test_attachment_plugin_new_record(
    browser: Browser,
    editor_client: RemoteSettingsClient,
    editor_auth: Auth,
    server: str,
):
    context = browser.new_context(
        base_url=server,
        extra_http_headers=create_extra_headers(editor_auth[0], editor_auth[1]),
    )

    with open("kinto-logo.svg", "rb") as attachment:
        resp = context.request.post(
            f"{editor_client.get_endpoint('record', id='logo')}/attachment",
            multipart={
                "attachment": {
                    "name": "kinto-logo.svg",
                    "mimeType": "image/svg",
                    "buffer": attachment.read(),
                }
            },
        )
        assert resp.status == 201, "Issue creating a new record with an attachment"

    record = editor_client.get_record(id="logo")

    assert record
    assert "data" in record
    assert "attachment" in record["data"]


def test_attachment_plugin_existing_record(
    editor_client: RemoteSettingsClient,
    browser: Browser,
    editor_auth: Auth,
    server: str,
):
    editor_client.create_record(
        id="logo",
        data={"type": "logo"},
        if_not_exists=True,
    )

    context = browser.new_context(
        base_url=server,
        extra_http_headers=create_extra_headers(editor_auth[0], editor_auth[1]),
    )

    with open("kinto-logo.svg", "rb") as attachment:
        resp = context.request.post(
            f"{editor_client.get_endpoint('record', id='logo')}/attachment",
            multipart={
                "attachment": {
                    "name": "kinto-logo.svg",
                    "mimeType": "image/svg",
                    "buffer": attachment.read(),
                }
            },
        )
        assert (
            resp.status == 200
        ), "Issue updating an existing record to include an attachment"

    record = editor_client.get_record(id="logo")

    assert record
    assert "data" in record
    assert "attachment" in record["data"]
