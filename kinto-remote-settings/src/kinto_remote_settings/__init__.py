import json
from pathlib import Path


def get_version():
    path = Path(__file__).parent.parent.parent.parent / "version.json"
    return json.load(open(path))["version"].replace("v", "").split("-")[0]


__version__ = get_version()


def includeme(config):
    config.include("kinto_remote_settings.changes")
    config.include("kinto_remote_settings.signer")
