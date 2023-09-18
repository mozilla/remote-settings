import json
from pathlib import Path

import setuptools


path = Path(__file__).parent.parent / "version.json"
version = json.load(open(path))["version"].replace("v", "").split("-")[0]

INSTALL_REQUIRES = [
    "kinto",
    "canonicaljson-rs",
    "ecdsa",
    "requests_hawk",
]

setuptools.setup(
    name="kinto_remote_settings",
    version=version,
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    install_requires=INSTALL_REQUIRES,
)
