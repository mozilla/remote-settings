from typing import Callable, Tuple

import pytest
from kinto_http import AsyncClient
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement


def test_admin_login(
    base_url: str,
    selenium: WebDriver,
    make_client: Callable[[Tuple[str, str]], AsyncClient],
    auth: Tuple[str, str],
):
    make_client(auth)

    selenium.get(base_url)

    header: WebElement = selenium.find_element(By.CSS_SELECTOR, ".content div > h1")
    assert header, "Header element not found"
    assert "Administration" in header.text
    assert header.is_displayed()

    sign_in(selenium, auth)


def test_create_bucket_and_collection(
    base_url: str,
    selenium: WebDriver,
    make_client: Callable[[Tuple[str, str]], AsyncClient],
    auth: Tuple[str, str],
):
    make_client(auth)

    selenium.get(base_url)

    sign_in(selenium, auth)

    # find and click create bucket button
    create_bucket_button: WebElement = selenium.find_element(
        By.XPATH, "//a[@href='#/buckets/create']"
    )
    assert create_bucket_button, "Create bucket button not found"
    create_bucket_button.click()

    header: WebElement = selenium.find_element(By.CSS_SELECTOR, ".content div > h1")
    assert header, "Header element not found"
    assert header.text == "Create a new bucket"
    assert header.is_displayed()

    # ensure bucket id field renders and enter bucket id
    bucket_id: WebElement = selenium.find_element(By.ID, "root_id")
    assert bucket_id, "Bucket id field not found"
    assert bucket_id.is_displayed()
    bucket_id.send_keys("demo_bucket")

    # find and click create bucket button
    create_bucket_button: WebElement = selenium.find_element(
        By.XPATH, "//button[@type='submit']"
    )
    assert create_bucket_button, "Create bucket button not found"
    create_bucket_button.click()

    # determine if successfully created new bucket
    try:
        bucket: WebElement = selenium.find_element(
            By.XPATH,
            "//div[@class='card-header' and contains(., 'demo_bucket')]",
        )
        assert bucket, "demo_bucket not found"
        assert bucket.text == "demo_bucket bucket"
        assert bucket.is_displayed()
    except NoSuchElementException:
        pytest.fail("Create bucket was unsuccessful")

    # find and click create collection button
    create_collection_button: WebElement = selenium.find_element(
        By.XPATH, "//a[@href='#/buckets/demo_bucket/collections/create']"
    )
    assert create_collection_button, "Create collection button not found"
    create_collection_button.click()

    header: WebElement = selenium.find_element(By.CSS_SELECTOR, ".content div > h1")
    assert header, "Header element not found"
    assert header.text == "Create a new collection in demo_bucket bucket"
    assert header.is_displayed()

    # ensure collection id field renders and enter collection id
    collection_id: WebElement = selenium.find_element(By.ID, "root_id")
    assert collection_id, "Collection id field not found"
    assert collection_id.is_displayed()
    collection_id.send_keys("demo_collection")

    # find and click create collection button
    create_collection_button: WebElement = selenium.find_element(
        By.XPATH, "//button[@type='submit']"
    )
    assert create_collection_button, "Create collection button not found"
    create_collection_button.click()

    # determine if successfully created new collection
    try:
        collection: WebElement = selenium.find_element(
            By.XPATH,
            "//a[@href='#/buckets/demo_bucket/collections/demo_collection/records' and contains(., 'demo_collection')]",
        )
        assert collection, "demo_collection not found"
        assert collection.text == "demo_collection"
        assert collection.is_displayed()
    except NoSuchElementException:
        pytest.fail("Create collection was unsuccessful")


def sign_in(selenium: WebDriver, auth: Tuple[str, str]):
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
