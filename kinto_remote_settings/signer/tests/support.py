import os

try:
    import ConfigParser as configparser
except ImportError:
    import configparser

from kinto import main as kinto_main
from kinto.core.testing import BaseWebTest as CoreWebTest
from kinto.core.testing import DummyRequest, get_user_headers

__all__ = ["BaseWebTest", "DummyRequest", "get_user_headers"]


here = os.path.abspath(os.path.dirname(__file__))


class BaseWebTest(CoreWebTest):
    api_prefix = "v1"
    entry_point = kinto_main
    config = "config/signer.ini"

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
