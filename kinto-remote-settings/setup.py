from pathlib import Path

import setuptools


path = Path(__file__).parent / "../VERSION"
version = path.read_text().strip()

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
