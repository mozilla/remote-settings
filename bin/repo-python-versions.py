import re
import sys
from pathlib import Path


REGEXP_VERSION = r"[0-9]+\.[0-9]+(?:\.[0-9]+)?"


def extract_version_from_readthedocs(file_path):
    """
    .readthedocs.yaml:    python: "3.11"
    """
    content = file_path.read_text()
    match = re.search(r'python:\s*"?(' + REGEXP_VERSION + ')"?', content)
    return match.group(1) if match else None


def extract_version_from_pyproject(file_path):
    """ "
    pyproject.toml:python = ">=3.11, <3.14"
    cronjobs/pyproject.toml:python = ">=3.11, <3.14"
    browser-tests/pyproject.toml:python = ">=3.11, <3.14""
    """
    content = file_path.read_text()
    match = re.search(r'python\s*=\s*"(.*?)"', content)
    if match:
        version_range = match.group(1)
        min_version_match = re.search(r">=\s*(" + REGEXP_VERSION + ")", version_range)
        if min_version_match:
            return min_version_match.group(1)
    return None


def extract_versions_from_dockerfile(file_path):
    """
    cronjobs/Dockerfile:FROM python:3.13.1 AS build
    """
    content = file_path.read_text()
    return re.findall(f"python:({REGEXP_VERSION})", content)


def extract_versions_from_ci_workflow(file_path):
    """
    .github/workflows/ci.yaml:          python-version: "3.13"
    """
    content = file_path.read_text()
    return re.findall(r'python-version:\s*"?(' + REGEXP_VERSION + ')"?', content)


def main():
    versions = [extract_version_from_readthedocs(Path(".readthedocs.yaml"))]
    for path in Path(".").rglob("pyproject.toml"):
        versions += [extract_version_from_pyproject(path)]
    for path in Path(".github/workflows").glob("*.y*ml"):
        versions += extract_versions_from_ci_workflow(path)
    for path in Path(".").rglob("Dockerfile"):
        versions += extract_versions_from_dockerfile(path)

    cleaned_versions = sorted(set(v for v in versions if v))
    print("Extracted Python versions:")
    for v in cleaned_versions:
        print(f"- {v}")

    if len(cleaned_versions) > 1:
        print("❌ Inconsistent Python versions detected!")
        sys.exit(1)

    print("✅ Python versions are consistent.")


if __name__ == "__main__":
    main()
