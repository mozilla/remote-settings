.. _case-studies:

Case Studies
============

Search configuration
--------------------

Configuration
'''''''''''''

* A complex JSON schema validates entries (`source <https://searchfox.org/mozilla-central/rev/8a4aa0c699d9ec281d1f576c9be1c6c1f289e4e7/toolkit/components/search/schema/Readme.txt>`__)

* On the server, the group of editors different from group of users allowed to approve changes (`permissions <https://github.com/mozilla-services/remote-settings-permissions/blob/master/kinto.prod.yaml#L2560-L2565>`_)


Implementation
''''''''''''''

* Client initialization from the Search service (`source <https://searchfox.org/mozilla-central/rev/8a4aa0c699d9ec281d1f576c9be1c6c1f289e4e7/toolkit/components/search/components.conf#11-17>`__)

* Initial data is packaged in release, and is loaded on first startup from a call to ``.get()`` (`source <https://searchfox.org/mozilla-central/rev/8a4aa0c699d9ec281d1f576c9be1c6c1f289e4e7/toolkit/components/search/SearchService.jsm#2840-2851>`__)

* A hijack blocklist is managed separately, and the integrity/signature of the local records is verified on each read (`source <https://searchfox.org/mozilla-central/rev/8a4aa0c699d9ec281d1f576c9be1c6c1f289e4e7/toolkit/modules/IgnoreLists.jsm#74-78>`__). A certificate might have to be downloaded if missing/outdated.


Misc
''''

* `searchengine devtools <https://github.com/mozilla-extensions/searchengine-devtools/>`_


Normandy
--------

* Synchronization happens on first startup because no initial data is packaged:

  - ``Normandy.init()`` in BrowserGlue (`source <https://searchfox.org/mozilla-central/rev/0db73daa4b03ce7513a7dd5f31109143dc3b149e/browser/components/BrowserGlue.jsm#1359-1361>`_)
  - Calling ``.get()`` with implicit ``syncIfEmpty: true`` option will initialize the local DB by synchronizing the collection  for Normandy (`source <https://searchfox.org/mozilla-central/rev/8a4aa0c699d9ec281d1f576c9be1c6c1f289e4e7/toolkit/components/normandy/lib/RecipeRunner.jsm#319-326>`__)

* In order to guarantee that the records are published from Normandy, each record is signed individually on the server side (`source <https://github.com/mozilla/normandy/blob/526eaeb4a5d4e28fd4266e0191557150120d37e7/normandy/recipes/exports.py#L15-L33>`__). Records are published from Django using ``kinto-http.py``, with signoff is disabled.

* Signature verification for the whole collection is done as usual, and the per-record one is verified on read when recipe eligibility is checked (`source <https://searchfox.org/mozilla-central/rev/8a4aa0c699d9ec281d1f576c9be1c6c1f289e4e7/toolkit/components/normandy/lib/RecipeRunner.jsm#519-524>`__)


Misc
''''

* `Poucave checks for Normandy <https://github.com/mozilla-services/poucave/tree/v1.32.0/checks/normandy>`_


HIBP Monitor Breaches
---------------------

Automation
''''''''''

* A script pulls from `Have I Been Powned <https://haveibeenpwned.com/>`_ API, and creates the missing records using a Kinto Account, and then requests review (`source <https://github.com/mozilla/blurts-server/blob/c33a85b/scripts/updatebreaches.js>`__)
* This script is ran by OPs as a cron job (`source <https://github.com/mozilla-services/cloudops-infra/blob/4c43e86cf8beabb8fe4fea6871121f867217df5b/projects/firefoxmonitor/k8s/charts/firefoxmonitor/templates/cronjob-load-breaches.yaml#L43>`__, `request ticket <https://bugzilla.mozilla.org/show_bug.cgi?id=1529860>`_)
* A human approves the changes manually


Blocklist
---------

Addons blocklist implemented using a bloomfilter (`docs <https://github.com/mozilla/addons-server/blob/ac50305b57a67c0e6ccb1ba121f223b007ccba15/docs/topics/blocklist.rst#bloomfilter-records>`_)

* Bloomfilters are published from a Cron job on the addons-server, implementated using raw Python requests (`source <https://github.com/mozilla/addons-server/blob/d94705157627e0ed4b526fd1c9af5dfe7b7d362b/src/olympia/lib/remote_settings.py#L92-L120>`__)

* Incremental updates of bloomfilters are downloaded as binary attachments, full or base + stashes (`source <https://searchfox.org/mozilla-central/rev/8a4aa0c699d9ec281d1f576c9be1c6c1f289e4e7/toolkit/mozapps/extensions/Blocklist.jsm#1423-1456>`__)

* Attachments are stored in IndexedDB thanks to the ``useCache: true`` option (`source <https://searchfox.org/mozilla-central/rev/8a4aa0c699d9ec281d1f576c9be1c6c1f289e4e7/toolkit/mozapps/extensions/Blocklist.jsm#1382-1390>`__)

* When using the attachment IndexedDB cache, attachments can be packaged in release in order to avoid downloading on new profiles initialization. The bloomfilter base attachment is shipped in release along with its record metadata (`source <https://searchfox.org/mozilla-central/rev/8a4aa0c699d9ec281d1f576c9be1c6c1f289e4e7/services/settings/dumps/blocklists/addons-bloomfilters/addons-mlbf.bin.meta.json>`__)

* Attachments are updated in tree regularly using custom code in ``periodic_file_updates.sh`` (`source <https://searchfox.org/mozilla-central/rev/8a4aa0c699d9ec281d1f576c9be1c6c1f289e4e7/taskcluster/docker/periodic-updates/scripts/periodic_file_updates.sh#309-319>`__)

Misc
''''

* `Remote Settings authentication from CLI in Javascript <https://github.com/kewisch/mozblocklist/blob/6d7e0d1be9877dd9a40e7c02c4aba008b8412eee/src/kinto-client.js#L68-L128>`_ (See `Bug 1630651 <https://bugzilla.mozilla.org/show_bug.cgi?id=1630651>`_)


User Journey
------------

Localization
''''''''''''

* Contextual recommandations are published using translatable placeholders or string IDs

::

    "content": {
      "icon": "chrome://browser/skin/notification-icons/block-fingerprinter.svg",
      "text": {
        "string_id": "cfr-doorhanger-fingerprinters-description"
      },
      "layout": "icon_and_message",
      "buttons": {
        "primary": {
          "event": "PROTECTION",
          "label": {
            "string_id": "cfr-doorhanger-socialtracking-ok-button"
          },
          "action": {
            "type": "OPEN_PROTECTION_PANEL"
          }
        },
        ...


* In parallel, localizations are published in a separate collection
* Each locale has its own record, with its ID in the following format `` `cfr-v1-${locale}` `` and a Fluent file attached.
* A specificly instantiated downloader fetches the relevant one and reloads l10n (`source <https://searchfox.org/mozilla-central/rev/8a4aa0c699d9ec281d1f576c9be1c6c1f289e4e7/browser/components/newtab/lib/ASRouter.jsm#302-320>`__)
* This specific record is checked on each load, attachment is downloaded only if updated/missing/corrupted (built-in feature of attachment downloader)


Security State
--------------

* Dedicated bucket in order to have specific content signature certificates

.. code:: javascript

    const OneCRLBlocklistClient = RemoteSettings(
      Services.prefs.getCharPref(ONECRL_COLLECTION_PREF),
      {
        bucketNamePref: ONECRL_BUCKET_PREF,
        lastCheckTimePref: ONECRL_CHECKED_PREF,
        signerName: Services.prefs.getCharPref(ONECRL_SIGNER_PREF),
      }
    );

`source <https://searchfox.org/mozilla-central/rev/8a4aa0c699d9ec281d1f576c9be1c6c1f289e4e7/security/manager/ssl/RemoteSecuritySettings.jsm#325-364>`__


Cert Revocations (CRLite)
'''''''''''''''''''''''''

Certificates revocation list using a bloomfilter.

* Sysops run a scheduled job that pulls data from a Git repo, authenticates using a Kinto account to publish (``account:crlite_publisher``), and approves changes with another one (``account:crlite_reviewer``) (`source <https://github.com/mozilla/crlite/blob/dddf2e9feb149f070fdb3985881cc605b11bb7fe/moz_kinto_publisher/main.py#L279-L340>`__)

* Download of attachments happens sequentially at the end of first sync (*caution*)

* Incremental updates of bloomfilters are downloaded as binary attachments in profile folder (`source <https://searchfox.org/mozilla-central/rev/8a4aa0c699d9ec281d1f576c9be1c6c1f289e4e7/security/manager/ssl/RemoteSecuritySettings.jsm#724-853>`__)

* Poucave check for age of revocations (`source <https://github.com/mozilla-services/poucave/blob/0e695c1b7b0f54c8e486f3e7c22eab772173c081/checks/remotesettings/crlite_filter_age.py>`__).


Intermediates
'''''''''''''

* Download of attachments sequentially at the end of first sync (*caution*)
