.. _architecture:

Architecture
============

Remote Settings is a `Kinto <https://github.com/Kinto/kinto>`_ server with Mozilla-specific
plugins, fronted by a CDN, plus two clients: a JavaScript one built into Gecko, and a Rust
one for mobile apps. The main pieces are:

- **Writer**: the Kinto server at ``remote-settings.mozilla.org`` where editors and
  reviewers change data. It implements multi-signoff and content signing, authenticates
  editors through Mozilla SSO, and notifies them by email and Slack as reviews progress.
- **Reader and Remote Settings CDN**: a read-only Kinto deployment, served through a
  Fastly CDN at ``firefox.settings.services.mozilla.com``. Firefox polls it for collection
  changesets.
- **Attachments CDN and buckets**: files attached to records, bundles, and compression
  dictionaries live in three Google Cloud Storage buckets and are served to Firefox
  through a second Fastly CDN.
- **Cronjobs**: scheduled jobs that refresh signatures, build bundles and compressed
  attachments, export data to Git, purge old data, and report on CDN consumption. A
  separate job applies editor and reviewer group memberships from the
  `remote-settings-permissions <https://github.com/mozilla/remote-settings-permissions>`_
  repository. Ingestion jobs owned by other teams run on the same cluster but are not part
  of the system.
- **Git reader**: a read-only service that serves the same data out of a Git repository
  under ``/v2``.
- **Autopush**: notifies Firefox when collections change, so clients do not have to wait
  for their next poll.

System context
--------------

.. mermaid:: architecture/diagrams/system-context.mmd
   :align: center

Containers
----------

.. mermaid:: architecture/diagrams/containers.mmd
   :align: center
   :zoom:

Core cronjobs
-------------

.. mermaid:: architecture/diagrams/cronjobs.mmd
   :align: center

Flows
-----

.. toctree::
   :maxdepth: 1

   architecture/compression-dictionaries
