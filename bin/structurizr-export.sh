#!/usr/bin/env bash
# Generate the Structurizr static site that the architecture docs embed as iframes.
#
# Input:  docs/architecture/workspace.dsl (+ icons/)
# Output: docs/_static/diagrams/ (not committed; see .gitignore)
#
# Structurizr is only distributed as a Docker image, so Docker is used for local
# development and GitHub Actions. Read the Docs (detected via READTHEDOCS=True) has no
# Docker: there, the same image is pulled with crane, structurizr.war is extracted from it
# and run with the system Java (installed via build.apt_packages in .readthedocs.yaml).
set -euo pipefail

STRUCTURIZR_VERSION=2026.09.19
IMAGE="structurizr/structurizr:${STRUCTURIZR_VERSION}"
CRANE_VERSION=0.22.1
CRANE_SHA256=0ab7a1d6932a213aed964ce97666c3077fe691c8606413674a8b3e0b9ec4cda0  # pragma: allowlist secret

ROOT=$(cd "$(dirname "$0")/.." && pwd)
WORKSPACE_DIR="$ROOT/docs/architecture"
STATIC_DIR="$ROOT/docs/_static"
OUTPUT_NAME=diagrams

rm -rf "$STATIC_DIR/$OUTPUT_NAME"
mkdir -p "$STATIC_DIR"

if [ "${READTHEDOCS:-}" = "True" ]; then
    WORK=$(mktemp -d)
    trap 'rm -rf "$WORK"' EXIT

    curl -fsSL -o "$WORK/crane.tar.gz" \
        "https://github.com/google/go-containerregistry/releases/download/v${CRANE_VERSION}/go-containerregistry_Linux_x86_64.tar.gz"
    echo "$CRANE_SHA256  $WORK/crane.tar.gz" | sha256sum --check --quiet -
    tar -xzf "$WORK/crane.tar.gz" -C "$WORK" crane

    "$WORK/crane" --platform linux/amd64 export "$IMAGE" - | tar -xO usr/local/structurizr.war > "$WORK/structurizr.war"

    (cd "$WORKSPACE_DIR" && java -jar "$WORK/structurizr.war" export -w workspace.dsl -f static -o "$STATIC_DIR/$OUTPUT_NAME")
else
    if ! docker info >/dev/null 2>&1; then
        echo "Could not reach Docker. Make sure Docker is running and try again." >&2
        exit 1
    fi

    # Offer to pull the image when running interactively; otherwise `docker run` pulls it.
    if [ -t 0 ] && ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
        read -r -p "$IMAGE is not available locally. Pull it now? [Y/n] " answer
        case "$answer" in
            [nN]*) echo "Pull it with: docker pull $IMAGE" >&2; exit 1 ;;
        esac
        docker pull "$IMAGE"
    fi

    docker run --rm --user "$(id -u):$(id -g)" \
        -v "$WORKSPACE_DIR:/usr/local/structurizr" \
        -v "$STATIC_DIR:/output" \
        "$IMAGE" export -w workspace.dsl -f static -o "/output/$OUTPUT_NAME"
fi

test -f "$STATIC_DIR/$OUTPUT_NAME/index.html" || { echo "Structurizr export failed: no index.html produced" >&2; exit 1; }
