# git-reader: Missing Tombstones for Old `_since` Timestamps

* Status: proposed
* Deciders: acottner, smarnach, mleplatre
* Date: Aug 14, 2026

## Context and Problem Statement

In the `/v2` git-based implementation, each collection publication is a tag on the bucket branch (`timestamps/{bucket}/{collection}/{timestamp}`), and a partial changeset (`?_since={T}`) is computed as the diff between the tree at tag `{T}` and the tree at the branch tip.

Tags are files on disk and slow down git operations, so the export job deletes the ones older than 30 days (`TAGS_MAX_AGE_DAYS`). Clients coming with a `_since` timestamp that has no matching tag are redirected to the full changeset ([#1474](https://github.com/mozilla/remote-settings/pull/1474)).

A full changeset contains only the live records and has no tombstone. Therefore, if records were deleted in the meantime, these clients never learn about the deletions, and **clients that do not verify signatures silently keep obsolete records in their local data**.

Clients verifying signatures catch up on retry: the signature covers the live record set, so the extraneous records make verification fail, and the client wipes its local data and pulls again. 
The Application-Service Rust client do have the signature verification feature, but it is not enabled on iOS or Android builds ([Bug 2063304](https://bugzilla.mozilla.org/show_bug.cgi?id=2063304)).

## Decision Drivers

- **Exhaustiveness**: does the solution cover *all* deletions, or only some?
- **Fixes existing clients**: does it repair clients already deployed, or only future ones?
- **Cost of implementation**: Low → High
- **Cost of operation**: Low → High: repository size, number of git objects, CDN cache cardinality

## Considered Options

1. [Option A - Make signature verification mandatory](#option-a---make-signature-verification-mandatory)
1. [Option B - Keep all timestamps](#option-b---keep-all-timestamps)
1. [Option C - Resolve unknown `_since` to nearest older tag, and pin the genesis tag](#option-c---resolve-unknown-_since-to-nearest-older-tag-and-pin-the-genesis-tag)
1. [Option D - Trim tags exponentially instead of a flat cutoff](#option-d---trim-tags-exponentially-instead-of-a-flat-cutoff)
1. [Option E - Tombstones ledger on the bucket branch](#option-e---tombstones-ledger-on-the-bucket-branch)

## Decision Outcome

Chosen option: **Option E - Tombstones ledger**, because it is the only option that covers every deletion, that can reconstruct the history we already truncated, and that does not prevent the correctness of partial changesets to the number of tags we are willing to keep.

**Option A** remains desirable and no option below removes the need for it, but it does not repair existing clients, and is not a clean solution for clients synchronizing with an >30 days old `_since` (~1%) since it produces signature failure noise in telemetry.

## Pros and Cons of the Options

### Option A - Make signature verification mandatory

Change the client specifications from SHOULD to MUST, and enable verification on the Android and iOS megazords ([bug 2063304](https://bugzilla.mozilla.org/show_bug.cgi?id=2063304)).

- **Exhaustiveness**: N/A. Does not prevent the missing tombstones, but makes clients recover from them.
- **Fixes existing clients**: No, but this is the norm for client bugs.
- **Cost of implementation**: Mid. Requires client work on several platforms, especially regarding usage of root certificates instead of root hashes ([bug 1940903](https://bugzilla.mozilla.org/show_bug.cgi?id=1940903))
- **Cost of operation**: Mid. To detect the extraneous records, clients have to fail verification, retry, and succeed, which produces extra traffic and signature failure noise in telemetry.

### Option B - Keep all timestamps

Stop deleting old tags. The reason for trimming git objects was to prune LFS objects from the server, but LFS pointers live on the `common` branch, and bucket branches only contain records data — their commits are in fact already never truncated. So this option is really about tag retention only: keeping every tag means every past timestamp remains resolvable, and only clients with a genuinely unknown timestamp are redirected.

- **Exhaustiveness**: Full, for the future.
- **Fixes existing clients**: Partially — works from now on, but does not reconstruct the history already truncated at 30 days.
- **Cost of implementation**: Low.
- **Cost of operation**: High. Tags grow unbounded for frequently updated collections, which is the constraint we introduced the cutoff for.

### Option C - Resolve unknown `_since` to nearest older tag, and pin the genesis tag

Instead of redirecting to the full changeset, resolve an unknown `_since` to the most recent tag older than it ([#1474](https://github.com/mozilla/remote-settings/pull/1474)), and never delete the oldest tag of each collection so that this resolution always has a base. Diffing from an older tree returns a superset of the changes: unchanged records are sent again, which is harmless since clients apply them by id.

- **Exhaustiveness**: Partial. A tombstone can only be produced for a record present in the base tree, so records created, synced, and deleted after the base tag are invisible.
- **Fixes existing clients**: Yes if we rewrite the git repo history using V1 data.
- **Cost of implementation**: Very low. A few lines in git-reader plus a small change in `delete_old_tags()`.
- **Cost of operation**: Low. One extra tag per collection.

### Option D - Trim tags exponentially instead of a flat cutoff

Same as *Option C*, but keep every tag < 7 days, daily < 3 months, weekly < 2 years. This avoids serving thousands of tombstones since a collection's genesis to a client whose local state is only a few months old.

- **Exhaustiveness**: Partial. The gap of Option C shrinks to the thinning interval but never closes.
- **Fixes existing clients**: Yes if we rewrite the git repo history using V1 data.
- **Cost of implementation**: Low.
- **Cost of operation**: Low. Tag count becomes asymptotic instead of linear.

### Option E - Tombstones ledger on the bucket branch

Store the ids of all deleted records and their deletion timestamp as data on the bucket branch, next to the records. A partial changeset for `_since={T}` is then the live records whose `last_modified > T`, plus the ledger entries whose deletion timestamp is `> T`. 

Since the ledger would be up-to-date at the tip of each branch, this solution therefore involves no tag lookup at all. This means that git-reader could use shallow clones, and repack the clones to only keep the bare minimum objects.

Downside: it is less elegant than deriving everything from the versioned trees, and it only records *which* records existed. But since we would now only do shallow clones and wouldn't need tags anymore, we can stop truncating bucket branches, and a human would thus be able to check out the past content of a collection.

- **Exhaustiveness**: Full. Every deletion is recorded explicitly, including for records created and deleted between two publications.
- **Fixes existing clients**: Yes. Past deletions can be backfilled from the `/v1` API, so coverage is complete once backfilled.
- **Cost of implementation**: Mid. Export job, git-reader, and a one-shot backfill.
- **Cost of operation**: Low. Ledger entries are ids and timestamps; the number of tags no longer grows; git-reader can use shallow clones since only the branch tips are needed.

#### Implementation

**Storage.** One file per month, `{cid}/tombstones/{YYYYMM}.txt`, with one `{rid}@{timestamp}` per line. Monthly files rather than a single `tombstones.json` so that old files are immutable. Each publication rewrites at most one small blob, and readers only open the files they need.

**Export job.** The deleted ids are already derived when building the branch content (`changeset_to_branch_folder()` diffs the changeset against the branch tree). They are appended to the current month's file in the same commit as the record removal, so the ledger can never be out of step with the tree it describes.

**git-reader.** For `?_since={T}`: keep the tip records whose `last_modified > T`, then read the ledger files by name descending and stop after the first file that contains an entry `<= T`. A record that is live and in the ledger (deleted, then created again) is served as a change, not as a tombstone, and only the most recent deletion of an id is kept. Any `T` is valid, including a value that was never published, so `_since` never triggers a redirect.

**Collection timestamp.** Since tags are no longer used to resolve `_since`, the timestamp is derived from the tip: `max(live last_modified, most recent tombstone)`, falling back to `metadata.last_modified` for a collection without any record. This is exactly the records timestamp served by `/v1`.

#### Plan

1. Approve ADR
1. Implement `git-reader` that fallsback nicely if no `tombstones/` folder
1. Implement ledger in `git-export` job
1. Use a script to build `tombstones/*.txt` files from `v1/` API
1. Stop `git-export` cronjob
1. Commit backfill of tombstones files manually
1. Run `git-export` again


## Links

- Old `_since` redirection is [done by the CDN VCL code](https://github.com/mozilla/webservices-infra/blob/75b41b73ef0c92f83d2bedfefdd6e0f80dd194cc/remote-settings/tf/prod/waf.tf#L251-L256), but only for the `monitor/changes` endpoint, which has no tombstone
- [ADR 008 - Remote Settings Over Git](./adr_008_git-readers.md)
