# Broadcast Endpoint Debounce

* Status: draft
* Deciders: acottner, mleplatre, smarnach
* Date: Feb 12, 2026

## Context and Problem Statement

The goal of this document is to propose a design in which the **frequency of publication** is decoupled from the **frequency of broadcasts** to the Push service.

Currently, the broadcast endpoint relies on an **in-memory cache backend**. In a Kubernetes deployment with:

- Multiple pods  
- Multiple worker processes per pod  

each worker computes its own debounced timestamp independently.

As a result, if multiple changesets are published in rapid succession:

- Each worker may independently determine that a broadcast should be emitted.
- Multiple broadcasts may be triggered within a short time window.
- This increases CDN cache cardinality and thus load on origins

Introspecting logs, we can observe of lot of different timestamps being broadcasted within a short time window:

```sql
WITH base AS (
  SELECT REGEXP_EXTRACT(l.http_request.request_url, r'_expected=([^&]+)') AS url, COUNT(*) AS count
  FROM `moz-fx-remote-settings-prod.gke_remote_settings_prod_log_linked._AllLogs` l
  where l.timestamp > '2026-02-02T21:45:00.000Z'
  AND l.timestamp < '2026-02-02T22:10:00.000Z'
  AND l.http_request.request_url LIKE '%/buckets/monitor/collections/changes%'
  GROUP BY 1
  ORDER BY 2 DESC
  LIMIT 30
)
SELECT DISTINCT TIMESTAMP_MILLIS(SAFE_CAST(REPLACE(url, "%22", "") AS INT64))
FROM base
ORDER BY 1 DESC
```

```
1	2026-02-02 21:55:24.230000 UTC
2	2026-02-02 21:54:25.006000 UTC
3	2026-02-02 21:53:02.982000 UTC
4	2026-02-02 21:52:35.707000 UTC
5	2026-02-02 21:49:55.510000 UTC
6	2026-02-02 21:48:49.616000 UTC
7	2026-02-02 21:46:43.298000 UTC
8	2026-02-02 21:46:34.617000 UTC
9	2026-02-02 21:26:11.431000 UTC
10	2026-02-02 20:56:44.736000 UTC
11	2026-02-02 20:52:04.420000 UTC
12	2026-02-02 19:43:41.067000 UTC
```

The current design does **not provide cluster-wide debouncing guarantees**.
We want a single, globally consistent debounce window across all pods and workers, without introducing disproportionate infrastructure or operational overhead.

> Note: we cannot use our PostgreSQL database as a shared cache backend on the readers nodes, because
> they are isolated on a read-only replica without write access.


## Decision Drivers

To choose our solution, we considered the following criteria:

- **Complexity**: Low → High — Architectural and operational complexity introduced by the solution.
- **Cost of implementation**: Low → High — Engineering effort required to implement and deploy.
- **Cost of operation**: Low → High: Infrastructure and maintenance cost over time.
- **Scalability**: Low → High: Ability to handle increasing load and horizontal scaling.

## Considered Options

1. [Option 0 – Do Nothing](#option-0--do-nothing)
1. [Option 1 – Use a Redis Backend](#option-1--use-a-redis-backend)
1. [Option 2 – Shared Redis instance](#option-2--shared-redis-instance)
1. [Option 3 – Use a File on GCS](#option-3--use-a-file-on-gcs)  
1. [Option 4 – Use a Dedicated Nginx Microcache](#option-4--use-a-dedicated-nginx-microcache)  
1. [Option 5 – Use a File on Disk (Shared Volume)](#option-5--use-a-file-on-disk-shared-volume)  
1. [Option 6 – Kubernetes Leader Election](#option-6--kubernetes-leader-election)
1. [Option 7 – CDN Caching](#option-7--cdn-caching)  
1. [Option 8 – Use git-reader Broadcast Endpoint](#option-8--use-git-reader-broadcast-endpoint)
1. [Option 9 – Use a Dedicated Container for the Broadcast Endpoint](#option-9--use-a-dedicated-container-for-the-broadcast-endpoint)

## Decision Outcome

Chosen option: **Option X**. This approach offers XXX, while YYY.

## Pros and Cons of the Options

### Option 0 - Do nothing

The broadcast endpoint currently relies on an in-memory cache backend.

Because this cache is local to each worker process:

- Debounce state is not shared.
- Multiple workers can independently emit broadcasts.
- Debouncing is only per-process, not cluster-wide.

- **Complexity**: N/A
- **Cost of implementation**: N/A
- **Cost of implementation**: Low
- **Scalability**: Low. This solution does not scale well, as it can lead to multiple broadcasts in a short time, which increases CDN cache cardinality and load on the origins


### Option 1 - Use a Redis backend

Use Redis as a shared cache backend to store the last broadcast timestamp.

When a changeset is published:

1. The server reads the last timestamp from Redis.
2. It compares it against the debounce window.
3. It conditionally uses the new timestamp.

This ensures cluster-wide consistency.

- **Complexity**: Mid. Requires introducing a new dependency (Redis) to just store a single timestamp.
- **Cost of implementation**: Low. Kinto already supports Redis as a cache backend. Enabling with Terraform is straightforward (see [this PR](https://github.com/mozilla/webservices-infra/pull/9534)).
- **Cost of operation**: High (~$3–4k/year across environments)  
- **Scalability**: High. Reading from Redis is fast and readers can easily scale horizontally.

Redis is technically sound but arguably disproportionate to the problem.

> Note: in order to reduce cost, we could run a tiny Redis container. We could afford loosing the data on restarts,
> as it would only result in a temporary loss of the last broadcast timestamp.


### Option 3 - Use file on GCS

Write the current timestamp into a file stored in GCS, updated via a scheduled job (e.g., every 5 minutes).

The broadcast endpoint serves a `3XX Redirect` to the GCS file.

- **Complexity**: Mid. We can control the frequency of broadcasts by controlling how often we update the file on GCS. However, it introduces a new moving part (the cronjob), but we already have Telescope checks in place to monitor the broadcasted value.
- **Cost of implementation**: Low. We already have the code to write files on GCS. We already have scheduled jobs.
- **Cost of operation**: Low. GCS is cheap to use, and we would only write a file every 5min, which is negligible in terms of cost. It would also remove the current trafic on our origins.
- **Scalability**: High. Serving a redirect is cheap, and GCS can handle a large number of requests without any issue.

Concerns:

- Publication becomes time-driven rather than event-driven.
- Failure of the scheduled job could freeze broadcasts.
- Adds an additional moving part (cron).

Viable, but indirect and less elegant.


### Option 4 - Use a dedicated Nginx microcache

Introduce a dedicated Nginx container per deployment:

- It exclusively handles the broadcast endpoint.
- It microcaches the upstream response (e.g., 5 min TTL).
- The Python endpoint simply returns the current timestamp.

- **Complexity**: Mid. Requires introducing a new service (Nginx microcache) to handle the debouncing logic. k8s can be configured to always keep a single replica of the Nginx microcache running, and avoid interruptions during deployments.
- **Cost of implementation**: Mid. Requires changes to the Ingress configuration and setting up DNS resolution of the Nginx debouncer to one of the pods (see [Pull request](https://github.com/mozilla/webservices-infra/pull/9552).
- **Cost of operation**: Low. Nginx is lightweight and can be easily scaled, and it would only cache the response for a short duration, which is negligible in terms of cost.
- **Scalability**: High. A single Nginx can handle a large number of requests from its microcache without any issue.

Moves debouncing to the HTTP caching layer.

Pros:
- Clean separation of concerns.
- Simple origin logic.
- Strong TTL control.

Cons:
- Introduces another service.
- Requires careful deployment configuration.

Architecturally clean, but not minimal.

### Option 5 - Use a file on disk

Use a Kubernetes shared volume between pods and store the timestamp on disk.


- **Complexity**: Low. This is very simple to reason about
- *Cost of implementation**: Mid. Requires a shared volume between pods, and handling file locking to avoid race conditions, and TTL management to ensure the timestamp is updated correctly.
- **Cost of operation**: Low. Sahred volumes are not expensive
- **Scalability**: Mid. Reading from disk is slower than reading from memory, but it should be sufficient for our use case

Concerns:

- Requires distributed file locking.
- Risk of race conditions.


### Option 6 - Kubertnetes Leader Election

Since version 1.33, Kubernetes has built-in [leader election](https://kubernetes.io/docs/concepts/cluster-administration/coordinated-leader-election/) support.

We could leverage this mechanism to elect a single leader pod, and route all broadcast endpoint traffic to a single pod and rely on its microcache.

- **Complexity**: Low. This is a simple solution that does not require any additional infrastructure.
- **Cost of implementation**: Mid. Requires to dive in Kubernetes leader election configuration and implementation.
- **Cost of operation**: Low. This does not introduce any additional cost.
- **Scalability**: High. However it creates an implicit singleton, which becomes a single point of failure.

Concerns:
- While our shared cluster is on version 1.33, leader election is not enabled by default and would require the feature activation.


### Option 7 - CDN caching

Let Push servers pull from CDN endpoints instead of origins.

Control TTL using `Cache-Control` headers. 5min on the broadcast endpoint, and a longer TTL on the other changeset endpoints.

- **Complexity**: Low.
- **Cost of implementation**: Low.
- **Cost of operation**: Low.
- **Scalability**: High.

- Uses existing infrastructure.
- Requires no new services.
- Provides global consistency.
- Moves debouncing to the edge.
- Aligns with HTTP semantics.

Concerns:
- Less control over exact timing of broadcasts (depends on CDN behavior).
- Fastly has many edge servers at each POP, and clients would hit a random one of them. There aren't any guarantees that the cached state is consistent across edge servers, which could lead to inconsistent broadcasts and almost impossible to reproduce and debug.


### Option 8 - Use git-reader Broadcast Endpoint

The git-reader service reads its data from the Git repository, which is updated by the `git-export` cronjob every 5 minutes.

We could point the Push server to the git-reader endpoints (`/v2/__broadcasts__` instead of `/v1/__broadcasts__`).

- **Complexity**: Low.
- **Cost of implementation**: Zero.
- **Cost of operation**: Zero.
- **Scalability**: Mid-High. The git-reader service is designed to handle a large number of requests.

Concerns:

- The published timestamp could take up to 10 minutes to be broadcasted (5min for the cronjob, and up to 5min for the git-reader clone to be updated).
- If the git-export cronjob fails or git-reader clone is not updated, the broadcast could be delayed or frozen. Note that this would be a general issue for all git-reader data, and not specific to the broadcast endpoint.


### Option 9 - Use a Dedicated Container for the Broadcast Endpoint

Same as Option 4, but instead of using a dedicated Nginx microcache, we could use a dedicated container for the broadcast endpoint.

The dedicated container would run the Remote Settings service but with a single process to avoid in-memory cache inconsistencies.
It would be fronted by a microcache with a 5min TTL to ensure debouncing.

- **Complexity**: Mid. This solution requires introducing a new service (dedicated container) just to handle the debouncing logic.
- **Cost of implementation**: Mid. This requires to duplicate the Remote Settings service configuration to only set the process number to 1.
- **Cost of operation**: Low. The dedicated container would be lightweight.
- **Scalability**: High. The dedicated container can handle a large number of requests, and the microcache would ensure that the broadcast is debounced.
