# Attachments Binary Diffs

* Status: accepted
* Deciders: acottner, mleplatre, smarnach
* Inputs: nalexander, bvandersloot, ezuhlcke, imani, thuang
* Date: Jul 8, 2026

## Context and Problem Statement

The Privacy team needs to deliver the Easylist to our users.
The Easylist filter lists are sets of rules used to remove unwanted content from the Internet, including annoying adverts, banners and tracking.

The list is a text file of 90K lines, 2.2MB (810K gzip, 692K brotli). It contains one rule per line, for example:
```
@@||tiktok.com^$generichide
```

As [its source repository shows](https://github.com/easylist/easylist), the list receives regular updates, and grows steadily, and even rapidly since 2026 (+20%): 


![Easylist git repo size over time using `du -sk .git`)](./adr_009_image1.png "Proposed Solution Diagram")

This document explores the different approaches that could be leveraged in order to deliver this list efficiently to our millions of users.

### Assumptions

This approach specifically targets the optimization of synchronization by minimizing bandwidth overhead for delta updates. It is not intended to enhance change previews, QA workflows, or associated tooling.

## Decision Drivers

To choose our solution, we considered the following criteria:

- **Complexity**: Low → High — Architectural and operational complexity introduced by the solution.
- **Cost of implementation**: Low → High — Engineering effort required to design, implement and deploy the required new features.
- **Cost of operation**: Low → High: Infrastructure, maintenance and bandwidth cost over time. Each MB that is published turns into several hundred of TB of bandwidth on the CDN.
- **Scalability**: Low → High: Ability to handle increasing load without affecting other use-cases.
- **Data Review**: Detailed → Opaque: When a new dataset is published, what details are provided to the reviewers?

## Considered Options

1. [Option 0 – Do Nothing](#option-0--do-nothing)
1. [Option 1 – Use a Redis Backend](#option-1--use-a-redis-backend)

## Decision Outcome

We recommend adopting [Option A - Compression Dictionary Transport](), because it offers great bandwidth optimizations for attachments updates, does not introduce any significant architectural complexity, and would be inexpensive to operate and monitor. Its implementation is decoupled from application code and happens at the networking level.

### Risks and Mitigations

Since we **exclude iOS** in the first phase, where CDT would have to be implemented almost from scratch, then implementation costs drop drastically, since CDT comes out of the box on the JS client (Gecko Desktop+Android).

## Pros and Cons of the Options

### Option A - Compression Dictionary Transport

In this option, the full attachment is republished on each update, but the client optimizes the transfer using Compression Dictionary Transport (CDT), standardized as [RFC 9842](https://datatracker.ietf.org/doc/rfc9842/).

The basic idea would be:

* The user publishes the full attachment as usual.
* On first download, the server serves the file with a header that tells the client to store it as a dictionary
* On subsequent downloads of updated attachments, the client advertises the dictionary it has, and the server returns the new full file compressed against that dictionary.

This is the most viable solution because similarly to GZip or Brotli, the optimization happens at the HTTP transfer layer, and the consuming code receives a complete new file transparently.

`RFC 9842` defines the HTTP negotiation using headers and content types.
CDT compression would apply to other collections transparently, and not only for text attachments. For example, let’s look at a `tracking-protection-list` binary [attachment update](https://remote-settings.mozilla.org/v1/admin/#/buckets/main-workspace/collections/tracking-protection-lists/records/google-trackwhite-digest256/history):

```
$ wget "https://firefox-settings-attachments.cdn.mozilla.net/main-workspace/tracking-protection-lists/858e061b-c92c-4d02-9cdd-515437571e40"
$ wget "https://firefox-settings-attachments.cdn.mozilla.net/main-workspace/tracking-protection-lists/62b7f4c5-cfd0-4c92-bea4-7c437d064a7b"

$ zstd -D 858e061b-c92c-4d02-9cdd-515437571e40 62b7f4c5-cfd0-4c92-bea4-7c437d064a7b
62b7f4c5-cfd0-4c92-bea4-7c437d064a7b : 26.81%   (  1.40 MiB =>    385 KiB, 62b7f4c5-cfd0-4c92-bea4-7c437d064a7b.zst)
```

Without fancy dictionary training on multiple files, just by using the previously published attachment, we observe a **75% compression**! This compression will offer an immense cost savings given that tracking-protection-list is in our top 5 bandwidth consumers.

The publication of compressed files on our CDN could be decorrelated from the data publication workflow, and would most likely be coupled with the push notification mechanism, so that compressed files are available when client synchronization is triggered. If for any reason, the compressed files would not be available in time, the full attachment would be served. 

The job would:

1. List existing attachment objects in GCS folder `/attachments/main-workspace/easylist/`
1. Select the latest 4 previous files (using GCS metadata)
1. The latest is `{new}`, and the 3 others are `{old-N}`
1. For each previous file `{old-N}`, publish a compressed file for the target `{new}` `/cdt/main-workspace/easylist/compressed/target-{new}/from-{old-N}.dcz` (and set original content-type in metadata)
1. Publish a JSON manifest for admin/debugging purposes at `/cdt/main-workspace/easylist/compressed/target-{new}/manifest.json` (with target, sha256 and ids of supported dictionaries, etc.)
1. Delete old pairs

For the collections that would have CDT enabled, the CDN would tell the client to use the full attachment as the dictionary:

```
GET /main-workspace/easylist/d7c001fe.txt

HTTP/1.1 200 OK
Content-Type: text/plain
Cache-Control: public, max-age=31536000, immutable
Use-As-Dictionary: match="/main-workspace/easylist/*", id="d7c001fe.txt", type=raw

...full EasyList bytes...
```

Later, the client will fetch the updated attachment of the record. Since the dictionary was served with `match="/main-workspace/easylist/*"`, the client has stored it as such and will use it for any subsequent attachment download in this collection. It tells the server about it using the `Available-Dictionary` header:

```
GET /main-workspace/easylist/a83f91de.txt
Accept-Encoding: dcz, br, gzip
Available-Dictionary: :<sha256-of-d7c001fe.txt-bytes>:
Dictionary-ID: "d7c001fe.txt"
```

The CDN extracts the `(old, new)` pair from this request `(d7c001fe.txt, a83f91de.txt)`, then fetches the adequate compressed file from GCS at `/cdt/main-workspace/easylist/compressed/target-7c001fe.txt/from-a83f91de.txt.dcz` and serves it to the client:

```
HTTP/2 200 OK
Content-Type: text/plain; charset=utf-8
Content-Encoding: dcz
Vary: Accept-Encoding, Available-Dictionary
Cache-Control: public, max-age=31536000, immutable
Use-As-Dictionary: match="/main-workspace/easylist/*", id="a83f91de.txt", type=raw
```

If the server does not have the `.dcz` file matching the `(old, pair)`, because it was not published yet, or because the client base file is too old, it would just return the full attachment, as for the first download. We should be able to implement this logic in pure Fastly VCL (see below) and may not have to run a GCS proxy ourselves for this.

#### Support and Cost of Implementation

On the client side, CDT support is not supported everywhere yet:

| Gecko JS client                                                                                             | A-S Rust Client (Android)                                                                                                                               | A-S Rust Client (**iOS**)                                                                                                                               |
| (Desktop/Android) [source](https://searchfox.org/firefox-main/source/services/settings/Attachments.sys.mjs) | [source](https://github.com/mozilla/application-services/blob/ecd8f5cb4c3503b4d31b01654077ad6d744b507a/components/remote_settings/src/lib.rs#L173-L185) | [source](https://github.com/mozilla/application-services/blob/ecd8f5cb4c3503b4d31b01654077ad6d744b507a/components/remote_settings/src/lib.rs#L173-L185) |
|-------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Built-in support.**                                                                                       | Partial.                                                                                                                                                | **None.**                                                                                                                                               |
| Enabling the feature would basically consist in adding `Accept-Encoding`: dcz when fetching attachments.    | Rust client relies on reqwest+viaduct, and support is partly provided under the hood by Necko. But would still require surface API changes.             | Client relies on reqwest+viaduct, the viaduct implementation is Hyper, which doesn’t have dictionary compression support at all.                        |
| (shipped recently in Nightly, ref MDN)                                                                      |                                                                                                                                                         |                                                                                                                                                         |

For the Easylist feature, the Privacy team targets Gecko, and iOS.
On iOS, the Gecko JS client is not available, and the only Remote Settings client is the A-S Rust client.

To address the current limitations on iOS, an initial phase will proceed without CDT support on this platform. Indeed, the implementation of CDT for iOS does not have to be a blocker. With this approach, iOS clients would continue to download the complete file for each update until CDT is integrated into the iOS networking layer. Provided we accept the temporary increase in client-side data usage, the CDN bandwidth overhead just for Firefox on iOS would be manageable. Indeed, the Easylist is only 700KB compressed and iOS MAU is far from being as high as desktop, plus we could reduce the synchronization frequency specifically in the client if required. 

#### Implementation Phases

1. Deploy the compressed files publication in a simple cron job (eg. execute every 5min)
1. Enable it for a few key collections (eg. easylist)
1. Deploy Fastly VCL code to advertise CDT dictionaries and files
1. Enable `Accept-Encoding` header in JS client
1. Validate behaviour using attachments download client telemetry
1. Enable it for a few key collections (eg. tracking-protection-list)
1. Observe CDN costs for iOS. Decide whether it justifies implementing CDT support in hyper.

- **Complexity**: **Mid**. We’d have to build out some functionality on the server side. It introduces several new components: the building of compressed files, the VCL code or proxy to advertise them.
- **Cost of implementation**: **a) Low** or **b) High**. 
  a) If iOS data consumption is acceptable, then we would only have to build the compressed files job (zstd compression is now available in Python 3.14). Building a CDT proxy would be cheap in case the advertisement/handling of dictionaries cannot be done fully in VCL.
  b) High cost if the Easylist targets iOS, since we have to add CDT support to the application-services Rust client. Adding the surface API to reqwest-viaduct + iOS Hyper low-level implementation. Integrating a new transport compression algorithm in Hyper could represent a significant amount of work (integration with content negotiation, dictionary acquisition, persistence, decompression, …), and relatively advanced knowledge of the Application Services stack.
- **Cost of operation**: **a) Low** - **b)Mid**. 
  a) The production of compressed files via a cronjob would be relatively easy to maintain (eg. cronjob) and are cheap to distribute via the CDN. 
  b) It would be slightly more costly if we had to run a proxy to handle the advertisement/handling of dictionaries.
- **Data Review**: Opaque. The full attachment file gets republished.
- **Scalability**: High. CDN would handle distribution. If following the proxy approach, we could use a high performance micro-service to handle the requests and redirects.

→ Simple and cheap to implement if we accept to put iOS (Rust hyper) aside for now.

#### VCL Sketch

Extract info from request and store it on request:

```
sub vcl_recv {
  if (
    req.http.Dictionary-ID &&
    req.http.Available-Dictionary &&
    req.http.Accept-Encoding ~ "(^|,)\s*dcz\s*(,|$)"
  ) {
    set req.http.X-CDT-Enable = "1";
    set req.http.X-CDT-Dict-ID = req.http.Dictionary-ID;

    # /bid/cid/a83f91de.txt
    # ->
    # bid, cid, a83f91de.txt
    set bereq.http.X-RS-BID = regsub(
      bereq.url,
      "^/([^/]+)/[^/]+/[^/]+$",
      "\1"
    );
    set bereq.http.X-RS-CID = regsub(
      bereq.url,
      "^/[^/]+/([^/]+)/[^/]+$",
      "\1"
    );
    set bereq.http.X-CDT-Target-ID = regsub(
      bereq.url,
      "^/[^/]+/[^/]+/([^/]+)$",
      "\1"
    );
  }
}
```

Fetch from GCS (rewriting if necessary):

```
sub vcl_backend_fetch {
  if (bereq.http.X-CDT-Enable == "1") {
    if (req.http.Dictionary-ID) {
      # /bid/cid/a83f91de.txt
      # -> /bid/cid/cdt/compressed/target-a83f91de.easylist/dcz/from-d7c001fe.easylist.dcz
      set bereq.http.X-Orig-URL = bereq.url;
      set bereq.url = regsub(
        bereq.url,
        "^/([^/]+)/([^/]+)/([^/]+)$",
        "/cdt/\1/\2/compressed/target-\3/dcz/from-" + bereq.http.X-CDT-Dict-ID + ".dcz"
      );
      set bereq.http.X-CDT-Rewritten = "1";
    }
  }
}

```

If successful, set `Use-As-Dictionary` and serve. Otherwise retry with full attachment.

```
sub vcl_backend_response {
  if (bereq.http.X-CDT-Rewritten == "1") {
    if (beresp.status == 404 && bereq.retries == 0) {
      set bereq.url = bereq.http.X-Orig-URL;
      unset bereq.http.X-CDT-Rewritten;
      return(retry);
    }

    if (beresp.status == 200) {
      set beresp.http.Content-Encoding = "dcz";
      set beresp.http.Vary = "Accept-Encoding, Available-Dictionary";
      set beresp.http.Cache-Control = "public, max-age=31536000, immutable";
      set beresp.http.Use-As-Dictionary =
        "match=\"/" + bereq.http.X-RS-BID + "/" + bereq.http.X-RS-CID + "/*\", id=\"" + bereq.http.X-CDT-Target-ID + "\", type=raw";
    }
  }
}
```

### Option B -  Individual Records

The list is turned into individual records, without file attachments.

`@@||tiktok.com^$generichide`

becomes

```json
{
  “id”: “8A0C5B10-4B07-40E0-8F66-DE34D75FC4B2”
  “last_modified”: 1776245289147, 
  “rule”: “@@||tiktok.com^$generichide”
}
```

When serialized by the server the resulting JSON dataset is 9MB (3.5MB gzipped).

As of April 2026, the `/changeset` endpoint of Remote Settings does not support pagination. Although iterating the database pages on the server side in order to assemble a single changeset response is trivial, adding server and client pagination support so that client can fetch the dataset using several pages will require some engineering efforts. And on the client side, loading so many IndexedDB rows and serializing them for signature verification could have a significant impact on performance.

- **Complexity**: Low. Built-in.
- **Cost of implementation**: Low. without client side pagination.
- **Cost of operation**: **Low**, if the base dataset is shipped in the Firefox binary (requires RelEng to validate a 3.5MB size increase!) **High**, if clients sync the whole collection from scratch.
- **Data review**: Detailed. Changes appear as individual changes.
- **Scalability**: High. Load is handled by the CDN.

→ High stress on the service and client performance.


### Option C - Base Attachment + Operations Log Records

A full file is published regularly (eg. bi-weekly), and incremental updates are published daily.

Records contain a `type` field (`base` or `delta`). The base record has a regular attachment, and the delta records contain add/delete operations.

The clients without local data would:
- Pull all the records
- Identify the newest record with `type=base`
- Download the attachment, store its content 
- Iterate through the `type=delta` records published after the base and apply their changes

And clients with local data would just:
- Pull records that changes since last sync (built-in)
- Iterate the records with `type=delta` and apply their changes.

The daily  incremental changes could be grouped in one record with a simple list of operations:

```
{
  "id": "6DBB2528-D074-46EE-820F-3DC34699FC5E",
  “last_modified”: 1776245289147,
  "type": "delta",
  "operations": [
    {"op":"add","rule":"||newad.example^"}
    {"op":"del","rule":"||deadtracker.example^"}
    {"op":"add","rule":"example.com##.sponsored"}
  ]
}
```

Once a week, the publication workflow would:
- Download the new version of the list from easylist.to 
- Recreate a new record with `type: base` and the new full text attachment
- Delete the previous `type: base` record 

Every day, it would:
- List existing records, and download the attachment of the newest record with `type: base` (assuming the publication job is stateless, it uses Remote Settings to compute diffs)
- Apply the latest records with `type: delta` on this temporary file
- Download the new version of the list from easylist.to 
- Create a new record with `type: delta` with the detected changes

Some extra integrity checks can be added on delta records (eg. using a field that contains the resulting dataset SHA256: `"result_sha256":"...”`).

- **Complexity**: **Mid**. This pattern introduces some complexity on the server and client side. However, we could imagine designing a solution that would be generic and reused by other use-cases.
- **Cost of implementation**: **High**. The implementation of the basic is relatively straightforward, but would have to be implemented in both the Rust and desktop clients.
- **Cost of operation**: Low. Clients download the base attachment once (<1MB) and a few KB everyday.
- **Data Review**: Detailed. Changes appear as a list of operations in the JSON record. Humans can even edit them.
- **Scalability**: High. Load is lower than most use-cases with attachments.

→ This looks a lot like what is implemented for the built-in records synchronization (pull base + diff sync + integrity check). Before considering this option, analyzing the impact and engineering cost of *Option A - Individual Records* seems very recommended.


### Option D - Snapshot and Diff Attachments

With this approach, we rely on diff attachments instead of a list of operations in records.

The `base` record contains the original attachment:

```
{
   id: "6DBB2528-D074-46EE-820F-3DC34699FC5E",
   last_modified: 1776245289147,
   type: "base",
   
   attachment: {
     location: "bid/cid/easylist.txt",
     sha256: "efg...",
     ...
   }
}
```

And the `delta` records contain the diff to be applied, stored as attachment too.
They contain metadata about the diff format and expected result. 
The deltas are applied in the order of `last_modified` ascending. 

```
{
     id: "415577EC-CD0C-4AEB-A685-66E9237AE363",
     last_modified: 1776407787891,
     type: "delta",
     format: "udiff-patch",
     result_sha256: "e3b0c44.....f4c89",
     attachment: {
       location: "bid/cid/efgh.diff",
       sha256: "abc...",
       ...
     }
  }
```

This would be similar in spirit to what is currently done with CRLite and addons bloomfilters, except the incremental changes are served in a standard format instead of a bloom filter specific format.

The client logics would be:

1. On synchronization, receive the list of records since last sync
1. If local file does not exist
   a) Use list of current  records (from .on(“sync”, { data: { current }})) 
   b) Fetch the attachment of record type: base
   c) Apply each type: delta record on top of it
1. If local file exists
   a) Compute local sha256
   b) Iterate list of current records to find record with matching result_sha256
   c) Apply each type: delta record on top of it
1. If the newest record is of type: delta, compute sha256 of local file and compare it.
   a) If it fails, delete the local file and retry from scratch.

**Standard Diff Formats**

* Unified Diff Patch (`diff -u`)
* VCDIFF is a standardized generic delta format defined in [RFC 3284](https://www.rfc-editor.org/rfc/rfc3284). It encodes the new version relative to a source version using delta instructions such as ADD, COPY, and RUN.

The important difference from the operation log model of *Option C* is that the delta attachments are opaque, and not self-describing since they are patches that transform a byte sequence.

In this model, integrity metadata is more important, because deltas must be applied on just bytes. For example, we may have to ensure local file hash before applying, and after applying.

This option is interesting because we could start with text diffs, and expand it to binary diffs later. 

The implementation of this option would have 3 dimensions:

* A set of tools to automate publication (Eg. refresh the base and create delta records from arbitrary files)   
* A set of helpers in the Remote Settings client (Rust + Desktop) to reconstruct the final binary from base and delta records on synchronization
* The Easylist team that would leverage these new tools for their use-case

- **Complexity**: **Mid**. This pattern introduces some complexity on the server and client side. However, we could imagine designing a solution that would be generic and reused by other use-cases.
- **Cost of implementation**: **High**. The implementation of the basic text diff should be relatively straightforward, but would have to be implemented in both the Rust and desktop clients.
- **Cost of operation**: Low. Clients download the base attachment once and a few KB everyday.
- **Data Review**: Opaque. Diffs as attachments cannot be reviewed without extra tooling or new Admin UI features. Humans cannot edit the records manually and must use the publication tools to produce the records.
- **Scalability**: High. Load is lower than most use-cases with regularly updated attachments.

→ Adhoc design that requires code changes on both JS and Rust clients.


### Option E. Live Computed Diffs

With this option, a new server piece is introduced: an endpoint that serves attachment diffs.

The client knows the attachment that it currently has, and the attachment that it is being asked to pull. 
It sends a request to the server providing (`from`, `to`, `format`), and the response contains the diff.
The sha256 of the result is already provided in the `attachment` field of the new record.

Every time an attachment is published, it is stored at a new immutable filename. The request could simply look like `/diff?from={old-location}&to={new-location}&format=udiff-patch` (API-like) or `/diffs/{bid}/{cid}/{rid}/{old-file}/{new-file}.{format}` (File based).

> **Note:** The diff would not be available for two different records. In other words, if a record is deleted and recreated with a different id (`rid`), the diff would not be available between the two versions. 

Potential error states:

1. 404 - download the latest full file
   a) If one of the parameters is unknown, or if the file was purged.
   b) If the computed diff is larger than the new file, there is no point in using the diff. Return 404 so the new file is pulled.
   c) If there is a wild change in the files (ex: old file was a jpeg and new file is a png) then there is no point in processing the diff.

We could thus enable this on a per-collection, or even per-record, basis. This would limit the scope of what possible diffs we would be calculating. There is a finite set of combinations, but we could also control how many days/versions in the past we would want to expose. 

The advantage of this compared to *Option D* is that the collection is not bloated with delta records, and **the collection content remains fully backward compatible** and identical for old clients that don’t support diff or use-cases that don’t have the diff feature enabled.

The implementation of this option would have 3 dimensions:
* A new GCS bucket that serves the diffs or new diff microservice
* A set of helpers in the Remote Settings client (Rust + Desktop) to pull the diffs and reconstruct the final file
* The Easylist team that would leverage these new tools for their use-case

**Variants:**

1. Diffs could be calculated just-in-time or pre-calculated as records are updated on the server.
   a) If pre-calculated, the diff files for all the new (from, to, format) combinations could be computed and published on a GCS bucket when the collection changes are approved. Or alternatively, using a pub/sub worker or a cronjob.
   b) If calculated just-in-time, a micro service would receive the request and output the diff. Note that scaling and performance would matter even if responses are cached by the CDN. A stateless Rust service on top of GCS could be fun to write. 
1. Diffs could have different formats, as requested by the client. Clients hold the diff application code and can pick different diffs formats based on their evolving capabilities. Like in Option D, we could start with text diffs and evolve into binary diffs later.

Potential attacks and how to avoid them in the JIT version:

1. DoS - an attacker could try to make several arbitrary diff requests, costing us compute time.
   a) Our CDN would prevent us from making the same effort multiple times. We can even have fastly cache error responses for hours or days.
   b) Validating the inbound request and restricting what diffs we will calculate would limit cardinality. For example, we could choose to only support calculating attachment diffs for the same record.
   c) Feature toggling this per collection or record would mean an attacker would be severely limited to what diffs they could pull.
2. Cache poisoning - an attacker could cause us to return an error response for a soon-to-be valid diff. If they are watching our preview collections this is trivial to pull off, but would have severely limited impact as clients would then just pull the valid full file.
Probably not worth worrying about?

- **Complexity**: Mid. We’d have to build out some functionality both client and server side. But nothing seems particularly challenging here.
- **Cost of implementation**: High. Would require changes in both the rust client and desktop client. Unlike Option D there is no need for publication tools. But we have to implement the JIT diff service or the pre-calculated routine during publication.
- **Cost of operation**: Mid. Easy to maintain and very low cost to distribute the diffs. But higher than low since we have to run a new service and/or monitor the diffs availability.
- **Data Review**: Opaque. The full attachment file gets republished.
- **Scalability**: High. CDN would handle distribution. If doing JIT diffs, we could use a high performance micro-service to handle the requests on the origin.

→ Simple API design, but requires server and client code changes on both JS and Rust clients.


### Option F. Other options considered

#### Built-In Attachment

The list is shipped as a single record with the full file as an attachment.
The attachment file will be compressed by the CDN (810K gzip, 692K brotli).
Each time the list is updated, the whole attachment is republished and redownloaded entirely by clients.

- **Complexity**: Low. Built-in.
- **Cost of implementation**: Low. Built-in.
- **Cost of operation**: High. Depending on update frequency and MAU. See Looker dashboard for estimates.
- **Data Review**: Opaque. Without additional tooling, no diff is given for attachments.
- **Scalability**: High. Load is handled by the CDN.

→ Very inefficient and expensive to run.


#### Bittorrent Attachment

Same as *Option A*, where the full attachment is republished everyday, except that we rely on an efficient distribution protocol instead of relying on a CDN. This is the approach that many Linux distributions took to distribute their ISO files.

Basic pieces for this option:

1. Classic attachment file on the CDN becomes a Web seed (BEP19, relying on Range requests) Trackerless torrent (DHT+PEX)
2. Magnet link exposed in records along classic RS attachment pointer

Bittorrent could be disabled (eg. Enterprise) since the CDN would always serve as fallback. Imagine a household that has a few devices with Firefox on them, we could easily divide our consumed bandwidth by 2 or more if the devices share the data between them. 

Client strategy:
- try BitTorrent (cheap, distributed)
- fallback to CDN (fast, reliable)

We could generalize this solution to all collections with huge binary attachments (translation models, AI weights, AI runtimes, CRLite bloomfilters, etc), and reduce distribution costs drastically. See [current CDN costs for RS](https://lookerstudio.google.com/reporting/6c012341-6083-4138-b61e-3757579b64a9/page/hbdNF). Plus, it makes distribution of RS data resilient to blocking parties. The Bittorrent idea was mentioned during conversations with the security team on the [FEISTY project](https://docs.google.com/document/d/17wsq9thEuZIB9tp0P_eVwKhihT_h_gySKQfAyVIkRDE/edit?tab=t.0#heading=h.y30vhfoa4dfk).

- **Complexity**: High. More moving pieces than traditional distribution, security concerns, etc.
- **Cost of implementation**: High. 
- **Cost of operation**: Low. Creating torrents is free, and distribution becomes very cheap since only the first clients would pull from the CDN. Hundreds of millions of Firefox become seeders after a few minutes.
- **Data Review**: Opaque. Full file republished everyday.
- **Scalability**: High. Only the magnet link is distributed.

→ Fun. This could be an interesting internship topic :) 

Rust libraries exist:
- [cratetorrent](https://github.com/vimpunk/cratetorrent): best library shape, least complete (no DHT, no magnet links yet).
- [rqbit](https://github.com/ikatson/rqbit): most mature, but heavier and client-oriented.
