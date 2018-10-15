.. _tutorial-normandy-integration:

Normandy Integration
====================

Goals
-----

* Synchronize settings on certain clients only
* Settings available only temporarily

.. note::
   This differs from :ref:`JEXL filters <target-filters>`, with which all records are synchronized but the listing locally gives a filtered set.


Introduction
------------

When a collection is published on the server, a client synchronizes it if and only if one the following conditions is met:

* it has an instantiated client — ie. a call to ``RemoteSettings("cid")`` was done earlier
* some local data exists in the internal IndexedDB
* a JSON dump was shipped in mozilla-central for this collection in ``services/settings/dumps/``

Basically, we will leverage the fact that if the client is never instantiated, then it will be never synchronized, and thus will never have any local data.


Disabled by default
-------------------

Instantiating a client conditionnaly using a preference whose default value is ``false`` does the trick! By default, users won't synchronize this collection.

.. code-block:: javascript

    if (Services.prefs.getBoolPref("my-feature-pref")) {
        const client = RemoteSettings("cid");
        const records = await client.get();
    }


Pref Flip
---------

Using `Normandy preference experiments <https://normandy.readthedocs.io/en/latest/user/actions/preference-experiment.html>`_, you can flip the above preference to ``true`` for a sub-population of users, or temporarily etc. (using JEXL filters BTW).

When the experiment will be *enabled* on the targeted users, the client will be instantiated and the synchronization of the collection data will take place.


Clean-up
--------

Once the experiment is switched back to *disabled*, the preference can be switched back to ``false`` and the local data should be deleted:

.. code-block:: javascript

    const collection = await RemoteSetttings("cid").openCollection();
    await collection.clear();

You can also open a ticket to request the deletion of the collection from the server.
