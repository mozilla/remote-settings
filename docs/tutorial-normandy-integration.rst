.. _tutorial-normandy-integration:

Normandy Integration
====================

Goals
-----

* Synchronize settings on certain clients only
* Settings available only temporarily

.. note::

   This differs from :ref:`JEXL filters <target-filters>`, with which all records are synchronized but listing them locally returns a filtered set.


Introduction
------------

When a collection is published on the server, it get pulled during synchronization if at least one the following conditions is met:

* There is an instantiated client — ie. a call to ``RemoteSettings("cid")`` was done earlier
* Some local data exists in the internal IndexedDB — ie. it was pulled once already
* A JSON dump was shipped in mozilla-central for this collection — in ``services/settings/dumps/``

Basically, here we will leverage the fact that **if the client is never instantiated, then it will never get synchronized**, and thus will never have any local data.


Disabled by default
-------------------

Instantiating a client conditionnaly using a preference whose default value is ``false`` does the trick! By default, users won't synchronize this collection data.

.. code-block:: javascript

    if (Services.prefs.getBoolPref("my-feature-pref", false)) {
        const client = RemoteSettings("cid");
        const records = await client.get();
    }


Pref Flip
---------

Using `Normandy preference experiments <https://normandy.readthedocs.io/en/latest/user/actions/preference-experiment.html>`_, you can flip the above preference to ``true`` for a sub-population of users, or temporarily etc. (using JEXL filters BTW).

When the experiment will be *enabled* on the targeted users, the client will be instantiated and the synchronization of the collection data will take place.


Clean-up
--------

Once the experiment is switched back to *disabled*, the local data should be deleted. We will use a preference observer to detect that the preference is switched back to ``false``:

.. code-block:: javascript

    Services.prefs.addObserver("my-feature-pref", {
      async observe(aSubject, aTopic, aData) {
        if (!Services.prefs.getBoolPref(aData)) {
          // Pref was switched to false, clean-up local IndexedDB data.
          const collection = await RemoteSetttings("cid").openCollection();
          await collection.clear();
        }
      }
    });


You can also open a ticket to request the deletion of the collection from the server.
