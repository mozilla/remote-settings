CHANGELOG
#########

This document describes changes between each past release as well as
the version control of each dependency.

0.6.1 (2016-07-13)
==================

Kinto
'''''

**kinto 3.2.1 → 3.2.2**: https://github.com/Kinto/kinto/releases/tag/3.2.2

**Bug fixes**

- Fix bug in object permissions with memory backend (#708)
- Make sure the tombstone is deleted when the record is created with PUT. (#715)
- Bump ``last_modified`` on record when provided value is equal to previous
  in storage ``update()`` method (#713)


0.6.0 (2016-05-25)
==================

This release moves to the Kinto 3 series. This version merges Cliquet
into ``kinto.core`` and all plugins have been updated to work with this
change. This is a change to code structure, but there is a
user-visible change, which is that settings referring to Cliquet
module paths should now be updated to refer to ``kinto.core.`` module
paths. For example::

    kinto.cache_backend = cliquet.cache.postgresql

Should be changed to::

    kinto.cache_backend = kinto.core.cache.postgresql


Kinto
'''''

**kinto 2.1.2 → 3.2.0**: https://github.com/Kinto/kinto/releases/tag/3.2.0

**Protocol**

- Added the ``GET /contribute.json`` endpoint for open-source information (fixes #607)
- Allow record IDs to be any string instead of just UUIDs (fixes #655).

Protocol is now at version **1.7**. See `API changelog <http://kinto.readthedocs.io/en/latest/api/>`_.

**New features**

- Major version update. Merged cliquet into kinto.core. This is
  intended to simplify the experience of people who are new to Kinto.
  Addresses #687.
- Removed ``initialize_cliquet()``, which has been deprecated for a while.
- Removed ``cliquet_protocol_version``. Kinto already defines
  incompatible API variations as part of its URL format (e.g. ``/v0``,
  ``/v1``). Services based on kinto.core are free to use
  ``http_api_version`` to indicate any additional changes to their
  APIs.
- Simplify settings code. Previously, ``public_settings`` could be
  prefixed with a project name, which would be reflected in the output
  of the ``hello`` view. However, this was never part of the API
  specification, and was meant to be solely a backwards-compatibility
  hack for first-generation Kinto clients. Kinto public settings
  should always be exposed unprefixed. Applications developed against
  kinto.core can continue using these names even after they transition
  clients to the new implementation of their service.
- ``kinto start`` now accepts a ``--port`` option to specify which port to listen to.
  **Important**: Because of a limitation in [Pyramid tooling](http://stackoverflow.com/a/21228232/147077),
  it won't work if the port is hard-coded in your existing ``.ini`` file. Replace
  it by ``%(http_port)s`` or regenerate a new configuration file with ``kinto init``.
- Add support for ``pool_timeout`` option in Redis backend (fixes #620)
- Add new setting ``kinto.heartbeat_timeout_seconds`` to control the maximum duration
  of the heartbeat endpoint (fixes #601)

**Bug fixes**

- Fix internal storage filtering when an empty list of values is provided.
- Authenticated users are now allowed to obtain an empty list of buckets on
  ``GET /buckets`` even if no bucket is readable (#454)
- Fix enabling flush enpoint with ``KINTO_FLUSH_ENDPOINT_ENABLED`` environment variable (fixes #588)
- Fix reading settings for events listeners from environment variables (fixes #515)
- Fix principal added to ``write`` permission when a publicly writable object
  is created/edited (fixes #645)
- Prevent client to cache and validate authenticated requests (fixes #635)
- Fix bug that prevented startup if old Cliquet configuration values
  were still around (#633)
- Fix crash when a cache expires setting is set for a specific bucket or collection. (#597)
- Mark old cliquet backend settings as deprecated (but continue to support them). (#596)

- Add an explicit message when the server is configured as read-only and the
  collection timestamp fails to be saved (ref Kinto/kinto#558)
- Prevent the browser to cache server responses between two sessions. (#593)
- Redirects version prefix to hello page when trailing_slash_redirect is enabled. (#700)
- Fix crash when setting empty permission list with PostgreSQL permission backend (fixes Kinto/kinto#575)
- Fix crash when type of values in querystring for exclude/include is wrong (fixes Kinto/kinto#587)
- Fix crash when providing duplicated principals in permissions with PostgreSQL permission backend (fixes #702)
- Add ``app.wsgi`` to the manifest file. This helps address Kinto/kinto#543.
- Fix loss of data attributes when permissions are replaced with ``PUT`` (fixes Kinto/kinto#601)
- Fix 400 response when posting data with ``id: "default"`` in default bucket.
- Fix 500 on heartbeat endpoint when a check does not follow the specs and raises instead of
  returning false.


Kinto-attachment
''''''''''''''''

**kinto-attachment 0.5.0 → 0.7.0**: https://github.com/Kinto/kinto-attachment/releases/tag/0.7.0

**Breaking changes**

- When the gzip option is used during upload, the ``original`` attribute  is now within
  the ``attachment`` information.

**New features**

- Kinto 3.0 compatibility update
- Add a ``kinto.attachment.extra.base_url`` settings to be exposed publicly. (#73)
- Add the gzip option to automatically gzip files on upload (#85)


kinto-amo
'''''''''

**kinto-amo 0.1.0 → 0.2.0**: https://github.com/mozilla-services/kinto-amo/releases/tag/0.2.0

- Kinto 3.0 compatibility update


kinto-changes
'''''''''''''

**kinto-changes 0.2.0 → 0.3.0**: https://github.com/Kinto/kinto-changes/releases/tag/0.3.0

- Kinto 3.0 compatibility update


kinto-signer
''''''''''''

**kinto-signer 0.4.0 → 0.7.0**: https://github.com/Kinto/kinto-signer/releases/tag/0.7.0

**Breaking changes**

- The collection timestamp is now included in the payload prior to signing.
  Old clients won't be able to verify the signature made by this version.

**Bug fixes**

- Do not crash on record deletion if destination was never synced (Kinto/kinto-signer#82)

**New features**

- Raise configuration errors if resources are not configured correctly (Kinto/kinto-signer#88)


kinto-fxa
'''''''''

**cliquet-fxa 1.4.0 → kinto-fxa  2.0.0**: https://github.com/mozilla-services/kinto-fxa/releases/tag/2.0.0

**Breaking changes**

- Project renamed to *Kinto-fxa* to match the rename of ``cliquet`` to
  ``kinto.core``.
- The setting ``multiauth.policy.fxa.use`` must now
  be explicitly set to ``kinto_fxa.authentication.FxAOAuthAuthenticationPolicy``
- Kinto 3.0 compatibility update

**Bug fixes**

- Fix checking of ``Authorization`` header when python is ran with ``-O``
  (ref mozilla-services/cliquet#592)


kinto-ldap
''''''''''

**kinto-ldap 0.1.0**: https://github.com/Kinto/kinto-ldap/releases/tag/0.1.0



0.5.1 (2016-05-20)
==================

**Version control**

- **Cliquet 3.1.5**: https://github.com/mozilla-services/cliquet/releases/tag/3.1.5
- **kinto 2.1.2**: https://github.com/Kinto/kinto/releases/tag/2.1.2


0.5.0 (2016-05-17)
==================

**Version control**

- **Cliquet 3.1.4**: https://github.com/mozilla-services/cliquet/releases/tag/3.1.4
- **kinto 2.1.1**: https://github.com/Kinto/kinto/releases/tag/2.1.1
- **kinto-attachment 0.5.1**: https://github.com/Kinto/kinto-attachment/releases/tag/0.5.1
- **kinto-amo 0.1.1**: https://github.com/mozilla-services/kinto-amo/releases/tag/0.1.1
- **kinto-changes 0.2.0**: https://github.com/Kinto/kinto-changes/releases/tag/0.2.0
- **kinto-signer 0.5.0**: https://github.com/Kinto/kinto-signer/releases/tag/0.5.0
- **cliquet-fxa 1.4.0**: https://github.com/mozilla-services/cliquet-fxa/releases/tag/1.4.0
- **boto 2.40**: http://docs.pythonboto.org/en/latest/releasenotes/v2.40.0.html


0.4.0 (2016-04-27)
==================

**Version control**

- **kinto 2.1.0**: https://github.com/Kinto/kinto/releases/tag/2.10
- **kinto-changes 0.2.0**: https://github.com/Kinto/kinto-changes/releases/tag/0.2.0
- **kinto-signer 0.3.0**: https://github.com/Kinto/kinto-signer/releases/tag/0.3.0


0.3.0 (2016-04-18)
==================

- Fix kinto-attachment bucket setting in configuration example

**Version control**

Dependencies version were updated to:

- **kinto-attachment 0.5.1**: https://github.com/Kinto/kinto-attachment/releases/tag/0.5.1


0.2.0 (2016-03-22)
==================

**Version control**

Dependencies version where updated to:

- **kinto-signer 0.2.0**: https://github.com/Kinto/kinto-signer/releases/tag/0.2.0


0.1.0 (2016-03-11)
==================

**Configuration changes**

- ``kinto.plugins.default_bucket`` plugin is no longer assumed. We invite users
  to check that the ``kinto.plugins.default_bucket`` is present in the
  ``includes`` setting if they expect it. (ref #495)

**Version control**

Dependencies version were updated to:

- **cliquet 3.1.0**: https://github.com/mozilla-services/cliquet/releases/tag/3.1.0
- **kinto 2.0.0**: https://github.com/Kinto/kinto/releases/tag/2.0.0
- **kinto-attachment 0.4.0**: https://github.com/Kinto/kinto-attachment/releases/tag/0.4.0
- **kinto-changes 0.1.0**: https://github.com/Kinto/kinto-changes/releases/tag/0.1.0
- **kinto-signer 0.1.0**: https://github.com/Kinto/kinto-signer/releases/tag/0.1.0
- **cliquet-fxa 1.4.0**: https://github.com/mozilla-services/cliquet-fxa/releases/tag/1.4.0
- **boto 2.39**: https://github.com/boto/boto/releases/tag/2.39.0
