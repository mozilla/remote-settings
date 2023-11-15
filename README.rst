Remote Settings
===============

Remote Settings is a Mozilla service that makes it easy to manage evergreen settings data in Firefox. A simple API is available in Firefox for accessing the synchronized data.

https://remote-settings.readthedocs.io
--------------------------------------

.. image:: https://img.shields.io/badge/Status-Sustain-green

Content
-------

This *Remote Settings* repository contains the following files and directories of note:

* ``bin/``: container entry point and script(s)
* ``config/``: example configuration file(s)
* ``docs/``: documentation source files
* ``kinto-remote-settings/``: Kinto plugin specific to Remote Settings
* ``tests/``: browser and integration tests
* ``pyproject.toml``: contains dependency information and (most) config settings
* ``VERSION``: SemVer version number that serves as both the version of the service and the ``kinto-remote-settings`` plugin

Setup
-----

You will need:

- Docker
- ``docker-compose`` with `buildkit <https://docs.docker.com/develop/develop-images/build_enhancements/>`_ enabled
- `poetry <https://python-poetry.org/>`_
- `Make <https://www.gnu.org/software/make/>`_

Usage
-----

.. code-block:: shell

    make start

Your *Remote Settings* instance is now ready at http://localhost:8888. See the `*Setup a Local Server* <https://remote-settings.readthedocs.io/en/latest/tutorial-local-server.html>`_ tutorial for more details.


Test Locally
------------

**Kinto Remote Settings Unit Tests**

To run unit tests, you need Postgres installed and a database ``testdb`` available. This can be created with:

.. code-block:: shell

    make build-db

After this setup is complete, tests can be run with ``pytest`` using ``make``:

.. code-block:: shell

    make test


**Integration & Browser Tests**

With Docker and docker-compose, test that all components are working as expected with:

.. code-block:: shell

    make build
    make integration-test
    make browser-test

.. note::

    The ``docker-compose run web migrate`` command is only needed once, to prime the
    PostgreSQL server (this is done automatically for you in the make command).
    You can flush all the Kinto data in your local persistent PostgreSQL with
    ``curl -XPOST http://localhost:8888/v1/__flush__``

That will start ``memcached``, ``postgresql``, ``autograph`` and Kinto (at ``web:8888``)
and lastly the ``tests`` container that primarily
uses ``pytest`` to test various things against ``http://web:8888/v1``.

When you're done running the above command, the individual servers will still
be running and occupying those ports on your local network. When you're
finished, run:

.. code-block:: shell

    make stop


Test Remote Server
------------------

Integration tests can be executed on a remote server.

To run the integration test suite, first build the integration tests container

.. code-block:: shell

    docker-compose build tests

or download a pre-built container from `Dockerhub <https://hub.docker.com/r/mozilla/remote-settings-integration-tests>`_.

Next run the tests, supplying config values as necessary. Config values are
set as environment variables provided to the Docker container. See
``tests/conftest.py`` for descriptions of all of the config options that are
available.

Note that the tests assume that the server has the ``attachments``,
``changes``, ``history``, and ``signer`` plugins enabled. It may optionally
have the ``email`` plugin installed.

To have the tests bootstrap themselves (i.e. when ``SKIP_SERVER_SETUP=false``),
the credentials passed in ``SETUP_AUTH`` should have the permission to create
users, buckets, and collections. These credentials will be in the form
``SETUP_AUTH=username:password`` or ``SETUP_AUTH="Bearer some_token"``

If the tests should not bootstrap themselves and instead use resources already
available on the server (i.e. when ``SKIP_SERVER_SETUP=true``):

- There should be a bucket and collection available

  - the bucket, if not specified by the ``BUCKET`` config option, should be named ``main-workspace``
  - the collection, if not specified by the ``COLLECTION`` config option, should be named ``integration-tests``

- There should be two users available

  - one user should be added to the ``editors`` group of the available collection
  - the other should be added to the ``reviewers`` group of the available collection
  - the credentials of these users should be passed in the ``EDITOR_AUTH`` and
    ``REVIEWER_AUTH`` config options respectively

Running integration tests on the Remote Settings DEV server should look something like:

.. code-block:: shell

    docker run --rm \
        --env SERVER=https://remote-settings-dev.allizom.org/v1 \
        --env MAIL_DIR="" `#disables test cases related to emails` \
        --env SKIP_SERVER_SETUP=true \
        --env TO_REVIEW_ENABLED=false \
        --env EDITOR_AUTH=<username:password, credentials available in 1Password> \
        --env REVIEWER_AUTH=<username:password, available in 1Password> \
    remotesettings/tests integration-test



Debugging Locally (simple)
--------------------------

The simplest form of debugging is to run a suite of tests against the Kinto server:

.. code-block:: shell

    make integration-test
    make browser-test

Debugging Locally (advanced)
----------------------------

Suppose you want to play with running the Kinto server, then go into
a ``bash`` session like this:

.. code-block:: shell

    docker-compose run --service-ports --user 0 web bash

Now you're ``root`` so you can do things like ``apt-get update && apt-get install jed``
to install tools and editors. Also, because of the ``--service-ports`` if you do
start a Kinto server on ``:8888`` it will be exposed from the host.

For example, instead of starting Kinto with ``uwsgi`` you can start it
manually with ``kinto start``:

.. code-block:: shell

    kinto start --ini config/local.ini

Another thing you might want to debug is the ``tests`` container that tests
against the Kinto server.

.. code-block:: shell

    docker-compose run --rm tests bash

Now, from that ``bash`` session you can reach the other services like:

.. code-block:: shell

    http http://autograph:8000/__heartbeat__
    http http://web:8888/v1/__heartbeat__


Upgrade Things
--------------

Dependabot is enabled on this repository, so it should keep dependencies up to date.

To manually edit dependency versions, use `standard poetry commands <https://python-poetry.org/docs/master/managing-dependencies/>`_. Because our
usecase is somewhat complex with multiple groups and some dependencies appearing
in multiple groups, sometimes the easiest way to update packages is to edit
``pyproject.toml`` to the specified package version, then run:

.. code-block:: shell

    poetry lock --no-update

to update the lockfile.

To test that this installs run:

.. code-block:: shell

    make install


About versioning
----------------

We respect `SemVer <http://semver.org>`_ here. However, the "public API" of this package is not the user-facing API of the service itself, but is considered to be the set of configuration and services that this package and its dependencies use. Accordingly, follow these rules:

* **MAJOR** must be incremented if a change on configuration, system, or third-party service is required, or if any of the dependencies has a major increment
* **MINOR** must be incremented if any of the dependencies has a minor increment
* **PATCH** must be incremented if no major nor minor increment is necessary.

In other words, minor and patch versions are uncomplicated and can be deployed automatically, and major releases are very likely to require specific actions somewhere in the architecture.


Releasing
---------

1. Go to project's releases on Github https://github.com/mozilla/remote-settings/releases
2. Publish a new release and tag ``vX.Y.Z``, using autogenerated changelog
3. Watch for deployment notifications in the Mozilla ``#kinto-standup`` Slack channel.

In order to deploy manually (eg. to production):

1. Go to [deployment workflow page](https://github.com/mozilla-sre-deploy/deploy-remote-settings/actions/workflows/gcp.yaml)
2. Click on `Run workflow`
3. Pick `Branch=main`, `Environment=prod`, `ref=vX.Y.Z`, and click `Run workflow`

See `Environments <https://remote-settings.readthedocs.io/en/latest/getting-started.html#environments>`_ section for more details about deployments.
