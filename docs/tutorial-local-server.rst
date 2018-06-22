Using a Local Server
====================

Goals
-----

* Run a local server
* Pull data from it
* Setup advanced features like multi signoff and signatures


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

Create a folder with your configuration file:

.. code-block:: bash

    mkdir rsconf/
    touch rsconf/server.ini

Edit the ``server.ini`` file to add the following:

.. code-block:: ini

    [app:main]
    use = egg:kinto
    kinto.includes = kinto.plugins.admin
                     kinto.plugins.accounts
                     kinto_changes
                     kinto_attachment

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

    [uwsgi]
    wsgi-file = app.wsgi
    enable-threads = true
    http-socket = 0.0.0.0:8888
    processes =  3
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
    plugin = python


Now, we will run the container with a mounted folder on the local ``rsconf/`` one so that the configuration file gets loaded.

.. code-block:: bash

    sudo docker run -v `pwd`/rsconf:/etc/rsconf \
                -e KINTO_INI=/etc/rsconf/server.ini \
                -p 8888:8888 \
                mozilla/kinto-dist

Your local instance should now be running at http://localhost:8888/v1

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

    curl -X PUT ${SERVER}/buckets/main \
         -d '{"permissions": {"read": ["system.Everyone"], "collection:create": ["system.Authenticated"]}}' \
         -H 'Content-Type:application/json' \
         -u admin:s3cr3t

Now your local server will roughly behave like the dev server, you can jump to :ref:`the other tutorial` in order to create remote records and synchronize locally.


Configure multi-signoff
-----------------------

*TBD*
