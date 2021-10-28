Support
=======

.. _troubleshooting:

Troubleshooting
---------------

* Open a `Server Side ticket <https://bugzilla.mozilla.org/enter_bug.cgi?product=Cloud%20Services&component=Server%3A%20Remote%20Settings>`_ (Admin, permissions etc.)
* Open a `Client Side ticket <https://bugzilla.mozilla.org/enter_bug.cgi?product=Firefox&component=Remote%20Settings%20Client>`_ (Gecko API related)

I cannot access my collection
'''''''''''''''''''''''''''''

* Check that you can ping the server on the VPN
  - Make sure you were added in the appropriate VPN group (see :ref:`getting-started`)
  - Join ``#engops`` on Slack to troubleshoot.
* Check that you can login on the Admin UI
* In the ``main-workspace`` bucket, check that you can create records in your collection (eg. ``main-workspace/tippytop``)

I approved the changes, but still don't see them
''''''''''''''''''''''''''''''''''''''''''''''''

* A CDN serves as a cache, only push notifications bust the cache efficiently
* Check that your data is visible on the source server: eg. https://settings.prod.mozaws.net/v1/buckets/main/collections/cfr/changeset?_expected=something-random-42


.. _faq:

Frequently Asked Questions
--------------------------

How often the synchronization happens?
''''''''''''''''''''''''''''''''''''''

Synchronizations can be within 10 minutes of the change or in 24 hours.

There are two triggers for synchronization: a push notification and a polling check. Every five minutes a server side process checks for changes. If any changes are found a push notification will be sent and online clients will check in for updates. Clients that are offline or did not receive the push notification will either catch-up on next startup or automatically poll for changes every 24 hours.


What is the lag on the CDN?
'''''''''''''''''''''''''''

The client uses the ``/v1/buckets/main/collections/{cid}/changeset`` endpoint, which requires a ``?_expected={}`` query parameter. Since the Push notification contains the latest change timestamp, the first clients to pull the changes from the CDN will bust its cache.

When using the ``/records`` endpoint manually, without any query parameters, the CDN lag can be much higher (typically 1H).


How do I setup Firefox to pull data from STAGE?
'''''''''''''''''''''''''''''''''''''''''''''''

The **recommended way** to setup Firefox to pull data from STAGE is to use the `Remote Settings DevTools <https://github.com/mozilla/remote-settings-devtools>`_ extension: switch the environment in the configuration section and click the *Sync* button.

Alternatively, in order to point STAGE before on fresh profiles for example, you can set the `appropriate preferences <https://github.com/mozilla/remote-settings-devtools/blob/1.4.0/extension/experiments/remotesettings/api.js#L113-L124>`_ in a ``user.js`` file:

::

    user_pref("services.settings.server", "https://settings.stage.mozaws.net/v1");
    user_pref("dom.push.serverURL", "https://autopush.stage.mozaws.net");
    user_pref("security.content.signature.root_hash", "3C:01:44:6A:BE:90:36:CE:A9:A0:9A:CA:A3:A5:20:AC:62:8F:20:A7:AE:32:CE:86:1C:B2:EF:B7:0F:A0:C7:45");
    user_pref("services.settings.load_dump", false);

See `developer docs <https://firefox-source-docs.mozilla.org/services/settings/#trigger-a-synchronization-manually>`_ to trigger a synchronization manually.


How do I preview the changes before approving?
''''''''''''''''''''''''''''''''''''''''''''''

The recommended way to setup Firefox to pull data from the preview collection is to use the `Remote Settings DevTools <https://github.com/mozilla/remote-settings-devtools>`_ extension: switch the environment to *Preview* and click the *Sync* button.

Alternatively, you can change the ``services.settings.default_bucket`` preference to ``main-preview``, and trigger a synchronization manually.


How do I preview the changes before requesting review?
''''''''''''''''''''''''''''''''''''''''''''''''''''''

Currently, this is not possible.

Possible workarounds:

- use a :ref:`local server <tutorial-local-server>` or the :ref:`DEV server <tutorial-dev-server>`
- request review, preview changes, fix up, request review again


How do I trigger a synchronization manually?
''''''''''''''''''''''''''''''''''''''''''''

See `developer docs <https://firefox-source-docs.mozilla.org/services/settings/#trigger-a-synchronization-manually>`_.


How do I define default data for new profiles?
''''''''''''''''''''''''''''''''''''''''''''''

See `developer docs about initial data <https://firefox-source-docs.mozilla.org/services/settings/#initial-data>`_.


How do I automate the publication of records? (one shot)
''''''''''''''''''''''''''''''''''''''''''''''''''''''''

The Remote Settings server is a REST API (namely a `Kinto instance <https://www.kinto-storage.org>`_). Records can be created in batches, and as seen in the :ref:`multi signoff tutorial <tutorial-multi-signoff>` reviews can be requested and approved using ``PATCH`` requests.

If it is a one time run, then you can run the script as if it was you:

1. Authenticate on the Admin UI
2. On the top right corner, use the 📋 icon to copy the authentication string (eg. ``Bearer r43yt0956u0yj1``)
3. Use this header in your ``cURL`` commands (or Python/JS/Rust clients etc.)

.. code-block:: bash

	curl 'https://settings-writer.stage.mozaws.net/v1/' \
	  -H 'Authorization: Bearer r43yt0956u0yj1'


How do I automate the publication of records? (forever)
'''''''''''''''''''''''''''''''''''''''''''''''''''''''

If the automation is meant to last (eg. cronjob, lambda, server to server) then the procedure would look like this:

1. `Request a dedicated Kinto internal account <https://bugzilla.mozilla.org/enter_bug.cgi?product=Cloud%20Services&component=Server%3A%20Remote%20Settings>`_ to be created for you (eg. ``password-rules-publisher``). Secret password should remain in a vault and managed by OPs.
2. Write a script that:

  1. takes the server and credentials as ENV variables (eg. ``SERVER=prod AUTH=password-rules-publisher:s3cr3t``);
  2. compares your source of truth with the collection records. Exit early if no change;
  3. performs all deletions/updates/creations;
  4. patches the collection metadata in order to request review (see :ref:`multi-signoff tutorial <tutorial-multi-signoff-request-review>`);

3. Request the OPs team to setup a cronjob in order to run your script (`request example <https://bugzilla.mozilla.org/show_bug.cgi?id=1529860>`_)

We recommend the use of `kinto-http.py <https://github.com/Kinto/kinto-http.py>`_ (`script exanple <https://gist.github.com/leplatrem/f3cf7ac5b0b9b0b27ff6456f47f719ca>`_), but Node JS is also possible (`HIBP example <https://github.com/mozilla/blurts-server/blob/c33a85b/scripts/updatebreaches.js>`_).

.. note::

	Even if publication of records is done by a script, a human will have to approve the changes manually.
	Generally speaking, disabling dual sign-off is possible, but only in **very** specific cases.

	If you want to skip manual approval, request a review of your design by the cloud operations security team.


.. _duplicate_data:

Once data is ready in DEV or STAGE, how do we go live in PROD?
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Stage and prod are aligned in terms of setup, features and versions.

Hence, once done in DEV or STAGE there is nothing specific / additional to do: you should be able to redo the same in PROD!


If you have a lot of data that you want to duplicate from one instance to another, you can use `kinto-wizard <https://github.com/Kinto/kinto-wizard/>`_ to dump and load records!

.. code-block:: bash

	pip install --user kinto-wizard

Dump the main records:

.. code-block:: bash

    kinto-wizard dump --records --server https://settings.stage.mozaws.net/v1 --bucket=main --collection=top-sites > top-sites.yaml

Open the ``.yaml`` file and rename the bucket name on top to ``main-workspace``.

Login in the Remote Settings Admin and copy the authentication header (icon in the top bar), in order to use it in the ``--auth`` parameter of the ``kinto-wizard load`` command.

.. code-block:: bash

    kinto-wizard load --server https://settings.prod.mozaws.net/v1 --auth="Bearer uLdb-Yafefe....2Hyl5_w" top-sites.yaml

Requesting review can be done via the UI, :ref:`or the command-line <tutorial-multi-signoff-request-review>`.


How many records does it support?
'''''''''''''''''''''''''''''''''

We already have use-cases that contain several hundreds of records, and it's totally fine.

Nevertheless, if you have thousands of records that change very often, we should talk! Mostly in order to investigate the impact in terms of payload, bandwidth, signature verification etc.


Are there any size restrictions for a single record, or all records in a collection?
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Quotas were not enabled on the server. Therefore, technically you can create records with any size, and have as many as you want in the collection.

**However**, beyond some reasonable size for the whole collection serialized as JSON, it is recommended using our :ref:`attachments feature <tutorial-attachments>`.

Using attachments on records, you can publish data of any size (as JSON, gzipped, etc.). It gets published on S3 and the records only contain metadata about the remote file (including hash, useful for signature verification).


Also does remote settings do any sort of compression for the records?
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

We are working on improving the handling of Gzip encoding for the attachments files (see `Bug 1339114 <https://bugzilla.mozilla.org/show_bug.cgi?id=1339114>`_).

But by default, Remote Settings does not try to be smart regarding compression.


Is it possible to deliver remote settings to some users only?
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

By default, settings are delivered to every user.

You can add :ref:`JEXL filters on records <target-filters>` to define targets. Every record will be downloaded but the list obtained with ``.get()`` will only contain entries that match.

In order to limit the users that will download the records, you can check out our :ref:`dedicated tutorial <tutorial-normandy-integration>`.


How does the client choose the collections to synchronize?
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

First, the client fetches the `list of published collections <https://firefox.settings.services.mozilla.com/v1/buckets/monitor/collections/changes/records>`_.

Then, it synchronizes the collections that match one of the following:

* it has an instantiated client — ie. a call to ``RemoteSettings("cid")`` was done earlier
* some local data exists in the internal IndexedDB
* a JSON dump was shipped in mozilla-central for this collection in ``services/settings/dumps/``
