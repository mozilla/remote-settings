# Server Side Filtering

* Status: proposed
* Deciders: mleplatre, acottner, najiang
* Date: Jan 3, 2024

## Context and Problem Statement

In some situations, clients only need a subset of the collection records.

And since the signature is computed on the server side for the whole dataset, clients are obliged to also download the same whole dataset locally in order to verify the data integrity.

In this document, we explore possible solutions to overcome this limitation.

## Decision Drivers

In order to choose our solution we considered the following criteria:

- **Complexity**: Low → High: how complex is the solution
- **User experience**: Bad → Good: how adapted to users is the solution
- **Cost of implementation**: Low → High: how much efforts does it represent
- **Cost of operation**: Low → High: how much does the solution cost to run

## Considered Options

1. [Option 0 - Do nothing](#option-0---do-nothing)
1. [Option 1 - Split into several collections](#option-1---split-into-several-collections)
1. [Option 2 - Read-only mirrors](#option-2---read-only-mirrors)
1. [Option 3 - Implement notion of datasets](#option-3---implement-notion-of-datasets)
1. [Option 4 - Implement dynamic signatures](#option-4---implement-dynamic-signatures)

## Decision Outcome

Chosen option: if it fits the segmentation requirements, we would pick *Option 2*. We already have all the pieces in place, it is very low tech and low cost, while still providing a good user experiences for editors and publication of data.

## Pros and Cons of the Options

### Option 0 - Do nothing

No change is made. All clients download everything and filter locally using JEXL targeting.

- **Complexity**: N/A
- **User experience**: Good, users edit a single collection.
- **Cost of implementation**: N/A
- **Cost of operation**: High. All clients download everything, resulting in higher bandwidth costs.


### Option 1 - Split into several collections

The single collections is split into several ones, and the client is able to determine which collection it should pull from (eg. one per region).

If a record is required in different subsets, it is duplicated in each collection.

- **Complexity**: N/A
- **User experience**: Bad, even if a script could automate the publication of records into several collections, editors don't have a single source of truth for the content, leading to duplicated actions and data.
- **Cost of implementation**: Low. Creating collections is cheap.
- **Cost of operation**: Low. Clients download only the subset of data, saving bandwidth.


### Option 2 - Read-only mirrors

With this solution, the main collection is maintained, and several "*side collections*" are created. As with *Option 1*, the clients are able to pick which collection to pull from.

Unlike *Option 1*, the additional collections are read-only. Editors publish data in the main collection, and a scheduled job will copy the records at regular intervals to the side collections using filters.

The [`backport_records` cronjob](https://github.com/mozilla-services/remote-settings-lambdas?tab=readme-ov-file#backport_records) copies records from one collection to another and signs it. It can take querystring filters as parameters in order to only copy of subset of the source.

For example, if records have a `regions` field:

```
{
    "id": "shop-A",
    "regions": ["europe", "asia", "north-america"],
},
{
    "id": "shop-B",
    "regions": ["europe", "africa"],
}
```

Then different collections can be populated using this field in [a querystring filter](https://docs.kinto-storage.org/en/latest/api/1.x/filtering.html#comparison):

* `shops-africa`: `?contains_regions=["africa"]`
* `shops-europe`: `?contains_regions=["europe"]`
* `shops-asia`: `?contains_regions=["asia"]`

- **Complexity**: Low. It is based on existing pieces of the current architecture.
- **User experience**: Good, because editors only manipulate the main collection to assign datasets and to publish data.
- **Cost of implementation**: Low. Creating collections is cheap and onboarding new instances of the `backport_records` job also.
- **Cost of operation**: Low. Clients download only the subset of data, saving bandwidth, and running cronjobs is cheap.


### Option 3 - Implement notion of datasets

With this solution, we compute several signatures for a single collection.

On the server side, we could introduce the notion of *datasets* for a collection. Datasets could be declared in the server configuration:

```
# config.ini

kinto.signer.datasets.main.shops.shops-africa = ?contains_regions=["africa"]
kinto.signer.datasets.main.shops.shops-europe = ?contains_regions=["europe"]
kinto.signer.datasets.main.shops.shops-asia = ?contains_regions=["asia"]
```

When a change is published in the collection, instead of computing a single signature for the whole collection, we compute a signature for each dataset and put them in the collection metadata:

```
{
    "metadata": {
        "signatures": {
            "shops-africa": {
                "filter": "?contains_regions=["africa"]",
                "signature": "P2OAvlvj1uhIAafIVgtpuAo3lF4pZWERc...C4rC7c9-EC4cl77R35Qo3hRYg2lKU",
            },
            "shops-europe": {
                "filter": "?contains_regions=["europe"]",
                "signature": "MHYwEAYHKoZIzj0CAQYFK4EEACIDYgAEab4HfqYGRLW...",
            }
        }
    }
}

```

The clients would pull the subset of data, and use the specific signature to verify the integrity.

- **Complexity**: Medium-High. We introduce some coupling between server configuration and client behaviour.
- **User experience**: Good, users edit a single collection.
- **Cost of implementation**: Medium-High. Server side code is relatively straightforward, but the different clients implementations have to be modified to support this new type of metadata.
- **Cost of operation**:  Low. Clients download only the subset of data, saving bandwidth, and signing datasets on each publication is relatively cheap.


### Option 4 - Implement dynamic signatures

With this solution we sign every server response dynamically.

- **Complexity**: Medium. In terms of architecture, this would introduce any real complexity/
- **User experience**: Good, users edit a single collection.
- **Cost of implementation**: Medium-High, this would represent a big change of approach and thus code.
- **Cost of operation**: High. Autograph would have to scale to the traffic received on the origin servers of Remote Settings.
