#!/usr/bin/env bash
set -Eeuo pipefail

LOG_PREFIX=""
log() { printf '[%s]%s %s\n' "$(date +'%F %T')" "${LOG_PREFIX:+ [$LOG_PREFIX]}" "$*"; }
die() { log "ERROR: $*"; exit 1; }

fmt_duration() { printf '%dm%02ds' $(($1 / 60)) $(($1 % 60)); }

log_sizes() {
    local repo_path="$1" total_size git_size lfs_size
    total_size=$(du -sh "$repo_path" 2>/dev/null | cut -f1) || true
    git_size=$(du -sh "$repo_path/.git/objects" 2>/dev/null | cut -f1) || true
    lfs_size=$(du -sh "$repo_path/.git/lfs" 2>/dev/null | cut -f1) || true
    log "Size of $repo_path: ${total_size} (git objects=${git_size:-n/a}, LFS=${lfs_size:-n/a})"
    du -sh "$repo_path}/attachments/*/*" | sort -hr | head -n 10
}

ORIGIN_NAME="origin"

cmd_web() {
    granian --interface asgi --host $GRANIAN_HOST --port $GRANIAN_PORT --factory app:app_factory
}


cmd_gitupdate() {
    local repo_path="$1"
    local active_dir inactive_dir result
    local start_total start_update start_replicate
    start_total=$(date +%s)
    log "Repository path is $repo_path"

    # Check if latest symlink exists.
    if [ ! -L "$repo_path/latest" ]; then
        LOG_PREFIX="init"
        log "Latest symlink not found, initializing repository structure..."
        # If A doesn't exist, clone into A.
        if [ ! -d "$repo_path/A" ]; then
            log "Cloning repository ${GIT_REPO_URL} into $repo_path/A..."
            git clone "${GIT_REPO_URL}" "$repo_path/A"
            log "Clone took $(fmt_duration $(($(date +%s) - start_total)))."
            # Fresh clone don't contain attachments, fetch them from LFS.
            if [ "${SELF_CONTAINED:-false}" = "true" ]; then
                start_update=$(date +%s)
                git_fetch_lfs "$repo_path/A"
                log "First LFS pull took $(fmt_duration $(($(date +%s) - start_update)))."
            else
                log "Skipping LFS objects fetch."
            fi
        fi
        # Check that A was cloned properly.
        log "Verifying repository in A..."
        git -C "$repo_path/A" status || die "Failed to clone repository into $repo_path/A"
        log "Checking LFS objects in A..."
        git -C "$repo_path/A" lfs fsck || die "LFS of $repo_path/A is broken."

        # If B doesn't exist, duplicate into B.
        if [ ! -d "$repo_path/B" ]; then
            log "Duplicating A to B..."
            cp -R "$repo_path/A" "$repo_path/B"
        fi
        # Set latest to A.
        log "Setting latest symlink to A..."
        ln -sfn "$repo_path/A" "$repo_path/latest"

        # A was just cloned at origin HEAD and B is an exact copy, so there is
        # nothing to update yet. Return and let the next run pick up changes.
        LOG_PREFIX=""
        log "Initialization complete in $(fmt_duration $(($(date +%s) - start_total)))."
        return 0
    fi

    LOG_PREFIX="update"
    # Determine whether A or B is the latest.
    if [ -d "$repo_path/A" ] && [ -d "$repo_path/B" ]; then
        if [ "$repo_path/latest" -ef "$repo_path/A" ] ; then
            active_dir="$repo_path/A"
            inactive_dir="$repo_path/B"
        else
            active_dir="$repo_path/B"
            inactive_dir="$repo_path/A"
        fi
    fi

    log "Active directory is $active_dir"
    log "Updating inactive directory $inactive_dir..."
    start_update=$(date +%s)
    if git_fetch_lfs "$inactive_dir"; then
        log "Repository updated"
    else
        result=$?
        if [ $result -eq 1 ]; then
            log "No LFS update available"
        else
            log "Error during update (exit code $result)"
            exit $result
        fi
    fi
    log "Update took $(fmt_duration $(($(date +%s) - start_update)))."
    log_sizes "$inactive_dir"

    log "Switching latest symlink to $inactive_dir..."
    ln -sfn "$inactive_dir" "$repo_path/latest"

    LOG_PREFIX="replicate"
    start_replicate=$(date +%s)
    log "Syncing updates back to previously active directory $active_dir..."
    # Keep attributes, preserve hardlinks where possible; avoid copying .git objects redundantly
    rsync -a --delete "$inactive_dir/.git/lfs/objects/". "$active_dir/.git/lfs/objects/"
    log "Replicate of LFS objects took $(fmt_duration $(($(date +%s) - start_replicate)))."

    log "Replicate updates in $active_dir too ..."
    # Add the sibling remote if it doesn't already exist
    if git -C "$active_dir" remote get-url sibling >/dev/null 2>&1; then
        git -C "$active_dir" remote set-url sibling "$inactive_dir"
    else
        git -C "$active_dir" remote add sibling "$inactive_dir"
    fi
    git -C "$active_dir" fetch --tags --force --verbose sibling
    git -C "$active_dir" reset --hard sibling/v1/common
    log "Replicate of Git objects took $(fmt_duration $(($(date +%s) - start_replicate)))."
    log_sizes "$active_dir"

    LOG_PREFIX=""
    log "Fetch completed in $(fmt_duration $(($(date +%s) - start_total)))."
}


git_fetch_lfs() {
    local repo_path="$1"

    log "Current commit for $repo_path"
    git -C $repo_path log -n 1

    # Remove Git lock if any. Or fetch will fail with "fatal: Unable to create '.../.git/index.lock': File exists."
    lock_file="$repo_path/.git/index.lock"
    if [ -f "$lock_file" ]; then
        log "Removing stale lock file $lock_file..."
        rm -f "$lock_file"
    fi

    git -C "$repo_path" checkout v1/common
    # Fetch everything, remote references always win.
    git -C "$repo_path" fetch --tags --force --verbose $ORIGIN_NAME

    # Check if there were any updates
    local_head=$(git -C "$repo_path" rev-parse HEAD)
    origin_head=$(git -C "$repo_path" rev-parse "$ORIGIN_NAME/v1/common")
    log "Local HEAD: $local_head"
    log "Remote HEAD: $origin_head"
    if [ "$local_head" = "$origin_head" ]; then
        log "No LFS updates..."
        return 0
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
        log "Pruning LFS objects..."
        git -C "$repo_path" lfs prune
        log "Checking LFS objects..."
        git -C "$repo_path" lfs fsck
    else
        log "Skipping LFS objects fetch (SELF_CONTAINED=${SELF_CONTAINED:-false})."
    fi
    return 0   # update happened
}


case "${1:-}" in
  gitupdate)
    [ -z "${GIT_REPO_URL:-}" ] && die "GIT_REPO_URL must be set for init."
    [ -z "${GIT_REPO_PATH:-}" ] && die "GIT_REPO_PATH must be set for update."
    # For consistency with the web server, we expect GIT_REPO_PATH to point to
    # the "latest" symlink, so we use its parent directory to create A and B.
    parent_dir=$(dirname "${GIT_REPO_PATH}")
    mkdir -p "${parent_dir}" || die "Failed to create parent directory ${parent_dir}."
    (
        # See https://manpages.debian.org/testing/util-linux/flock.1.en.html#EXAMPLES
        flock -n 9 || { echo "Update already running."; exit 0; };
        cmd_gitupdate "${parent_dir}";
    ) 9>"${parent_dir}/.fetch-lock"
    ;;
  web)
    cmd_web;
    ;;
  *)
    # Run the command as given.
    log "Running command: $*"
    exec "$@"
    ;;
esac
