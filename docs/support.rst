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

.. note::

    On Beta and Release, you have to run Firefox with the environment variable ``MOZ_REMOTE_SETTINGS_DEVTOOLS=1`` to toggle environments. 

Alternatively, in order to point STAGE before on fresh profiles for example, you can set the `appropriate preferences <https://github.com/mozilla/remote-settings-devtools/blob/1.7.0/extension/experiments/remotesettings/api.js#L173-L184>`_ in a ``user.js`` file:

::

    user_pref("services.settings.server", "https://settings.stage.mozaws.net/v1");
    user_pref("dom.push.serverURL", "https://autopush.stage.mozaws.net");

See `developer docs <https://firefox-source-docs.mozilla.org/services/settings/#trigger-a-synchronization-manually>`_ to trigger a synchronization manually.


How do I preview the changes before approving?
''''''''''''''''''''''''''''''''''''''''''''''

The recommended way to setup Firefox to pull data from the preview collection is to use the `Remote Settings DevTools <https://github.com/mozilla/remote-settings-devtools>`_ extension: switch the environment to *Preview* and click the *Sync* button.

.. note::

    On Beta and Release, you have to run Firefox with the environment variable ``MOZ_REMOTE_SETTINGS_DEVTOOLS=1`` to toggle environments. 

See `developer docs about preview mode <https://firefox-source-docs.mozilla.org/services/settings/index.html#preview-mode>`_ for manual toggling. 


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

1. Get in touch with us on ``#delivery`` ;)
2. Fork `this repo <https://github.com/firefox-devtools/remote-settings-mdn-browser-compat-data>`_ as a base example
3. `Request a dedicated Kinto internal account <https://bugzilla.mozilla.org/enter_bug.cgi?product=Cloud%20Services&component=Server%3A%20Remote%20Settings>`_ to be created for you (eg. ``password-rules-publisher``). Secret password should remain in a vault and managed by Ops.
4. Request the Ops team to run your ingestion job (`Bugzilla template <https://bugzilla.mozilla.org/enter_bug.cgi?assigned_to=sven%40mozilla.com&bug_ignored=0&bug_severity=--&bug_status=NEW&cf_fx_iteration=---&cf_fx_points=---&cf_status_firefox100=---&cf_status_firefox98=---&cf_status_firefox99=---&cf_status_firefox_esr91=---&cf_tracking_firefox100=---&cf_tracking_firefox98=---&cf_tracking_firefox99=---&cf_tracking_firefox_esr91=---&cf_tracking_firefox_relnote=---&cf_tracking_firefox_sumo=---&comment=Collection%3A%20%20main%2Fmy-collection%0D%0A%0D%0A%2A%20Account%20was%20created%3A%20Bug%20XXXX%0D%0A%2A%20Account%20is%20listed%20as%20editor%20for%20this%20collection%3A%20https%3A%2F%2Fgithub.com%2Fmozilla-services%2Fremote-settings-permissions%2Fpull%2FXXX%20%0D%0A%0D%0AScript%3A%20%20%20https%3A%2F%2Fgithub.com%2FXXXX%2FYYYY%0D%0A%0D%0A%2A%20Frequency%3A%20Every%20X%20hours%0D%0A%2A%20Contact%20team%3A%20_____%0D%0A%0D%0APlease%20setup%20the%20scheduled%20execution%3A%0D%0A%0D%0A1.%20Configure%20CircleCI%20for%20Docker%20image%20publication%20%28create%20credentials%20and%20repo%20on%20dockerhub%2C%20add%20environment%20secrets%20to%20CircleCI%29%0D%0A2.%20Execute%20the%20docker%20default%20command%20of%20the%20container%2C%20with%20the%20%5Bappropriate%20env%20vars%5D%28https%3A%2F%2Fremote-settings.readthedocs.io%2Fen%2Flatest%2Fsupport.html%23how-do-i-automate-the-publication-of-records-forever%29%0D%0A%0D%0A%0D%0A&component=Server%3A%20Remote%20Settings&contenttypemethod=list&contenttypeselection=text%2Fplain&defined_groups=1&filed_via=standard_form&flag_type-37=X&flag_type-607=X&flag_type-708=X&flag_type-721=X&flag_type-737=X&flag_type-748=X&flag_type-787=X&flag_type-800=X&flag_type-803=X&flag_type-846=X&flag_type-864=X&flag_type-936=X&flag_type-947=X&form_name=enter_bug&maketemplate=Remember%20values%20as%20bookmarkable%20template&op_sys=Unspecified&priority=--&product=Cloud%20Services&rep_platform=Unspecified&short_desc=Please%20schedule%20the%20ingestion%20script%20for%20collection%20XXXX&target_milestone=---&version=unspecified>`_)

With regards to the script:

- MUST read the following environment variables:

  * ``AUTHORIZATION``: Credentials for building the Authorization Header (eg. ``Bearer f8435u30596``, ``some-user:some-password``)
  * ``SERVER``: Writer server URL (eg. ``https://settings-writer.stage.mozaws.net/v1``)
  * ``ENVIRONMENT`` (optional): ``dev``, ``stage``, ``prod``
  * ``DRY_RUN`` (optional): do not perform operations is set to ``1``

- MUST exit with a ``0`` for success and a ``1`` if there were any errors.
- MUST be idempotent (ie. no-op if no change)
- MUST output logs to stdout

- CAN request review on the collection (with ``PATCH {"data": {"status": "to-review"}}``)
- CAN self approve changes if ``ENVIRONMENT==dev`` (with ``PATCH {"data": {"status": "to-sign"}}``)

See :ref:`multi-signoff tutorial <tutorial-multi-signoff-request-review>` for more information about requesting and approving review.

With regards to the repository:

- MUST build a Docker container
- MUST contain a CircleCI configuration that will publish to Dockerhub once credentials are setup by Ops

We recommend the use of `kinto-http.py <https://github.com/Kinto/kinto-http.py>`_ (`script example <https://gist.github.com/leplatrem/f3cf7ac5b0b9b0b27ff6456f47f719ca>`_), but Node JS is also possible (See `mdn-browser-compat-data <https://github.com/firefox-devtools/remote-settings-mdn-browser-compat-data/>`_ or `HIBP <https://github.com/mozilla/blurts-server/blob/c33a85b/scripts/updatebreaches.js>`_ examples).

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

Content is Gzip encoded.


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


How to debug JEXL expressions on records?
'''''''''''''''''''''''''''''''''''''''''

From a browser console, you can debug JEXL expressions using the raw libraries:

.. code-block:: javascript

    const { FilterExpressions } = ChromeUtils.import(
      "resource://gre/modules/components-utils/FilterExpressions.jsm"
    );

    await FilterExpressions.eval("a.b == 1", {a: {b: 1}});

In order to test using a real application context instead of an arbitrary object:

.. code-block:: javascript

    const { ClientEnvironmentBase } = ChromeUtils.import(
      "resource://gre/modules/components-utils/ClientEnvironment.jsm"
    );

    await FilterExpressions.eval("env.locale == 'fr-FR'", {env: ClientEnvironmentBase})
