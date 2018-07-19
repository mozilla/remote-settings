.. _tutorial-multi-signoff:

Multi Signoff Workflow
======================

Goals
-----

* Create some records
* Request review
* Preview changes in the browser
* Approve/Decline the changes

Prerequisites
-------------

This guide assumes you have already installed and set up the following:

- cURL
- `jq <https://stedolan.github.io/jq/>`_
- :ref:`a local instance <tutorial-local-server>` with multi signoff enabled
  or access/contact with two users that have permissions on STAGE/PROD

We'll refer the running instance as ``$SERVER`` (eg. ``http://localhost:8888/v1``).

Introduction
------------

Multi signoff basically consists in 3 steps:

1. Editors create/update/delete records on the ``main-workspace`` bucket
2. Editors request review. The changes are automatically published in the ``main-preview`` bucket.
3. Reviewers can configure their browser to preview the changes, and will approve (or decline) the review request. The records are automatically published in the ``main`` bucket.


Create some users
'''''''''''''''''

If you're not using STAGE or PROD, we'll need some ``reviewer`` and ``editor`` users, using the ``admin`` superuser seen in previous tutorials.

.. code-block:: bash

    curl -X PUT ${SERVER}/accounts/editor \
         -d '{"data": {"password": "3d1t0r"}}' \
         -H 'Content-Type:application/json'

    curl -X PUT ${SERVER}/accounts/reviewer \
         -d '{"data": {"password": "r3v13w3r"}}' \
         -H 'Content-Type:application/json'

.. note::

    In STAGE or PROD, humans authenticate via LDAP/OpenID Connect. But scripted/scheduled tasks can have their dedicated account like above. Ask us!


Create a collection
-------------------

The ``main-workspace`` bucket is where every edit happens.

We first have to create a new collection (eg. ``password-recipes``). We'll use the ``editor`` account:

.. code-block:: bash

    curl -X PUT ${SERVER}/buckets/main-workspace/collections/password-recipes \
         -H 'Content-Type:application/json' \
         -u editor:3d1t0r

.. note::

    In PROD, only administrators are allowed to create collections. See `instructions on Mana <https://mana.mozilla.org/wiki/pages/viewpage.action?pageId=66655528>`_.

Now that we created this collection, two groups should have been created automatically. Check their presence and content with:

.. code-block:: bash

    curl -s ${SERVER}/buckets/main-workspace/groups/password-recipes-editors | jq
    curl -s ${SERVER}/buckets/main-workspace/groups/password-recipes-reviewers | jq


Manage reviewers
----------------

Only the members of the ``password-recipes-editors`` group are allowed to request reviews for the records changes.

Only the members of the ``password-recipes-reviewers`` group are allowed to approve/decline them.

We will add our ``reviewer`` user above to the ``password-recipes-reviewers`` group with this `JSON PATCH <https://tools.ietf.org/html/rfc6902>`_ request:

.. code-block:: bash

    curl -X PATCH $SERVER/buckets/main-workspace/groups/password-recipes-reviewers \
         -H 'Content-Type:application/json-patch+json' \
         -d '[{ "op": "add", "path": "/data/members/0", "value": "account:reviewer" }]' \
         -u editor:3d1t0r

.. note::

    When using internal accounts the, user IDs are prefixed with ``account:``. In STAGE/PROD, most user IDs look like this: ``ldap:jdoe@mozilla.com``.


Change records and request review
---------------------------------

.. seealso::

    Check out :ref:`the dedicated screencast <screencasts-modify-request-review>` for the equivalent with the Admin UI!

Create (or update or delete) some records:

.. code-block:: bash

    for i in `seq 1 10`; do
        curl -X POST ${SERVER}/buckets/main-workspace/collections/password-recipes/records \
             -H 'Content-Type:application/json' \
             -d "{\"data\": {\"property\": $i}}" \
             -u editor:3d1t0r
    done

And request review:

.. code-block:: bash

    curl -X PATCH ${SERVER}/buckets/main-workspace/collections/password-recipes \
            -H 'Content-Type:application/json' \
            -d '{"data": {"status": "to-review"}}' \
            -u editor:3d1t0r

At this point the changes were published to the ``main-preview`` bucket, which is publicly readable:

.. code-block:: bash

    curl -s ${SERVER}/buckets/main-preview/collections/password-recipes/records | jq

The collection metadata now contain some signature information:

.. code-block:: bash

    curl -s ${SERVER}/buckets/main-preview/collections/password-recipes | jq .data.signature

The monitor/changes endpoint mentions the new collection ``password-recipes``:

.. code-block:: bash

    curl -s ${SERVER}/buckets/monitor/collections/changes/records | jq


Preview changes in the browser
------------------------------

The following preferences must be changed to the following values in ``about:config``:

* ``services.settings.server`` : ``http://localhost:8888/v1``
* ``services.settings.default_bucket`` : ``main-preview``

.. important::

    Changing the ``default_bucket`` settings currently requires a browser restart. See `Bug 1475487<https://bugzilla.mozilla.org/show_bug.cgi?id=1475487>`_.

From your code, or the browser console, register the new collection by listening to the ``sync`` event and trigger synchronization:

.. code-block:: bash

    const { RemoteSettings } = ChromeUtils.import("resource://services-settings/remote-settings.js", {});

    RemoteSettings("password-recipes").on("sync", ({ data }) => {
      data.current.forEach(r => dump(`${r.property}\n`));
    });

Then force a synchronization manually with:

.. code-block:: javascript

    RemoteSettings.pollChanges();


Approve/Decline changes
-----------------------

.. seealso::

    Check out :ref:`the dedicated screencast <screencasts-approve-review>` for the equivalent with the Admin UI!

Using the ``reviewer`` authentication, change the collection status to either ``to-sign`` (approve) or ``work-in-progress`` (decline).

.. code-block:: bash

    curl -X PATCH ${SERVER}/buckets/main-workspace/collections/password-recipes \
         -H 'Content-Type:application/json' \
         -d '{"data": {"status": "to-sign"}}' \
         -u reviewer:r3v13w3r

At this point the changes were published to the ``main`` bucket, which is publicly readable:

.. code-block:: bash

    curl -s ${SERVER}/buckets/main/collections/password-recipes/records | jq

The main collection metadata now contain some signature information:

.. code-block:: bash

    curl -s ${SERVER}/buckets/main/collections/password-recipes | jq .data.signature

In the browser, the following preferences must be reset to their default value:

* ``services.settings.default_bucket`` : ``main``
