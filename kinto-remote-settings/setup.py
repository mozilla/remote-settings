from pathlib import Path

import setuptools


path = Path(__file__).parent / "../VERSION"
version = path.read_text().strip()

setuptools.setup(
    name="kinto_remote_settings",
    version=version,
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
)
