.. _architecture:

Architecture
============

Remote Settings is a `Kinto <https://github.com/Kinto/kinto>`_ server with Mozilla-specific
plugins, fronted by a CDN, plus a client built into Firefox. The main pieces are:

- **Writer**: the Kinto server where editors and reviewers change data. It implements
  multi-signoff and content signing.
- **Remote Settings CDN**: a Fastly CDN in front of the read-only server. Firefox polls it
  for collection changesets.
- **Attachments CDN and buckets**: files attached to records are stored in Google Cloud
  Storage and served to Firefox through a second Fastly CDN.
- **Cronjobs**: scheduled jobs that refresh signatures, build bundles and compressed
  attachments, export data to Git, and so on.
- **Git reader**: a read-only service that serves the same data out of a Git repository
  under ``/v2``.
- **Autopush**: notifies Firefox when collections change, so clients do not have to wait
  for their next poll.

The pages below walk through specific flows. Their diagrams are generated at build time
from a `Structurizr <https://structurizr.com>`_ model kept in
``docs/architecture/workspace.dsl``. The diagrams are interactive: double-click an element
to navigate, use the mouse wheel to zoom, and ``i`` to show the key.

.. toctree::
   :maxdepth: 1

   architecture/compression-dictionaries
