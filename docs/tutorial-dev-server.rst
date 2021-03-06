.. _tutorial-dev-server:

Use the Dev Server
==================

Goals
-----

* Create remote records
* Pull them from the server


Prerequisites
-------------

This guide assumes you have already installed and set up the following:

- cURL
- `jq <https://stedolan.github.io/jq/>`_ (*optional*)


Introduction
------------

Remote Settings is built on top of a project called Kinto. As a
service to the Kinto community, Mozilla hosts a public instance of
Kinto at https://kinto.dev.mozaws.net/v1. Although this server is not
officially maintained and has no official connection with the Remote
Settings project, it can be convenient to use it when exploring Remote
Settings.

Several authentication options are available. We will use local accounts and Basic Auth for the sake of simplicity.

.. warning::

    Since the server is publicly accessible, we flush its content every day. We thus **recommend you to keep the initialization commands in a small shell script**.


Create your account
-------------------

Let's create a user ``alice`` with password ``w0nd3rl4nd``.

.. code-block:: bash

    SERVER=https://kinto.dev.mozaws.net/v1

    curl -X PUT ${SERVER}/accounts/alice \
         -d '{"data": {"password": "w0nd3rl4nd"}}' \
         -H 'Content-Type:application/json'

When reaching out the server root URL with these credentials you should see a ``user`` entry whose ``id`` field is ``account:alice``.

.. code-block:: bash

    BASIC_AUTH=alice:w0nd3rl4nd

    curl -s ${SERVER}/ -u $BASIC_AUTH | jq .user


Create a collection
-------------------

Choose a name for your settings that makes sense for your use-case and is specific enough (eg. ``focus-search-engines``, not ``search``).

.. code-block:: bash

    CID=focus-search-engines

Using the REST API, we create a collection:

.. code-block:: bash

    curl -X PUT ${SERVER}/buckets/main/collections/${CID} \
         -H 'Content-Type:application/json' \
         -u ${BASIC_AUTH}

We create a simple record for testing purposes:

.. code-block:: bash

    curl -X POST ${SERVER}/buckets/main/collections/${CID}/records \
         -d '{"data": {"title": "example"}}' \
         -H 'Content-Type:application/json' \
         -u ${BASIC_AUTH}

At this point, the server part is ready: it contains a public collection with one record. You can fetch its records with:

.. code-block:: bash

    curl ${SERVER}/buckets/main/collections/${CID}/records

And it should be listed in the monitor/changes endpoint:

.. code-block:: bash

    curl ${SERVER}/buckets/monitor/collections/changes/records


Prepare the client
------------------

There is no officially "blessed" way to point the client at the dev
server. Unlike other environments, the `Remote Settings dev tools
<https://github.com/mozilla-extensions/remote-settings-devtools/>`_
cannot be used for this purpose. You can change the
``services.settings.server`` preference if you like, but because the
data in the dev server is not signed, you will get signature
verification errors.

.. important::

    This is a critical preference, you should use a dedicated Firefox profile for development.

From your code, or the browser console, register the new collection by listening to the ``sync`` event:

.. code-block:: bash

    const { RemoteSettings } = ChromeUtils.import("resource://services-settings/remote-settings.js", {});

    const client = RemoteSettings("focus-search-engines");

    // No signature on Dev Server
    client.verifySignature = false;

    client.on("sync", ({ data }) => {
      // Dump records titles to stdout
      data.current.forEach(r => dump(`${r.title}\n`));
    });


Synchronize manually
--------------------

Then force a synchronization manually with:

.. code-block:: javascript

    await RemoteSettings.pollChanges();

.. note::

    Since the developement server is flushed every day, if the client was previously synchronized with data that is not there anymore, the synchronization might fail. You can start from a new profile (``./mach run --temp-profile``) or clear the local state manually (using `Remote Settings DevTools <https://github.com/mozilla/remote-settings-devtools>`_ or `development docs about local data <https://firefox-source-docs.mozilla.org/services/settings/#manipulate-local-data>`_).

.. seealso::

    Check out :ref:`the dedicated screencast <screencasts-fetch-local-settings>` for this operation!


Going further
-------------

Now that your client can pull data from the server, you can proceed with more advanced stuff like:

* `Login on the Admin UI <https://kinto.dev.mozaws.net/v1/admin/>`_ and browse your data
* Create, modify, delete remote records on the server and check out the different ``sync`` event data attributes
* Define a `JSON schema on your collection <http://docs.kinto-storage.org/en/stable/api/1.x/collections.html#collection-json-schema>`_ to validate records and have forms in the Admin UI
* Attach files to your records (see :ref:`tutorial <tutorial-attachments>`)
* If you feel ready, try out the STAGE environment with VPN access, multi signoff (see :ref:`tutorial <tutorial-multi-signoff>`), running a :ref:`local server <tutorial-local-server>` etc.
