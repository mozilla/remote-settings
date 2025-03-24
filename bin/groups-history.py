"""
This script will list all groups and find in their history the entries
that don't modify any attribute, and can thus be deleted.

See mozilla/remote-settings#804
"""
import asyncio
import difflib
import itertools
import json
import os
from copy import copy

import kinto_http


ENV = os.getenv("ENV", "prod")
SERVER_URL = {
    "prod": "https://remote-settings.mozilla.org/v1",
    "stage": "https://remote-settings.allizom.org/v1",
    "dev": "https://remote-settings-dev.allizom.org/v1",
    "local": "http://localhost:8888/v1",
}[ENV.lower()]
AUTH = os.getenv("AUTH")

LIMIT = 100000  # more than server limit to get max
CHUNK_SIZE = 4

RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_colored(line):
    if line.startswith("+") and not line.startswith("+++"):
        print(f"{GREEN}{line}{RESET}")
    elif line.startswith("-") and not line.startswith("---"):
        print(f"{RED}{line}{RESET}")
    elif line.startswith("@@"):
        print(f"{BOLD}{YELLOW}{line}{RESET}")
    elif line.startswith("---") or line.startswith("+++"):
        print(f"{BLUE}{line}{RESET}")
    else:
        print(line)


def diff_dicts(old, new):
    """Show Git-style diff between two dicts with ANSI color highlighting."""
    old_str = json.dumps(old, indent=2, sort_keys=True).splitlines()
    new_str = json.dumps(new, indent=2, sort_keys=True).splitlines()

    diff = difflib.unified_diff(
        old_str, new_str, fromfile="previous", tofile="current", lineterm=""
    )

    for line in diff:
        print_colored(line)


async def fetch_groups(client, bid):
    """Fetch groups for a given bucket."""
    groups = await client.get_groups(bucket=bid)
    return [(bid, g["id"]) for g in groups]


async def fetch_history(client, bid, gid):
    print(".", end="", flush=True)
    entries = await client.get_history(
        bucket=bid, resource_name="group", group_id=gid, _limit=LIMIT
    )
    return reversed(entries)


async def main():
    client = kinto_http.AsyncClient(server_url=SERVER_URL, auth=AUTH)

    # Fetch all groups in parallel
    bucket_ids = ["main-workspace", "security-state-staging", "staging"]
    results = await asyncio.gather(*(fetch_groups(client, bid) for bid in bucket_ids))
    all_groups = list(itertools.chain.from_iterable(results))

    print(len(all_groups), "groups to analyze")
    all_histories = []
    for i in range(0, len(all_groups), CHUNK_SIZE):
        chunk = all_groups[i : i + CHUNK_SIZE]
        chunk_results = await asyncio.gather(
            *(fetch_history(client, bid, gid) for bid, gid in chunk)
        )
        all_histories.extend(chunk_results)

    to_delete = set()

    for entries in all_histories:
        prev_data = None
        for i, entry in enumerate(entries):
            current_data = entry["target"]["data"]
            user = entry["user_id"]
            group_id = current_data["id"]
            date = entry["date"]
            if prev_data is not None:
                prev_without_timestamp = copy(prev_data)
                del prev_without_timestamp["last_modified"]
                current_without_timestamp = copy(current_data)
                del current_without_timestamp["last_modified"]

                if prev_without_timestamp == current_without_timestamp:
                    # This history entry can be deleted.
                    to_delete.add(entry["id"])
                else:
                    print(
                        f"\n{BOLD}{BLUE}=== {user} modified group '{group_id}' on {date} ==={RESET}"
                    )
                    diff_dicts(prev_data, current_data)
            prev_data = current_data

    if to_delete:
        print(len(to_delete), "history entries can be deleted")
        sql = f"DELETE FROM objects WHERE resource_name = 'history' AND id IN ({','.join(f"'{uuid}'" for uuid in to_delete)});"
        print(sql)


# Run the asyncio event loop
asyncio.run(main())
