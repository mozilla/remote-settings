Kinto Distribution
==================

.. image:: https://circleci.com/gh/mozilla-services/kinto-dist/tree/main.svg?style=svg
   :target: https://circleci.com/gh/mozilla-services/kinto-dist

This repository contains:

1. A set requirements file that combines all packages needed
   to run a Kinto server with a known good set of dependencies.
2. An example configuration file to run it.

**The most important function of this repository is to build a Docker image
with a set of known working dependencies and then ship that to DockerHub.**

Test Locally
------------

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

If it fails because ``pip`` believes your new package has other dependencies
not already mentioned in ``requirements/constraints.txt`` add them like this:

.. code-block:: shell

    $ hashin -r requirements/constraints.txt imneedy alsoneeded

And finally, run ``docker-compose build web`` again.


About versioning
----------------

We respect `SemVer <http://semver.org>`_ here. However, the "public API" of this package is not the user-facing API of the service itself, but is considered to be the set of configuration and services that this package and its dependencies use. Accordingly, follow these rules:

* **MAJOR** must be incremented if a change on configuration, system, or third-party service is required, or if any of the dependencies has a major increment
* **MINOR** must be incremented if any of the dependencies has a minor increment
* **PATCH** must be incremented if no major nor minor increment is necessary.

In other words, minor and patch versions are uncomplicated and can be deployed automatically, and major releases are very likely to require specific actions somewhere in the architecture.



Pull requests
-------------

All PRs should be merged via the `bors merge bot <https://bors.tech>`_. Bors
will automate that the requirements for a PR have been met, and will then
merge the PR in an orderly fashion.

Only users with write access to the repository may use bors. Other users will
get an error message. To use bors to merge a PR, leave a comment that
includes a line such as::

    bors r+

Alternatively, you can list the user that approved the PR, which could be
someone else, or multiple people, such as one of the following::

    bors r= @alex
    bors r= @bob, @carol

If a PR should not be merged, for example because it is a work-in-progress,
then add the label ``bors-dont-merge`` to the PR. This will prevent bors from
merging the PR, even if it is ``r+``ed. To allow bors to merge the PR again,
remove the label and say ``bors r+`` again.

It is possible to temporarily delegate permission to a user to approve a
particular PR. For example, if the PR is documentation for the ops team, you
could grant merge access to the ops engineer reviewing the documentation.
Note that delegating to a use that already has permission (such as an admin
of the repo) has no affect. To do so, use a command such as::

    bors delegate= @ops-dave

If a PR failed to merge for an intermittent reason, such as network failure,
you can instruct bors to try to merge the same commit with the same approver
again with the command::

    bors retry

For more details, see `the bors reference docs <https://bors.tech/documentation/>`_

Releasing
---------

We follow the usual ``zest.releaser`` approach for releases.

First:

- Make sure the CHANGELOG is up-to-date and includes details about all the components included in the release

.. code-block:: bash

  $ git checkout -b prepare-X.Y.Z
  $ prerelease

Then:

- Open a PR
- When the PR is approved, merge it using bors

Then:

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

Known Instances
---------------

To know all places where we use ``kinto-dist`` we maintain a list of in a
machine readable file ``Kinto-Instances.yml``.

Use that to update URLs of instances of ``kinto-dist``. It can be leveraged
for automation (e.g. places to upgrade) and auditing.
