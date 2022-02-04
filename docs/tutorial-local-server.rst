.. _tutorial-local-server:

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


Simple Mode (testing)
---------------------

We will run a local container with the minimal configuration. It should be enough to hack on your Remote Settings integration in the plane.
However if your goal is to setup a local server that has the same signoff features as STAGE and PROD, you can continue into the configuration of the next section.

Pull the Docker container:

.. code-block:: bash

    docker pull mozilla/remote-settings

Create a local folder to receive the potential records attachments, Docker should have the permissions to write it:

.. code-block:: bash

    mkdir -m 777 attachments  # world writable

Now, we will run the container with the local configuration file and attachments folder mounted:

.. code-block:: bash

    docker run -v `pwd`/attachments:/tmp/attachments \
               -e KINTO_INI=config/testing.ini \
               -p 8888:8888 \
               mozilla/remote-settings

Your local instance should now be running at http://localhost:8888/v1 and the Admin UI available at http://localhost:8888/v1/admin/

With this configuration, this local server will roughly behave like the DEV server, but without authentication and with a dummy multi-signoff system.

You can now jump to :ref:`the other tutorial <tutorial-dev-server>` in order to create remote records and synchronize locally.


With Multi-signoff (advanced)
-----------------------------

Using a different configuration, we can obtain a local instance that has proper authentication and multi-signoff that interacts with an `Autograph instance <https://github.com/mozilla-services/autograph/>`_ in order to sign the data, roughly like the STAGE server.

We will run the Autograph container in a separate terminal. Since Autograph generates the ``x5u`` certificate chains on startup, we will use a volume mounted on the same location, so that Firefox can download them at the same location as the native ``x5u`` URLs (Autograph will point ``x5u`` URLs to ``file:///tmp/attachments``).

.. code-block:: bash

    mkdir -m 777 /tmp/attachments  # world writable

.. code-block:: bash

    docker run -v /tmp/attachments:/tmp/attachments \
               --rm --name autograph mozilla/autograph

And run the Remote Settings server with a link to ``autograph`` container:

.. code-block:: bash

    docker run --link autograph:autograph \
               -e KINTO_INI=config/local.ini \
               -p 8888:8888 \
               mozilla/remote-settings

Both containers should be connected, and the heartbeat endpoint should only return positive checks:

.. code-block:: bash

    curl http://localhost:8888/v1/__heartbeat__

    {"attachments":true, "cache":true, "permission":true, "signer": true, "storage":true}

Unlike with *Simple Mode*, we'll need an ``admin`` user:

.. code-block:: bash

    curl -X PUT ${SERVER}/accounts/admin \
         -d '{"data": {"password": "s3cr3t"}}' \
         -H 'Content-Type:application/json'

.. note::

    Another option is to clone the `mozilla/remote-settings <https://github.com/mozilla/remote-settings>`_ repository and run ``make start``


Prepare the client
------------------

The official way to point the client at another server is using the
`Remote Settings dev tools
<https://github.com/mozilla-extensions/remote-settings-devtools>`_. This
tool can set the constellation of preferences necessary to operate
correctly with your local server.

.. seealso::

    Check out :ref:`the dedicated screencast <screencasts-fetch-local-settings>` for this operation!

What's next?
------------

- Create a collection in the ``main-workspace`` bucket
- Assign users to editors and reviewers groups
- Create records, request review, preview changes in the browser, approve the changes

We cover that in :ref:`the dedicated multi-signoff tutorial <tutorial-multi-signoff>`.
