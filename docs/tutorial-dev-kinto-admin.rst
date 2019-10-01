.. _tutorial-dev-kinto-admin:

Kinto Admin Development
=======================

Goals
-----

* Development environment for Kinto Admin
* Connect to a local Remote Settings server
* Contribute patches

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

We'll create a small bash script ``init.sh`` with the following commands:

.. code-block:: bash

    set -e
    set -o pipefail

    SERVER=http://localhost:8888/v1

In the :ref:`prerequisiste tutorial <tutorial-local-server>`, an ``admin`` user was created, as well as the basic buckets. Let's add that to our script:

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

The process for a patch to reach Remote Settings is the following:

* Get the patch merged on Kinto/kinto-admin
* Release a new version of `kinto-admin on NPM <https://www.npmjs.com/package/kinto-admin>`_
* Upgrade the kinto-admin plugin in Kinto (`example PR <https://github.com/Kinto/kinto/pull/2255>`_)
* Release a new version of Kinto
* Upgrade Kinto in `kinto-dist <https://github.com/mozilla-services/kinto-dist/>`_
* Release a new version of kinto-dist
* STAGE is deployed automatically when a new tag of kinto-dist is published
* Request a deployment in PROD on Bugzilla (`example <https://bugzilla.mozilla.org/show_bug.cgi?id=1570037>`_)
