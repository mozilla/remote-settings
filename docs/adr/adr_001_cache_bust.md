# Cache Bust on Signature Refresh

- Status: proposed
- Date: 2022-03-03

Tracking issue: https://github.com/mozilla/remote-settings/issues/186

## Context and Problem Statement

When clients synchronize their local state with the server, they pull the list of latest changes from the monitor/changes endpoint.

They iterate the list of collections, and use the provided timestamp in the `?_expected=` query param when fetching the changeset, in order to bust the CDN cache.

For example, given the following list of latest changes:

```
GET /buckets/monitor/collections/changes/records

{
  "data": [
    {
      "id": "eae22ba6-631d-fcab-fa53-8a7c5adb39a9",
      "last_modified": 1646297843179,
      "bucket": "security-state",
      "collection": "cert-revocations",
      "host": "firefox.settings.services.mozilla.com"
    },
    {
      "id": "e9f76a09-1c31-7dce-7c40-8abfbcfb244d",
      "last_modified": 1646261592246,
      "bucket": "main",
      "collection": "normandy-recipes-capabilities",
      "host": "firefox.settings.services.mozilla.com"
    },
    ...
  ]
}
```

The clients will pull from:

* `GET /buckets/security-state/collections/cert-revocations/changeset?_expected=1646297843179`
* `GET /buckets/security-state/collections/normandy-recipes-capabilities/changeset?_expected=1646261592246`

The CDN will cache the responses [aggressively](https://github.com/mozilla/remote-settings/blob/d1996490b2f5dc7f4d098c14f89dc86f3f568ca1/kinto-remote-settings/src/kinto_remote_settings/changes/views.py#L126-L138) for [1 hour](https://github.com/mozilla-services/cloudops-deployment/blob/b2ed06d77b6d84860b7bada0834c866fe37b289f/projects/kinto/puppet/modules/kinto/templates/kinto.ini.erb#L144).

Similarly, when a single collection is synchronized manually (or in the Rust client), we first fetch the list of latest changes, lookup the collection timestamp, and then fetch the changeset with the appropriate `?_expected` value.

The timestamps provided are the collection records timestamp, not the collections metadata timestamp. In other words, the timestamp won't be bumped if only the collection metadata is modified, and not its records data.

The collections content signatures rely on certificates that are relatively short-lived. Since some collections are not changed often enough, we regularly refresh collections signatures (using [a lambda](https://github.com/mozilla-services/remote-settings-lambdas/blob/master/commands/refresh_signature.py)) if it is older than 7 days.

This operation does not change the records, it only updates the signature fields. Namely, the certificate URL (x5u) and the signing value.

Because of this, the CDN cache is not busted on signature refresh. This lead to signature verification errors because clients could fetch an outdated response, like pointing to an expired certificate chain.

For example:

1. Changes are made on collection, data timestamp is bumped (`last_modified=42`)
1. Clients pull data from `/changeset?_expected=42`
1. CDN caches the response
1. Certificate expires
1. Signature is refreshed, the collection metadata is updated, data timestamp remains the same
1. Client queries monitor/changes endpoint, `last_modified=42`, pull changeset with `_expected=42`
1. CDN returns the cached changeset
1. Client pull expired certificate, signature fails
1. Client retries, clears local data, pulls full changeset again with `_expected=42`
1. Client signature fails again.


## Decision Drivers

In order to choose our solution we considered the following criteria:

- **Complexity**: Low → High: how much additional complexity
- **Impact**: Low → High: how big is the change on the whole service
- **Efforts**: Low → High: how much efforts are necessary
- **Rollout**: Slow → Fast: how fast can we roll out the fix

## Considered Options

1. Bump data timestamp on signature refresh
1. Use metadata timestamp as cache bust

## Decision Outcome

Chosen option: option 2, because it has the less impact on the service. We accept the slow rollout and would aim for an uplift in Beta at least, and maybe Release.


## Pros and Cons of the Options

### Option 1 - Bump data timestamp on signature refresh

On signature refresh, the timestamps in the monitor/changes response will be bumped. The highest timestamp in the list will also be bumped, which will lead to a push notification being sent to all clients.

Clients will fetch the changeset with a fresh cache bust and always obtain the latest version.

**Complexity**

Low. The overall architecture would not be modified.

**Impact**

High.

Even if no data is changed, clients will fetch a changeset response containing zero new change, only refreshed metadata. This will thus force synchronization of all collections on all clients (every 7 days at most). The client will apply the empty delta and revalidate the signature of their local data.

Impact is high since this will increase trafic on our servers and will force signature re-verification on clients.

> Note: traffic on origin shouldn't be too affected. And we are very likely to refresh signatures of several collections are once, therefore grouping them in one push notification.

**Efforts**

Low. This would be a one-liner in the `kinto-remote-settings` server plugin. Tagging and deploying is relatively cheap.

**Rollout**

Fast. The code change can be rolled out immediately. Effects would be visible after first signature refresh.

This would cover both Desktop and Rust clients.


### Option 2 - Use metadata timestamp as cache bust

This option would consist in adding a new field in the monitor/changes entries, providing the metadata timestamp.

```
GET /buckets/monitor/collections/changes/records

{
  "data": [
    {
      "id": "eae22ba6-631d-fcab-fa53-8a7c5adb39a9",
      "last_modified": 1646297843179,
      "metadata_timestamp": 1646293449944,
      "bucket": "security-state",
      "collection": "cert-revocations",
      "host": "firefox.settings.services.mozilla.com"
    },
    ...
  ]
}
```

The clients would use this `metadata_timestamp` field instead of `last_modified` as the value passed in the `?_expected=` query param to bust the cache.

**Complexity**

Low. The overall architecture would not be modified.

**Impact**

Mid-Low. This will slightly increase trafic on our servers, since we would have a population of clients that would bust the cache with one timestamp value, and the rest with another value.

**Efforts**

Mid-Low. Adding the new field is a one-liner on the server. Tagging and deploying is relatively cheap.

This would require a change in both the Desktop and the Rust client.

**Rollout**

Slow.

The Rust client could be tagged and released immediately.

But we would have to ride trains for the Desktop client.

However, the change is reasonable and we would have a chance to be accepted in uplifts for Beta. Maybe Release too.


```diff
--- a/services/settings/remote-settings.js
+++ b/services/settings/remote-settings.js
@@ -292,27 +292,27 @@ function remoteSettingsFunction() {
     gPrefs.setIntPref(PREF_SETTINGS_CLOCK_SKEW_SECONDS, clockDifference);
     const checkedServerTimeInSeconds = Math.round(serverTimeMillis / 1000);
     gPrefs.setIntPref(PREF_SETTINGS_LAST_UPDATE, checkedServerTimeInSeconds);

     // Iterate through the collections version info and initiate a synchronization
     // on the related remote settings clients.
     let firstError;
     for (const change of changes) {
-      const { bucket, collection, last_modified } = change;
+      const { bucket, collection, last_modified: dataTimestamp, metadata_timestamp: metadataTimestamp } = change;

       const client = await _client(bucket, collection);
       if (!client) {
         // This collection has no associated client (eg. preview, other platform...)
         continue;
       }
       // Start synchronization! It will be a no-op if the specified `lastModified` equals
       // the one in the local database.
       try {
-        await client.maybeSync(last_modified, { trigger });
+        await client.maybeSync(dataTimestamp, { trigger, metadataTimestamp });

         // Save last time this client was successfully synced.
         Services.prefs.setIntPref(
           client.lastCheckTimePref,
           checkedServerTimeInSeconds
         );
       } catch (e) {
         console.error(e);
```


```diff
--- a/services/settings/RemoteSettingsClient.jsm
+++ b/services/settings/RemoteSettingsClient.jsm
   /**
    * Synchronize the local database with the remote server, **only if necessary**.
    *
-   * @param {int}    expectedTimestamp the lastModified date (on the server) for the remote collection.
+   * @param {int}    dataTimestamp     the lastModified date (on the server) for the remote collection.
    *                                   This will be compared to the local timestamp, and will be used for
    *                                   cache busting if local data is out of date.
    * @param {Object} options           additional advanced options.
    * @param {bool}   options.loadDump  load initial dump from disk on first sync (default: true, unless
    *                                   `services.settings.load_dump` says otherwise).
    * @param {string} options.trigger   label to identify what triggered this sync (eg. ``"timer"``, default: `"manual"`)
    * @return {Promise}                 which rejects on sync or process failure.
    */
-  async maybeSync(expectedTimestamp, options = {}) {
+  async maybeSync(dataTimestamp, options = {}) {
     // Should the clients try to load JSON dump? (mainly disabled in tests)
-    const { loadDump = gLoadDump, trigger = "manual" } = options;
+    const { loadDump = gLoadDump, trigger = "manual", metadataTimestamp: expectedTimestamp } = options;

     // Make sure we don't run several synchronizations in parallel, mainly
     // in order to avoid race conditions in "sync" events listeners.
     if (this._syncRunning) {
       console.warn(`${this.identifier} sync already running`);
       return;
     }

@@ -576,26 +576,26 @@ class RemoteSettingsClient extends Event
         } catch (e) {
           // Report but go-on.
           Cu.reportError(e);
         }
       }
       let syncResult;
       try {
         // Is local timestamp up to date with the server?
-        if (expectedTimestamp == collectionLastModified) {
+        if (dataTimestamp == collectionLastModified) {
           console.debug(`${this.identifier} local data is up-to-date`);
           reportStatus = UptakeTelemetry.STATUS.UP_TO_DATE;


```