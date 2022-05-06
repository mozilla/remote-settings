#!/bin/bash

# THIS IS MEANT TO BE RUN BY CI ONLY.

set -e

# Usage: retry MAX CMD...
# Retry CMD up to MAX times. If it fails MAX times, returns failure.
# Example: retry 3 docker push "$DOCKERHUB_REPO:$TAG"
function retry() {
    max=$1
    shift
    count=1
    until "$@"; do
        count=$((count + 1))
        if [[ $count -gt $max ]]; then
            return 1
        fi
        echo "$count / $max"
    done
    return 0
}

# configure docker creds
echo "$DOCKER_PASS" | docker login -u="$DOCKER_USER" --password-stdin

docker images

SERVER_CONTAINER="remotesettings/server"
TEST_CONTAINER="remotesettings/tests"
SERVER_DOCKER_REPO="mozilla/remote-settings"
INTEGRATION_TEST_DOCKER_REPO="mozilla/remote-settings-integration-tests"

# docker tag and push git branch to dockerhub
if [ -n "$1" ]; then
    TAG="$1"
    echo "Tag and push server and integration test containers to Dockerhub"
    echo "${SERVER_DOCKER_REPO}:${TAG}"
    echo "${INTEGRATION_TEST_DOCKER_REPO}:${TAG}"

    docker tag $SERVER_CONTAINER "$SERVER_DOCKER_REPO:$TAG" ||
        (echo "Couldn't tag $SERVER_CONTAINER as $SERVER_DOCKER_REPO:$TAG" && false)
    retry 3 docker push "$SERVER_DOCKER_REPO:$TAG" ||
        (echo "Couldn't push $SERVER_DOCKER_REPO:$TAG" && false)

    docker tag $TEST_CONTAINER "$INTEGRATION_TEST_DOCKER_REPO:$TAG" ||
        (echo "Couldn't tag $TEST_CONTAINER as $INTEGRATION_TEST_DOCKER_REPO:$TAG" && false)
    retry 3 docker push "$INTEGRATION_TEST_DOCKER_REPO:$TAG" ||
        (echo "Couldn't push $INTEGRATION_TEST_DOCKER_REPO:$TAG" && false)

    echo "Done."
fi
