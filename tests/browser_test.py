import os
import re
import unittest

from playwright.sync_api import expect, sync_playwright


baseUrl = os.getenv("SERVER", "http://localhost:8888/v1")
auth = {"user": "user", "password": "pass"}

browser = sync_playwright().start().firefox.launch()
context = browser.new_context(base_url=baseUrl)
page = browser.new_page()


class BrowserTest(unittest.TestCase):
    def setUp(self):
        request = context.request
        request.post(
            "accounts",
            data={"data": {"id": auth["user"], "password": auth["password"]}},
        )

    def test_login_and_submit_review(self):
        # load login page
        page.goto(f"{baseUrl}/admin/")
        expect(page).to_have_title(re.compile("Remote Settings"))

        # login
        page.get_by_label("Kinto Account Auth").click()
        txtUsername = page.get_by_label(re.compile("Username"))
        txtPassword = page.get_by_label(re.compile("Password"))
        txtUsername.fill(auth["user"])
        txtPassword.fill(auth["password"])
        page.get_by_text(re.compile("Sign in using Kinto Account Auth")).click()

        # verify home page loaded
        expect(page.get_by_text("project_name")).to_be_visible()
        expect(page.get_by_text("project_version")).to_be_visible()
        expect(page.get_by_text("http_api_version")).to_be_visible()
        expect(page.get_by_text("project_docs")).to_be_visible()

        # navigate to test collection
        page.click('[href="#/buckets/main-workspace/collections/integration-tests/records"]')
        expect(page.get_by_text("Records of main-workspace/integration-tests")).to_be_visible()
        
        # create a record
        page.get_by_text("Create record").first.click()
        page.get_by_label("JSON record").fill('{"prop": "val"}');
        page.get_by_text("Create record").click()

        # request a review
        page.get_by_text("Request review...").first.click()
        page.get_by_placeholder("Comment...").last.fill("Review comment")
        page.get_by_text("Request review").last.click()

        # verify that we are in-progress for review
        expect(page.locator(".bs-wizard-step.complete").first).to_contain_text("Work in progress")
        expect(page.locator(".bs-wizard-step.active").first).to_contain_text("Waiting review")
        expect(page.locator(".bs-wizard-step.disabled").first).to_contain_text("Approved")

