Kinto Distribution
##################

|travis|

.. |travis| image:: https://travis-ci.org/mozilla-services/kinto-dist.svg?branch=master
    :target: https://travis-ci.org/mozilla-services/kinto-dist


This repository contains:

1. a Pip requirements file that combines all packages needed
   to run a Kinto server with a known good set of dependencies and plugins
2. an example configuration file to run it


Install
=======

To install it on a debian-based linux installation, make sure you have Python 2.x or 3.x with virtualenv, and run::

    $ sudo apt-get install golang postgresql libpq-dev libffi-dev libssl-dev\
                           libsasl2-dev python-dev libldap2-dev
    $ git clone https://github.com/Kinto/kinto-dist.git && cd kinto-dist
    $ sudo -n -u postgres -s -- psql -c "CREATE DATABASE dbname ENCODING 'UTF8' TEMPLATE template0;" -U postgres
    $ sudo -n -u postgres -s -- psql -c "CREATE USER admin WITH PASSWORD 'pass';" -U postgres
    $ sudo -n -u postgres -s -- psql -c "GRANT ALL PRIVILEGES ON DATABASE dbname TO admin;" -U postgres
    $ sudo -n -u postgres -s -- psql -c "ALTER DATABASE dbname SET TIMEZONE TO UTC;" -U postgres
    $ make install

Last, you need to install and run the autograph signature server, whicg requires Golang::

    $ GOPATH=`pwd`/.venv go get github.com/mozilla-services/autograph
    $ .venv/bin/autograph -c .autograph.yml

To run the server::

    $ make serve


About versioning
================

We respect `SemVer <http://semver.org>`_ here. However, the "public API" of this package is not the user-facing API of the service itself, but is considered to be the set of configuration and services that this package and its dependencies use. Accordingly, follow these rules:

* **MAJOR** must be incremented if a change on configuration, system, or third-party service is required, or if any of the dependencies has a major increment
* **MINOR** must be incremented if any of the dependencies has a minor increment
* **PATCH** must be incremented if no major nor minor increment is necessary.

In other words, minor and patch versions are uncomplicated and can be deployed automatically, and major releases are very likely to require specific actions somewhere in the architecture.
