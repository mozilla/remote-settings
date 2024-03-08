#!/bin/bash
set -euo pipefail

VERSION=$(cat `pwd`/kinto-admin/VERSION)
TAG="v${VERSION}"

# download and unzip release
wget https://github.com/Kinto/kinto-admin/releases/download/${TAG}/kinto-admin-release.tar
rm -rf ./kinto-admin/build && mkdir ./kinto-admin/build
tar -xf kinto-admin-release.tar -C ./kinto-admin/build && rm kinto-admin-release.tar
# copy the VERSION file if not present (kinto-admin <= v3.0.3)
cp -n `pwd`/kinto-admin/VERSION ./kinto-admin/build/
