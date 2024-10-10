.. _tutorial-attachments:

Work with Attachments
=====================

Goals
-----

* Publish large or binary content

Prerequisites
-------------

This guide assumes that you have already installed the following commands:

- cURL
- uuidgen
- `jq <https://stedolan.github.io/jq/>`_ (*optional*)

And that you are familiar with the Remote Settings API, at least on the dev server.

We'll refer the running instance as ``$SERVER`` (eg. ``https://remote-settings-dev.allizom.org/v1``).


Introduction
------------

Files can be attached to records. When a record has a file attached to it, it has an ``attachment`` attribute, which contains the file related information (url, hash, size, mimetype, etc.).

The Remote Settings client API is **not in charge** of downloading the remote files during synchronization.

However, a `helper is available <https://firefox-source-docs.mozilla.org/services/settings/#file-attachments>`_ on the client instance.

During synchronization, only the records that changed are fetched. Depending on your implementation, attachments may have to be redownloaded completely even if only a few bytes were changed.


Publish records with attachments
--------------------------------

Files can be attached to existing records or records can be created when uploading the attachment.

Suppose that we want to attach a file (``/home/mathieu/DAFSA.bin``) to the existing record ``bec3e95c-4d28-40c1-b486-76682962861f``:

.. code-block:: bash

    BUCKET=main-workspace # (or just ``main`` in Dev)
    COLLECTION=public-suffix-list
    RECORD=bec3e95c-4d28-40c1-b486-76682962861f
    FILEPATH=/home/mathieu/DAFSA.bin

    curl -X POST ${SERVER}/buckets/${BUCKET}/collections/${COLLECTION}/records/${RECORD}/attachment \
         -H 'Content-Type:multipart/form-data' \
         -F attachment=@$FILEPATH \
         -u user:pass

And in order to create a record with both attributes and attachment, you'll have a generate a record id yourself.

.. code-block:: bash

    RECORD=`uuidgen`

    curl -X POST ${SERVER}/buckets/${BUCKET}/collections/${COLLECTION}/records/${RECORD}/attachment \
         -H 'Content-Type:multipart/form-data' \
         -F attachment=@$FILEPATH \
         -F 'data={"name": "Mac Fly", "age": 42}' \
         -u user:pass

.. note::

    Since the dev server is open to anyone and runs on ``.allizom.org``, we only allow certain types of files (images, audio, video, archives, ``.bin``, ``.json``, ``.gz``).

    If you need to upload files with a specific extension, let us know and we will add it to the whitelist (except ``.html``, ``.js``).


Synchronize attachments
-----------------------

Attachments can be downloaded when the ``"sync"`` event is received.

.. code-block:: bash

    const client = RemoteSettings("a-key");

    client.on("sync", async ({ data: { created, updated, deleted } }) => {
      const toDownload = created
        .concat(updated.map(u => u.new))
        .filter(d => d.attachment);

      // Download attachments
      const fileURLs = await Promise.all(
        toDownload.map(entry => client.attachments.download(entry, { retries: 2 }))
      );

      // Open downloaded files...
      const fileContents = await Promise.all(
        fileURLs.map(async url => {
          const r = await fetch(url);
          return r.blob();
        })
      );
    });

See more details in `client documentation <https://firefox-source-docs.mozilla.org/services/settings/#file-attachments>`_.


About compression
-----------------

The server does not compress the files.

We plan to enable compression at the HTTP level (`Bug 1339114 <https://bugzilla.mozilla.org/show_bug.cgi?id=1339114>`_) for when clients fetch the attachment using the ``Accept-Encoding: gzip`` request header.


In the admin tool
-----------------

The Remote Settings administration tool supports attachments as well. If a collection has a record schema and attachments are "enabled" for that collection, then editors will be able to upload attachments as part of editing records.

The controls for attachments in a given collection are in the ``attachment`` field in the collection metadata (probably located in the `remote-settings-permissions <https://github.com/mozilla-services/remote-settings-permissions>`_ repo). The ``attachment`` attribute should be an object and it can have the following properties:

- ``enabled``: boolean, true to enable attachments for this collection
- ``required``: boolean, true if records in this collection must have an attachment
