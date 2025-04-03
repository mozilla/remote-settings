# Handle Growing Objects Table

* Status: draft
* Deciders: mleplatre, acottner
* Date: Apr 3, 2025

## Context and Problem Statement

The Remote Settings storage implementation for PostgreSQL relies on a single table:

```
rs=# \d objects
                              Table "public.objects"
    Column     |            Type             | Collation | Nullable |   Default
---------------+-----------------------------+-----------+----------+-------------
 id            | text                        | C         | not null |
 parent_id     | text                        | C         | not null |
 resource_name | text                        | C         | not null |
 last_modified | timestamp without time zone |           | not null |
 data          | jsonb                       |           | not null | '{}'::jsonb
 deleted       | boolean                     |           | not null | false

```

* Buckets have `resource_name="bucket"` and `parent_id=""`
* Collections have `resource_name="collection"` and `parent_id="/buckets/{bid}"`
* Groups have `resource_name="group"` and `parent_id="/buckets/{bid}"`
* Records have `resource_name="record"` and `parent_id="/buckets/{bid}/collections/{cid}"`
* Deleted objects are kept in the table as tombstones with empty data and `deleted=true`
* The `kinto.plugins.history` creates an object with `resource_name="history"` for every write operation on the API

Over the years, this `objects` table grew significantly in production, reaching 840K+ rows in early 2025.

### Proportions

Because some use-cases generate a lot of changes, a huge proportion of it were history entries:

// TODO: do we have numbers before cleanup?

```
rs=# SELECT resource_name, COUNT(*) AS total FROM objects GROUP BY resource_name ORDER BY total DESC;
 resource_name | total
---------------+--------
 history       | 321089
 record        | 151911
               |   3767
 collection    |    346
 group         |    236
 bucket        |     26
(6 rows)
```

In [mozilla/remote-settings#836](https://github.com/mozilla/remote-settings/issues/836) we introduced new routines that will
keep the history size under control.

However, still a good proportion of objects (80+% for records) are tombstones that we can't delete from the database since clients rely on them for synchronization.

```
rs=# SELECT resource_name, deleted, COUNT(*) AS count, ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY resource_name), 2) AS percentage FROM objects GROUP BY resource_name, deleted;

 resource_name | deleted | count  | percentage
---------------+---------+--------+------------
 ...
 record        | t       | 124846 |      82.18
```

### Architecture

With the current architecture, our public read-only instances at the origin of our CDN point to the same database as our writer instances behind the VPN.

In comparison with write operations (a few per day), the database receive a tremendous amount of read queries (thousands per seconds).

Readers do not read objects like `history` or attachments links, and mostly read records and their tombstones.

The readers queries could be greatly optimized if they would handle a database limited to their dataset.

In this document, we explore possible solutions to overcome this limitation.

## Decision Drivers

In order to choose our solution we considered the following criteria:

- **Complexity**: Low → High: how complex is the solution
- **Cost of implementation**: Low → High: how much efforts does it represent
- **Cost of operation**: Low → High: how much does the solution cost to run
- **Future-resilience**: Low → High: how well it will handle future growth

## Considered Options

1. [Option 0 - Do nothing](#option-0---do-nothing)
1. [Option 1 - Partition the objects table by `resource_name`](#option-1---xxx)
1. [Option 2 - Logical replicas for readers](#option-2---xxx)

## Decision Outcome

Chosen option: X

## Pros and Cons of the Options

### Option 0 - Do nothing

No change is made.

After trimming the history, and fixing [mozilla/remote-settings#830](https://github.com/mozilla/remote-settings/pull/830), our database CPU is now under 10%, even during spikes.

- **Complexity**: N/A
- **Cost of implementation**: N/A
- **Cost of operation**: Low (average over the years)
- **Future-resilience**: Medium. The records and their tombstones will continue to grow, and will require our attention at some point in the future.


### Option 1 - Partition the objects table by `resource_name`

The single `objects` table could be partitioned into several segments (see implementation in [kinto/kinto#3516](https://github.com/Kinto/kinto/pull/3516)).

In this case, the “parent“ `objects` table acts more like a “routing layer” for the partitions. It doesn't store any data itself.

Since most (all?) queries in Kinto include a `resource_name` filter, using partitions would immediately bring:

- better query performance (smaller sub-tables, parallel execution, ...)
- better write performance
- faster indexing

The main downside is that objects triggers and indexes would have to be re-created on each partition table, making future database migrations more complex.

Also, with the current code architecture, `kinto.core` is not “aware“ of possible values for `resource_name`. Creating partitions for `history`, `bucket`, etc. would either break this separation of concern, and would have to be done elsewhere, like in the `kinto-remote-settings` plugin (for which we currently don't have notions of database migrations).

Note that since our storage implementation lives in *Kinto*, we would impose this partitioning to all users, even for small use-cases.

- **Complexity**: Medium-High. The database schema and migrations would become more complex
- **Cost of implementation**: Medium-Low. Creating partitions is cheap, but maintaining the layer of abstraction of `kinto.core` could require us to introduce database migrations in plugins ([Kinto/kinto#2391](https://github.com/Kinto/kinto/issues/2391)).
- **Cost of operation**: Low. PostgreSQL handles everything for us.
- **Future-resilience**: Medium (Same as status quo since tombstones are not partitioned).


### Option 2 - Logical replicas for readers

With this solution, we deploy a new database to be used by readers.

PostgreSQL would copy data between the source database and this new one using a publisher/subscriber model, replicating data changes (INSERT/UPDATE/DELETE) at the table level, and we could select only the objects used by readers (buckets, collections, and records).

Objects used by the writer, like accounts, history, attachments links, etc. would not be replicated.

We would have some flexibility to control the final dataset (eg. do not include tombstones that are more than 2 years old).

Since performance on the writer is not critical, we could adjust the database resources according to their respective load.
Any CPU spike on the reader database would not affect user experience.

- **Complexity**: Low. This setup a classic read/write split architecture
- **Cost of implementation**: Medium-Low. We have done similar work for the CTMS project already
- **Cost of operation**: Medium-Low. We would have one more database to monitor. And although they don't have often, we would have to run schema migrations manually on the reader replica (??)
- **Future-resilience**: Medium-High. We control the amount of data that are exposed to readers using queries.
