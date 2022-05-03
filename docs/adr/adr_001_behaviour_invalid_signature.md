# Desktop Client: Invalid Signature and Local Data

* Status: proposed
* Deciders: mleplatre, gbeckley, bwong
* Date: May 2, 2022

## Context and Problem Statement

The goal of this document is to determine what to do with the local data when the verification of signatures fails and no dump is packaged. Problem identified as [Bug 1712108](https://bugzilla.mozilla.org/show_bug.cgi?id=1712108).

This bug was created in the following context: we had a issue where one intermediate in the server certificate chain was about to expire. We were alerted, and realized that if we would not refresh signatures right away, all clients would have faced signature errors.

As explicated in the [synchronization process documentation](https://firefox-source-docs.mozilla.org/services/settings/#synchronization-process), when the signature verification fails after retry, the local DB is left empty if the collection does not have any packaged dump.

Any subsequent call to `.get()` will then trigger a synchronization. But if that synchronization fails again, then [the error is caught and an empty list is returned](https://searchfox.org/mozilla-central/rev/a730b83206183bf097820c5780eef0d5e4103b9d/services/settings/RemoteSettingsClient.jsm#451-454).

Consumers have then no way to distinguish an empty collection (no record on the server), from a failed synchronization that returns an empty list.

In the case of Normandy, if the Remote Settings collection becomes empty, then the user is unrolled from experiments. In other words, if the server certificates become invalid, all users are unrolled from all experiments. This is why this bug was created: prevent this from happening.

## Decision Drivers

In order to choose our solution we considered the following criteria:

- **Complexity**: Low → High: how complex is the solution
- **Cost of implementation**: Low → High: how much efforts does it represent
- **Generalization**: Specific → Global: does the solution apply to all consumers
- **Security**: Bad → Good: does it affect security

## Considered Options

1. [Option 0 - Do nothing](#option-0---do-nothing)
1. [Option 1 - Replace with server data](#option-1---replace-with-server-data)
1. [Option 2 - Leave local data](#option-2---leave-local-data)
1. [Option 3 - Throw error on `.get()` if signature is invalid in last sync](#option-3---throw-error-on-get-if-signature-is-invalid-in-last-sync)
1. [Option 4 - Overwrite local data only if successful](#option-4---overwrite-local-data-only-if-successful)
1. [Option 5 - Keep a copy of last successful state](#option-5---keep-a-copy-of-last-successful-state)

## Decision Outcome

Chosen option: Option XX because

## Pros and Cons of the Options

### Option 0 - Do nothing

Currently, this is equivalent to clearing the local database when the signature verification fails and the collection has no packaged dump.

- **Complexity**: N/A
- **Cost of implementation**: N/A
- **Generalization**: Global, affects all collections without dump
- **Security**: Good, local data reflects the server's or is cleared


### Option 1 - Replace with server data

With this option, instead of leaving the local DB empty, we could replace it with the server content, even if the signature does not verify.

- **Complexity**: Low
- **Cost of implementation**: Low
- **Generalization**: Global, affects all collections without dump
- **Security**: *Very bad*: this would allow attackers to perform man-in-the-middle attacks. By serving a fake server response with an invalid certificate, attackers could replace the local content with theirs.


### Option 2 - Leave local data

With this option, instead of leaving the local DB empty, we restore the data that was stored before starting the synchronization.

- **Complexity**: Low
- **Cost of implementation**: Low
- **Generalization**: Global, affects all collections without dump
- **Security**: *Bad*: This would allow attackers that gain access to the local DB to perform man-in-the-middle attacks. By serving a fake server response with an invalid certificate, and storing their content in the local DB beforehand, clients would be stuck with attackers' data.


### Option 3 - Throw error on `.get()` if signature is invalid in last sync

With this solution, we distinguish an empty collection from a collection that was cleared after invalid signature.

This way, consumers like Normandy can distinguish a situation where no experiments is available from a situation where the collection could not be synced successfully. We would let consumers handle this situation themselves.

In order to avoid breakage of all consumers, we could introduce a new flag (eg. `throwIfInvalidSignature`). If the last synchronization failed, and no dump was found, and the flag is set, then `.get()` will throw.

Modifying the Normandy recipe runner to use it is straightforward:

```diff
--- a/toolkit/components/normandy/lib/RecipeRunner.jsm
+++ b/toolkit/components/normandy/lib/RecipeRunner.jsm
@@ -329,7 +329,9 @@ var RecipeRunner = {
       // Fetch recipes before execution in case we fail and exit early.
       let recipesAndSignatures;
       try {
-        recipesAndSignatures = await gRemoteSettingsClient.get();
+        recipesAndSignatures = await gRemoteSettingsClient.get({
+          throwIfInvalidSignature: true,
+        });
       } catch (e) {
         await Uptake.reportRunner(Uptake.RUNNER_SERVER_ERROR);
         return;
```

If synchronization failed, the recipe runner exits instead of receiving an empty list from the Remote Settings client.

- **Complexity**: Medium. We introduce an additional option and a new state for each collection (ie. last sync status).
- **Cost of implementation**: Low
- **Generalization**: Specific. It only affects collections that enabled the option. Some consumers may not be aware of this behavior on sync error.
- **Security**: Good, when enabled, this option doesn't let consumers list the local data if it's invalid.

> Note: We could leverage the history of status introduced in [Bug 1732056](https://bugzilla.mozilla.org/show_bug.cgi?id=1732056) to save the last sync status of a collection, and throw the appropriate error on `.get()`.


### Option 4 - Overwrite local data only if successful

With this solution, we perform the synchronization fully in memory and overwrite the local data only if signature verification succeeds.

Unlike the current implementation, which merges the diff locally, then clears the DB if invalid, then retries with the full dataset, then clears if invalid again and restores local dataset or dump, this solution would involve a lot less write operations and would be more efficient when synchronization errors happen.

However, unlike the current implementation which verifies signatures after storing, this solution would not verify integrity on what is actually stored in the local DB. Even if the code that applies diffs [is relatively straightforward](https://searchfox.org/mozilla-central/rev/ea1234192518e01694a88eac8ff090e4cadf5ca4/services/settings/Database.jsm#129-154), there is still a chance of having a discrepancy between what is computed in memory and what is executed in the IndexedDB code.

Since we would store the data in a single IndexedDB transaction, we should be safe with regards to storage shutdown, crash, or interruptions.

- **Complexity**: Low. This is likely to simplify the code base.
- **Cost of implementation**: Medium, critical code paths in the synchronization flow have to be modified.
- **Generalization**: Global. It would affect all consumers.
- **Security**: Good, only valid data is stored using a single IndexedDB transaction.

> Note: The downside of this approach could be mitigated by implementing [signature verification when data is up-to-date](https://bugzilla.mozilla.org/show_bug.cgi?id=1640126).


### Option 5 - Keep a copy of last successful state

With this solution, we would synchronize into a temporary location, and point the collection to the new dataset only if successful.

If signature fails on an empty profile, the last successful dataset is empty (if no dump is packaged).

With this approach, the whole collection dataset has to be duplicated on each sync. This would have a significant impact on performance, especially with collections like `security-state/onecrl` or `security-state/intermediates` which have more than 1000 records.

- **Complexity**: High. This solution would require a lot of changes in a critical part of the code base.
- **Cost of implementation**: High. This solution involves adding a level of indirection in the database to point *locations*.
- **Generalization**: Global. It would affect all consumers.
- **Security**: Good, consumers can only read valid data.
