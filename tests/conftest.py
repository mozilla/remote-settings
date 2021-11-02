import pytest


DEFAULT_SERVER = "http://localhost:8888/v1"
DEFAULT_AUTH = "user:pass"
DEFAULT_BUCKET = "default"
DEFAULT_COLLECTION = "source"


def pytest_addoption(parser):
    parser.addoption(
        "--server",
        action="store",
        default=DEFAULT_SERVER,
        help="Kinto server (in form 'http(s)://<host>:<port>/v1')",
    )
    parser.addoption(
        "--auth",
        action="store",
        default=DEFAULT_AUTH,
        help="Basic authentication",
    )
    parser.addoption(
        "--editor-auth",
        action="store",
        default=None,
        help="Basic authentication for editor",
    )
    parser.addoption(
        "--reviewer-auth",
        action="store",
        default=None,
        help="Basic authentication for reviewer",
    )
    parser.addoption(
        "--bucket",
        action="store",
        default=DEFAULT_BUCKET,
        help="Source bucket",
    )
    parser.addoption(
        "--collection",
        action="store",
        default=DEFAULT_COLLECTION,
        help="Source collection",
    )
    parser.addoption(
        "--reset",
        action="store_true",
        default=False,
        help="Reset collection data",
    )


@pytest.fixture(scope="session")
def server(request):
    return request.config.getoption("--server")


@pytest.fixture(scope="session")
def auth(request):
    return tuple(request.config.getoption("--auth").split(":"))


@pytest.fixture(scope="session")
def editor_auth(request):
    return request.config.getoption("--editor-auth")


@pytest.fixture(scope="session")
def reviewer_auth(request):
    return request.config.getoption("--reviewer-auth")


@pytest.fixture(scope="session")
def bucket(request):
    return request.config.getoption("--bucket")


@pytest.fixture(scope="session")
def collection(request):
    return request.config.getoption("--collection")


@pytest.fixture(scope="session")
def reset(request):
    return request.config.getoption("--reset")
