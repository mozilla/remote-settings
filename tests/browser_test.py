import re

import pytest
from kinto_http.patch_type import JSONPatch
from playwright.sync_api import expect


@pytest.fixture(autouse=True)
def _do_setup(
    source_bucket,
    source_collection,
    setup_auth,
    skip_server_setup,
    keep_existing,
    editor_auth,
    reviewer_auth,
    make_client,
):
    if skip_server_setup:
        return

    editor_client = make_client(editor_auth)
    reviewer_client = make_client(reviewer_auth)

    editor_id = editor_client.server_info()["user"]["id"]
    reviewer_id = reviewer_client.server_info()["user"]["id"]

    setup_client = make_client(setup_auth)
    setup_client.create_bucket(if_not_exists=True)
    setup_client.create_collection(
        permissions={"write": [editor_id, reviewer_id]},
        if_not_exists=True,
    )
    data = JSONPatch([{"op": "add", "path": "/data/members/0", "value": editor_id}])
    setup_client.patch_group(id=f"{source_collection}-editors", changes=data)
    data = JSONPatch([{"op": "add", "path": "/data/members/0", "value": reviewer_id}])
    setup_client.patch_group(id=f"{source_collection}-reviewers", changes=data)
    if not keep_existing:
        setup_client.delete_records()


def test_login_and_submit_review(
    server,
    page,
    editor_auth,
    source_bucket,
    source_collection,
    setup_auth,
    skip_server_setup,
    keep_existing,
):
    # load login page
    page.goto(f"{server}/admin/")
    expect(page).to_have_title(re.compile("Remote Settings"))

    # login
    page.get_by_label("Kinto Account Auth").click()
    txtUsername = page.get_by_label(re.compile("Username"))
    txtPassword = page.get_by_label(re.compile("Password"))
    txtUsername.fill(editor_auth[0])
    txtPassword.fill(editor_auth[1])
    page.get_by_text(re.compile("Sign in using Kinto Account Auth")).click()

    # verify home page loaded
    expect(page.get_by_text("project_name")).to_be_visible()
    expect(page.get_by_text("project_version")).to_be_visible()
    expect(page.get_by_text("http_api_version")).to_be_visible()
    expect(page.get_by_text("project_docs")).to_be_visible()

    # navigate to test collection
    page.click(
        '[href="#/buckets/main-workspace/collections/integration-tests/records"]'
    )
    expect(
        page.get_by_text("Records of main-workspace/integration-tests")
    ).to_be_visible()

    # create a record
    page.get_by_text("Create record").first.click()
    page.get_by_label("JSON record").fill('{"prop": "val"}')
    page.get_by_text("Create record").click()

    # request a review
    page.get_by_text("Request review...").first.click()
    page.get_by_placeholder("Comment...").last.fill("Review comment")
    page.get_by_text("Request review").last.click()

    # verify that we are in-progress for review
    expect(page.locator(".bs-wizard-step.complete").first).to_contain_text(
        "Work in progress"
    )
    expect(page.locator(".bs-wizard-step.active").first).to_contain_text(
        "Waiting review"
    )
    expect(page.locator(".bs-wizard-step.disabled").first).to_contain_text("Approved")


# TODO: reviewer test scenario - login to approve pending request
