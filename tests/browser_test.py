from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement


def test_admin_login(base_url: str, selenium: WebDriver):
    print(base_url)
    selenium.get(base_url)
    header: WebElement = selenium.find_element(By.CSS_SELECTOR, ".content div > h1")
    assert "Administration" in header.text
    assert header.is_displayed()

    sign_in_button: WebElement = selenium.find_element(By.CLASS_NAME, "btn-info")
    assert sign_in_button.is_displayed()
    sign_in_button.click()

    title: WebElement = selenium.find_element(By.CSS_SELECTOR, ".content div > h1")
    assert title.is_displayed()


# TODO: add more tests
