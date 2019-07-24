.. _faq:

Frequently Asked Questions
==========================

How do I setup Firefox to pull data from STAGE?
-----------------------------------------------

The recommended way to setup Firefox to pull data from STAGE is to use the `Remote Settings DevTools <https://github.com/mozilla/remote-settings-devtools>`_ extension: switch the environment in the configuration section and click the *Sync* button.

Alternatively, you can change the `appropriate preferences <https://github.com/mozilla/remote-settings-devtools/blob/1.0.0/extension/experiments/remotesettings/api.js#L96-L106>`_, restart and trigger a synchronization manually.


How do I preview the changes before approving?
----------------------------------------------

The recommended way to setup Firefox to pull data from the preview collection is to use the `Remote Settings DevTools <https://github.com/mozilla/remote-settings-devtools>`_ extension: switch the environment to *Preview* and click the *Sync* button.

Alternatively, you can change the ``services.settings.default_bucket`` preference to ``main-preview``, and trigger a synchronization manually.


How do I preview the changes before requesting review?
------------------------------------------------------

Currently, this is not possible.

Possible workarounds:

- use a :ref:`local server <tutorial-local-server>` or the :ref:`DEV server <tutorial-dev-server>`
- request review, preview changes, fix up, request review again


How do I trigger a synchronization manually?
--------------------------------------------

See `developer docs <https://firefox-source-docs.mozilla.org/services/common/services/RemoteSettings.html#trigger-a-synchronization-manually>`_.


How do I define default data for new profiles?
----------------------------------------------

See `developer docs about initial data <https://firefox-source-docs.mozilla.org/services/common/services/RemoteSettings.html#initial-data>`_.


How do I automate the publication of records?
---------------------------------------------

The Remote Settings server is a REST API (namely a `Kinto instance <https://www.kinto-storage.org>`_). Records can be created in batches, and as seen in the :ref:`multi signoff tutorial <tutorial-multi-signoff>` reviews can be requested and approved using ``PATCH`` requests.

If the automation is meant to last (eg. cronjob, AWS lambda) then `request a dedicated Kinto internal account <https://bugzilla.mozilla.org/enter_bug.cgi?product=Cloud%20Services&component=Server%3A%20Remote%20Settings>`_ to be created for you.

If it is a one time run, then you can run the script as if it was you:

1. Authenticate on the Admin UI
2. Using the DevTools, inspect the outgoing requests and copy the ``Authorization`` header (eg. ``Bearer r43yt0956u0yj1``)
3. Use this header in your ``cURL`` commands (or Python/JS/Rust clients etc.)


How often the synchronization happens?
--------------------------------------

Right now, every 24H. But once integrated with the Megaphone project in Firefox 64, it will be a matter of minutes thanks to push notifications.


Once data is ready in STAGE, how do we go live in PROD?
-------------------------------------------------------

Stage and prod are aligned in terms of setup, features and versions.

Hence, once done in STAGE there is nothing specific / additional to do: you should be able to redo the same in PROD!

.. note::

    If you have a lot of data that you want to duplicate from one instance to another, check out `kinto-wizard <https://github.com/Kinto/kinto-wizard/>`_ that can dump and load records!


How many records does it support?
---------------------------------

We already have use-cases that contain several hundreds of records, and it's totally fine.

Nevertheless, if you have thousands of records that change very often, we should talk! Mostly in order to investigate the impact in terms of payload, bandwidth, signature verification etc.


Are there any size restrictions for a single record, or all records in a collection?
------------------------------------------------------------------------------------

Quotas were not enabled on the server. Therefore, technically you can create records with any size, and have as many as you want in the collection.

**However**, beyond some reasonable size for the whole collection serialized as JSON, it is recommended using our :ref:`attachments feature <tutorial-attachments>`.

Using attachments on records, you can publish data of any size (as JSON, gzipped, etc.). It gets published on S3 and the records only contain metadata about the remote file (including hash, useful for signature verification).


Also does remote settings do any sort of compression for the records?
---------------------------------------------------------------------

We are working on improving the handling of Gzip encoding for the attachments files (see `Bug 1339114 <https://bugzilla.mozilla.org/show_bug.cgi?id=1339114>`_).

But by default, Remote Settings does not try to be smart regarding compression.


Is it possible to deliver remote settings to some users only?
-------------------------------------------------------------

By default, settings are delivered to every user.

You can add :ref:`JEXL filters on records <target-filters>` to define targets. Every record will be downloaded but the list obtained with ``.get()`` will only contain entries that match.

In order to limit the users that will download the records, you can check out our :ref:`dedicated tutorial <tutorial-normandy-integration>`.


How does the client choose the collections to synchronize?
----------------------------------------------------------

First, the client fetches the `list of published collections <https://firefox.settings.services.mozilla.com/v1/buckets/monitor/collections/changes/records>`_.

Then, it synchronizes the collections that match one of the following:

* it has an instantiated client — ie. a call to ``RemoteSettings("cid")`` was done earlier
* some local data exists in the internal IndexedDB
* a JSON dump was shipped in mozilla-central for this collection in ``services/settings/dumps/``


.. _troubleshooting:

Troubleshooting
===============

* Open a `Server Side ticket <https://bugzilla.mozilla.org/enter_bug.cgi?product=Cloud%20Services&component=Server%3A%20Remote%20Settings>`_ (Admin, permissions etc.)
* Open a `Client Side ticket <https://bugzilla.mozilla.org/enter_bug.cgi?product=Firefox&component=Remote%20Settings%20Client>`_ (Gecko API related)


I cannot access my collection
-----------------------------

* Check that you can ping the server on the VPN
  - If not, contact ``:wezhou`` on #engops on Slack
* Check that you can login on the Kinto Admin UI
* In the ``main-workspace`` bucket, check that you can create records in your collection (eg. main-workspace/tippytop)
