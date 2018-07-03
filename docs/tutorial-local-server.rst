Setup a Local Server
====================

Goals
-----

* Run a local server
* Pull data from it
* Setup advanced features like multi signoff and signatures

Prerequisites
-------------

This guide assumes you have already installed and set up the following:

- cURL
- Docker

Introduction
------------

There are several ways to run a local instance of Kinto, the underlying software of Remote Settings.

We will use Docker for the sake of simplicity, but you may find more convenient to `install the Python package for example <http://kinto.readthedocs.io/en/stable/tutorials/install.html#using-the-python-package>`_.


Quick start
-----------

We will run a local container with the minimal configuration. It should be enough to hack on your Remote Settings integration in the plane.
However if your goal is to setup a local server that has the same signoff features as STAGE and PROD, you can continue into the configuration of the next section.

Pull the Docker container:

.. code-block:: bash

    docker pull mozilla/kinto-dist

Create a configuration file ``server.ini`` with the following content:

.. code-block:: ini

    [app:main]
    use = egg:kinto
    kinto.includes = kinto.plugins.admin
                     kinto.plugins.accounts
                     kinto_changes
                     kinto_attachment
                     kinto_signer

    kinto.storage_backend = kinto.core.storage.memory
    kinto.storage_url =
    kinto.cache_backend = kinto.core.cache.memory
    kinto.cache_url =
    kinto.permission_backend = kinto.core.permission.memory
    kinto.permission_url =

    multiauth.policies = account
    multiauth.policy.account.use = kinto.plugins.accounts.authentication.AccountsAuthenticationPolicy
    kinto.userid_hmac_secret = 284461170acd78f0be0827ef514754937474d7c922191e4f78be5c1d232b38c4

    kinto.bucket_create_principals = system.Authenticated
    kinto.account_create_principals = system.Everyone
    kinto.account_write_principals = account:admin

    kinto.experimental_permissions_endpoint = true
    kinto.experimental_collection_schema_validation = true
    kinto.changes.resources = /buckets/main
    kinto.attachment.base_path = /tmp
    kinto.signer.resources = /buckets/main-workspace -> /buckets/main-preview -> /buckets/main
    kinto.signer.group_check_enabled = true
    kinto.signer.to_review_enabled = true
    kinto.signer.signer_backend = kinto_signer.signer.autograph
    kinto.signer.stage.editors_group = {collection_id}-editors
    kinto.signer.stage.reviewers_group = {collection_id}-reviewers
    kinto.signer.autograph.server_url = http://autograph-server:8000
    # Use credentials from https://github.com/mozilla-services/autograph/blob/2bc1af/autograph.yaml#L348-349
    kinto.signer.autograph.hawk_id = normandev
    kinto.signer.autograph.hawk_secret = 3dhoaupudifjjvm7xznd9bn73159xn3xwr77b61kzdjwzzsjts

    [uwsgi]
    wsgi-file = app.wsgi
    enable-threads = true
    http-socket = 0.0.0.0:8888
    processes =  1
    master = true
    module = kinto
    harakiri = 120
    uid = kinto
    gid = kinto
    lazy = true
    lazy-apps = true
    single-interpreter = true
    buffer-size = 65535
    post-buffering = 65535

    [loggers]
    keys = root, kinto

    [handlers]
    keys = console

    [formatters]
    keys = color

    [logger_root]
    level = INFO
    handlers = console

    [logger_kinto]
    level = DEBUG
    handlers = console
    qualname = kinto

    [handler_console]
    class = StreamHandler
    args = (sys.stderr,)
    level = NOTSET
    formatter = color

    [formatter_color]
    class = logging_color_formatter.ColorFormatter


Now, we will run the container with the local configuration file mounted:

.. code-block:: bash

    docker run -v `pwd`/server.ini:/etc/kinto.ini \
               -e KINTO_INI=/etc/kinto.ini \
               -p 8888:8888 \
               mozilla/kinto-dist

Your local instance should now be running at http://localhost:8888/v1 and the Admin UI available at http://localhost:8888/v1/admin/


Create basic objects
''''''''''''''''''''

Let's create an ``admin`` user:

.. code-block:: bash

    SERVER=http://localhost:8888/v1

    curl -X PUT ${SERVER}/accounts/admin \
         -d '{"data": {"password": "s3cr3t"}}' \
         -H 'Content-Type:application/json'

And a ``main`` bucket, that is publicly readable and where authenticated users can create collections:

.. code-block:: bash

    BASIC_AUTH=admin:s3cr3t

    curl -X PUT ${SERVER}/buckets/main \
         -d '{"permissions": {"read": ["system.Everyone"], "collection:create": ["system.Authenticated"]}}' \
         -H 'Content-Type:application/json' \
         -u $BASIC_AUTH

Now your local server will roughly behave like the dev server, you can jump to :ref:`the other tutorial` in order to create remote records and synchronize locally.


Configure multi-signoff
-----------------------

In this section, we will have a local setup that enables multi-signoff and interacts with an `Autograph instance <https://github.com/mozilla-services/autograph/>`_ in order to sign the data.

First, run the Autograph container in a separate terminal:

.. code-block:: bash

    docker run --name autograph-server mozilla/autograph

And run the remote settings server with a link to ``autograph-server`` container:

.. code-block:: bash

    docker run -v `pwd`/server.ini:/etc/kinto.ini \
               --link autograph-server:autograph-server \
               -e KINTO_INI=/etc/kinto.ini \
               -p 8888:8888 \
               mozilla/kinto-dist

Both containers should be connected, and the heartbeat endpoint should only return positive checks:

.. code-block:: bash

    curl http://localhost:8888/v1/__heartbeat__

    {"attachments":true, "cache":true, "permission":true, "signer": true, "storage":true}

In the previous section we were using the ``main`` bucket directly, but in this setup, we will create the collections in the ``main-workspace`` bucket. Data will be automatically copied to the ``main-preview`` and ``main`` when requesting review and approving changes during the multi-signoff workflow.

We'll use the same ``admin`` user:

.. code-block:: bash

    curl -X PUT ${SERVER}/accounts/admin \
         -d '{"data": {"password": "s3cr3t"}}' \
         -H 'Content-Type:application/json'

The ``main-workspace`` bucket allows any authenticated user to create collections (like on STAGE):

.. code-block:: bash

    BASIC_AUTH=admin:s3cr3t

    curl -X PUT ${SERVER}/buckets/main-workspace \
         -d '{"permissions": {"collection:create": ["system.Authenticated"], "group:create": ["system.Authenticated"]}}' \
         -H 'Content-Type:application/json' \
         -u $BASIC_AUTH

The ``main-preview`` and ``main`` buckets are (re)initialized with read-only permissions:

.. code-block:: bash

    curl -X PUT ${SERVER}/buckets/main-preview \
         -d '{"permissions": {"read": ["system.Everyone"]}}' \
         -H 'Content-Type:application/json' \
         -u $BASIC_AUTH

    curl -X PUT ${SERVER}/buckets/main \
         -d '{"permissions": {"read": ["system.Everyone"]}}' \
         -H 'Content-Type:application/json' \
         -u $BASIC_AUTH


Prepare the client
------------------

The following preferences must be changed to the following values in ``about:config``:

* ``services.settings.server`` : ``http://localhost:8888/v1``

.. note::

    Since we now sign the data locally, the ``services.settings.verify_signature`` preference must be left to its default value (``true``).


What's next?
------------

- Create a collection in the ``main-workspace`` bucket
- Assign users to editors and reviewers groups
- Create records, request review, preview changes in the browser, approve the changes

We cover that in :ref:`the dedicated multi-signoff tutorial <tutorial-multi-signoff>`.
