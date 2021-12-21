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
        assert "Server information" in server_info.text
        assert server_info.is_displayed()
    except NoSuchElementException:
        pytest.fail("Login was unsuccessful")


# TODO: add more tests
