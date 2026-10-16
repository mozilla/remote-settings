.. _architecture-compression-dictionaries:

Compression dictionaries for attachments
========================================

Attachments change incrementally: a new version of a block list or a model is mostly the
same bytes as the previous one. With `Compression Dictionary Transport
<https://datatracker.ietf.org/doc/rfc9842/>`_ (CDT), Firefox offers the version it already
has as a dictionary, and the CDN answers with the new version compressed against it.

.. note::

   This page describes the intended architecture at the level of Remote Settings
   components. Firefox networking internals are out of scope. Filenames, hashes and record
   IDs in the examples are illustrative.

Glossary
--------

Firefox
   The browser and its networking layer. It advertises ``dcz`` support, stores
   dictionaries, sends ``Available-Dictionary``, and decodes ``.dcz`` responses.

Remote Settings client
   The Remote Settings library inside Firefox. It syncs collections, and its
   ``attachments.download(record)`` issues the attachment request. It never sees CDT.

Consumer
   Firefox feature code that calls the Remote Settings client.

CDT (Compression Dictionary Transport)
   The HTTP standard (`RFC 9842 <https://datatracker.ietf.org/doc/rfc9842/>`_) that lets an
   HTTP client (here, Firefox) offer a file it already has as a dictionary, so the server
   can send a newer file compressed using it as the dictionary. Firefox decodes the
   response before the Remote Settings client sees it, so consumers always get the full
   attachment.

Attachment (or full attachment)
   A file published on a record, stored in the attachments bucket as
   ``{bid}/{cid}/{timestamp}--{record-id}--{filename}``. Each update creates a new object;
   earlier versions stay in the bucket.

Dictionary
   A previous version of the same record's attachment, which Firefox already has. The
   server never stores dictionaries as separate files; on the server side they are just
   older attachments in the attachments bucket. The CDN uses ``Use-As-Dictionary`` to tell
   Firefox to keep an attachment as a dictionary, and limits it to the same record with
   ``match="/{bid}/{cid}/*--{record-id}--*"``.

Compressed attachment (``.dcz``)
   The latest attachment compressed with zstd using one dictionary, prefixed with a 40-byte
   header that holds the dictionary's SHA-256. The cronjob builds one per (dictionary,
   attachment) pair for the last ``PREVIOUS_VERSIONS_COUNT`` (default 5) versions. They are
   stored in the compression dictionaries bucket as
   ``cdt/{bid}/{cid}/compressed/target-{attachment}/dcz/from-{dictionary}.dcz``.

``source_sha256``
   GCS metadata on each ``.dcz`` (served as ``x-goog-meta-source_sha256``) holding the
   SHA-256 of the dictionary it was built from. The CDN compares it with Firefox's
   ``Available-Dictionary``.

Compression dictionaries bucket and ``build_compression_dictionaries``
   The GCS bucket and the cronjob command. Despite their names, they hold and build
   compressed attachments, not dictionaries.

How Firefox detects updated collections
---------------------------------------

.. mermaid::
   :align: center

   sequenceDiagram
     participant Autopush
     participant Firefox
     participant CDN as Remote Settings CDN

     alt Push notification
       Autopush->>Firefox: Push: collection changesets
     else On startup, and periodically
       Firefox->>CDN: Fetches collection changesets
       CDN-->>Firefox: Changed collections and timestamps
     end
     Firefox->>CDN: Fetch changed collections
     CDN-->>Firefox: Changesets
     Note over Firefox: Emits 'sync', consumers download attachments

Autopush notifies Firefox when collections change; Firefox also polls the Remote Settings
CDN on startup and periodically. Either way, Firefox fetches the changed collections and
emits a ``sync`` event, and consumers then download the attachments they need.

Attachments from collections without CDT
----------------------------------------

.. mermaid::
   :align: center

   sequenceDiagram
     participant Firefox
     participant CDN as Attachments CDN
     participant Bucket as Attachments bucket

     Firefox->>CDN: Consumer calls attachments.download(record)
     CDN->>Bucket: Cache miss: fetch the full attachment and cache it
     Bucket-->>CDN: Full attachment
     CDN-->>Firefox: Full attachment returned to Firefox

For collections where CDT is not enabled, the consumer's ``attachments.download(record)``
is a plain request to the attachments CDN. On a cache miss, the CDN fetches the full
attachment from the attachments bucket, caches it, and returns it.

No dictionary available
-----------------------

.. mermaid::
   :align: center

   sequenceDiagram
     participant Firefox
     participant CDN as Attachments CDN
     participant Bucket as Attachments bucket

     Firefox->>CDN: attachments.download(record): first download with CDT
     Note right of Firefox: GET, Accept-Encoding: dcz, no Available-Dictionary
     CDN->>Bucket: Cache miss: fetch the full attachment
     Bucket-->>CDN: Full attachment
     CDN-->>Firefox: Full attachment, Use-As-Dictionary
     Note over Firefox: Stores it as this record's dictionary

Firefox has never downloaded this record with CDT, so it has no dictionary to offer.

.. code-block:: http

   GET /main-workspace/product-integrity/1759000000--abc123--list.bin HTTP/2
   Host: firefox-settings-attachments.cdn.mozilla.net
   Accept-Encoding: gzip, br, zstd, dcz

On a cache miss the CDN fetches the full attachment from the attachments bucket and
advertises it as a dictionary for later versions of the same record:

.. code-block:: http

   HTTP/2 200
   Use-As-Dictionary: match="/main-workspace/product-integrity/*--abc123--*", id="1759000000--abc123--list.bin", type=raw

Dictionary available, compressed attachment available
-----------------------------------------------------

.. mermaid::
   :align: center

   sequenceDiagram
     participant Firefox
     participant CDN as Attachments CDN
     participant Dictionaries as compression-dictionaries bucket

     Firefox->>CDN: attachments.download(record)
     Note right of Firefox: Accept-Encoding: dcz, Available-Dictionary, Dictionary-ID
     CDN->>Dictionaries: Cache miss: fetch the .dcz built from Firefox's dictionary
     Dictionaries-->>CDN: Compressed attachment (200, x-goog-meta-source_sha256)
     Note over CDN: Checks it was built from Firefox's dictionary
     CDN-->>Firefox: Compressed attachment (200, Content-Encoding: dcz, Use-As-Dictionary)
     Note over Firefox: Once decoded, the new attachment becomes the next dictionary

The record has a newer attachment, and Firefox offers the previous attachment as its
dictionary. ``Available-Dictionary`` is the SHA-256 of the previous attachment as a
structured-field byte sequence; ``Dictionary-ID`` is the ``id`` from the earlier
``Use-As-Dictionary``.

.. code-block:: http

   GET /main-workspace/product-integrity/1759600000--abc123--list.bin HTTP/2
   Host: firefox-settings-attachments.cdn.mozilla.net
   Accept-Encoding: gzip, br, zstd, dcz
   Available-Dictionary: :pZGm1Av0IEBKARczz7exkNYsZb8LzaMrV7J32a2fFG4=:
   Dictionary-ID: "1759000000--abc123--list.bin"

The cache key includes the dictionary ID and hash. On a miss the CDN rewrites the backend
request to the compression dictionaries bucket (despite the name, it holds compressed
attachments, not dictionaries):

.. code-block:: text

   GET /cdt/main-workspace/product-integrity/compressed/target-1759600000--abc123--list.bin/dcz/from-1759000000--abc123--list.bin.dcz

In the path, ``target-`` is the attachment being requested and ``from-`` is the dictionary
it was compressed with. The object's ``x-goog-meta-source_sha256`` is the hash of that
dictionary ("source" means the dictionary, not the attachment). It matches Firefox's
``Available-Dictionary``, so the CDN returns it as ``dcz``:

.. code-block:: http

   HTTP/2 200
   Content-Encoding: dcz
   Vary: Accept-Encoding, Available-Dictionary
   Cache-Control: public, max-age=31536000, immutable
   Use-As-Dictionary: match="/main-workspace/product-integrity/*--abc123--*", id="1759600000--abc123--list.bin", type=raw

Firefox decodes the ``.dcz`` and stores the resulting full attachment, not the ``.dcz``, as
its next dictionary.

Dictionary available, compressed attachment unavailable
-------------------------------------------------------

.. mermaid::
   :align: center

   sequenceDiagram
     participant Firefox
     participant CDN as Attachments CDN
     participant Dictionaries as compression-dictionaries bucket
     participant Bucket as Attachments bucket

     Firefox->>CDN: attachments.download(record)
     Note right of Firefox: GET, Accept-Encoding: dcz, Available-Dictionary, Dictionary-ID
     CDN->>Dictionaries: Cache miss: fetch the .dcz built from Firefox's dictionary
     Dictionaries-->>CDN: No .dcz for this dictionary, or built from different content (404, or source_sha256 mismatch)
     CDN->>Bucket: Restart once: fetch the full attachment
     Bucket-->>CDN: Full attachment
     CDN-->>Firefox: Full attachment, advertised as the next dictionary (Use-As-Dictionary)

Same request as above, but the rewritten backend request fails in one of two ways:

- ``404``: the cronjob hasn't built this ``.dcz`` yet, or Firefox's dictionary is older
  than the last ``PREVIOUS_VERSIONS_COUNT`` (default 5) versions.
- ``200``, but ``x-goog-meta-source_sha256`` doesn't match Firefox's
  ``Available-Dictionary``: the ``.dcz`` was built from a different attachment with the
  same name.

Either way the CDN restarts once with the fallback flag set and fetches the full attachment
from the attachments bucket under the plain URL's cache key, shared with requests without
CDT (older Firefox versions, the iOS Rust client, other HTTP clients). The response is the
same as in `No dictionary available`_: the full attachment with ``Use-As-Dictionary``.

Building compressed attachments
-------------------------------

.. mermaid::
   :align: center

   sequenceDiagram
     participant Job as build_compression_dictionaries
     participant Writer
     participant Bucket as Attachments bucket
     participant Dictionaries as compression-dictionaries bucket

     Job->>Writer: Determine attachments that need to be compressed
     Writer-->>Job: Records with attachments in CDT-enabled collections
     Job->>Bucket: Fetch latest attachments and their previous versions (dictionaries)
     Bucket-->>Job: Attachments
     Job->>Dictionaries: Upload compressed attachments (.dcz) and manifest.json

The ``build_compression_dictionaries`` cronjob asks the writer for records with
attachments in CDT-enabled collections, fetches each latest attachment and its previous
versions from the attachments bucket, and uploads the missing ``.dcz`` files and a
``manifest.json`` per collection to the compression dictionaries bucket.
