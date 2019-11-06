import pytest
import requests
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter


@pytest.fixture(scope="session", autouse=True)
def _verify_url(request, base_url):
    """Verifies the base URL"""
    verify = request.config.option.verify_base_url
    if base_url and verify:
        session = requests.Session()
        retries = Retry(backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
        session.mount(base_url, HTTPAdapter(max_retries=retries))
        session.get(base_url, verify=False)

@pytest.fixture
def firefox_options(firefox_options):
    """Set Firefox Options."""
    firefox_options.headless = True
    return firefox_options

@pytest.mark.nondestructive
def test_html_loads_correctly(base_url, selenium):
    selenium.get(base_url)
    header = selenium.find_element_by_css_selector(".content div > h1")
    assert "Administration" in header.text
    assert header.is_displayed()
