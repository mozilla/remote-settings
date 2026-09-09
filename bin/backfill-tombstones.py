"""
This is the one-shot backfill script to build the tombstones ledger files from the `/v1` API.

The output folder is a clone of the git export repository.

Usage:
    uv run bin/backfill-tombstones.py https://firefox.settings.services.mozilla.com/v1 /tmp/git-export.git
"""

import asyncio
import logging
import os
import pathlib
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone

import kinto_http


MAX_PARALLEL_REQUESTS = 16
TIMESTAMP_SEPARATOR = "\t"


def run_git(repo: pathlib.Path, *args: str) -> str:
    print("Running ", ["git", "-C", str(repo), *args])
    env = os.environ.copy()
    p = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={"GIT_LFS_SKIP_SMUDGE": "true", **env},
    )
    if p.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({p.returncode}):\n{p.stderr.strip()}"
        )
    return p.stdout.strip()


async def fetch_tombstones(
    client: kinto_http.AsyncClient, sem: asyncio.Semaphore, bid: str, cid: str
) -> list[tuple[str, int]]:
    async with sem:
        # Tombstones are only returned when `_since` is specified.
        records = await client.get_records(  # ty: ignore[invalid-await]
            bucket=bid, collection=cid, _since=0, deleted="true", pages=float("inf")
        )
    print(f"{bid}/{cid}: {len(records)} tombstones")
    return [(r["id"], r["last_modified"]) for r in records]


def write_ledgers(
    repo: pathlib.Path, cid: str, tombstones: list[tuple[str, int]]
) -> None:
    # The `git-export` cronjob is stopped while this runs, and `/v1` knows every
    # deletion, so the existing ledgers are simply replaced.
    folder = repo / cid / "tombstones"
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)

    by_month = defaultdict(list)
    for rid, timestamp in tombstones:
        dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
        month = dt.strftime("%Y%m")
        by_month[month].append((rid, timestamp))

    for month, entries in by_month.items():
        # Oldest first, since the `git-export` job will append them.
        entries.sort(key=lambda entry: (entry[1], entry[0]))
        ledger = folder / f"{month}.txt"
        ledger.write_text(
            "".join(f"{ts}{TIMESTAMP_SEPARATOR}{rid}\n" for rid, ts in entries)
        )


def commit_bucket(
    repo: pathlib.Path, bid: str, tombstones_by_cid: dict[str, list], message: str
) -> int:
    """
    Write the ledgers of every collection of the bucket on its branch, and commit.
    Return the number of entries that were written.
    """
    branch = f"v1/buckets/{bid}"
    try:
        run_git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}")
    except RuntimeError:
        print(f"WARNING: no '{branch}' branch, skipping {bid}.")
        return 0

    run_git(repo, "checkout", "--quiet", branch)

    written = 0
    for cid, tombstones in tombstones_by_cid.items():
        if not (repo / cid).is_dir():
            # This would only happen if a collection was created and the server
            # and not available in the local clone.
            # git-reader would not like a folder without any `metadata.json`, skip.
            print(f"⚠️ WARNING: {bid}/{cid} not found on {branch}, skipping.")
            continue
        write_ledgers(repo, cid, tombstones)
        written += len(tombstones)

    run_git(repo, "add", "--all")
    if not run_git(repo, "diff", "--staged", "--name-only"):
        print(f"{branch}: already up-to-date.")
        return 0

    run_git(repo, "commit", "--message", message)
    print(f"{branch}: {written} tombstones in {run_git(repo, 'rev-parse', 'HEAD')}")
    return written


async def main() -> None:
    try:
        server_url, output_folder = sys.argv[-2:]
    except ValueError:
        sys.exit(f"Usage: {sys.argv[0]} SERVER_URL GIT_REPO_FOLDER")

    repo = pathlib.Path(output_folder)
    if not (repo / ".git").exists():
        sys.exit(f"ERROR: {repo} is not a Git repository.")
    if run_git(repo, "status", "--porcelain"):
        sys.exit(f"ERROR: {repo} has uncommitted work in progress.")

    initial_branch = run_git(repo, "rev-parse", "--abbrev-ref", "HEAD")

    client = kinto_http.AsyncClient(server_url=server_url)
    sem = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)

    monitor_changeset = await client.get_changeset(
        bucket="monitor", collection="changes", bust_cache=True
    )
    collections = [
        (entry["bucket"], entry["collection"]) for entry in monitor_changeset["changes"]
    ]
    print(f"Fetching tombstones of {len(collections)} collections...")

    all_tombstones = await asyncio.gather(
        *(fetch_tombstones(client, sem, bid, cid) for bid, cid in collections)
    )

    by_bucket: dict[str, dict[str, list]] = defaultdict(dict)
    for (bid, cid), tombstones in zip(collections, all_tombstones):
        by_bucket[bid][cid] = tombstones

    message = f"Backfill tombstones @ {datetime.now(tz=timezone.utc).isoformat()}"
    total = 0
    try:
        for bid, tombstones_by_cid in sorted(by_bucket.items()):
            total += commit_bucket(repo, bid, tombstones_by_cid, message)
    finally:
        run_git(repo, "checkout", "--quiet", initial_branch)

    print(f"\nAdded {total} tombstones in {repo}, on {len(by_bucket)} bucket branches.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
    logging.getLogger("kinto_http").setLevel(logging.DEBUG)
    logging.getLogger("urllib3").setLevel(logging.DEBUG)

    asyncio.run(main())
