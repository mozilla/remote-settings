Support
=======

.. _troubleshooting:

Troubleshooting
---------------

* Open a `Server Side ticket <https://bugzilla.mozilla.org/enter_bug.cgi?product=Cloud%20Services&component=Server%3A%20Remote%20Settings>`_ (Admin, permissions etc.)
* Open a `Client Side ticket <https://bugzilla.mozilla.org/enter_bug.cgi?product=Firefox&component=Remote%20Settings%20Client>`_ (Gecko API related)

Before reaching out in ``#delivery`` on Slack, double-check that your question wasn't already covered here.

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
* Check that your data is visible on the source server: eg. https://prod.remote-settings.prod.webservices.mozgcp.net/v1/buckets/main/collections/cfr/changeset?_expected=something-random-42


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

Alternatively, in order to point STAGE before on fresh profiles for example, you can set the `appropriate preferences <https://github.com/mozilla-extensions/remote-settings-devtools/blob/1.10.0/extension/experiments/remotesettings/api.js#L126-L131>`_ in a ``user.js`` file:

::

    user_pref("services.settings.server", "https://firefox.settings.services.allizom.org/v1");
    user_pref("dom.push.serverURL", "wss://autoconnect.stage.mozaws.net");

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

	curl 'https://remote-settings.allizom.org/v1/' \
	  -H 'Authorization: Bearer r43yt0956u0yj1'


How do I automate the publication of records? (forever)
'''''''''''''''''''''''''''''''''''''''''''''''''''''''

If the automation is meant to last (eg. cronjob, server to server) then the procedure would look like this:

1. Get in touch with us on ``#delivery`` ;)
2. Fork `this repo <https://github.com/leplatrem/remote-settings-cronjob-example>`_ as a base example (or `this Node.js one <https://github.com/firefox-devtools/remote-settings-mdn-browser-compat-data>`_)
3. Rename the repo ``remote-settings-{collection-id}-updater``
4. Request a deployment of your job `using this Bugzilla template <https://bugzilla.mozilla.org/enter_bug.cgi?assigned_to=rmuller%40mozilla.com&bug_ignored=0&bug_severity=--&bug_status=NEW&cf_accessibility_severity=---&cf_fx_iteration=---&cf_fx_points=---&cf_status_conduit_push=---&cf_status_firefox132=---&cf_status_firefox133=---&cf_status_firefox134=---&cf_status_firefox_esr115=---&cf_status_firefox_esr128=---&cf_tracking_conduit_push=---&cf_tracking_firefox132=---&cf_tracking_firefox133=---&cf_tracking_firefox134=---&cf_tracking_firefox_esr115=---&cf_tracking_firefox_esr128=---&cf_tracking_firefox_relnote=---&comment=The%20script%20already%20follows%20%5Bthe%20specifications%5D%28https%3A%2F%2Fremote-settings.readthedocs.io%2Fen%2Flatest%2Fsupport.html%23how-do-i-automate-the-publication-of-records-forever%29%2C%20and%20is%20ready%20to%20be%20deployed.%0D%0A%0D%0A%2A%20Collection%3A%20%20main%2F%7Bcollection-id%7D%0D%0A%2A%20Script%3A%20%20https%3A%2F%2Fgithub.com%2Fmozilla%2F%7Brepo-name%7D%0D%0A%2A%20Frequency%3A%20every%2010min%20%2F%201day%0D%0A%0D%0A----------%0D%0A%0D%0ANotes%20for%20the%20Remote%20Settings%20DEV%20%2F%20SREs%3A%0D%0A%0D%0A1.%20Create%20the%20%60%7Brepo-name%7D-publisher%60%20Kinto%20Account%20on%20the%203%20environments%0D%0A2.%20Add%20the%20credentials%20to%201Password%20%60%7Benv%7D%20-%20%7Baccount%20name%7D%60%0D%0A3.%20Add%20%60account%3A%7Brepo-name%7D-publisher%60%20as%20editor%20for%20this%20collection%20to%20https%3A%2F%2Fgithub.com%2Fmozilla-services%2Fremote-settings-permissions%0D%0A4.%20Create%20the%20cronjob%20on%20the%20%5BRemote%20Settings%20Helm%20chart%5D%28https%3A%2F%2Fgithub.com%2Fmozilla-it%2Fwebservices-infra%2Ftree%2Fmain%2Fremote-settings%2Fk8s%2Fremote-settings%29%0D%0A5.%20Create%20the%20GKE%20secret%20in%20the%20form%20of%20%60%7Benv%7D-gke-cronjob-%7Brepo-name%7D-secrets%60%20with%20payload%20%60%7B%22AUTHORIZATION%22%3A%20%22%7Baccount%7D%3A%7Bpasswd%7D%22%7D%60%0D%0A6.%20Create%20a%20GKE%20event%20router%20secret%20and%20add%20the%20Webhook%20to%20the%20repo%0D%0A7.%20Enable%20building%20and%20publishing%20of%20container%20in%20%5Bcronjobs%20deploy%20repo%5D%28https%3A%2F%2Fgithub.com%2Fmozilla-sre-deploy%2Fdeploy-remote-settings-cronjobs%2Fpull%2F14%29%0D%0A%0D%0A%5BMore%20details%5D%28https%3A%2F%2Fmozilla-hub.atlassian.net%2Fwiki%2Fspaces%2FSRE%2Fpages%2F834961436%2Fcreate%2Ba%2Bremote-settings%2Bcronjob%2Bingestion%2Bpipeline%29%0D%0A%0D%0A&component=Server%3A%20Remote%20Settings&contenttypemethod=list&contenttypeselection=text%2Fplain&defined_groups=1&filed_via=standard_form&flag_type-37=X&flag_type-607=X&flag_type-708=X&flag_type-721=X&flag_type-737=X&flag_type-748=X&flag_type-787=X&flag_type-803=X&flag_type-846=X&flag_type-864=X&flag_type-936=X&flag_type-963=X&flag_type-967=X&needinfo_role=other&needinfo_type=needinfo_from&op_sys=Unspecified&priority=--&product=Cloud%20Services&rep_platform=Unspecified&short_desc=Please%20schedule%20the%20ingestion%20script%20for%20collection%20XXXX&target_milestone=---&version=unspecified>`_

With regards to the script:

- MUST read the following environment variables:

  * ``AUTHORIZATION``: Credentials for building the Authorization Header (passed as ``"Bearer f8435u30596"`` for LDAP OAuth, or as ``"some-user:some-password"`` for Kinto Accounts)
  * ``SERVER``: Writer server URL (eg. ``https://remote-settings.allizom.org/v1``)
  * ``ENVIRONMENT`` (optional): ``dev``, ``stage``, ``prod``
  * ``DRY_RUN`` (optional): do not perform operations if set to ``1``

- MUST exit with a ``0`` for success and a ``1`` if there were any errors.
- MUST be idempotent (ie. no-op if no change)
- MUST output logs to stdout

- CAN request review on the collection (with ``PATCH {"data": {"status": "to-review"}}``)
- CAN self approve changes if ``ENVIRONMENT==dev`` (with ``PATCH {"data": {"status": "to-sign"}}``)

See :ref:`multi-signoff tutorial <tutorial-multi-signoff-request-review>` for more information about requesting and approving review.

With regards to the Github repository:

- MUST build a Docker container
- MUST give admin permissions to `Remote Settings SREs <https://mozilla-hub.atlassian.net/wiki/people/team/11d438c7-c347-4dc8-a25c-984b3d0a8e2d>`_
- MUST have version tag format ``vX.Y.Z``

.. note::

	Even if publication of records is done by a script, a human will have to approve the changes manually.
	Generally speaking, disabling dual sign-off is possible, but only in **very** specific cases.

	If you want to skip manual approval, you will have to request a review of your design by the cloud operations security team.

  They will need answers to the following points:

    - summary / context / problem statement
    - data dictionary (name, private/public, comments)
    - threat scenarios (what impact, what happens if...)
    - `See more details <https://mozilla-hub.atlassian.net/wiki/spaces/SECENGOPS/pages/610074988/How+to+request+start+a+Rapid+Risk+Assessment+RRA>`_

  For the threat scenarios, think of what would be the impact if bad/malicious data is published, in terms of product, integrity, availability (eg. perfs if 100000 items are published), etc...

.. _duplicate_data:

Once data is ready in DEV or STAGE, how do we go live in PROD?
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

Stage and prod are aligned in terms of setup, features and versions.

Hence, once done in DEV or STAGE there is nothing specific / additional to do: you should be able to redo the same in PROD!


If you have a lot of data that you want to duplicate from one instance to another, you can use `kinto-wizard <https://github.com/Kinto/kinto-wizard/>`_ to dump and load records!

.. code-block:: bash

	pip install --user kinto-wizard

Dump the main records from STAGE:

.. code-block:: bash

    kinto-wizard dump --records --server https://firefox.settings.services.allizom.org/v1 --bucket=main --collection=top-sites > top-sites.yaml

Open the ``.yaml`` file and rename the bucket name on top to ``main-workspace``.

Login in the Remote Settings Admin and copy the authentication header (icon in the top bar), in order to use it in the ``--auth`` parameter of the ``kinto-wizard load`` command. And load into PROD:

.. code-block:: bash

    kinto-wizard load --server https://remote-settings.mozilla.org/v1 --auth="Bearer uLdb-Yafefe....2Hyl5_w" top-sites.yaml

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

* Attachments are served using Gzip encoding.
* Records are not (`Due to regression on our GCP setup <https://mozilla-hub.atlassian.net/browse/SE-3468>`_)

Is it possible to deliver remote settings to some users only?
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

By default, settings are delivered to every user.

You can add :ref:`JEXL filters on records <target-filters>` to define targets. Every record will be downloaded but the list obtained with ``.get()`` will only contain entries that match.


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

    const { FilterExpressions } = ChromeUtils.importESModule(
      "resource://gre/modules/components-utils/FilterExpressions.sys.mjs"
    );

    await FilterExpressions.eval("a.b == 1", {a: {b: 1}});

In order to test using a real application context instead of an arbitrary object:

.. code-block:: javascript

    const { ClientEnvironmentBase } = ChromeUtils.importESModule(
      "resource://gre/modules/components-utils/ClientEnvironment.sys.mjs"
    );

    await FilterExpressions.eval("env.locale == 'fr-FR'", {env: ClientEnvironmentBase})
