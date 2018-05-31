## What is Remote Settings

Remote Settings is a Mozilla service that makes it easy to manage evergreen
settings data in Firefox. [kinto](https://github.com/Kinto/kinto) is used
for syncing of data.  A simple API is available in Firefox for accessing
the synchronized data.

## Why is it better than building my own? 

Out of the box you get for free: 

* Syncing of data 
* Content signing - your data is signed server side and verified on the client side transparently
* File attachment support
* !!! Real time, push based updates in Fx63/64 with no changes to your code !!!

## When will it be available?

* The new API will be available in Fx62 (nightly). 

## What does the RemoteSettings client API Look like?

There are two main functions to work with settings:

1. `get()`
2. `on()`

### get()

```js
const { RemoteSettings } = ChromeUtils.import("resource://services-common/remote-settings.js", {});

const records = await RemoteSettings("my-collection").get();

/*
  records == [
    {label: "Yahoo",  enabled: true,  weight: 10, id: "d0782d8d", last_modified: 1522764475905},
    {label: "Google", enabled: true,  weight: 20, id: "8883955f", last_modified: 1521539068414},
    {label: "Ecosia", enabled: false, weight: 5,  id: "337c865d", last_modified: 1520527480321},
  ]
*/

for(const record of records) {
  // await InternalAPI.load(record.id, record.label, record.weight);
});
```

### on("sync", (e) => { ... })

The `on()` function registers handlers to be triggered when records changes on the server side.
Your handler is given an event object that contains a `.data` attribute that has information
about the changes.

Currently the only available event is `sync`.

```js
RemoteSettings("my-collection").on("sync", (e) => {
   // e.data.current = [ Record, Record, ... ]
   // e.data.updated = [ Record, Record, ... ]
   // e.data.created = [ Record, Record, ... ]
   // e.data.deleted = [ Record, Record, ... ]
});
```

The `.data` attribute includes:

* `.data.current` - a list of the all records in your collection
* `.data.updated` - a list of the records updated by the sync
* `.data.created` - a list of the records that were added by the sync
* `.data.deleted` - a list of the records that were deleted by the sync

## What does the server side API look like? 

* You can use the [REST APIs](https://kinto.readthedocs.io/en/latest/api/1.x/index.html#full-reference)
* You can use our [web based GUI](https://github.com/Kinto/kinto-admin)

## Awesome! How do I get started? 

* The [mana page](https://mana.mozilla.org/wiki/pages/viewpage.action?pageId=66655528) has the process for requesting a new settings collection
* ([official developer docs](https://firefox-source-docs.mozilla.org/services/common/services/RemoteSettings.html)) 

