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

# Usage: push_container_to_repo CONTAINER REPO TAG
# Push container to specified repo with tag
# Example: push_container_to_repo remotesettings mozilla/remote-settings latest
function push_container_to_repo() {
    container=$1
    repo=$2
    tag=$3
    docker tag $container "$repo:$tag" ||
        (echo "Couldn't tag $container as $repo:$tag" && false)
    retry 3 docker push "$repo:$tag" ||
        (echo "Couldn't push $repo:$tag" && false)
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
    push_container_to_repo $SERVER_CONTAINER $SERVER_DOCKER_REPO $TAG
    push_container_to_repo $TEST_CONTAINER $INTEGRATION_TEST_DOCKER_REPO $TAG

    echo "Done."
fi
