import re
import time

from playwright.sync_api import expect


def test_login_and_submit_review(
    server,
    page,
    editor_auth,
    source_bucket,
    source_collection,
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
        f'[href="#/buckets/{source_bucket}/collections/{source_collection}/records"]'
    )
    expect(
        page.get_by_text(f"Records of {source_bucket}/{source_collection}")
    ).to_be_visible()

    # create a record
    page.get_by_text("Create record").first.click()
    page.get_by_label("Title").fill("val")
    page.get_by_label("File attachment*").set_input_files("kinto-logo.svg")
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


def test_review_requested_changes(
    server,
    page,
    reviewer_auth,
    source_bucket,
    source_collection,
    editor_client,
    editor_auth,
):
    # setup changes to review
    editor_client.create_record(data={"title": "val"})
    editor_client.patch_collection(data={"status": "to-review"})

    # load login page
    page.goto(f"{server}/admin/")

    # login
    page.get_by_label("Kinto Account Auth").click()
    page.get_by_label(re.compile("Username")).fill(reviewer_auth[0])
    page.get_by_label(re.compile("Password")).fill(reviewer_auth[1])
    page.get_by_text(re.compile("Sign in using Kinto Account Auth")).click()

    # navigate to test collection
    page.click(
        f'[href="#/buckets/{source_bucket}/collections/{source_collection}/records"]'
    )
    expect(
        page.get_by_text(f"Records of {source_bucket}/{source_collection}")
    ).to_be_visible()

    # navigate to review page
    page.click(
        f'[href="#/buckets/{source_bucket}/collections/{source_collection}/simple-review"]'
    )
    expect(page.get_by_text("Review requested by")).to_be_visible()

    # approve and verify no changes are pending
    page.get_by_text("Approve...").click()
    expect(page.get_by_text("No changes to review")).to_be_visible()


def test_review_existing_record(
    server,
    page,
    reviewer_client,
    editor_client,
    editor_auth,
    source_bucket,
    source_collection,
    preview_bucket,
):
    record_id = "abc"
    # setup changes to review
    editor_client.create_record(data={"id": record_id, "title": "val"})
    editor_client.add_attachment(id=record_id, filepath="kinto-logo.svg")
    editor_client.patch_collection(data={"status": "to-review"})
    reviewer_client.patch_collection(data={"status": "to-sign"})

    # load login page
    page.goto(f"{server}/admin/")

    # login
    page.get_by_label("Kinto Account Auth").click()
    page.get_by_label(re.compile("Username")).fill(editor_auth[0])
    page.get_by_label(re.compile("Password")).fill(editor_auth[1])
    page.get_by_text(re.compile("Sign in using Kinto Account Auth")).click()

    # navigate to test collection
    page.click(
        f'[href="#/buckets/{source_bucket}/collections/{source_collection}/records"]'
    )
    expect(
        page.get_by_text(f"Records of {source_bucket}/{source_collection}")
    ).to_be_visible()

    # navigate to record form
    page.click(
        f'[href="#/buckets/{source_bucket}/collections/{source_collection}/records/{record_id}/attributes"]'
    )
    expect(
        page.get_by_text(
            f"Edit {source_bucket}/{source_collection}/{record_id} record attributes"
        )
    ).to_be_visible()
    expect(page.get_by_text("Update record")).to_be_visible()

    # Update fields and overwrite attachment
    page.get_by_label("Title").fill("new val")
    page.get_by_label("File attachment").set_input_files("kinto-logo.jpg")
    page.get_by_text("Update record").click()

    # request a review
    page.get_by_text("Request review...").first.click()
    page.get_by_placeholder("Comment...").last.fill("Modified record and attachment")
    page.get_by_text("Request review").last.click()
    expect(page.get_by_text("Review requested.")).to_be_visible()

    # Check that preview record has the appropriate values
    record = editor_client.get_record(id=record_id, bucket=preview_bucket)
    assert record["data"]["title"] == "new val"
    assert record["data"]["attachment"]["filename"] == "kinto-logo.jpg"
