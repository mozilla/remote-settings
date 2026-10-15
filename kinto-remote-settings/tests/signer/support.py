import configparser
import os
from unittest import mock

from kinto import main as kinto_main
from kinto.core.testing import BaseWebTest as CoreWebTest
from kinto.core.testing import DummyRequest, get_user_headers


__all__ = ["BaseWebTest", "DummyRequest", "get_user_headers", "mock_autograph_sign"]


here = os.path.abspath(os.path.dirname(__file__))


def mock_autograph_sign(mocked_requests, fake_signature):
    """Make the mocked Autograph return one signature per signing request."""

    def post(url, auth, json):
        response = mock.MagicMock()
        response.json.return_value = [fake_signature() for _ in json]
        return response

    mocked_requests.post.side_effect = post


class BaseWebTest(CoreWebTest):
    api_prefix = "v1"
    entry_point = kinto_main
    config = "config.ini"

    def __init__(self, *args, **kwargs):
        super(BaseWebTest, self).__init__(*args, **kwargs)
        self.headers.update(get_user_headers("mat"))

    @classmethod
    def get_app_settings(cls, extras=None):
        ini_path = os.path.join(here, cls.config)
        config = configparser.ConfigParser()
        config.read(ini_path)
        settings = dict(config.items("app:main"))
        settings["signer.to_review_enabled"] = False
        return settings
