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

# docker tag and push git branch to dockerhub
if [ -n "$1" ]; then
    TAG="$1"
    echo "Tag and push ${DOCKERHUB_REPO}:${TAG} to Dockerhub"
    docker tag remotesettings:server "$DOCKERHUB_REPO:$TAG" ||
        (echo "Couldn't tag remote-settings as $DOCKERHUB_REPO:$TAG" && false)
    retry 3 docker push "$DOCKERHUB_REPO:$TAG" ||
        (echo "Couldn't push $DOCKERHUB_REPO:$TAG" && false)
    echo "Done."
fi
