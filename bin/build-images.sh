#!/usr/bin/env bash
set -eo pipefail

docker build . -t kinto:build
docker build . --file Dockerfile.Testing -t kinto:tests
