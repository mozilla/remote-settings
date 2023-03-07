Remote Settings
===============

Remote Settings is a Mozilla service that makes it easy to manage evergreen settings data in Firefox. A simple API is available in Firefox for accessing the synchronized data.

https://remote-settings.readthedocs.io
--------------------------------------

.. image:: https://circleci.com/gh/mozilla/remote-settings/tree/main.svg?style=svg
   :target: https://circleci.com/gh/mozilla/remote-settings


Content
-------

This *Remote Settings* repository contains the following:

* ``bin/``: container entry point and script(s)
* ``config/``: example configuration file(s)
* ``docs/``: documentation source files
* ``kinto-remote-settings/``: Kinto plugin specific to Remote Settings
* ``tests/``: browser and integration tests
* ``requirements.in``: Python packages for the service (source of truth for ``requirements.txt``)
* ``requirements-dev.txt``: Python packages for local development and tests
* ``VERSION``: SemVer version number that serves as both the version of the service and the ``kinto-remote-settings`` plugin


Run
---

You need Docker and ``docker-compose``. Ensure `buildkit <https://docs.docker.com/develop/develop-images/build_enhancements/>`_ is enabled on your Docker engine.

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

To have the tests bootstrap themselves (i.e. when ``SKIP_SERVER_SETUP=false``):

- a user account should available with the ability to create users, buckets, and
  collections
- the account should also be able to assign users to groups
- the credentials of this user should be supplied to the container

If the tests should not bootstrap themselves and instead use resources already
available on the server (i.e. when ``SKIP_SERVER_SETUP=true``):

- There should a bucket and collection available
- There should be two users available

  - one user should be added to the ``editor`` group of the available collection
  - the other should be added to the ``reviewer`` group of the available collection

- the names of the bucket, collection, and user credentials should be supplied
  as environment variables to the container

Running integration tests on the Remote Settings dev server should look something like:

.. code-block:: shell

    docker run --rm \
        --env SERVER=https://settings.dev.mozaws.net/v1 \
        --env MAIL_DIR="" \
        --env SKIP_SERVER_SETUP=true \
        --env TO_REVIEW_ENABLED=false \
        --env EDITOR_AUTH=<credentials available in 1Password> \
        --env REVIEWER_AUTH=<credentials available in 1Password> \
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

    docker-compose run tests bash

Now, from that ``bash`` session you can reach the other services like:

.. code-block:: shell

    http http://autograph:8000/__heartbeat__
    http http://web:8888/v1/__heartbeat__


Upgrade Things
--------------

Most common use-case is that you want to upgrade one of the dependencies.

Top level dependencies are listed in ``requirements.in``.

We use `pip-tools's pip-compile <https://pypi.org/project/pip-tools/>`_ command to generate the exhaustive list of pinned dependencies with their hash.

To upgrade a single package, run:

.. code-block:: shell

    pip-compile --upgrade-package kinto-attachment

To test that this installs run:

.. code-block:: shell

    docker-compose build web


About versioning
----------------

We respect `SemVer <http://semver.org>`_ here. However, the "public API" of this package is not the user-facing API of the service itself, but is considered to be the set of configuration and services that this package and its dependencies use. Accordingly, follow these rules:

* **MAJOR** must be incremented if a change on configuration, system, or third-party service is required, or if any of the dependencies has a major increment
* **MINOR** must be incremented if any of the dependencies has a minor increment
* **PATCH** must be incremented if no major nor minor increment is necessary.

In other words, minor and patch versions are uncomplicated and can be deployed automatically, and major releases are very likely to require specific actions somewhere in the architecture.


Releasing
---------

First:

- Make sure the CHANGELOG is up-to-date and includes details about all the components included in the release

.. code-block:: bash

    git checkout -b prepare-X.Y.Z
    prerelease

- At this point, the ``CHANGELOG.rst`` header and version number in ``VERSION`` are set.

.. code-block:: bash

    git commit -a --amend
    git push

- Open a PR, and when the PR is approved:

.. code-block:: bash

    git checkout main
    git pull
    git tag -a X.Y.Z
    git push origin X.Y.Z

- Now prepare the next version:

.. code-block:: bash

    git checkout -b start-X.Y.Z
    git push

- Draft a release on Github: https://github.com/mozilla/remote-settings/releases
  For release notes, just use the CHANGELOG entry for the release, but change all
  the ReST-style section headings to Markdown-style ``##`` headings.


.. note::

    The Mozilla Jenkins job will catch the latest Docker container on Dockerhub
    and immediately deploy it to Remote Settings DEV. It will deploy the latest tag
    on Remote Settings STAGE.
    Integration tests will be executed.
    Results are reported in the Mozilla ``#kinto-standup`` Slack channel.
