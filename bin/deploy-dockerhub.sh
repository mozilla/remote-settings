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
retry 3  echo "$DOCKER_PASS" | docker login -u="$DOCKER_USER" --password-stdin

docker images

# docker tag and push git branch to dockerhub
if [ -n "$1" ]; then
    [ "$1" == master ] && TAG=latest || TAG="$1"
    docker tag kinto-dist "$DOCKERHUB_REPO:$TAG" ||
        (echo "Couldn't tag kinto-dist as $DOCKERHUB_REPO:$TAG" && false)
    retry 3 docker push "$DOCKERHUB_REPO:$TAG" ||
        (echo "Couldn't push $DOCKERHUB_REPO:$TAG" && false)
    echo "Pushed $DOCKERHUB_REPO:$TAG"
fi
