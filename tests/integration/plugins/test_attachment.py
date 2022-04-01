import pytest
import requests

from ...conftest import Auth, ClientFactory
from ..utils import setup_server


pytestmark = pytest.mark.asyncio


async def test_attachment_plugin_new_record(
    make_client: ClientFactory,
    setup_auth: Auth,
    editor_auth: Auth,
    skip_server_setup: bool,
):
    if not skip_server_setup:
        setup_client = make_client(setup_auth)
        await setup_server(setup_client)

    editor_client = make_client(editor_auth)
    with open("kinto-logo.svg", "rb") as attachment:
        assert requests.post(
            f"{editor_client.session.server_url}{await editor_client.get_endpoint('record', id='logo')}/attachment",
            files={"attachment": attachment},
            auth=editor_client.session.auth,
        ), "Issue creating a new record with an attachment"

    record = await editor_client.get_record(id="logo")

    assert record
    assert "data" in record
    assert "attachment" in record["data"]


async def test_attachment_plugin_existing_record(
    make_client: ClientFactory,
    setup_auth: Auth,
    editor_auth: Auth,
    skip_server_setup: bool,
):
    if not skip_server_setup:
        setup_client = make_client(setup_auth)
        await setup_server(setup_client)

    editor_client = make_client(editor_auth)
    await editor_client.create_record(
        id="logo",
        data={"type": "logo"},
        if_not_exists=True,
    )

    with open("kinto-logo.svg", "rb") as attachment:
        assert requests.post(
            f"{editor_client.session.server_url}{await editor_client.get_endpoint('record', id='logo')}/attachment",
            files={"attachment": attachment},
            auth=editor_client.session.auth,
        ), "Issue updating an existing record to include an attachment"

    record = await editor_client.get_record(id="logo")

    assert record
    assert "data" in record
    assert "attachment" in record["data"]
