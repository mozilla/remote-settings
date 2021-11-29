#!/usr/bin/env bash
set -eo pipefail

docker build . -t kinto:build
docker build . --file Testing.Dockerfile -t kinto:tests
