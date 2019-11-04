import pytest


@pytest.fixture
def firefox_options(firefox_options):
    """Set Firefox Options."""
    firefox_options.headless = True
    return firefox_options

@pytest.mark.nondestructive
def test_html_loads_correctly(base_url, selenium):
    selenium.get(base_url)
    header = selenium.find_element_by_css_selector(".content div > h1")
    assert "Kinto Administration" in header.text
    assert header.is_displayed()
