.. _tutorial-dev-server:

Use the Dev Server
==================

Goals
-----

* Discover Remote Settings without VPN
* Create remote records
* Pull them from the server


Prerequisites
-------------

This guide assumes you have already installed and set up the following:

- cURL
- `jq <https://stedolan.github.io/jq/>`_ (*optional*)


Introduction
------------

The DEV server is different from STAGE and PROD:

- it runs the latest version of `Remote Settings <https://github.com/mozilla/remote-settings/>`_
- it is accessible without VPN
- authenticated users are allowed to create collections
- it does not support push notifications

.. note::

    Until November 2021, we were using the Kinto demo server, which had
    no sign-off and was flushed everyday. This DEV instance is now running
    the same configuration as STAGE/PROD.


Obtain credentials
------------------

Until `Bug 1630651 <https://bugzilla.mozilla.org/show_bug.cgi?id=1630651>`_ happens, the easiest way to obtain your OpenID credentials is to use the admin interface.

1. `Login on the Admin UI <AdminUI>`_ using your LDAP identity
2. Copy the authentication header (📋 icon in the top bar)
3. Test your credentials with ``curl``. When reaching out the server root URL with this bearer token you should see a ``user`` entry whose ``id`` field is ``ldap:<you>@mozilla.com``.

.. code-block:: bash

    SERVER=https://settings.dev.mozaws.net/v1
    BEARER_TOKEN="Bearer uLdb-Yafefe....2Hyl5_w"

    curl -s ${SERVER}/ -H "Authorization:${BEARER_TOKEN}" | jq .user


(optional) Create a collection
------------------------------

All PROD collections will be available, with the same permissions and groups memberships.

Choose a name for your settings that makes sense for your use-case and is specific enough (eg. ``focus-search-engines``, not ``search``).

.. code-block:: bash

    CID=focus-search-engines

Using the REST API, we create a collection:

.. code-block:: bash

    curl -X PUT ${SERVER}/buckets/main-workspace/collections/${CID} \
         -H 'Content-Type:application/json' \
         -H "Authorization:${BEARER_TOKEN}"

Now that we created this collection, two groups should have been created automatically. Check their presence and content with:

.. code-block:: bash

    curl -s ${SERVER}/buckets/main-workspace/groups/${CID}-editors | jq
    curl -s ${SERVER}/buckets/main-workspace/groups/${CID}-reviewers | jq

We create a simple record for testing purposes:

.. code-block:: bash

    curl -X POST ${SERVER}/buckets/main-workspace/collections/${CID}/records \
         -d '{"data": {"title": "example"}}' \
         -H 'Content-Type:application/json' \
         -H "Authorization:${BEARER_TOKEN}"

And request a review in order to trigger content signatures:

.. code-block:: bash

    curl -X PATCH ${SERVER}/buckets/main-workspace/collections/${CID} \
         -H 'Content-Type:application/json' \
         -d '{"data": {"status": "to-review"}}' \
         -H "Authorization:${BEARER_TOKEN}"

At this point, the server part is ready: it contains a public **preview** collection with one record. You can fetch its content (records and signature) with:

.. code-block:: bash

    curl ${SERVER}/buckets/main-preview/collections/${CID}/changeset?_expected=0  # arbitrary cache-bust value

And it should be listed in the special endpoint that provides all collections timestamps:

.. code-block:: bash

    curl ${SERVER}/buckets/monitor/collections/changes/records


Prepare the client
------------------

Until `support for the DEV environment <https://github.com/mozilla-extensions/remote-settings-devtools/issues/66>`_ is added to the `Remote Settings dev tools
<https://github.com/mozilla-extensions/remote-settings-devtools/>`_, we'll change the preferences manually.

.. important::

    This is a critical preference, you should use a dedicated Firefox profile for development.

.. code-block:: javascript

    Services.prefs.setCharPref("services.settings.loglevel", "debug");
    Services.prefs.setCharPref("services.settings.server", "https://settings.dev.mozaws.net/v1");
    // Dev collections are signed with the STAGE infrastructure, use STAGE's hash:
    Services.prefs.setCharPref("security.content.signature.root_hash", "3C:01:44:6A:BE:90:36:CE:A9:A0:9A:CA:A3:A5:20:AC:62:8F:20:A7:AE:32:CE:86:1C:B2:EF:B7:0F:A0:C7:45");
    // Prevent packaged dumps to interfere.
    Services.prefs.setBoolPref("services.settings.load_dump", false);
    // The changes are not approved yet, point the client to «preview»
    Services.prefs.setCharPref("services.settings.default_bucket", "main-preview");

From your code, or the browser console, register the new collection by listening to the ``sync`` event:

.. code-block:: bash

    const { RemoteSettings } = ChromeUtils.import("resource://services-settings/remote-settings.js", {});

    const client = RemoteSettings("your-collection-id");

    client.on("sync", ({ data }) => {
      // Dump records titles to stdout
      data.current.forEach(r => dump(`${r.title}\n`));
    });


Synchronize manually
--------------------

Then force a synchronization manually with:

.. code-block:: javascript

    await RemoteSettings.pollChanges();

.. seealso::

    Check out :ref:`the dedicated screencast <screencasts-fetch-local-settings>` for this operation!


Going further
-------------

Now that your client can pull data from the server, you can proceed with more advanced stuff like:

* `Login on the Admin UI <AdminUI>`_ and browse your data
* Create, modify, delete remote records on the server and check out the different ``sync`` event data attributes
* Define a `JSON schema on your collection <http://docs.kinto-storage.org/en/stable/api/1.x/collections.html#collection-json-schema>`_ to validate records and have forms in the Admin UI
* Attach files to your records (see :ref:`tutorial <tutorial-attachments>`)
* Read the multi signoff tutorial (see :ref:`tutorial <tutorial-multi-signoff>`), to add a reviewer to your collection
* Import the data from the STAGE/PROD collection into your DEV (see :ref:`usage of kinto-wizard <duplicate_data>`.)
* If you feel ready, try out the STAGE environment with VPN access, running a :ref:`local server <tutorial-local-server>` etc.


Delete your collection
----------------------

.. code-block:: bash

    curl -X DELETE ${SERVER}/buckets/main-workspace/groups/${CID}-editors -H "Authorization:${BEARER_TOKEN}"
    curl -X DELETE ${SERVER}/buckets/main-workspace/groups/${CID}-reviewers -H "Authorization:${BEARER_TOKEN}"
    curl -X DELETE ${SERVER}/buckets/main-workspace/collections/${CID} -H "Authorization:${BEARER_TOKEN}"
    curl -X DELETE ${SERVER}/buckets/main-preview/collections/${CID} -H "Authorization:${BEARER_TOKEN}"
    curl -X DELETE ${SERVER}/buckets/main/collections/${CID} -H "Authorization:${BEARER_TOKEN}"


.. _AdminUI: https://kinto.dev.mozaws.net/v1/admin/