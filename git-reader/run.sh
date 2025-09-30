#!/usr/bin/env bash
set -Eeuo pipefail

log() { printf '[%s] %s\n' "$(date +'%F %T')" "$*"; }
die() { log "ERROR: $*"; exit 1; }

ORIGIN_NAME="origin"


cmd_web() {
    log "Starting web server..."
    poetry run uvicorn app:app --host 0.0.0.0 --port 8000
}


cmd_init() {
    local repo_path="$1"

    # Initialize only if neither latest, nor A nor B exists.
    if [ -d "$repo_path/latest" ] || [ -d "$repo_path/A" ] || [ -d "$repo_path/B" ]; then
        log "Directory $repo_path already initialized, skipping."
        return 0
    fi

    log "Initializing directory $repo_path..."
    mkdir -p "$repo_path"

    log "Cloning repository ${GIT_REPO_URL} into $repo_path/A..."
    git clone "${GIT_REPO_URL}" "$repo_path/A"

    if [ "${SELF_CONTAINED:-false}" = "true" ]; then
    git_fetch_lfs "$repo_path/A"
    else
    log "Skipping LFS objects fetch."
    fi

    log "Duplicating A to B..."
    cp -R "$repo_path/A" "$repo_path/B"

    log "Setting latest symlink to A..."
    ln -sfn "$repo_path/A" "$repo_path/latest"
}


cmd_update() {
    local repo_path="$1"

    # Determine whether A or B is the latest.
    if [ -d "$repo_path/A" ] && [ -d "$repo_path/B" ]; then
        if [ "$repo_path/latest" -ef "$repo_path/A" ] ; then
            active_dir="$repo_path/A"
            inactive_dir="$repo_path/B"
        else
            active_dir="$repo_path/B"
            inactive_dir="$repo_path/A"
        fi
    else
        die "Both A and B must exist. Run 'init' first."
    fi

    log "Updating inactive directory $inactive_dir..."
    git_fetch_lfs "$inactive_dir"
    result=$?
    if [ $result -ne 0 ]; then
        log "No update available"
        return $result
    fi

    log "Switching latest symlink to $inactive_dir..."
    ln -sfn "$inactive_dir" "$repo_path/latest"

    log "Syncing updates back to previously active directory $active_dir..."
    # Keep attributes, preserve hardlinks where possible; avoid copying .git objects redundantly
    rsync -a --delete "$inactive_dir/". "$active_dir/"

    log "Fetching updates in $active_dir too ..."
    git_fetch_lfs "$active_dir"

    log "Fetch completed."
}


git_fetch_lfs() {
    local repo_path="$1"

    git -C "$repo_path" checkout v1/common
    git -C "$repo_path" fetch --verbose $ORIGIN_NAME

    # Check if there were any updates
    local_head=$(git -C "$repo_path" rev-parse HEAD)
    origin_head=$(git -C "$repo_path" rev-parse "$ORIGIN_NAME/v1/common")
    log "Local HEAD: $local_head"
    log "Remote HEAD: $origin_head"
    if [ "$local_head" = "$origin_head" ]; then
        return 1
    fi

    log "Updates found, set to remote content..."
    git -C "$repo_path" reset --hard "$ORIGIN_NAME/v1/common"
    log "Cleaning up repository..."
    git -C "$repo_path" remote prune "$ORIGIN_NAME"
    git -C "$repo_path" gc --prune=now
    git -C "$repo_path" repack -Ad

    if [ "${SELF_CONTAINED:-false}" = "true" ]; then
        log "Fetching LFS objects..."
        git -C "$repo_path" lfs pull
        log "Checking LFS objects..."
        git -C "$repo_path" lfs fsck
    else
        log "Skipping LFS objects fetch (SELF_CONTAINED=${SELF_CONTAINED:-false})."
    fi
}


case "${1:-}" in
  update)
    [ -z "${GIT_REPO_PATH:-}" ] && die "GIT_REPO_PATH must be set for update."
    log "Running fetch updates..."
    (
        # See https://manpages.debian.org/testing/util-linux/flock.1.en.html#EXAMPLES
        flock -n 9 || { echo "Update already running."; exit 1; };
        cmd_update "${GIT_REPO_PATH}";
    ) 9>"${GIT_REPO_PATH}/.fetch-lock"
    ;;
  web)
    log "Starting web server..."
    cmd_web;
    ;;
  init)
    log "Initializing folder..."
    [ -z "${GIT_REPO_URL:-}" ] && die "GIT_REPO_URL must be set for init."
    [ -z "${GIT_REPO_PATH:-}" ] && die "GIT_REPO_PATH must be set for init."
    # For consistency with the web server, we expect GIT_REPO_PATH to point to
    # the "latest" symlink, so we use its parent directory to create A and B.
    parent_dir=$(dirname "${GIT_REPO_PATH}")
    cmd_init "${parent_dir}"
    ;;
  *)
    # Run the command as given.
    log "Running command: $*"
    exec "$@"
    ;;
esac
