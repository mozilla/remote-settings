Kinto Distribution
==================

.. image:: https://circleci.com/gh/mozilla-services/kinto-dist/tree/main.svg?style=svg
   :target: https://circleci.com/gh/mozilla-services/kinto-dist

This repository contains:

1. A set requirements file that combines all packages needed to run a Kinto
   server with a known good set of dependencies.
2. Source code for several Kinto plugins that are specific to remote settings.
   These are contained in the ``kinto_remote_settings`` package.
3. An example configuration file to run it.

**The most important function of this repository is to build a Docker image
with a set of known working dependencies and then ship that to DockerHub.**

Test Locally
------------

**Kinto Remote Settings Unit Tests**

To run unit tests, you need Postgres installed and a database ``testdb`` available. This can be created like:

.. code-block:: shell

    $ psql -c "CREATE DATABASE testdb ENCODING 'UTF8' TEMPLATE template0;" -U postgres -h localhost
    $ psql -c "ALTER DATABASE testdb SET TIMEZONE TO UTC;"

You should also install the requirements found in ``dev-requirements.txt``:

.. code-block:: shell

    $ pip install -r dev-requirements.txt

After this setup is complete, run tests with ``pytest``

.. code-block:: shell

    $ pytest kinto_remote_settings


**Integration Tests**

You need Docker and ``docker-compose``. The simplest way to test that
all is working as expected is to run:

.. code-block:: shell

    $ docker-compose run web migrate  # only needed once
    $ docker-compose run tests

.. note:: The ``run web migrate`` command is only needed once, to prime the
          PostgreSQL server. You can flush
          all the Kinto data in your local persistent PostgreSQL with
          ``curl -XPOST http://localhost:8888/v1/__flush__``

That will start ``memcached``, ``postgresql``, ``autograph`` and Kinto (at ``web:8888``)
and lastly the ``tests`` container that primarily
uses ``curl http://web:8888/v1`` to test various things.

When you're done running the above command, the individual servers will still
be running and occupying those ports on your local network. When you're
finished, run:

.. code-block:: shell

    $ docker-compose stop

Debugging Locally (simple)
--------------------------

The simplest form of debugging is to start the Kinto server (with ``uwsgi``,
which is default) in one terminal first:

.. code-block:: shell

    $ docker-compose up web

Now, in a separate terminal, first check that you can reach the Kinto
server:

.. code-block:: shell

    $ curl http://localhost:8888/v1/__heartbeat__
    $ docker-compose run tests

Debugging Locally (advanced)
----------------------------

Suppose you want to play with running the Kinto server, then go into
a ``bash`` session like this:

.. code-block:: shell

    $ docker-compose run --service-ports --user 0 web bash

Now you're ``root`` so you can do things like ``apt-get update && apt-get install jed``
to install tools and editors. Also, because of the ``--service-ports`` if you do
start a Kinto server on ``:8888`` it will be exposed from the host.

For example, instead of starting Kinto with ``uwsgi`` you can start it
manually with ``kinto start``:

.. code-block:: shell

    $ kinto start --ini config/example.ini

Another thing you might want to debug is the ``tests`` container that does
the ``curl`` commands against the Kinto server. But before you do that,
you probably want to start the services:

.. code-block:: shell

    $ docker-compose up web

.. code-block:: shell

    $ docker-compose run tests bash

Now, from that ``bash`` session you can reach the other services like:

.. code-block:: shell

    $ curl http://autograph:8000/__heartbeat__
    $ curl http://web:8000/v1/__heartbeat__


Upgrade Things
--------------

Most common use-case with ``kinto-dist`` is that you want to upgrade one
of the dependencies. 

Top level dependencies are listed in ``requirements.in``.

We use `pip-tools's pip-compile <https://pypi.org/project/pip-tools/>`_ command to generate the exhaustive list of pinned dependencies with their hash.

To upgrade a single package, run:

.. code-block:: shell

    $ pip-compile --upgrade-package pyramid

To test that this installs run:

.. code-block:: shell

    $ docker-compose build web


About versioning
----------------

We respect `SemVer <http://semver.org>`_ here. However, the "public API" of this package is not the user-facing API of the service itself, but is considered to be the set of configuration and services that this package and its dependencies use. Accordingly, follow these rules:

* **MAJOR** must be incremented if a change on configuration, system, or third-party service is required, or if any of the dependencies has a major increment
* **MINOR** must be incremented if any of the dependencies has a minor increment
* **PATCH** must be incremented if no major nor minor increment is necessary.

In other words, minor and patch versions are uncomplicated and can be deployed automatically, and major releases are very likely to require specific actions somewhere in the architecture.


Releasing
---------

We follow the usual ``zest.releaser`` approach for releases.

First:

- Make sure the CHANGELOG is up-to-date and includes details about all the components included in the release

.. code-block:: bash

  $ git checkout -b prepare-X.Y.Z
  $ prerelease

- Bump the ``__version__`` value in ``kinto_remote_settings/__init__.py`` to match the version to be released according to the CHANGELOG

.. code-block:: bash

  $ git commit -a --amend
  $ git push

Then open a PR, and when the PR is approved:

.. code-block:: bash

   $ git checkout main
   $ git pull
   $ release
   $ git checkout -b start-X.Y.Z
   $ postrelease

The Mozilla remote-settings CI will immediately deploy the
newly-tagged version to remote-settings stage and run the QA tests
against it. Results are reported in the Mozilla ``#storage`` channel.

Draft a release on Github:
https://github.com/mozilla-services/kinto-dist/releases . For release
notes, just use the CHANGELOG entry for the release, but change all
the ReST-style section headings to Markdown-style ``##`` headings.

Then:

The "Back to development" commit cannot be pushed to main because we don't allow pushes to main.

You can just throw away the commit (``git reset --hard HEAD^``) but
the next person to touch the changelog will have to introduce a new
heading for the next version. Another option is to push the commit and
have it be reviewed:

.. code-block:: bash

   $ git checkout main

Then:

- Open another PR

Then:

- Create a release on the Github page using the contents of the CHANGELOG as the body
- Open a Bugzilla bug telling ops to deploy the new release
