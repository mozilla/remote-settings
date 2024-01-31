#!/bin/bash
set -euo pipefail

VERSION=$(cat `pwd`/kinto-admin/VERSION)
TAG="v${VERSION}"

# download and unzip release
curl -OL https://github.com/Kinto/kinto-admin/releases/download/${TAG}/kinto-admin-release.tar
tar -xf kinto-admin-release.tar -C ./kinto-admin/build && rm kinto-admin-release.tar
