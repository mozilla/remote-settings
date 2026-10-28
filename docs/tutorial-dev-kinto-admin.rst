.. _tutorial-dev-kinto-admin:

Kinto Admin Development
=======================

Goals
-----

* Development environment for Kinto Admin
* Connect to a local Remote Settings server
* Contribute patches
* Ship changes to production

Prerequisites
-------------

This guide assumes you have already installed and set up the following:

- :ref:`tutorial-local-server` with multi-signoff

Kinto Admin
-----------

This part is very classic. We recommend `using NVM <https://github.com/nvm-sh/nvm>`_ in order to have recent versions of Node and NPM.

.. code-block::

    git clone git@github.com:Kinto/kinto-admin.git

    cd kinto-admin/

    npm install
    npm start

The UI should be accessible at http://0.0.0.0:3000

Initialization script
---------------------

Since the container is not configured with a real database by default, the content is flushed on each restart.

This means you will have to populate data regularly.

We'll create a small bash script ``init.sh`` with the following commands:

.. code-block:: bash

    set -e
    set -o pipefail

    SERVER=http://localhost:8888/v1

In the :ref:`prerequisite tutorial <tutorial-local-server>`, an ``admin`` user was created, as well as the basic buckets. Let's add that to our script:

.. code-block:: bash

    curl -X PUT --fail --verbose ${SERVER}/accounts/admin \
         -d '{"data": {"password": "s3cr3t"}}' \
         -H 'Content-Type:application/json'

    BASIC_AUTH=admin:s3cr3t

    curl -X PUT --fail --verbose ${SERVER}/buckets/main-workspace \
         -d '{"permissions": {"collection:create": ["system.Authenticated"], "group:create": ["system.Authenticated"]}}' \
         -H 'Content-Type:application/json' \
         -u $BASIC_AUTH

    curl -X PUT --fail --verbose ${SERVER}/buckets/main-preview \
         -d '{"permissions": {"read": ["system.Everyone"]}}' \
         -H 'Content-Type:application/json' \
         -u $BASIC_AUTH

    curl -X PUT --fail --verbose ${SERVER}/buckets/main \
         -d '{"permissions": {"read": ["system.Everyone"]}}' \
         -H 'Content-Type:application/json' \
         -u $BASIC_AUTH

In order to play with multi-signoff, we'll create an ``editor`` and a ``reviewer`` accounts, put these lines in the ``init.sh`` script.

.. code-block:: bash

    curl -X PUT --fail --verbose ${SERVER}/accounts/editor \
         -d '{"data": {"password": "3d1t0r"}}' \
         -H 'Content-Type:application/json'

    curl -X PUT --fail --verbose ${SERVER}/accounts/reviewer \
         -d '{"data": {"password": "r3v13w3r"}}' \
         -H 'Content-Type:application/json'


Now create a collection, with a dedicated reviewer group:

.. code-block:: bash

    curl -X PUT --fail --verbose ${SERVER}/buckets/main-workspace/collections/password-recipes \
         -H 'Content-Type:application/json' \
         -u editor:3d1t0r


    curl -X PATCH --fail --verbose $SERVER/buckets/main-workspace/groups/password-recipes-reviewers \
         -H 'Content-Type:application/json-patch+json' \
         -d '[{ "op": "add", "path": "/data/members/0", "value": "account:reviewer" }]' \
         -u $BASIC_AUTH

And at last, create some records, request review and approve changes.

.. code-block:: bash

    for i in `seq 1 10`; do
        curl -X POST --fail --verbose ${SERVER}/buckets/main-workspace/collections/password-recipes/records \
             -H 'Content-Type:application/json' \
             -d "{\"data\": {\"property\": $i}}" \
             -u editor:3d1t0r
    done

    curl -X PATCH --fail --verbose ${SERVER}/buckets/main-workspace/collections/password-recipes \
            -H 'Content-Type:application/json' \
            -d '{"data": {"status": "to-review"}}' \
            -u editor:3d1t0r

    curl -X PATCH --fail --verbose ${SERVER}/buckets/main-workspace/collections/password-recipes \
         -H 'Content-Type:application/json' \
         -d '{"data": {"status": "to-sign"}}' \
         -u reviewer:r3v13w3r

    echo ""
    echo "Done."


With the service running locally, populating it should now just consist in running:

.. code-block:: bash

    bash init.sh


Connect Admin UI
----------------

On http://0.0.0.0:3000, when specifying http://0.0.0.0:8888/v1 in the *Server URL*, the option to login with *Kinto Account* should be shown.

Using Container Tabs in Firefox, you can have one tab logged as ``editor`` with password ``3d1t0r`` and another one with ``reviewer`` and ``r3v13w3r``.


Submit Patches
--------------

Development `happens on Github <https://github.com/Kinto/kinto-admin>`_.

How Kinto Admin is packaged
'''''''''''''''''''''''''''

The Admin UI served at ``/v1/admin/`` is included in the server image by downloading a prebuilt release of Kinto Admin, at the version pinned in `kinto-admin/VERSION <https://github.com/mozilla/remote-settings/blob/main/kinto-admin/VERSION>`_:

* ``kinto-admin/VERSION`` holds a Kinto Admin release number, without the ``v`` prefix (eg. ``6.6.0``)
* The ``get-admin`` stage of `RemoteSettings.Dockerfile <https://github.com/mozilla/remote-settings/blob/main/RemoteSettings.Dockerfile>`_ runs `bin/pull-kinto-admin.sh <https://github.com/mozilla/remote-settings/blob/main/bin/pull-kinto-admin.sh>`_, which downloads ``kinto-admin-release.tar`` from the GitHub release ``v$VERSION``
* The assets are served by Kinto's ``kinto.plugins.admin``, which reads them from ``KINTO_ADMIN_ASSETS_PATH``

The tarball is built by Kinto Admin's `release workflow <https://github.com/Kinto/kinto-admin/blob/master/.github/workflows/release.yml>`_ when a ``vX.Y.Z`` tag is pushed, using ``npm run build:kinto-single``. The Kinto Admin bundled in the Kinto Python package is not used.

Shipping a change to production
'''''''''''''''''''''''''''''''

#. **Merge the change** on `Kinto/kinto-admin <https://github.com/Kinto/kinto-admin>`_.
#. **Release Kinto Admin.** Publish a ``vX.Y.Z`` release on `Kinto Admin releases <https://github.com/Kinto/kinto-admin/releases>`_, from the GitHub UI or by pushing a tag (see `Releasing <https://github.com/Kinto/kinto-admin#releasing>`_). Wait until ``kinto-admin-release.tar`` is attached to the release: it takes a few minutes, and the Remote Settings image build fails without it.
#. **Bump the version in Remote Settings.** A `scheduled workflow <https://github.com/mozilla/remote-settings/blob/main/.github/workflows/scheduled.yaml>`_ checks for a new Kinto Admin release daily at 00:00 UTC, and opens a pull-request titled *Update Kinto Admin version to X.Y.Z*. To skip the wait, edit ``kinto-admin/VERSION`` in a pull-request yourself.
#. **Merge the pull-request.** DEV and STAGE are deployed automatically on merges to ``main``.
#. **Check the change on STAGE.** This is the last chance before PROD.
#. **Release Remote Settings.** Publish a new ``vX.Y.Z`` release (see `Releasing <https://github.com/mozilla/remote-settings#releasing>`_). Following our `versioning rules <https://github.com/mozilla/remote-settings#about-versioning>`_, a Kinto Admin minor bump is a Remote Settings minor bump.
#. **Wait for PROD.** STAGE is updated to the release version, and an ArgoCD workflow automatically promotes STAGE to PROD after successful `browser tests <https://github.com/mozilla/remote-settings/tree/main/browser-tests>`_.

For example:

* 2026-10-09: `Kinto Admin v6.6.0 <https://github.com/Kinto/kinto-admin/releases/tag/v6.6.0>`_ was released
* 2026-10-10: the scheduled workflow opened `#1642 <https://github.com/mozilla/remote-settings/pull/1642>`_
* 2026-10-13: #1642 was merged, deploying it to DEV and STAGE
* 2026-10-15: `Remote Settings v43.3.0 <https://github.com/mozilla/remote-settings/releases/tag/v43.3.0>`_ was released and promoted to PROD

Check the deployed version
''''''''''''''''''''''''''

The server exposes the Kinto Admin version in its capabilities:

.. code-block:: bash

    curl -s https://remote-settings-dev.allizom.org/v1/ | jq .capabilities.admin.version
