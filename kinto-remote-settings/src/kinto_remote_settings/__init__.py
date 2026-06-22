from pyramid.config import Configurator


def get_version() -> str:
    """
    Get the version of the application from the version file.
    """
    import json
    import os

    VERSION_FILE = os.getenv("VERSION_FILE", "version.json")
    if not os.path.exists(VERSION_FILE):
        return "0.0.0"

    with open(VERSION_FILE) as f:
        return json.load(f)["version"].replace("v", "").split("-")[0]


__version__ = get_version()


def includeme(config: Configurator) -> None:
    config.include("kinto_remote_settings.changes")
    config.include("kinto_remote_settings.signer")
