.. _deployment:

Deployment
==========

Reader Service
--------------

The *reader* service is made of three components:

- a folder where the Remote Settings Data git repository is checked out
- a Web API service that points to this folder
- a cronjob that regularly pulls the latest data from the Git origin

The reader service has two modes:

- ``SELF_CONTAINED=false`` (*default*): only collection data is served by the Web API. Certificate chains are served from the Autograph CDN and attachments are served from the ``ATTACHMENTS_BASE_URL`` domain.
- ``SELF_CONTAINED=true``: everything is served by the Web API: collection data, certificate chains, attachments. This is relevant when the clients activity must be confined to a single server/domain (eg. on premise instance).


Official Git Repositories
'''''''''''''''''''''''''

- **Production** data: ``git@github.com:mozilla/remote-settings-data.git``
- **Stage** data: ``git@github.com:mozilla/remote-settings-data-stage.git``
- **Dev** data: ``git@github.com:mozilla/remote-settings-data-dev.git``

.. note::

    Using forks of these repositories is possible. However, forks must be kept up-to-date since the
    certificates chains and signatures are short-lived (6 weeks). And modifying data would require
    disabling signature verification on the client.


Official Docker Images
''''''''''''''''''''''

* **Stable**: ``us-docker.pkg.dev/moz-fx-remote-settings-prod/remote-settings-prod/remote-settings-git-reader`` (Published on release tags)
* **Dev**: ``us-docker.pkg.dev/moz-fx-remote-settings-nonprod/remote-settings-stage/remote-settings-git-reader`` (Published on each code change)


Container Entry Points
''''''''''''''''''''''

* ``web`` (*default*): runs the Web API on port ``8000`` with Prometheus metrics on port ``9090``. The following env vars must be set:
  - ``GIT_REPO_PATH``: the path to the checked out git repo folder
  - ``SELF_CONTAINED``: whether to serve everything from the Web API
  - ``ATTACHMENTS_BASE_URL``: the attachments base URL if ``SELF_CONTAINED=false``
  - ``CACHE_CONTROL_SHORT_EXPIRES_SECONDS``: sets the ``cache-control`` response header to ``max-age={value}`` value for volatile endpoints. Default is 60.
  - ``CACHE_CONTROL_LONG_EXPIRES_SECONDS``: sets the ``cache-control`` response header ``max-age={value}`` value for stable/static endpoints. Default is 3600.

* ``gitupdate``: initializes or update the checked out git repo folder. Requires the following settings:
  - ``GIT_REPO_PATH``: the path to the checked out git repo folder
  - ``GIT_REPO_URL``: the Git+SSH origin URL
  - In order to avoid rate limiting with pulling large amounts of files from Git LFS, SSH authentication must be setup. Recommended way is to mount SSH keys into the container at ``/app/.ssh/id_ed25519`` and ``/app/.ssh/id_ed25519.pub``. See git-reader's README for more details.

Liveliness and readiness probe at ``:8000/__lbheartbeat__``.


Kubernetes Shared Volume
''''''''''''''''''''''''

With Kubernetes, the Git repo folder will be checked out in a shared volume (``PersistentVolumeClaim``).


Monitoring
''''''''''

The Web API container exposes two sets of Prometheus metrics:

- ``:8000/__metrics__``: Domain specific metrics (eg. repository read latency, repository age seconds, request summary, etc.)
- ``:9090/``: Low level `Granian metrics <https://github.com/emmett-framework/granian/>_`

All logs are sent to stdout in JSON format.


Support
'''''''

Need help? Found a bug? Reach out in a `Github issue <https://github.com/mozilla/remote-settings/issues/new>`_.


Writer Service
--------------

The *writer* service is made of these components:

- a Web API service
- a PostgreSQL database
- a cache backend (eg. Memcached or Redis)
- a signing service (eg. Autograph)
- a file storage service (eg. GCS or S3)
- a series of cronjobs to refresh signatures, build startup and attachments bundles, export data to a Git repository, purge obsolete data, etc.

Although it would totally be feasible to deploy your own Remote Settings writer instance, we officially don't support it.
