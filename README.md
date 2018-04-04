# remote-settings

This repo is for tracking issues / project management for the Remote Settings v2 Project. 

## What is Remote Settings V2? 

These attributes differentiate V1 from V2: 

1. Simplier API in Firefox
1. Self serve setting creation
1. Targeting ability. Setting values can be different based on Firefox's criteria (platform, locale, version, etc)
1. Reduced update latency. Support for broadcast API (server push) as well as polling

## When will it be available? 

* We are targetting Firefox 62 (nightly) to have the new APIs available

## What will the API Look like? 

There are two new APIs to work with settings:

1. `get()` 
2. `on()` 

### get()

```js
const { RemoteSettings } = ChromeUtils.import("resource://services-common/remote-settings.js", {});

const records = await RemoteSettings("my-key").get();

/*
  records == [
    {label: "Yahoo",  enabled: true,  weight: 10, id: "d0782d8d", last_modified: 1522764475905},
    {label: "Google", enabled: true,  weight: 20, id: "8883955f", last_modified: 1521539068414},
    {label: "Ecosia", enabled: false, weight: 5,  id: "337c865d", last_modified: 1520527480321},
  ]
*/

for(const entry of records) {
  // Do something with entry, e.g:
  // await InternalAPI.load(entry.id, entry.label, entry.weight);
});
```

### on() 

The `on()` allows handlers to be triggered when records changes on the server side. 

```js
RemoteSettings("my-key").on("create", (event) => { 
   for (const record of event.created) { /* ... */ }
});
RemoteSettings("my-key").on("update", (event) => { 
   for (const record of event.updated) { /* ... */ }
});
RemoteSettings("my-key").on("delete", (event) => { 
   for (const record of event.deleted) { /* ... */ }
});
```

