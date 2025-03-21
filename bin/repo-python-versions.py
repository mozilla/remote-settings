import re
import sys
from pathlib import Path


REGEXP_VERSION = r"[0-9]+\.[0-9]+(?:\.[0-9]+)?"


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
    versions = []
    for path in Path(".github/workflows").glob("*.y*ml"):
        versions += extract_versions_from_ci_workflow(path)
    for path in Path(".").rglob("Dockerfile"):
        versions += extract_versions_from_dockerfile(path)

    # We don't verify `pyproject.toml` files, since they provide a range
    # for developers convenience, and won't build if CI or Dockerfiles
    # don't match.

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
