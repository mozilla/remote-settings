.. _case-studies:

Case Studies
============

This page (*under construction*) contains some pointers to existing use cases and implementations.


Search configuration
--------------------

The list of search engines is managed via the ``search-config`` collection.


Configuration
'''''''''''''

* A complex JSON schema validates entries (`source <https://searchfox.org/mozilla-central/rev/8a4aa0c699d9ec281d1f576c9be1c6c1f289e4e7/toolkit/components/search/schema/Readme.txt>`__)

* On the server, the group of editors is different from the group of users allowed to approve changes (`permissions <https://github.com/mozilla-services/remote-settings-permissions/blob/master/kinto.prod.yaml#L2560-L2565>`_)


Implementation
''''''''''''''

* Client is initialized from the Search service (`source <https://searchfox.org/mozilla-central/rev/8a4aa0c699d9ec281d1f576c9be1c6c1f289e4e7/toolkit/components/search/components.conf#11-17>`__)

* Initial data is packaged in release, and is loaded on first startup from a call to ``.get()`` (`source <https://searchfox.org/mozilla-central/rev/8a4aa0c699d9ec281d1f576c9be1c6c1f289e4e7/toolkit/components/search/SearchService.jsm#2840-2851>`__)

* A hijack blocklist is managed separately, and the integrity/signature of the local records is verified on each read (`source <https://searchfox.org/mozilla-central/rev/8a4aa0c699d9ec281d1f576c9be1c6c1f289e4e7/toolkit/modules/IgnoreLists.jsm#74-78>`__). A certificate might have to be downloaded if missing/outdated.


Misc
''''

* `searchengine devtools <https://github.com/mozilla-extensions/searchengine-devtools/>`_


HIBP Monitor Breaches
---------------------

The list of websites whose credentials database was leaked is managed via the ``fxmonitor-breaches`` collection.

Automation
''''''''''

* A script pulls from `Have I Been Powned <https://haveibeenpwned.com/>`_ API, and creates the missing records using a Kinto Account, and then requests review (`source <https://github.com/mozilla/blurts-server/blob/c33a85b/scripts/updatebreaches.js>`__)
* This script is ran by OPs as a cron job (`source <https://github.com/mozilla-services/cloudops-infra/blob/4c43e86cf8beabb8fe4fea6871121f867217df5b/projects/firefoxmonitor/k8s/charts/firefoxmonitor/templates/cronjob-load-breaches.yaml#L43>`__, `request ticket <https://bugzilla.mozilla.org/show_bug.cgi?id=1529860>`_)
* A human approves the changes manually


Blocklist
---------

The list of blocked addons is managed via the ``blocklists/addons-bloomfilters``.


Implementation
''''''''''''''

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

Contextual features recommandations is managed via the ``cfr`` collection.


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

Several security related collections are managed in the dedicated ``security-state`` bucket.

Configuration
'''''''''''''

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
