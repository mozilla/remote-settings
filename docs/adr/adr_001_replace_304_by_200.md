# Server: Do not serve `304 Not Modified` responses to old clients

* Status: accepted
* Deciders: smarnach, mleplatre, gbeckley
* Date: Oct 21, 2022

## Context and Problem Statement

Google Cloud CDN does not cache `304 Not Modified` responses ([source](https://cloud.google.com/cdn/docs/caching#cacheability)), and a large amount of requests reach our origin servers.

The majority of cache misses for the main CDN is 304s from the monitor/changes `/records` endpoint.

Our goal is to increase the CDN cache hit rate.

## Decision Drivers

In order to choose our solution we considered the following criteria:

- **Complexity**: Low → High: how complex is the solution
- **Cost of implementation**: Low → High: how much efforts does it represent
- **Cost of operation**: Low → High: how much does the solution cost to run

## Considered Options

1. [Option 0 - Do nothing](#option-0---do-nothing)
1. [Option 1 - Ignore cache control headers and serve 200 responses](#option-1---ignore-cache-control-headers-and-serve-200-responses)

## Decision Outcome

Chosen option: Option 1 because the implementation is cheap, the introduced complexity is reasonable, and it will increase the cache hit rate significantly.

Indeed, after deploying [#308](https://github.com/mozilla/remote-settings/pull/308), we hit the cache for 99% of requests (instead of 97.3% before).

## Pros and Cons of the Options

### Option 0 - Do nothing

No change is made to the application, the cache hit rate remains low, our origin servers handle the load.

- **Complexity**: N/A
- **Cost of implementation**: N/A
- **Cost of operation**: High. Some of the 304 responses are the result of requests that hit the database. During spikes, our database server could potentially be overloaded and our service become unavailable, serving 5XX responses.


### Option 1 - Ignore cache control headers and serve 200 responses

Old clients, prior to Firefox 88  (1.5 y/o at this point), fetch the monitor/changes from `/buckets/monitor/collections/changes/records` providing an `If-None-Match` header with the last synchronization timestamp.
If no change was made since then, the server returns a `304 Not Modified` is returned with an empty body.
Otherwise, the list of changes is returned, potentially filtered based on the `?_since=` query parameter.

Clients since Firefox 88, fetch monitor/changes from the `/changeset` endpoint, which always serve `200 OK` responses, even for when the list of changes is empty.

The idea of this solution consists in aligning the `/records` endpoint with the `/changeset` endpoint, by always returning `200 OK` from there too.
Old clients will poll for changes, the server will ignore the `If-None-Match` request header, and return an empty list of changes when the client is up-to-date.

- **Complexity**: Low-Mid. An additional method will be overridden in the monitor/changes resource that inherits Kinto core. And the monitor/changes `/records` endpoint will behave differently than other `/records` endpoints.
- **Cost of implementation**: Low. See [#308](https://github.com/mozilla/remote-settings/pull/308)
- **Cost of operation**: Low. CDN will now cache all requests and preserve origin servers.

### Option 2 - Drop `If-None-Match` header using Nginx rules

With this option, Nginx would drop the header before reaching out the Python application.

- **Complexity**: Mid: the server API behaviour is spread across two repositories (application and deployment)
- **Cost of implementation**: Low: It's a one-liner (`proxy_set_header ...;`)
- **Cost of operation**: Low. CDN will now cache all requests and preserve origin servers.
