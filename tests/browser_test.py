import pytest
from kinto_http.patch_type import JSONPatch
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from .conftest import Auth, ClientFactory


pytestmark = pytest.mark.asyncio


async def test_review_signoff(
    base_url: str,
    selenium: WebDriver,
    make_client: ClientFactory,
    setup_auth: Auth,
    editor_auth: Auth,
    reviewer_auth: Auth,
    skip_server_setup: bool,
):
    editor_client = make_client(editor_auth)
    reviewer_client = make_client(reviewer_auth)

    editor_id = (await editor_client.server_info())["user"]["id"]
    reviewer_id = (await reviewer_client.server_info())["user"]["id"]

    # Setup remote server.
    if not skip_server_setup:
        setup_client = make_client(setup_auth)
        await setup_client.create_bucket(id="main-workspace", if_not_exists=True)
        await setup_client.create_collection(
            id="product-integrity",
            bucket="main-workspace",
            permissions={"write": [editor_id, reviewer_id]},
            if_not_exists=True,
        )
        data = JSONPatch([{"op": "add", "path": "/data/members/0", "value": editor_id}])
        await setup_client.patch_group(id="product-integrity-editors", changes=data)
        data = JSONPatch(
            [{"op": "add", "path": "/data/members/0", "value": reviewer_id}]
        )
        await setup_client.patch_group(id="product-integrity-reviewers", changes=data)

    # Sample data.
    await editor_client.create_record(
        bucket="main-workspace", collection="product-integrity", data={"testing": 123}
    )
    await editor_client.patch_collection(
        id="product-integrity", bucket="main-workspace", data={"status": "to-review"}
    )

    # Start browsing.
    selenium.get(base_url)

    sign_in(selenium, reviewer_auth)

    selenium.get(
        base_url
        + "/#/buckets/main-workspace/collections/product-integrity/simple-review"
    )
    selenium.refresh()

    approve_button: WebElement = selenium.find_element(
        By.XPATH, "//button[contains(., 'Approve')]"
    )
    assert approve_button, "Approve button not found"
    assert approve_button.text == "Approve"
    assert approve_button.is_displayed()

    reject_button: WebElement = selenium.find_element(
        By.XPATH, "//button[contains(., 'Reject')]"
    )
    assert reject_button, "Reject button not found"
    assert reject_button.text == "Reject"
    assert reject_button.is_displayed()

    approve_button.click()

    # find and click show readonly buckets/collections
    readonly_checkbox: WebElement = selenium.find_element(By.ID, "read-only-toggle")
    assert readonly_checkbox, "Readonly checkbox not found"
    assert readonly_checkbox.is_displayed()
    readonly_checkbox.click()

    # find and click on main bucket product-integrity collection
    product_integrity: WebElement = selenium.find_element(
        By.XPATH,
        "//a[@href='#/buckets/main/collections/product-integrity/records' and contains(., 'product-integrity')]",
    )
    assert product_integrity, "product-integrity collection not found under main bucket"
    assert product_integrity.is_displayed()
    product_integrity.click()

    # find and ensure record was properly signed to main bucket
    data: WebElement = selenium.find_element(By.XPATH, "//code")
    assert data, "Record not found in product-integrity collection under main bucket"
    assert data.is_displayed()
    assert data.text == '{"testing":123}'


def sign_in(selenium: WebDriver, auth: Auth):
    # find and select Kinto Account Auth for login
    kinto_auth_radio_button: WebElement = selenium.find_element(
        By.XPATH, "//input[@value='accounts']"
    )
    assert kinto_auth_radio_button, "Kinto Account Auth radio button not found"
    kinto_auth_radio_button.click()

    # ensure account credentials fields render
    account_creds_title: WebElement = selenium.find_element(
        By.ID, "root_credentials__title"
    )
    assert account_creds_title, "Account credentials title not found"
    assert account_creds_title.text == "Account credentials*"
    assert account_creds_title.is_displayed()

    # enter login username
    account_creds_user: WebElement = selenium.find_element(
        By.ID, "root_credentials_username"
    )
    assert account_creds_user, "Account credentials username entry not found"
    assert account_creds_user.is_displayed()
    account_creds_user.send_keys(auth[0])

    # enter login password
    account_creds_pass: WebElement = selenium.find_element(
        By.ID, "root_credentials_password"
    )
    assert account_creds_pass, "Account credentials password entry not found"
    assert account_creds_pass.is_displayed()
    account_creds_pass.send_keys(auth[1])

    # sign in
    sign_in_button: WebElement = selenium.find_element(By.CLASS_NAME, "btn-info")
    assert sign_in_button, "Sign in button not found"
    assert sign_in_button.text == "Sign in using Kinto Account Auth"
    assert sign_in_button.is_displayed()
    sign_in_button.click()

    # determine if successfully logged in to admin home page
    try:
        server_info: WebElement = selenium.find_element(
            By.XPATH,
            "//div[@class='card-header' and contains(., 'Server information')]",
        )
        assert server_info, "Server information not found"
        assert server_info.text == "Server information"
        assert server_info.is_displayed()
    except NoSuchElementException:
        pytest.fail("Login was unsuccessful")
