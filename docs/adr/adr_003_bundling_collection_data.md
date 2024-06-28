# Bundling Collection Data for Download


* Status: proposed
* Deciders: mleplatre, gbeckley, acottner
* Date: June 27 2024

Tracking issue(s):
-  [The initial remote settings download is inefficient](https://bugzilla.mozilla.org/show_bug.cgi?id=1889617)


## Context and Problem Statement
When a new Firefox client comes online for the first time, it makes over 1,700 HTTP requests to download the initial remote settings data. These are mostly attachments from large collections (ex: `security-state/intermediate, blocklists/certificates`). Opening this many HTTP connections to download small files is not as efficient compared to downloading a few larger files.
1. It’s a poor user experience if the UI locks up while trying to maintain this many connections
2. It causes excess power usage and [battery drain](https://bugzilla.mozilla.org/show_bug.cgi?id=1889617) on laptop and mobile devices by keeping modems/wifi devices running for longer than they need to 

If we can bundle these downloads together by collection, we could reduce the number of requests for certain collections from almost thousands to a few. This should reduce the overall time required to download the data (less time establishing connections), which will reduce power usage and improve the user experience.


### Data Bundling
We distinguish two parts for this data bundling:

 - A bundle for all records data for new profiles to fetch all collections data in one request instead of 50 (~6MB uncompressed); 
 - A bundle of all attachments data per collection (opt-in)

Looking at existing use-cases, we can observe that bundling attachments may not be equally relevant depending on the number of records and their attachment size:
 - `security-state/intermediates` collection: 1720 records for 3MB in total. Lots of tiny .pem files required as soon as possible after first startup for security features: __bundling very beneficial__
 - `fakespot-suggest-products` collection: 300 records with a few MB per attachment (eg. 5MB). Since the total size is huge: bundling brings __little advantage__
 - Machine learning collections: few records with big attachments (eg. 20MB): almost no advantage. 
 - `Translations-models` collection: 150 records for 1.2GB in total. Clients only download a few pairs when the user enables the feature for certain languages: __bundling is not feasible__

That’s why it would make sense for attachments bundling to be opt-in for stakeholders.

There is already a collection metadata attribute to mark attachments as enabled and/or required. The flag would just consist in adding a new field attachment.bundle: true|false.

Also, since [usage quotas](https://docs.kinto-storage.org/en/stable/api/1.x/quotas.html) are not enabled on the Remote Settings server, consumers can end up publishing huge files and bloat attachments bundles, we may want to have a server side configuration setting to fix a size limit for which the bundles won’t be built. For example, even when opted-in, if the target bundle exceeds 20MB, it won’t be built and published. Clients should thus be smart and fail soft if a bundle is not available.


### Bundle Formats
After some research and testing, we've decided to go with Zip compression. Zip is very easy to implement and allows for good flexibility moving forward. We could change our minds or add other bundle types in the future with very little effort.

- Zip - Reduces text content up to 17%.
    - Pros: Easy to work with. Easy to decompress client side.
    - Cons: Not as much compression as lzma. Need to decompress after receiving.
- Tar - When gzipped (automatically by cdn dynamic compression), we can expect to save around 43% size for text content. Probably not much for images.
    - Pros: very easy to work with server side and client side. Compression and decompression should be free at the transport layer.
    - Cons: doesn’t save as much as lzma.
- LZMA (7z) - Reduces text content up to 70%.
    - Pros: Very compressed
    - Cons: More compute intense to compress and decompress. Likely need to ship another library to decompress. Need to decompress after receiving.


### Client Implementation
This ADR mostly covers the server parts, since the client implementation to fetch and leverage bundling does not have many different possible approaches.

For the collections records bundle, clients with empty profiles will simply pull it on first synchronization:
- Pull the latest records bundle
- Extract it and store data into local IndexedDB
- Fetch latest timestamps from the server (like currently using `Utils.fetchLatestChanges()`)
- Synchronize potential outdated collections, and verify signatures of the ones that are up-to-date, to guarantee integrity/authenticity of the downloaded bundle

For the attachments, bundling would be opt-in, and leveraged explicitly by consumers in their code. Clients would have a new method `client.attachments.cacheAll()` that would:
- Pull the attachment bundle for the current collection timestamp
- Be resilient to missing bundles (eg. not yet available or exceeding configured server size limits)
- Extract it on disk (TODO: find example of zip extraction in Gecko)
- Put files contents in attachments cache ([source](https://searchfox.org/mozilla-central/rev/8ec3cc0472ad4f51b254728d024b696eaba82ba0/services/settings/Attachments.sys.mjs#259-261))
- Delete temporary content

After that, any call to `client.attachments.download()` would return the locally cached content as it does currently if the attachment has been downloaded previously. It also checks its hash using sha256 ([source](https://searchfox.org/mozilla-central/rev/b11735b86bb4d416c918e2b2413456561beff50c/services/settings/Attachments.sys.mjs#449-470)), which saves us from having to add content signature on the attachment bundle.

In future calls of `download()` on records whose attachment has been modified on the server, the client would fetch them individually as it does with the current code. In other words, in this ADR, we don’t address building “delta” or “diff” bundles for clients that already have local data.

Consumers would choose to explicitly use this new method in their code, based on their use-case. And we (SysEng) could easily modify existing code to rewrite the code of some use-cases that rely on massive parallel fetch (eg. replace with a call to `cacheAll()`).

Requirements
- Total amount of time to download, extract, and process, must not take longer than fetching attachments individually
- Handling the bundle in the client should not bloat the main thread or impact user experience in general
- Feature must not get in the way of legacy clients
- Implementation should be resilient to race conditions on attachment downloads. Unpacking the bundle can overwrite attachments that had been previously downloaded individually, and individual downloads can overwrite unbundled ones
- Bundle format should be easily readable by client (third-party libraries are hard to ship in Gecko)

References
- [The intermediates download code](https://searchfox.org/mozilla-central/rev/8ec3cc0472ad4f51b254728d024b696eaba82ba0/security/manager/ssl/RemoteSecuritySettings.sys.mjs#335-365) that fetches attachments in bulk, and stores state in records
- [Download of crlite files](https://searchfox.org/mozilla-central/rev/8ec3cc0472ad4f51b254728d024b696eaba82ba0/security/manager/ssl/RemoteSecuritySettings.sys.mjs#620-637)
- [Download of all regions files](https://searchfox.org/mozilla-central/rev/8ec3cc0472ad4f51b254728d024b696eaba82ba0/security/manager/ssl/RemoteSecuritySettings.sys.mjs#335-365)
- [Download of all addons suggestions files](https://searchfox.org/mozilla-central/rev/8ec3cc0472ad4f51b254728d024b696eaba82ba0/browser/components/urlbar/private/AddonSuggestions.sys.mjs#87-101)

### Metrics To Measure Before/After
CPU usage, bandwidth, usage for full synchronization. Power and performance profiles on different clients.
    - Mac Desktop
    - Linux Desktop
    - Windows Desktop
    - Android Mobile
- iOS Mobile (does it use remote-settings?)
- How much collections are compressed
- Total duration of synchronization on fresh profiles


## Non Goals
- Support diffs or delta bundles for clients that already have local data
- Reduce client performance (ex: we shouldn't increase power usage for clients)

## Assumptions
- We will find a way for Gecko clients to extract at least one archive format (very likely using third-party library)

## Decision Drivers
- Keep costs low
    - With millions of clients, the cost of shipping data is always a concern
- Server complexity & performance
    -Monitoring and operating should remain straightforward (ex: limit tech and deployment complexity if possible)
    -Performance of the service should not be affected
    - The code in place to support this feature should not involve complex components, libraries, or architecture (eg. to support resumable downloads and range requests)
- Long-term Maintenance
- Clients complexity
    - How complicated it is to know which bundle URL to pull

## Considered Options
1. Build bundles on attachment upload/removal
2. Build bundles on Cloud storage event
3. Build bundles on RS changes approval
4. Add new API endpoint to build or serve last bundle
5. Build bundles on schedule

## Decision Outcome
Chosen option: [Option 5](#Option-5) because it is easy to reason about, trivial to implement, does not affect user experience, and would not increase the overall service complexity. 

### Positive Consequences
- We provide records and attachments bundling without increasing our team maintenance

### Negative Consequences
- There is a window of time where clients could synchronize their local data before the bundle is available. But we can reduce this downside by coupling the push notification job with the bundling job. 

## Pros and Cons of the Options
### Option 1 - Build bundles on attachment upload/removal
Everytime an attachment is uploaded or removed, the attachment is added or removed to the bundle, within the request/response cycle.

This would be implemented in `kinto-attachment` code, in charge of uploading the attachments to the storage backend.

In Remote Settings, attachments are not duplicated on request review/approval. In other words, they “remain” in the `main-workspace` bucket, and when records are approved and published in `main`, their attachment location does not change.

This means that, with this option, we would have to serve multiple bundles and make sure clients download the one that matches the version/timestamp of the main collection.

With this solution, uploading or deleting an attachment would become slower since the bundle would be updated synchronously during the request/response cycle.
- Good, because the code would be extremely simple and confined to kinto-attachment source code
- Good, because no additional component to monitor or deploy
- Good, because bundles are only created/updated when attachments are updated/removed
- Not so good, because uploading/removing attachments would take longer
- Not so good, because in order to add or remove files from the bundle we may have to fetch from the storage backend first
- Not so good, because we would have to maintain several bundles in parallel, and find a smart way to purge old ones

### Option 2 - Build bundles on Cloud storage event
Fundamentally, this is the equivalent of Option 1, except that updating the bundle archive is decoupled from the request/response cycle.

A serverless function listens to [storage change events](https://cloud.google.com/functions/docs/calling/storage). As soon as file writes finish, the function will fire and build a new bundle. 

Note that the bundle is very likely to always be ready for clients, because there will always be at least a few minutes (if not hours) between the last attachment upload and the review request approval to publish the records.
- Good, because uploading/removing attachments would not take longer
- Good, because bundles are only created/updated when attachments are updated/removed
- Not so good, because like Option 1 we would have to maintain several bundles in parallel, and find a smart way to purge old ones
- Bad, because a new serverless function is introduced that has to be monitored, troubleshot, and deployed
- Bad, because this would be a remote-settings specific job and feature, and not part of `kinto-attachment`

### Option 3 - Build bundles on RS changes approval
This option would be similar to Option 1, except that the bundles are built when a user approves the changes.

This would be implemented in `kinto-remote-settings` repo, the code in charge of managing review requests and approvals.

The bundles would be built within the request/response cycle when the changes are approved.
- Bad, because approving changes would take longer
- Good, because unlike with Option 1 and 2, we don’t have to publish several bundles in parallel, only the latest
- Good, because it would be implemented in the kinto-remote-settings repo and almost free to monitor (errors would raise 5XX)
- Bad, because this would be a remote-settings specific job and feature, and not part of `kinto-attachment`

### Option 4 - Add new API endpoint to build or serve last bundle
With this option, we introduce a new endpoint that builds the bundle if it does not exist, or serves the one in cache if it does.

If we would like to prevent multiple pods from building the same bundle, we could have a singleton “bundle-builder” container that would be dedicated to building all attachment bundles. The API would receive a request, see that the bundle is missing, and ping the bundle-builder to make it. Once the bundle-builder is done and the file is published, it would respond to all waiting API nodes so they can redirect.

More alternatively, we could use event-driven architecture. The API would submit a request for the bundle to be built to a queue. A serverless function would process the request and return the response. In order to prevent multiple to build the same bundle multiple times, parallelism would have to be restricted, or we’d need to use a queue that supports partitioning based on collection name (or similar).
- Good, because it all happens in one endpoint and easy to reason about
- Good, because uploading/removing attachments or approving changes would not take longer
- Bad, because a new specific container that has to be monitored, troubleshot, and deployed
- Bad, because we have to introduce some complexity in order to prevent building several bundles in parallel

### Option 5 - Build bundles on schedule
A scheduled job iterates through the collections with the `attachment.bundle == true` flag and operates with the following logics:
- If there is a bundle for the current collection timestamp, nothing to do.
- If there isn’t, pull all attachments from storage, build a bundle with all current attachments, store it at `{folder}/attachments.zip` in cloud storage
- (repeat for each bucket, including preview buckets)

And creates a records bundle with all collections data (~6MB) for each bucket (`{folder}/changesets.zip`).

*Note: the job that is currently in charge of publishing the highest timestamp to the Push notification server, could first execute this attachment bundling job, in order to make sure bundles will be available when clients will pull changesets.*

This job would require GCloud credentials (Service Accounts credentials JSON file) and unlike `kinto-attachment` would be vendor-specific (ie. GCP Cloud storage using the `google-cloud-storage` Python library).

We would have to duplicate some of the `kinto-attachment` configuration values (eg. `kinto.attachment.gcloud.bucket_name` and `kinto.attachment.folder`) in order to store the bundles along attachments (ie. in the right folder `{bucket id}/{collections id}`), so that the final bundle URL remains straightforward for clients (eg. `capabilities.attachments.base_url` + `bucket_id/collection_id /bundle.zip`)

The clients would pull the records bundle on first sync, and the attachments bundle URL when `attachments.cacheAll()` is called. 
- Good, because ultra simple
- Good, because low cost
- Good, because monitored as other remote settings cronjobs
- Good, because it works easily for the preview bucket
- Not so good, because we would introduce some coupling with kinto-attachment config (unless we mount the same RS server .ini config in the container and read conf from it) 
- Not so good, because if we don’t couple it with the push timestamp cronjob, there could be a window of time where the bundle for a particular timestamp is not yet available
- Bad, because this would be a remote-settings specific job and feature, and not part of kinto-attachment
- Not so bad, because it would live along other cronjobs, and would be close to the one that syncs the timestamp with the push server  


