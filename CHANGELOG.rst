CHANGELOG
#########

This document describes changes between each past release as well as
the version control of each dependency.


17.1.3 (2019-07-04)
===================

kinto
-----

**kinto 13.1.1 → 13.2.2**: https://github.com/Kinto/kinto/releases/tag/13.2.2

**Bug fixes**

- Fix apparence of Admin notifications (Kinto/kinto#2191)


17.1.2 (2019-07-03)
===================

**kinto-fxa 2.5.2 → 2.5.3**: https://github.com/Kinto/kinto-fxa/releases/tag/2.5.3

**Optimization**

- Try to keep ``OAuthClient`` around longer to take advantage of HTTP keepalives (Kinto/kinto-fxa#133).


17.1.1 (2019-06-25)
===================

kinto-admin
-----------

**kinto-admin 1.24.0 → 1.24.1**: https://github.com/Kinto/kinto/releases/tag/1.24.1

**Bug fixes**

- Fix #977: Fix copy to clipboard in Firefox (#980)
- Fix #978: Move notifications below header bar (#979)


17.1.0 (2019-06-19)
===================

kinto-admin
-----------

**kinto-admin 1.23.0 → 1.24.0**: https://github.com/Kinto/kinto/releases/tag/1.24.0

**New features**

- Fix #501: UI notifications improvements (Kinto/kinto-admin#932)
- Fix #935: Show records changes without having to request review (Kinto/kinto-admin#943)
- Fix #915: Add button to copy authentication header
- Fix #443: Collapse diffs and only show 3 lines of context (Kinto/kinto-admin#960)
- Fix #467: Add links to source/preview/destination collections (Kinto/kinto-admin#959)

**Bug fixes**

- Fix #938: Show login form on authentication error (Kinto/kinto-admin#939)
- Fix #686: Do not scroll to bottom on pagination load (Kinto/kinto-admin#947)
- Fix #712: fix history pagination loading (Kinto/kinto-admin#948)
- Fix #949: fix history list from signoff diff details (Kinto/kinto-admin#950)
- Fix behaviour of servers history in login page (Kinto/kinto-admin#946)


17.0.0 (2019-05-27)
===================

kinto
-----

**kinto 12.0.1 → 13.1.1**: https://github.com/Kinto/kinto/releases/tag/13.1.1

**Breaking changes**

- Update Kinto OpenID plugin to redirect with a base64 JSON encoded token. (#1988).
  *This will work with kinto-admin 1.23*

**New features**

- Expose the user_profile in the user field of the hello page. (#1989)
- Add an "account validation" option to the accounts plugin. (#1973)
- Add a ``validate`` endpoint at ``/accounts/{user id}/validate/{validation
  key}`` which can be used to validate an account when the *account
  validation* option is enabled on the accounts plugin.
- Add a ``reset-password`` endpoint at ``/accounts/(user
  id)/reset-password`` which can be used to reset a user's password when the
  *account validation* option is enabled on the accounts plugin.

**Bug fixes**

- Fix cache heartbeat test (fixes Kinto/kinto#2107)
- Fix support of ``sqlalchemy.pool.NullPool`` for PostgreSQL backends.
  The default ``pool_size`` of 25 is maintained on the default pool class
  (``QueuePoolWithMaxBacklog``). When using custom connection pools, please
  refer to SQLAlchemy documentation for default values.
- Fixed two potential bugs relating to mutable default values.
- Fix crash on validating records with errors in arrays (#1508)
- Fix crash on deleting multiple accounts (#2009)
- Loosen up the Content-Security policies in the Kinto Admin plugin to prevent Webpack inline script to be rejected (fixes #2000)
- **security**: Fix a pagination bug in the PostgreSQL backend that could leak records between collections

kinto-redis
-----------

**kinto-redis 2.0.0 → 2.0.1**: https://github.com/Kinto/kinto-redis/releases/tag/2.0.1

**Bug fixes**

- ``pool_size`` setting should remain optional

16.1.0 (2019-04-10)
===================

- Add kinto-redis to the distribution (fixes #653). This allows use of
  the kinto-redis cache backend. The Docker compose configuration now
  uses Redis for the cache backend in order to ensure it works.


16.0.0 (2019-04-04)
===================

kinto-signer
------------

**kinto-signer 4.0.1 → 5.0.0**: https://github.com/Kinto/kinto-signer/releases/tag/5.0.0

**Breaking changes**

- Do not invalidate CloudFront on signature refresh (Kinto/kinto-signer#430)


15.1.0 (2019-02-21)
===================

kinto-changes
-------------

**kinto-changes 2.0.0 → 2.1.0**: https://github.com/Kinto/kinto-changes/releases/tag/2.1.0

- Send ``Cache-Control`` headers if cache busting query parameters or concurrency control request headers are sent (Kinto/kinto-changes#66)

kinto-emailer
-------------

**kinto-emailer 1.0.2 → 1.1.0**: https://github.com/Kinto/kinto-emailer/releases/tag/1.1.0

- Allow regexp in filters values when selecting events (Kinto/kinto-emailer#88)


15.0.2 (2019-01-30)
===================

kinto-signer
------------

**kinto-signer 4.0.0 → 4.0.1**: https://github.com/Kinto/kinto-signer/releases/tag/4.0.1

**Security issue**

- Signer parameters were displayed in capabilities. Fixed in Kinto/kinto-signer#326.


15.0.1 (2019-01-25)
===================

**Bug fixes**

- Include kinto-fxa script dependencies so that the
  process-account-events script can run. (#507)


15.0.0 (2019-01-22)
===================

kinto
-----

**kinto 11.1.0 → 12.0.1**: https://github.com/Kinto/kinto/releases/tag/12.0.1

**Breaking changes**

- Remove Python 3.5 support and upgrade to Python 3.6. (Kinto/kinto#1886)
- Remove ``record`` from UnicityError class (Kinto/kinto#1919). This enabled us to fix Kinto/kinto#1545.
- Storage backend API has changed, notions of collection and records were replaced
  by the generic terms *resource* and *object*. Plugins that subclass the internal
  ``ShareableResource`` class may also break.
- GET requests no longer include the ``Total-Records`` header. To get a count in a collection
  you need to do a HEAD request. And the new header name is ``Total-Objects``. (Kinto/kinto#1624)
- Remove the ``UserResource`` class. And ``ShareableResource`` is now deprecated in
  favor of ``Resource``.
- Removed ``kinto.core.utils.parse_resource()`. Use ``kinto.core.utils.view_lookup_registry()`` instead (Kinto/kinto#1828)
- Remove delete-collection command (Kinto/kinto#1959)

API is now at version **1.21**. See `API changelog`_.

**New features**

- Add a ``user-data`` endpoint at ``/__user_data__/`` which can be used to delete all data
  associated with a principal. This might be helpful for pursuing GDPR
  compliance, for instance. (Kinto/kinto#442.)
- Return a ``500 Internal Error`` on ``__version__`` instead of 404 if the version file
  cannot be found (Kinto/kinto#1841)

**Bug Fixes**

- Like query now returns 400 when a non string value is used. (Kinto/kinto#1899)
- Record ID is validated if explicitly mentioned in the collection schema (Kinto/kinto#1942)
- The Memory permission backend implementation of ``remove_principal``
  is now less generous with what it removes (Kinto/kinto#1955).
- Fix bumping of tombstones timestamps when deleting objects in PostgreSQL storage backend (Kinto/kinto#1981)
- Fix ETag header in responses of DELETE on plural endpoints (Kinto/kinto#1981)
- Fix the ``http_api_version`` exposed in the ``/v1/`` endpoint. The
  version ``1.20`` was getting parsed as a number ``1.2``.
- Fix ``record:create`` not taken into account from settings. (Kinto/kinto#1813)

**Documentation**

- Change PostgreSQL backend URLs to be ``postgresql://`` instead of the deprecated ``postgres://``
- Add documentation on troubleshooting Auth0 multiauth issue. (Kinto/kinto#1889)

kinto-attachment
----------------

**kinto-attachment 6.0.0 → 6.0.1**: https://github.com/Kinto/kinto-attachment/releases/tag/6.0.1

**Bug fixes**

- Fix support of Kinto >= 12

kinto-changes
-------------

**kinto-changes 1.3.0 → 2.0.0**: https://github.com/Kinto/kinto-changes/releases/tag/2.0.0

**Breaking changes**

- Require Kinto >= 12

kinto-signer
-------------

**kinto-signer 3.3.8 → 4.0.0**: https://github.com/Kinto/kinto-signer/releases/tag/4.0.0

**Bug fixes**

- Fix inconsistencies when source records are deleted via the DELETE /records endpoint (Kinto/kinto-signer#287)

**Breaking changes**

- Require Kinto >= 12.0.0


14.0.1 (2018-11-28)
===================

kinto-signer
------------

**kinto-signer 3.3.7 → 3.3.8**: https://github.com/Kinto/kinto-signer/releases/tag/3.3.7

**Bug fixes**

- Fix "RuntimeError: OrderedDict mutated during iteration" (#283).


14.0.0 (2018-11-22)
===================

**Breaking changes**

- ``kinto-ldap`` is not shipped in this distribution anymore (#369)

kinto-signer
------------

**kinto-signer 3.3.6 → 3.3.7**: https://github.com/Kinto/kinto-signer/releases/tag/3.3.7

**Bug fixes**

- If ``to_review_enabled`` is False, the preview collection is not created, nor updated (Kinto/kinto-signer#279)
- Show collections with specific settings in capabilities


13.0.0 (2018-11-12)
===================

kinto-megaphone
---------------

**kinto-megaphone 0.2.3 → 0.3.0**: https://github.com/Kinto/kinto-megaphone/releases/tag/0.3.0

**New features/Breaking changes**

- Add configuration to restrict what kinto-changes records cause
  notifications (#13). This configuration is **mandatory**.


12.0.2 (2018-11-08)
===================

kinto-signer
------------

**kinto-signer 3.3.5 → 3.3.6**: https://github.com/Kinto/kinto-signer/releases/tag/3.3.6

**Bug fixes**

- Fix Canonical JSON serialization of zero
- Allow installing ``kinto-signer`` with ``--no-deps`` in order to import ``kinto_signer.serializer.canonical_json()`` without the Pyramid ecosystem

kinto-megaphone
---------------

**kinto-megaphone 0.2.2 → 0.2.3**: https://github.com/Kinto/kinto-megaphone/releases/tag/0.2.3

- Remove a broken log message (Kinto/kinto-megaphone#10).


12.0.1 (2018-11-07)
===================

kinto-megaphone
---------------

**kinto-megaphone 0.2.0 → 0.2.2**: https://github.com/Kinto/kinto-megaphone/releases/tag/0.2.2

- Add a few log messages to help try to troubleshoot.
- 0.2.1 was a bogus release. Skip to 0.2.2.


12.0.0 (2018-11-06)
===================

kinto-attachment
----------------

**kinto-attachment 5.0.0 → 6.0.0**: https://github.com/Kinto/kinto-attachment/releases/tag/6.0.0

**Breaking changes**

- Do not allow any file extension by default. Now allow documents+images+text+data (Kinto/kinto-attachment#130)

**Bug fixes**

- Fix heartbeat when allowed file types is not ``any`` (Kinto/kinto-attachment#148)

kinto-signer
------------

**kinto-signer 3.3.4 → 3.3.5**: https://github.com/Kinto/kinto-signer/releases/tag/3.3.5

**Bug fixes**

- Fix Canonical JSON about float numbers to conform with `ECMAScript V6 notation <https://www.ecma-international.org/ecma-262/6.0/#sec-tostring-applied-to-the-number-type>`_


11.1.0 (2018-10-25)
===================

kinto
-----

**kinto 11.0.0 → 11.1.0**: https://github.com/Kinto/kinto/releases/tag/11.1.0

**New features**

- Add ability to configure the ``project_name`` in settings, shown in the `root URL <https://kinto.readthedocs.io/en/stable/api/1.x/utilities.html#get>`_ (Kinto/kinto#1809)
- Use ``.`` as bucket/collection separator in cache control settings (Kinto/kinto#1815)

**Bug fixes**

- Fix missing favicon and inline images in kinto-admin plugin

**Internal changes**

- Use mock from the standard library.
- Blackify the whole code base (Kinto/kinto#1799, huge thanks to @Cnidarias for this!)
- Upgrade kinto-admin to v1.22


kinto-signer
------------

**kinto-signer 3.3.3 → 3.3.4**: https://github.com/Kinto/kinto-signer/releases/tag/3.3.4

**Bug fixes**

- Prevent events to be sent if status is not changed (Kinto/kinto-signer#268)


11.0.0 (2018-10-22)
===================

kinto
-----

**kinto 10.1.2 → 11.0.0**: https://github.com/Kinto/kinto/releases/tag/11.0.0

**Breaking changes**

- The ``basicauth`` policy is not used by default anymore (#1736)

If your application relies on this specific behaviour, you now have to add explicitly settings:

.. code-block:: ini

    multiauth.policies = basicauth

But **it is recommended** to use other authentication policies like the *OpenID Connect* or the *accounts* plugin instead.

.. code-block:: ini

    # Enable plugin.
    kinto.includes = kinto.plugins.accounts

    # Enable authenticated policy.
    multiauth.policies = account
    multiauth.policy.account.use = kinto.plugins.accounts.AccountsPolicy

    # Allow anyone to create their own account.
    kinto.account_create_principals = system.Everyone

You will find more details the `authentication settings section of the documentation <https://kinto.readthedocs.io/en/stable/configuration/settings.html#authentication>`_

**Bug fixes**

- Fix crash when querystring filter contains NUL (0x00) character (Kinto/kinto#1704)
- Many bugs were fixed in the Kinto Admin UI (see `v1.21.0 <https://github.com/Kinto/kinto-admin/releases/tag/v1.21.0>`_)

**Documentation**

- Huge refactor of documentation about authentication (#1736)

kinto-admin
-----------

**kinto-admin 1.19.2 → 1.21.0**: https://github.com/Kinto/kinto-admin/releases/tag/v1.21.0

**New features**

* Remove brownish theme (Kinto/kinto-admin#658)
* Button labels consistency (Kinto/kinto-admin#659)
* Fix #118: order buckets alphabetically (Kinto/kinto-admin#650)
* Fix #170: show total number of records (Kinto/kinto-admin#657)
* Fix #529, Fix #617, Fix #618: Better handling of Kinto internal fields (Kinto/kinto-admin#626)
* Fix #66: Show record id in list by default (Kinto/kinto-admin#653)
* Fix #401: Show create bucket only if allowed (Kinto/kinto-admin#639)
* Fix #86: Show create collection only if allowed (Kinto/kinto-admin#651)
* Fix #74: Add a refresh button for bucket collections list (Kinto/kinto-admin#640)

**Bug fixes**

* Fix #641: Fix OpenID auth flow (Kinto/kinto-admin#642)
* Fix #648: Restore login failed detection (Kinto/kinto-admin#649)
* Fix #643, Fixup #630: fix crash when listing default bucket collections (Kinto/kinto-admin#647)
* Fix #609: Fix presence of ID value in record edit forms (Kinto/kinto-admin#611)
* Fix #619: fix display of attachment info (Kinto/kinto-admin#623)
* Fix #540, Fix #573: prevent root perm to become undefined bucket (Kinto/kinto-admin#631)
* Fix #584: remote Portier note about server install (Kinto/kinto-admin#632)
* Fix #629: always show default bucket (Kinto/kinto-admin#630)
* Fixup #630: hide default bucket if anonymous
* Fix #459: bucket readonly filter with writable collection (Kinto/kinto-admin#627)

kinto-changes
-------------

**kinto-changes 1.2.1 → 1.3.0**: https://github.com/Kinto/kinto-changes/releases/tag/1.3.0

**New feature**

- Add ability to configure cache control headers (Kinto/kinto-changes#47)


10.0.2 (2018-10-10)
===================

**kinto-signer 3.3.2 → 3.3.3**: https://github.com/Kinto/kinto-signer/releases/tag/3.3.3

**Bug fixes**

- Allow refresh of signature even if the collection was never signed (#267)


10.0.1 (2018-10-04)
===================

kinto
-----

**kinto 10.1.1 → 10.1.2**: https://github.com/Kinto/kinto/releases/tag/10.1.2

**Internal changes**

- Upgrade kinto-admin to v1.20.2


kinto-admin
-----------

**kinto-admin 1.20.1 → 1.20.2**: https://github.com/Kinto/kinto-admin/releases/tag/1.20.2

**Bug fixes**

- Fix OpenID login in Kinto-Admin (Kinto/kinto-admin#641)


10.0.0 (2018-09-12)
===================

kinto
-----

**kinto 9.2.3 → 10.1.1**: https://github.com/Kinto/kinto/releases/tag/10.1.1

**Breaking changes**

- ``kinto.core.events.get_resource_events`` now returns a generator
  rather than a list.


**New features**

- Include Python 3.7 support.
- ``kinto.core.events.notify_resource_event`` now supports
  ``resource_name`` and ``resource_data``. These are useful when
  emitting events from one view "as though" they came from another
  view.
- Resource events can now trigger other resource events, which are
  handled correctly. This might be handy if one resource wants to
  simulate events on another "virtual" resource, as in ``kinto-changes``.
- The registry now has a "command" attribute during one-off commands
  such as ``kinto migrate``. This can be useful for plugins that want
  to behave differently during a migration, for instance. (#1762)

**Bug fixes**

- Raise a configuration error if the ``kinto.plugin.accounts`` is included without being enabled in policies.
  Without this *kinto-admin* would present a confusing login experience (fixes #1734).
- Deleting a collection doesn't delete access_control_entrries for its children (fixes #1647)
- Fix for adding extra OpenId providers (fixes #1509)
- Change the meaning of ``event.payload["timestamp"]``. Previously it
  was ``@reify``\ 'd, which meant that it was calculated from before
  whatever thing triggered the event. Now we use a "fresh"
  timestamp. (Fixes #1469.)

**Internal changes**

- Upgrade kinto-admin to v1.20.0

kinto-changes
-------------

**kinto-changes 1.1.0 → 1.2.1**: https://github.com/Kinto/kinto-changes/releases/tag/1.2.1

**New feature**

- Events are now generated on the monitor/changes collection (#41).

**Bug fixes**

- Don't do anything during a ``migrate`` command (fixes #43).

**Internal changes**

- Get rid of six

kinto-megaphone
---------------

**kinto-megaphone 0.2.0**: https://github.com/Kinto/kinto-megaphone/releases/tag/0.2.0

Addition of this plugin.

kinto-signer
------------

**kinto-signer 3.3.0 → 3.3.2**: https://github.com/Kinto/kinto-signer/releases/tag/3.3.2

(Skipping 3.3.1 because of a mistake made during its release...)

**Internal changes**

- Support kinto 10.0.0, which allowed some simplifications (#264).



9.0.1 (2018-08-01)
==================

- Change CircleCI container in an attempt to successfully build a release.


9.0.0 (2018-07-31)
==================

kinto-attachment
----------------

**kinto-attachment 4.0.0 → 5.0.0**: https://github.com/Kinto/kinto-attachment/releases/tag/5.0.0

**Breaking changes**

- Gzip ``Content-Encoding`` is not used anymore when uploading on S3 (fixes #144)

**Internal changes**

- Heartbeat now uses ``utils.save_file()`` for better detection of configuration or deployment errors (fixes #146)


8.0.2 (2018-07-26)
==================

- Fix CircleCI job execution for tags (fixes #233)


8.0.1 (2018-07-25)
==================

- Fix Docker Hub publication issue from CircleCI


8.0.0 (2018-07-25)
==================

kinto-signer
------------

**kinto-signer 3.2.5 → 3.3.0**: https://github.com/Kinto/kinto-signer/releases/tag/3.3.0

**New features**

- Allow to refresh the signature when the collection has pending changes (Kinto/kinto-signer#245)

kinto-attachment
----------------

**kinto-attachment 3.0.1 → 4.0.0**: https://github.com/Kinto/kinto-attachment/releases/tag/4.0.0

**Breaking changes**

- Gzip ``Content-Encoding`` is now always enabled when uploading on S3 (Kinto/kinto-attachment#139)
- Overriding settings via the querystring (eg. ``?gzipped``, ``randomize``, ``use_content_encoding``) is not possible anymore


7.3.1 (2018-07-05)
==================

kinto
-----

**kinto 9.2.2 → 9.2.3**: https://github.com/Kinto/kinto/releases/tag/9.2.3

**Bug fixes**

- Upgrade to kinto-admin v1.19.2

kinto-admin
-----------

**kinto-admin 1.19.1 → 1.19.2**: https://github.com/Kinto/kinto-admin/releases/tag/1.19.2

**Bug fixes**

- Better auth error message (kinto/kinto-admin#566)
- Fix history diff viewing (kinto/kinto-admin#563)

kinto-signer
------------

**kinto-signer 3.2.4 → 3.2.5**: https://github.com/Kinto/kinto/releases/tag/3.2.5

**Bug fixes**

- Fix ``scripts/e2e.py`` script to work with per-bucket configuration (kinto/kinto-signer#255)
- Prevent kinto-attachment to raise errors when attachments are updated (kinto/kinto-signer#256)

kinto-fxa
---------

**kinto-fxa 2.5.1 → 2.5.2**: https://github.com/Kinto/kinto-fxa/releases/tag/2.5.2

**Bug fixes**

- Fix the ``process-account-events`` script to take client user ID suffixes into account (kinto/kinto-fxa#61)

kinto-attachment
----------------

**kinto-attachment 3.0.0 → 3.0.1**: https://github.com/Kinto/kinto-attachment/releases/tag/3.0.1

**Bug fixes**

- Do not delete attachment when record is deleted if ``keep_old_files`` setting is true (kinto/kinto-attachment#137)

amo2kinto
---------

**amo2kinto 3.2.1 → 4.0.1**: https://github.com/mozilla-services/amo2kinto/releases/tag/4.0.1

**Bug fix**

- Fix the XML item ID when squashing entries by addon ID (#88)
- Fix the affected users section (#87), thanks @rctgamer3!

**Breaking changes**

- Removed the AWS lambda code in charge of updating the collection schema (#85)


7.3.0 (2018-06-28)
==================

kinto
-----

**kinto 9.1.1 → 9.2.2**: https://github.com/Kinto/kinto/releases/tag/9.2.2

**API**

- JSON schemas can now be defined in the bucket metadata and will apply to every
  underlying collection, group or record (Kinto/kinto#1555)

**Bug fixes**

- Fixed bug where unresolved JSON pointers would crash server (Kinto/kinto#1685)

**New features**

- Kinto Admin plugin now supports OpenID Connect
- Limit network requests to current domain in Kinto Admin using `Content-Security Policies <https://hacks.mozilla.org/2016/02/implementing-content-security-policy/>`_
- Prompt for cache backend type in ``kinto init`` (Kinto/kinto#1653)
- kinto.core.utils now has new features ``route_path_registry`` and
  ``instance_uri_registry``, suitable for use when you don't
  necessarily have a ``request`` object around. The existing functions
  will remain in place.
- openid plugin will carry ``prompt=none`` querystring parameter if appended
  to authorize endpoint.

kinto-admin
-----------

**kinto-admin 1.17.2 → 1.19.1**: https://github.com/Kinto/kinto-admin/releases/tag/1.19.1

**New features**

- Add support of OpenID Connect (Kinto/kinto-admin#460)
- Fix accounts capability detection (Kinto/kinto-admin#558)
- Remember last used authentication method (Kinto/kinto-admin#525)

kinto-fxa
---------

**kinto-fxa 2.5.0 → 2.5.1**: https://github.com/Kinto/kinto-fxa/releases/tag/2.5.1

**Bug fixes**

- Set up metrics on the ``process-account-events`` script (#57).
- Set up logging on the ``kinto_fxa.scripts`` programs (#58).


7.2.1 (2018-05-30)
==================

kinto-signer
------------

**kinto-signer 3.2.3 → 3.2.4**: https://github.com/Kinto/kinto-signer/releases/tag/3.2.4

**Bug fixes**

- Fix CloudFront invalidation request with multiple paths (Kinto/kinto-signer#253)


7.2.0 (2018-05-23)
==================

kinto
-----

**kinto 9.0.1 → 9.1.1**: https://github.com/Kinto/kinto/releases/tag/9.1.1

**API**

- Batch endpoint now checks for and aborts any parent request if subrequest encounters ``409 Conflict`` constraint violation (Kinto/kinto#1569)

**Bug fixes**

- Fix a bug where you could not reach the last records via ``Next-Header`` when deleting with pagination (Kinto/kinto#1170)
- Slight optimizations on the ``get_all()`` query in the Postgres
  storage backend which should make it faster for result sets that
  have a lot of records (Kinto/kinto#1622). This is the first change meant to
  address Kinto/kinto#1507, though more can still be done.
- Fix a bug where the batch route accepted all content-types (Kinto/kinto#1529)


kinto-admin
-----------

**kinto-admin 1.17.1 → 1.17.2**: https://github.com/Kinto/kinto-admin/releases/tag/1.17.2

**Bug fixes**

- Don't request records as part of the permissions (Kinto/kinto-admin#536)
- Fix strange validation errors on collection forms (Kinto/kinto-admin#539)


7.1.0 (2018-05-17)
==================

kinto
-----

**kinto 9.0.0 → 9.0.1**: https://github.com/Kinto/kinto/releases/tag/9.0.0

- Update version of kinto-admin

kinto-admin
-----------

**kinto-admin 1.17.0 → 1.17.1**: https://github.com/Kinto/kinto-admin/releases/tag/1.17.1


**Bug fixes**

- Fetch capabilities from singleServer if set (Kinto/kinto-admin#532)

kinto-fxa
---------

**kinto-fxa 2.4.1 → 2.5.0**: https://github.com/Kinto/kinto-fxa/releases/tag/2.5.0

**New features**

- Introduce new kinto_fxa.scripts. Right now the only script available
  is process-account-events, which listens to an SQS queue for user
  delete events and deletes data from that user's default bucket, in
  order to comply with GDPR. (Kinto/kinto-fxa#55)


7.0.2 (2018-05-09)
==================

kinto-signer
------------

**kinto-signer 3.2.2 → 3.2.3**: https://github.com/Kinto/kinto-signer/releases/tag/3.2.3

**Bug fixes**

- Fix crash on collection delete (Kinto/kinto#248)


7.0.1 (2018-05-02)
==================

kinto-signer
------------

**kinto-signer 3.2.1 → 3.2.2**: https://github.com/Kinto/kinto-signer/releases/tag/3.2.2

**Bug fixes**

- Cleanup preview and destination when source collection is deleted (kinto/kinto-signer#114)


7.0.0 (2018-04-25)
==================

kinto
-----

**kinto 8.2.3 → 9.0.0**: https://github.com/Kinto/kinto/releases/tag/9.0.0

**API**

- Introduce ``contains`` and ``contains_any`` filter operators (Kinto/kinto#343).

API is now at version **1.19**. See `API changelog`_.

**Breaking changes**

- The storage class now exposes ``bump_timestamp()`` and ``bump_and_store_timestamp()`` methods
  so that memory based storage backends can use them. (Kinto/kinto#1596)

**Documentation**

- Version number is taken from package in order to ease release process (Kinto/kinto#1594)
- Copyright year is now dynamic (Kinto/kinto#1595)


kinto-admin
-----------

**kinto-admin 1.15.0 → 1.17.0**: https://github.com/Kinto/kinto-admin/releases/tag/v1.17.0

**New features**

- Get the list of auth methods supported by the server when first rendering the auth form (Kinto/kinto-admin#331, Kinto/kinto-admin#497, Kinto/kinto-admin#516)
- Date are now formatted as en-US (Kinto/kinto-admin#508)

**Bug fixes**

- Fix signoff workflow info when kinto-signer running on server is >= 3.2 (Kinto/kinto-admin#500)
- Better detection of authentication failures (Kinto/kinto-admin#330)
- Fix history table apparence (Kinto/kinto-admin#511)
- Wrap signoff comment (Kinto/kinto-admin#490)


kinto-signer
------------

**kinto-signer 3.0.0 → 3.2.1**: https://github.com/Kinto/kinto-signer/releases/tag/3.2.1

**New features**

- Cloudfront invalidation paths can be configured (kinto/kinto-signer#231)
- User does not have to be in the *reviewers* group to refresh a signature (kinto/kinto-signer#233)
- Give write permission to reviewers/editors groups on newly created collections (kinto/kinto-signer#237)
- The preview collection signature is now refreshed along the destination (kinto/kinto-signer#236)
- Tracking fields are now documented and new ones were added (``last_edit_date``, ``last_request_review_date``, ``last_review_date`` and ``last_signature_date``) (kinto/kinto-signer#137)

**Deprecations**

- The collection specific settings must now be separated with ``.`` instead of ``_``.
  (eg. use ``kinto.signer.staging.certificates.editors_group`` instead of ``kinto.signer.staging_certificates.editors_group``) (kinto/kinto-signer#224)

**Internal changes**

- Now log an INFO message when the CloudFront invalidation request is sent (kinto/kinto-signer#238)


kinto-elasticsearch
-------------------

**kinto-elasticsearch 0.3.0 → 0.3.1**: https://github.com/Kinto/kinto-elasticsearch/releases/tag/0.3.1

**Bug fixes**

- Fix the reindex get_paginated_records function. (Kinto/kinto-elasticsearch#61)


kinto-attachment
----------------

**kinto-attachment 2.1.0 → 3.0.0**: https://github.com/Kinto/kinto-attachment/releases/tag/3.0.0

**Breaking changes**

- The collection specific ``use_content_encoding`` setting must now be separated with ``.`` instead of ``_``.
  (eg. use ``kinto.attachment.resources.bid.cid.use_content_encoding`` instead of ``kinto.attachment.resources.bid_cid.use_content_encoding``) (fixes kinto/kinto-attachment#134)


6.0.2 (2018-04-06)
==================

kinto
-----

**kinto 8.2.2 → 8.2.3**: https://github.com/Kinto/kinto/releases/tag/8.2.3

**Security fix**

- Since Kinto 8.2.0 the `account` plugin had a security flaw where the password wasn't verified during the session duration.
  It now validates the account user password even when the session is cached (Kinto/kinto#1583).



6.0.1 (2018-03-28)
==================


kinto
-----

**kinto 8.2.0 → 8.2.2**: https://github.com/Kinto/kinto/releases/tag/8.2.2

**Internal changes**

- Upgrade to kinto-admin 1.15.1


kinto-admin
-----------

**kinto-admin 1.15.0 → 1.15.1**: https://github.com/Kinto/kinto-admin/releases/tag/v1.15.1

**Bug fixes**

- [signoff] Fix bug where users who are part of "editors" and "reviewers" groups do not get shown the "request review" or "approve" buttons (Kinto/kinto-admin#495)


6.0.0 (2018-03-09)
==================

kinto
-----

**kinto 8.1.5 → 8.2.0**: https://github.com/Kinto/kinto/releases/tag/8.2.0

**New features**

- Add Openid connect support (#939, #1425). See `demo <https://github.com/leplatrem/kinto-oidc-demo>`_
- Account plugin now caches authentication verification (Kinto/kinto#1413)

**Bug fixes**

- Fix missing principals from user info in root URL when default bucket plugin is enabled (fixes #1495)
- Fix crash in Postgresql when the value of url param is empty (Kinto/kinto#1305)

kinto-admin
-----------

**kinto-admin 1.14.0 → 1.15.0**: https://github.com/Kinto/kinto-admin/releases/tag/v1.15.0

**New features**

- [signoff] Fixes #461: Support per-bucket configuration (Kinto/kinto-admin#466)

**Bug fixes**

- Fix list permissions if anonymous (Kinto/kinto-admin#463)
- [signoff] Fix workflow info parameter types (Kinto/kinto-admin#470)


kinto-signer
------------

**kinto-signer 2.2.0 → 3.0.0**: https://github.com/Kinto/kinto/releases/tag/3.0.0

**Breaking changes**

- The settings ``reviewers_group``, ``editors_group``, ``to_review_enabled``, ``group_check_enabled``
  prefixed with ``_`` are not supported anymore. (eg. use ``kinto.signer.staging_certificates.editors_group``
  instead of ``kinto.signer.staging_certificates_editors_group``)

**New features**

- Allow spaces in resources configurations, and separate URIs with ``->`` for better readability (fixes Kinto/kinto-signer#148, fixes Kinto/kinto-signer#88)
- Allow configuration of ``reviewers_group``, ``editors_group``, ``to_review_enabled``, ``group_check_enabled``
  by bucket
- Allow placeholders ``{bucket_id}`` and ``{collection_id}`` in ``reviewers_group``, ``editors_group``,
  ``to_review_enabled``, and ``group_check_enabled`` settings
  (e.g. ``group:/buckets/{bucket_id}/groups/{collection_id}-reviewers``) (fixes Kinto/kinto-signer#210)
- Allow configuration by bucket. Every collections in the source bucket will be reviewed/signed (fixes Kinto/kinto-signer#144).
- Editors and reviewers groups are created automatically when source collection is created (fixes Kinto/kinto-signer#213)
- Preview and destination collections are automatically signed when source is created (fixes Kinto/kinto-signer#226)

**Bug fixes**

- Fix permissions of automatically created preview/destination bucket (fixes Kinto/kinto-signer#155)


5.2.1 (2018-02-09)
==================

kinto
-----

**kinto 8.1.4 → 8.1.5**: https://github.com/Kinto/kinto/releases/tag/8.1.5

**Bug fixes**

- Restore "look before you leap" behavior in the Postgres storage
  backend create() method to check whether a record exists before
  running the INSERT query (#1487). This check is "optimistic" in the sense
  that we can still fail to INSERT after the check succeeded, but it
  can reduce write load in configurations where there are a lot of
  create()s (i.e. when using the default_bucket plugin).


5.2.0 (2018-02-07)
==================

kinto-amo
---------

**kinto-amo 0.4.0 → 1.0.1**: https://github.com/mozilla-services/kinto-amo/releases/tag/1.0.1

**Bug fixes**

- Fix last update / last modified of blocklist XML endpoint (fixes mozilla-services/kinto-amo#25)

**New features**

- Pass application ID and version to amo2kinto code when generating blocklist.xml (mozilla-services/kinto-amo#23)
- Filter add-ons and plugins in v3 based on the requesting application and version. (mozilla-services/amo2kinto#74)
- Stop exporting cert items to Firefox 58 and above, where they aren't used. (mozilla-services/amo2kinto#75)


5.1.4 (2018-01-31)
==================

kinto
-----

**kinto 8.1.3 → 8.1.4**: https://github.com/Kinto/kinto/releases/tag/8.1.4

**Bug fixes**

- Allow inherited resources to set a custom model instance before instantiating (fixes #1472)
- Fix collection timestamp retrieval when the stack is configured as readonly (fixes #1474)


5.1.3 (2018-01-26)
==================

kinto
-----

**kinto 8.1.2 → 8.1.3**: https://github.com/Kinto/kinto/releases/tag/8.1.3

**Bug fixes**

- Optimize the PostgreSQL permission backend's
  ``delete_object_permissions`` function in the case where we are only
  matching one object_id (or object_id prefix).


5.1.2 (2018-01-24)
==================

kinto
-----

**kinto 8.1.1 → 8.1.2**: https://github.com/Kinto/kinto/releases/tag/8.1.2

**Bug fixes**

- Flushing a server no longer breaks migration of the storage backend
  (#1460). If you have ever flushed a server in the past, migration
  may be broken. This version of Kinto tries to guess what version of
  the schema you're running, but may guess wrong. See
  https://github.com/Kinto/kinto/wiki/Schema-versions for some
  additional information.

**Internal changes**

- We now allow migration of the permission backend's schema.

**Operational concerns**

- *The schema for the Postgres permission backend has changed.* This
  changes another ID column to use the "C" collation, which should
  speed up the `delete_object_permissions` query when deleting a
  bucket.


5.1.1 (2018-01-18)
==================

kinto
-----

**kinto 8.1.0 → 8.1.1**: https://github.com/Kinto/kinto/releases/tag/8.1.1

**Operational concerns**

- *The schema for the Postgres storage backend has changed.* This
  changes some more ID columns to use the "C" collation, which fixes a
  bug where the ``bump_timestamps`` trigger was very slow.


5.1.0 (2018-01-04)
==================

kinto
-----

**kinto 8.0.0 → 8.1.0**: https://github.com/Kinto/kinto/releases/tag/8.1.0

**Internal changes**

- Update the Docker compose configuration to use memcache for the cache backend (#1405)
- Refactor the way postgresql.storage.create_from_settings ignores settings (#1410)

**Operational concerns**

- *The schema for the Postgres storage backend has changed.* This
  changes some ID columns to use the "C" collation, which will make
  ``delete_all`` queries faster. (See
  e.g. https://www.postgresql.org/docs/9.6/static/indexes-opclass.html,
  which says "If you do use the C locale, you do not need the
  xxx_pattern_ops operator classes, because an index with the default
  operator class is usable for pattern-matching queries in the C
  locale.") This may change the default sort order and grouping of
  record IDs.

**New features**

- New setting ``kinto.backoff_percentage`` to only set the backoff header a portion of the time.
- ``make tdd`` allows development in a TDD style by rerunning tests every time a file is changed.

**Bug fixes**

- Optimize the Postgres collection_timestamp method by one query. It
  now only makes two queries instead of three.
- Update other dependencies: newrelic to 2.98.0.81 (#1409), setuptools
  to 38.4.0 (#1411, #1429, #1438, #1440), pytest to 3.3.2 (#1412,
  #1437), raven to 6.4.0 (#1421), werkzeug to 0.14.1 (#1418, #1434),
  python-memcached to 1.59 (#1423), zest.releaser to 6.13.3 (#1427),
  bravado_core to 4.11.2 (#1426, #1441), statsd to 3.2.2 (#1422),
  jsonpatch to 1.21 (#1432), sqlalchemy to 1.2.0 (#1430), sphinx to
  1.6.6 (#1442).


kinto-signer
------------

**kinto-signer 2.1.1 → 2.2.0**: https://github.com/Kinto/kinto-signer/releases/tag/2.2.0

**New features**

- Use generic config keys as a fallback for missing specific signer config keys. (Kinto/kinto-signer#151)
- Fix bad signature on empty collections. (Kinto/kinto-signer#164)


kinto-attachment
----------------

**kinto-attachment 2.0.1 → 2.1.0**: https://github.com/Kinto/kinto-attachment/releases/tag/2.1.0

**New features**

- Add support for the ``Content-Encoding`` header with the S3 backend (Kinto/kinto-attachment#132)


5.0.0 (2017-11-29)
==================

kinto
-----

**kinto 7.6.1 → 8.0.0**: https://github.com/Kinto/kinto/releases/tag/8.0.0

**Operational concerns**

- *The schema for the Postgres ``storage`` backend has changed.* This
  lets us prevent a race condition where deleting and creating a thing
  at the same time can leave it in an inconsistent state (#1386). You
  will have to run the ``kinto migrate`` command in order to migrate
  the schema. The safest way to do this is to disable Kinto traffic
  (perhaps using nginx), bring down the old Kinto service, run the
  migration, and then bring up the new Kinto service.

**Breaking changes**

- Storage backends no longer support the ``ignore_conflict``
  argument (#1401). Instead of using this argument, consider catching the
  ``UnicityError`` and handling it. ``ignore_conflict`` was only ever
  used in one place, in the ``default_bucket`` plugin, and was
  eventually backed out in favor of catching and handling a
  ``UnicityError``.

**Bug fixes**

- Fix a TOCTOU bug in the Postgres storage backend where a transaction
  doing a `create()` would fail because a row had been inserted after
  the transaction had checked for it (#1376).
- Document how to create an account using the ``POST /accounts`` endpoint (#1385).

**Internal changes**

- Update dependency on pytest to move to 3.3.0 (#1403).
- Update other dependencies: setuptools to 38.2.1 (#1380, #1381,
  #1392, #1395), jsonpatch to 1.20 (#1393), zest.releaser to 6.13.2
  (#1397), paste-deploy to 0.4.2 (#1384), webob to 1.7.4 (#1383),
  simplejson to 3.13.2 (#1389, #1390).
- Undo workaround for broken kinto-http.js in the kinto-admin plugin
  (#1382).


4.6.0 (2017-11-27)
==================

kinto-fxa
---------

**kinto-fxa 2.3.0 → 2.4.0**: https://github.com/Kinto/kinto-fxa/releases/tag/2.4.0

**New Feature**

- Add support for multiple FxA Clients (mozilla-services/kinto-fxa#52)


4.5.1 (2017-11-21)
==================

**kinto-emailer 1.0.0 → 1.0.1**: https://github.com/Kinto/kinto-emailer/releases/tag/1.0.1

- Remove hard requirements of Pyramid 1.8 (Kinto/kinto-emailer#46)


4.5.0 (2017-11-16)
==================

kinto
-----

**kinto 7.5.1 → 7.6.0**: https://github.com/Kinto/kinto/releases/tag/7.6.0

**Protocol**

- When a record is pushed with an older timestamp, the collection
  timestamps is not bumped anymore. (Kinto/kinto#1361)

**New features**

- A new custom logging formatter is available in ``kinto.core``. It fixes the issues of
  `mozilla-cloud-services-logger <https://github.com/mozilla/mozilla-cloud-services-logger>`_.
  Consider migrating your logging settings to :

::

    [formatter_json]
    class = kinto.core.JsonLogFormatter

**Bug fixes**

- Do not log empty context values (Kinto/kinto#1363)
- Fixed some attributes in logging of errors (Kinto/kinto#1363)
- Fixed logging of method/path of batch subrequests (Kinto/kinto#1363)
- Fix removing permissions with Json Merge (Kinto/kinto#1322).


**Internal changes**

- Moved PostgreSQL helper function to Python code (Kinto/kinto#1358)


kinto-changes
-------------

**kinto-changes 1.0.0 → 1.1.0**: https://github.com/Kinto/kinto-changes/releases/tag/1.1.0

**Bug fixes**

- Disable reify to always get the most accurate timestamp. (#36)


4.4.1 (2017-10-30)
==================

kinto-signer
------------

**kinto-signer 2.1.0 → 2.1.1**: https://github.com/Kinto/kinto-signer/releases/tag/2.1.1

**Bug fixes**

- Invalidate the CloudFront CDN cache. (Kinto/kinto-signer#199)


4.4.0 (2017-10-03)
==================

**amo2kinto 3.0.0 → 3.1.0**: https://github.com/mozilla-services/amo2kinto/releases/tag/3.1.0

**New features**

- Add support for cert items subject and pubKeyHash attributes. (mozilla-services/amo2kinto#70)

**kinto 7.5.0 → 7.5.1**: https://github.com/Kinto/kinto/releases/tag/7.5.1

**Bug fixes**

- Use the ``KINTO_INI`` env variable to findout the configuration file. (Kinto/kinto#1339)
- Fix ``create-user`` command for PostgreSQL backend (Kinto/kinto#1340)
- Make sure ``create-user`` command updates password (Kinto/kinto#1336)


4.3.0 (2017-09-28)
==================

amo2kinto
---------

**amo2kinto 1.7.2 → 3.0.0**: https://github.com/mozilla-services/kinto-amo/releases/tag/3.0.0

**Bug fixes**

- Remove json2kinto importer
- Remove xml verifier


kinto
-----

**kinto 7.4.1 → 7.5.0**: https://github.com/Kinto/kinto/releases/tag/7.5.0

**New features**

- Add a `Memcached` cache backend (Kinto/kinto#1332)


4.2.0 (2017-09-14)
==================

kinto-elasticsearch
-------------------

**kinto 0.2.1 → 0.3.0**: https://github.com/Kinto/kinto-elasticsearch/releases/tag/0.3.0

**New features**

- Add StatsD timer to measure E/S indexation (Kinto/kinto-elasticsearch#54)
- Add a ``kinto-reindex`` command to reindex existing collections of records (Kinto/kinto-elasticsearch#56)


4.1.0 (2017-09-01)
==================

kinto
-----

**kinto 7.3.2 → 7.4.1**: https://github.com/Kinto/kinto/releases/tag/7.4.1

**New features**

- Add a `create-user` kinto command (Kinto/kinto#1315)

**Bug fixes**

- Fix pagination token generation on optional fields (Kinto/kinto#1253)



4.0.1 (2017-08-14)
==================

kinto
-----

**kinto 7.3.1 → 7.3.2**: https://github.com/Kinto/kinto/releases/tag/7.3.2

**Bug fixes**

- The PostgreSQL cache backend now orders deletes according to keys,
  which are a well-defined order that never changes. (Fixes #1308.)

**Internal changes**

- Now all configuration options appear as commented lines on the configuration
  template (#895)
- Added task on PR template about updating the configuration template
  if a new configuration setting is added.
- Use json instead of ujson in storage in tests (#1255)
- Improve Docker container to follow Dockerflow recommendations (fixes #998)



4.0.0 (2017-08-09)
==================

kinto-signer
------------

**kinto-signer 1.5.4 → 2.1.0**: https://github.com/Kinto/kinto-signer/releases/tag/2.1.0

**Breaking changes**

- Upgrade to Autograph 2.0

**New features**

- Invalidate the monitor changes collection on updates (#187)

**Bug fixes**

- Allow kinto-attachment collections reviews. (#190)
- Remove additional / in invalidation collection path (#194)



3.3.0 (2017-07-13)
==================

kinto-elasticsearch
-------------------

**kinto-elasticsearch 0.2.1**: https://github.com/Kinto/kinto/releases/tag/0.2.1


**New features**

- Flush indices when server is flushed (fixes #4)
- Perform insertions and deletion in bulk for better efficiency (fixes #5)
- Add setting to force index refresh on change (fixes #6)
- Add heartbeat (fixes #3)
- Delete indices when buckets and collections are deleted (fixes #21)
- Support quick search from querystring (fixes #34)
- Return details about invalid queries in request body (fixes #23)
- Support defining mapping from the ``index:schema`` property in the collection metadata (ref #8)

**Bug fixes**

- Only index records if the storage transaction is committed (fixes #15)
- Do not allow to search if no read permission on collection or bucket (fixes #7)
- Fix empty results response when plugin was enabled after collection creation (ref #20)
- Limit the number of results returned by default (fixes #45)
- Fix crash on search parse exceptions (fixes #44)
- Fix the number of results when specified in query (ref #45)

**Internal changes**

- Create index when collection is created (fixes #27)


3.2.3 (2017-07-21)
==================

kinto-signer
------------

**kinto-signer 1.5.3 → 1.5.4**: https://github.com/Kinto/kinto-signer/releases/tag/1.5.4

**Bug fixes**

- Allow kinto-attachment collections reviews on subrequests too. (Kinto/kinto-signer#192)


3.2.2 (2017-07-20)
==================

- Update requirements.txt with kinto-signer version bump in 3.2.1 release


3.2.1 (2017-07-20)
==================

kinto-signer
------------

**kinto-signer 1.5.2 → 1.5.3**: https://github.com/Kinto/kinto-signer/releases/tag/1.5.3

**Bug fixes**

- Allow kinto-attachment collections reviews. (Kinto/kinto-signer#190)


3.2.0 (2017-07-05)
==================

kinto
-----

**kinto 7.1.0 → 7.3.1**: https://github.com/Kinto/kinto/releases/tag/7.3.1

**API**

- Filtering with like can now contain wild chars (eg. ``?like_nobody=*you*``).
  It is thus now impossible to search for the ``*`` character with this operator.
- Handle querystring parameters as JSON encoded values
  to avoid treating number as number where they should be strings. (Kinto/kinto#1217)
- Introduce ``has_`` filter operator (Kinto/kinto#344).

API is now at version **1.17**. See `API changelog <http://kinto.readthedocs.io/en/latest/api/>`_.

**New features**

- Account plugin now allows account IDs to be email addresses (Kinto/kinto#1283).

**Bug fixes**

- Make it illegal for a principal to be present in
  ``account_create_principals`` without also being in
  ``account_write_principals``. Restricting creation of accounts to
  specified users only makes sense if those users are "admins", which
  means they're in ``account_write_principals``. (Kinto/kinto#1281)
- Fix a 500 when accounts without an ID are created (Kinto/kinto#1280).
- Fix StatsD unparseable metric packets for the unique user counter (Kinto/kinto#1282)
- Fix permissions endpoint when using account plugin (Kinto/kinto#1276)
- Fix missing ``collection_count`` field in the rebuild-quotas script.
- Fix bug causing validation to always succeed if no required fields are present.
- Several changes to the handling of NULLs and how the full range of
  JSON values is compared in a storage backend (Kinto/kinto#1258, Kinto/kinto#1252,
  Kinto/kinto#1215, Kinto/kinto#1216, Kinto/kinto#1217 and Kinto/kinto#1257).
- Fix requests output when running with make serve (Kinto/kinto#1242)
- Fix pagination on permissions endpoint (Kinto/kinto#1157)
- Fix pagination when max fetch storage is reached (Kinto/kinto#1266)
- Fix schema validation when internal fields like ``id`` or ``last_modified`` are
  marked as required (Kinto/kinto#1244)
- Restore error format for JSON schema validation errors (which was
  changed in Kinto/kinto#1245).
- Fix bug in Postgres backend regarding the handling of combining
  filters and NULL values (Kinto/kinto#1291)

kinto-admin
-----------

**kinto-admin 1.13.3 → 1.14.0**: https://github.com/Kinto/kinto-admin/releases/tag/v1.14.0

**New features**

- Update kinto-http.js 4.3.3 (Kinto/kinto-admin#431)
- Add support for the Kinto Account plugin. (Kinto/kinto-admin#439)

kinto-amo
---------

**kinto-amo 0.3.0 → 0.4.0**: https://github.com/mozilla-services/kinto-amo/releases/tag/0.4.0

**New features**

- Add support for cache control headers (``If-None-Match`` and ``If-Modified-Since``) (mozilla-services/kinto-amo#21)


3.1.2 (2017-06-28)
==================

kinto-emailer
-------------

**kinto-emailer 0.4.0 → 1.0.0**: https://github.com/Kinto/kinto-emailer/releases/tag/1.0.0

**Bug fixes**

- Fix crash when creating bucket with ``POST /buckets`` (fixes Kinto/kinto-emailer#43)


kinto-signer
------------

**kinto-signer 1.5.1 → 1.5.2**: https://github.com/Kinto/kinto-signer/releases/tag/1.5.2

- Catch cache invalidation errors and log the error. (Kinto/kinto-signer#186)


3.1.1 (2017-06-28)
==================

kinto-signer
------------

**kinto-signer 1.5.0 → 1.5.1**: https://github.com/Kinto/kinto-signer/releases/tag/1.5.1

- Fix kinto-signer heartbeat. (Kinto/kinto-signer#182)


3.1.0 (2017-06-19)
==================

kinto-signer
------------

**kinto-signer 1.4.0 → 1.5.0**: https://github.com/Kinto/kinto-signer/releases/tag/1.5.0

**New features**

- Add support for CloudFront path cache invalidation. (Kinto/kinto-signer#178)

.. code-block:: ini

    # Configure the cloudfront distribution related to the server cache.
    kinto.signer.distribution_id = E2XLCI5EUWMRON


3.0.1 (2017-06-12)
==================

- Install mozilla-cloud-services-logger. (#134)


3.0.0 (2017-06-12)
==================

kinto
-----

**kinto 6.1.0 → 7.1.0**: https://github.com/Kinto/kinto/releases/tag/7.1.0

**Breaking changes**

- The flush endpoint is now a built-in plugin at ``kinto.plugins.flush`` and
  should be enabled using the ``includes`` section of the configuration file.
  ``KINTO_FLUSH_ENDPOINT_ENABLED`` environment variable is no longer supported. (#1147)
- Settings with ``cliquet.`` prefix are not supported anymore.
- Logging configuration now relies on standard Python logging module (#1150)

Before:

.. code-block:: ini

    kinto.logging_renderer = kinto.core.logs.ClassicLogRenderer

Now:

.. code-block:: ini

    [handler_console]
    ...
    formatter = color

    [formatters]
    keys = color

    [formatter_color]
    class = logging_color_formatter.ColorFormatter

- Forbid storing bytes in the cache backend. (#1143)
- ``kinto.core.api`` was renamed to ``kinto.core.openapi`` (#1145)
- Logging extra information on message must be done using the ``extra`` keyword
  (eg. ``logger.info('msg', extra={a=1})`` instead of ``logger.info('msg', a=1)``)
  (#1110, #1150)
- Cache entries must now always have a TTL. The ``ttl`` parameter of ``cache.set()``
  is now mandatory (fixes #960).
- ``get_app_settings()`` from ``kinto.core.testing.BaseWebTest`` is now a
  class method (#1144)

**Protocol**

- Groups can now be created with a simple ``PUT`` (fixes #793)
- Batch requests now raise ``400`` on unknown attributes (#1163).

Protocol is now at version **1.16**. See `API changelog`_.

**New features**

- Enforce the permission endpoint when the admin plugin is included (fixes #1059)
- Access control failures are logged with WARN level (fixes #1074)
- Added an experimental `Accounts API <http://kinto.readthedocs.io/en/latest/api/1.x/accounts.html>`_
  which allow users to sign-up modify their password or delete their account (fixes #795)
- ``delete()`` method from cache backend now returns the deleted value (fixes #1231)
- ``kinto rebuild-quotas`` script was written that can be run to
  repair the damage caused by #1226 (fixes #1230).

**Bug fixes**

- Fix Memory backend sometimes show empty permissions (#1045)
- Allow to create default bucket with a PUT request and an empty body (fixes #1080)
- Fix PostgreSQL backend when excluding a list of numeric values (fixes #1093)
- Fix ``ignore_conflict`` storage backend create method parameter to
  keep the existing rather than overriding it. (#1134)
- Fix impacted records of events generated by implicit creation in default
  bucket (#1137)
- Removed Structlog binding and bottlenecks (fixes #603)
- Fixed Swagger output with subpath and regex in pyramid routes (fixes #1180)
- Fixed Postgresql errors when specifying empty values in querystring numeric filters. (fixes #1194)
- Return a 400 Bad Request instead of crashing when the querystring contains bad characters. (fixes #1195)
- Fix PostgreSQL backend from deleting records of the same name in
  other buckets and collections when deleting a bucket. (fixes #1209)
- Fix race conditions on deletions with upsert in PostgreSQL ``storage.update()`` (fixes #1202)
- Fix PostgreSQL backend race condition when replacing permissions of an object (fixes #1210)
- Fix crash when deleting multiple buckets with quotas plugin enabled (fixes #1201)
- The ``default_bucket`` plugin no longer sends spurious "created"
  events for buckets and collections that already exist. This causes
  the ``quotas`` plugin to no longer leak "quota" when used with the
  ``default_bucket`` plugin. (#1226)
- Fix removal of timestamps when parent object is deleted (fixes #1233)
- Do not allow to reuse deletion tokens (fixes #1171)
- ``accounts`` plugin: fix exception on authentication. (#1224)
- Fix crash with JSONSchema validation of unknown required properties (fixes #1243)
- Fix bug on bucket deletion where other buckets could be deleted too if their id
  started with the same id
- Fix permissions of accounts created with PUT by admin (ref #1248)
- Fix ownership of accounts created with POST by admin (fixes #1248)

**Internal changes**

- Do not keep the whole Kinto Admin bundle in the repo (fixes #1012)
- Remove the email example from the custom code event listener tutorial (fixes #420)
- Removed useless logging info from resource (ref #603)
- Make sure prefixed userid is always first in principals
- Run functional tests on PostgreSQL
- Fix tests with Pyramid 1.9a
- Removed useless deletions in quota plugin
- Upgraded the kinto-admin to version 1.13.2

kinto-signer
------------

**kinto-signer 1.3.3 → 1.4.0**: https://github.com/Kinto/kinto-signer/releases/tag/1.4.0

**Internal changes**

- Upgrade to kinto 7.1


2.2.0 (2017-05-25)
==================

kinto
-----

**kinto 6.0.8 → 6.1.0**: https://github.com/Kinto/kinto/releases/tag/6.1.0

**New feature**

- ``kinto rebuild-quotas`` script was written that can be run to
  repair the damage caused by #1226 (fixes #1230).

**Bug fixes**

- The ``default_bucket`` plugin no longer sends spurious "created"
  events for buckets and collections that already exist. This causes
  the ``quotas`` plugin to no longer leak "quota" when used with the
  ``default_bucket`` plugin. (#1226)
- Fix race conditions on deletions with upsert in PostgreSQL ``storage.update()`` (fixes #1202).
- Fix PostgreSQL backend race condition when replacing permissions of an object (fixes #1210)
- Fix missing package.json file in package. (#1222)
- Fix removal of timestamps when parent object is deleted (fixes #1233)


2.1.3 (2017-05-04)
==================

kinto
-----

**kinto 6.0.7 → 6.0.8**: https://github.com/Kinto/kinto/releases/tag/6.0.8

**Bug fixes**

- Prevent PostgreSQL backend from deleting records of the same name in other buckets and collections when deleting a bucket. (fixes Kinto/kinto#1209)


2.1.2 (2017-04-27)
==================

kinto
-----

**kinto 6.0.6 → 6.0.7**: https://github.com/Kinto/kinto/releases/tag/6.0.7

**Bug fixes**

- Fix the kinto-admin to use PATCH instead of PUT when asking for a review.


2.1.1 (2017-04-26)
==================

kinto
-----

**kinto 6.0.4 → 6.0.6**: https://github.com/Kinto/kinto/releases/tag/6.0.6

**Bug fixes**

- Return a 400 Bad Request instead of crashing when the querystring contains bad characters. (Kinto/kinto#1195)
- Fixed Postgresql errors when specifying empty values in querystring numeric filters. (Kinto/kinto#1194)
- Upgrade the kinto-admin to v1.13.3

kinto-admin
-----------

**kinto-admin 1.13.2 → 1.13.3**: https://github.com/Kinto/kinto-admin/releases/tag/v1.13.3

**Bug fixes**

- Fix signoff plugin membership checks. (Kinto/kinto-admin#429).
  This was preventing using and navigating within signoff plugin views.


kinto-signer
------------

**kinto-signer 1.3.2 → 1.3.3**: https://github.com/Kinto/kinto-signer/releases/tag/1.3.3

**Bug fixes**

- Do not send ``ReviewApproved`` event when signing a collection that is already signed (Kinto/kinto-signer#174)



2.1.0 (2017-04-14)
==================

kinto
-----

**kinto 6.0.1 → 6.0.4**: https://github.com/Kinto/kinto/releases/tag/6.0.4

**Bug fixes**

- Fixed Swagger when routes contain subpath/regexp (Kinto/kinto#1180)


kinto-attachment
----------------

**kinto-attachment 2.0.0 → 2.0.1**: https://github.com/Kinto/kinto-attachment/releases/tag/2.0.1

**Bug fixes**

- Set request parameters before instantiating a record resource. (Kinto/kinto-attachment#127)


kinto-admin
-----------

**kinto-admin 1.10.0 → 1.13.2**: https://github.com/Kinto/kinto-admin/releases/tag/v1.13.2

**New features**

* Add review/decline comments (Kinto/kinto-admin#417)
* Limit number of collections listed in the sidebar. (Kinto/kinto-admin#410)
* Collection full diff view improvements. (Kinto/kinto-admin#409)
* Add support for Portier authentication. (Kinto/kinto-admin#395)

**Bug fixes**

* Preload all collections to populate state. (Kinto/kinto-admin#418)
* Order history entry target permissions consistently. (Kinto/kinto-admin#413)
* Fix Portier broken redirect URL handling after successful auth when coming from the homepage (Kinto/kinto-admin#414)
* Restore auth form contextual help. (Kinto/kinto-admin#396)
* Fix broken post-auth redirections. (Kinto/kinto-admin#397)
* Retrieve all paginated permissions. (Kinto/kinto-admin#400)


kinto-emailer
-------------

**kinto-emailer 0.3.0 → 0.4.0**: https://github.com/Kinto/kinto-emailer/releases/tag/0.4.0

**New features**

- Add a ``validate_setup.py`` script to check that server can actually send emails
- Add a ``kinto-send-email`` command to test the configuration (kinto/kinto-emailer#35)

**Bug fixes**

- Fix sending notifications by decoupling it from transactions (kinto/kinto-emailer#38)


kinto-signer
------------

**kinto-signer 1.3.0 → 1.3.2**: https://github.com/Kinto/kinto-signer/releases/tag/1.3.2

**Bug fixes**

- Allow ``canonical_json`` to work with iterators. (Kinto/kinto-signer#167)
- Fixed inconsistencies in ``ResourceChanged`` produced by Kinto signer (Kinto/kinto-signer#169)
- Update e2e.py to be robust against kinto_client returning an iterator in Python 3. (Kinto/kinto-signer#165)
- Send kinto-signer before committing since some database may have to be performed
  in the subscribers (Kinto/kinto-signer#172)


2.0.1 (2017-03-10)
==================

kinto
-----

**kinto 6.0.0 → 6.0.1**: https://github.com/Kinto/kinto/releases/tag/6.0.1

**Bug fixes**

- Fix Memory backend sometimes show empty permissions (Kinto/kinto#1045)
- Allow to create default bucket with a PUT request and an empty body (Kinto/kinto#1080)
- Fix PostgreSQL backend when excluding a list of numeric values (Kinto/kinto#1093)
- Fix ``ignore_conflict`` storage backend create method parameter to
  keep the existing rather than overriding it. (Kinto/kinto#1134)
- Fix impacted records of events generated by implicit creation in default
  bucket (Kinto/kinto#1137)

kinto-ldap
----------

**kinto-ldap 0.3.0 → 0.3.1**: https://github.com/Kinto/kinto-ldap/releases/tag/0.3.1

**Bug fixes**

- Fix support with Kinto 6 and Python 3. (Kinto/kinto-ldap#18)


2.0.0 (2017-03-06)
==================

Configuration Breaking Changes
------------------------------

* ``kinto_changes`` must now be present in ``kinto.includes`` (eg. on read-only stacks)
  otherwise the monitoring endpoint won't be accessible.
* The configuration of *kinto-changes* has to be changed:

Before:

.. code-block :: ini

    kinto.event_listeners = changes
    kinto.event_listeners.changes.use = kinto_changes.listener
    kinto.event_listeners.changes.http_host = website.domain.tld
    kinto.event_listeners.changes.collections = /buckets/settings
                                                /buckets/blocklists/collections/certificates

Now:

.. code-block :: ini

    kinto.changes.http_host = website.domain.tld
    kinto.changes.resources = /buckets/settings
                              /buckets/blocklists/collections/certificates


kinto
-----

**kinto 5.4.1 → 6.0.0**: https://github.com/Kinto/kinto/releases/tag/6.0.0

**Breaking changes**

- Remove Python 2.7 support and upgrade to Python 3.5. (Kinto/kinto#1050)
- Upgraded minimal PostgreSQL support to PostgreSQL 9.5 (Kinto/kinto#1056)
- The ``--ini`` parameter is now after the subcommand name (Kinto/kinto#1095)

**Protocol**

- Fixed ``If-Match`` behavior to match the RFC 2616 specification (Kinto/kinto#1102).
- A ``409 Conflict`` error response is now returned when some backend integrity
  constraint is violated (instead of ``503``) (Kinto/kinto#602)

Protocol is now at version **1.15**. See `API changelog`_.

**Bug fixes**

- Prevent injections in the PostgreSQL permission backend (Kinto/kinto#1061)
- Fix crash on ``If-Match: *`` (Kinto/kinto#1064)
- Handle Integer overflow in querystring parameters. (Kinto/kinto#1076)
- Flush endpoint now returns an empty JSON object instad of an HTML page (Kinto/kinto#1098)
- Fix nested sorting key breaks pagination token. (Kinto/kinto#1116)
- Remove ``deleted`` field from ``PUT`` requests over tombstones. (Kinto/kinto#1115)
- Fix crash when preconditions are used on the permission endpoint (Kinto/kinto#1066)
- Fixed resource timestamp upsert in PostgreSQL backend (Kinto/kinto#1125)
- Fix pserve argument ordering with Pyramid 1.8 (Kinto/kinto#1095)

**Internal changes**

- Update the upsert query to use an INSERT or UPDATE on CONFLICT behavior (Kinto/kinto#1055)
- Permission schema children fields are now set during initialization instead of on
  deserialization (Kinto/kinto#1046).
- Request schemas (including validation and deserialization) are now isolated by method
  and endpoint type (Kinto/kinto#1047).
- Move generic API schemas (e.g TimeStamps and HeaderFields) from `kinto.core.resource.schema`
  to a sepate file on `kinto.core.schema`. (Kinto/kinto#1054)
- Upgraded the kinto-admin to version 1.10.0 (Kinto/kinto#1086, Kinto/kinto#1128)
- Upgrade to Pyramid 1.8 (Kinto/kinto#1087)
- Use `Cornice Swagger <https://github.com/Cornices/cornice.ext.swagger>`_ rather than
  merging YAML files to generate the OpenAPI spec.
- Gracefully handle ``UnicityError`` with the ``default_bucket`` plugin and
  the PostgreSQL backend using PostgreSQL 9.5+ ``ON CONFLICT`` clause. (Kinto/kinto#1122)

kinto-attachment
----------------

**kinto-attachment 1.1.2 → 2.0.0**: https://github.com/Kinto/kinto-attachment/releases/tag/2.0.0

- Remove Python 2.7 support and upgrade to Python 3.5. (Kinto/kinto-attachment#125)

kinto-changes
-------------

**kinto-changes 0.5.0 → 1.0.0**: https://github.com/Kinto/kinto-changes/releases/tag/1.0

**Breaking changes**

* The change endpoint **location is now hard-coded** (``/buckets/monitor/collections/changes/records``)
  and cannot be configured.
* The permissions principals cannot be specified anymore.
  The change endpoint is now **always public**.
* The ``monitor`` bucket and ``changes`` collection are not required anymore and
  are not created anymore.
* ``POST`` and ``DELETE`` are not supported on the changes endpoint anymore.
* Individual entries (eg. ``/buckets/monitor/collections/changes/records/{id}``)
  cannot be accessed anymore.
* The listener was dropped. Configuration must be changed (see above)

kinto-signer
------------

**kinto-signer 1.2.0 → 1.3.0**: https://github.com/Kinto/kinto-signer/releases/tag/1.3.0

- Update e2e.py script to be compatible with Python 3.5 (Kinto/kinto-signer#165)


1.13.1 (2017-02-24)
===================

kinto
-----

**kinto 5.4.0 → 5.4.1**: https://github.com/Kinto/kinto/releases/tag/5.4.1

**Bug fixes**

- Fix unexpected references on the swagger spec that failed validation. (Kinto/kinto#1108)


1.13.0 (2017-02-21)
===================

amo2kinto
---------

**amo2kinto 1.6.0 → 1.7.2**: https://github.com/mozilla-services/kinto-amo/releases/tag/1.7.2

**Bug fixes**

- Fix XML exporter on missing blockID. (mozilla-services/amo2kinto#63)

kinto
-----

**kinto 5.3.5 → 5.3.6**: https://github.com/Kinto/kinto/releases/tag/5.3.6

**Bug fixes**

- Fix crash on ``If-Match: *`` (Kinto/kinto#1064)
- Handle Integer overflow in querystring parameters. (Kinto/kinto#1076)

kinto-admin
-----------

**kinto-admin 1.8.1 → 1.9.0**: https://github.com/Kinto/kinto-admin/releases/tag/v1.9.0

**New Feature**

- Fix Kinto/kinto-admin#377, Kinto/kinto-admin#378: Allow dropping edited resource properties. (Kinto/kinto-admin#379)
- Fix Kinto/kinto-admin#365: Render a JSON diff for history entries. (Kinto/kinto-admin#380)
- Fix Kinto/kinto-admin#376: Denote readonly buckets & collections in the sidebar. (Kinto/kinto-admin#382)
- Fix Kinto/kinto-admin#384: Live-searchable/filterable sidebar entries. (Kinto/kinto-admin#385)
- Hide auth method selector when a single one is configured.

**Bug fixes**

- Do not store passwords. Fixes #364 (#386)


1.12.1 (2017-02-08)
===================

kinto
-----

**kinto 5.3.4 → 5.3.5**: https://github.com/Kinto/kinto/releases/tag/5.3.5

**Bug fixes**

- Prevent injections in the PostgreSQL permission backend (Kinto/kinto#1061)


1.12.0 (2017-02-02)
===================

kinto
-----

**kinto 5.3.2 → 5.3.4**: https://github.com/Kinto/kinto/releases/tag/5.3.4

**Bug fixes**

- Update the upsert query to use an INSERT or UPDATE on CONFLICT behavior (Kinto/kinto#1055)

kinto-attachment
----------------

**kinto-attachment 1.0.1 → 1.1.2**: https://github.com/Kinto/kinto-attachment/releases/tag/1.1.2

**New features**

- Expose the gzipped settings value in the capability (Kinto/kinto-attachment#117)

**Bug fixes**

- Fixes crash when adding attachment to existing record with Kinto 5.3 (Kinto/kinto-attachment#120)
- Fix invalid request when attaching a file on non UUID record id (Kinto/kinto-attachment#122)


1.11 (2017-01-31)
=================

kinto
-----

**kinto 5.3.1 → 5.3.2**: https://github.com/Kinto/kinto/releases/tag/5.3.2

**Bug fixes**

- Retries to set value in PostgreSQL cache backend in case of BackendError (Kinto/kinto#1052)


1.10 (2017-01-30)
=================

kinto
-----

**kinto 5.3.0 → 5.3.1**: https://github.com/Kinto/kinto/releases/tag/5.3.1


**Bug fixes**

- Retries to set value in PostgreSQL cache backend in case of IntegrityError (Kinto/kinto#1035)
- Display Kinto-Admin version number in the footer. (Kinto/kinto#1040)
- Configure the Kinto Admin auth methods from the server configuration (Kinto/kinto#1042)


kinto-emailer
-------------

**kinto-emailer 0.3.0**: https://github.com/Kinto/kinto-emailer/releases/tag/0.3.0

This package allows to send email notifications when something happens in a bucket
or on a collection.

Emailing configuration is done in ``.ini`` whereas notifications configuration is done
via the HTTP API within bucket or collection metadata.

.. code-block:: ini

    kinto.includes = kinto_emailer

    mail.default_sender = firefox-settings-notifs@mozilla.com
    # mail.host = localhost
    # mail.port = 25
    # mail.username = None
    # mail.password = None

See more details in `Pyramid Mailer documentation <http://docs.pylonsproject.org/projects/pyramid_mailer/en/latest/#configuration>`_.


kinto-fxa
---------

**kinto-fxa 2.3.0 → 2.3.1**: https://github.com/Kinto/kinto-fxa/releases/tag/2.3.0

**Bug fixes**

- Make sure that caching of token verification nevers prevents from authenticating
  requests (see Mozilla/PyFxA#48)


1.9 (2017-01-24)
================

kinto-signer
------------

**kinto 5.2.0 → 5.3.0**: https://github.com/Kinto/kinto/releases/tag/5.3.0


**Bug fixes**

- Fix crash with batch endpoint when list of requests contains trailing comma (Kinto/kinto#1024)
- Cache backend transactions are not bound to the request/response cycle anymore (Kinto/kinto#879)


**kinto-changes 1.1.1 → 1.2.0**: https://github.com/Kinto/kinto-changes/releases/tag/1.2.0

**Bug fixes**

- Do not always reset destination permissions

**New features**

- Pyramid events are sent for each review step of the validation workflow (fixes #157)
- Kinto Admin UI fields like ``displayFields`` ``attachment`` and ``sort`` are copied
  from the source to the preview and destination collections (if not set) (fixes #161)

**kinto-admin 1.7.0 → 1.8.0**: https://github.com/Kinto/kinto-admin/releases/tag/v1.8.0

**Bug fixes**

- Fix Kinto/kinto-admin#353: Show changes in review step even if no permission to approve
- Fix Kinto/kinto-admin#248: Prevent crash on *uiSchema* validation when the entered JSON schema is invalid
- Fix Kinto/kinto-admin#302: Make whole menu entry area clickable for collections

**New features**

- Add a JSON editor for raw collection attributes. (Kinto/kinto-admin#116, Kinto/kinto-admin#371)
- Don't fail when fetching the list of buckets returns a HTTP 403. (Kinto/kinto-admin#370)
- Retry requests once (Kinto/kinto-admin#368)


1.8 (2017-01-16)
================

kinto-changes
-------------

**kinto-changes 0.4.0 → 0.5.0**: https://github.com/Kinto/kinto-changes/releases/tag/0.5.0

**Bug fixes**

- Do not force the timestamp of monitored entries, to avoid possible integrity errors (Kinto/kinto-changes#27)


kinto-signer
------------

**kinto-signer 1.0.0 → 1.1.1**: https://github.com/Kinto/kinto-signer/releases/tag/1.1.1

**Bug fixes**

- Fix consistency of setting names for per-collection workflows configuration (Kinto/kinto-signer#149)
- Remove recursivity of events when requesting review (Kinto/kinto-signer#158)


1.7 (2017-01-12)
================


Kinto
-----

**kinto 5.1.0 → 5.2.0**: https://github.com/Kinto/kinto/releases/tag/5.2.0

**Protocol**

- Add an `OpenAPI specification <https://kinto.readthedocs.io/en/latest/api/1.x/openapi.html>`_ for the HTTP API on ``/__api__`` (Kinto/kinto#997)

**New features**

- When admin is enabled, ``/v1/admin`` does not return ``404`` anymore, but now redirects to
  ``/v1/admin/`` (with trailing slash).

**Bug fixes**

- Add missing ``Total-Records`` field on ``DELETE`` header with plural endpoints (fixes Kinto/kinto#1000)


kinto-admin
-----------

**kinto-admin 1.6.1 → 1.7.0**: https://github.com/Kinto/kinto-admin/releases/tag/v1.7.0

* Added a TagsField form component (eg. devices list) (Kinto/kinto-admin#367)


1.6 (unreleased)
================

**Upgrade notes**

- Replace ``kinto_admin`` by ``kinto.plugins.admin`` for ``kinto.includes``
  setting in the INI file.

.. code-block:: ini

    kinto.includes = kinto.plugins.admin

- We can skip the history on the preview and production buckets:

.. code-block:: ini

    kinto.history.exclude_resources = /buckets/blocklists
                                      /buckets/blocklists-preview

Kinto
-----

**kinto 4.3.6 → 5.1.0**: https://github.com/Kinto/kinto/releases/tag/5.1.0

**Protocol**

- Add support for `JSON-Patch (RFC 6902) <https://tools.ietf.org/html/rfc6902>`_.
- Add support for `JSON-Merge (RFC 7396) <https://tools.ietf.org/html/rfc7396>`_.
- Added a principals list to ``hello`` view when authenticated.
- Added details attribute to 404 errors. (Kinto/kinto#818)
- Add a ``basicauth`` capability when activated on the server. (Kinto/kinto#937)
- Add ability to delete history entries using ``DELETE`` (Kinto/kinto#958)

**New features**

- Added a new built-in plugin ``kinto.plugins.admin`` to serve the kinto admin.
- Added a new ``parse_resource`` utility to ``kinto.core.utils``
- Add a setting to limit the maximum number of bytes cached in the memory backend. (Kinto/kinto#610)
- Add a setting to exclude certain resources from being tracked by history (Kinto/kinto#964)


kinto-admin
-----------

**kinto-admin 1.5.1 → 1.6.0**: https://github.com/Kinto/kinto-admin/releases/tag/v1.6.0

**New features**

* Fix Kinto/kinto-admin#208: Generalized pagination. (Kinto/kinto-admin#352)
* Fix Kinto/kinto-admin#208: Paginate history. (Kinto/kinto-admin#351)
* Add support for gzipped option on attachments (Kinto/kinto-admin#358)

**Bug fixes**

* Fix Kinto/kinto-admin#349: [signoff] Update the lastSigned timestamp. (Kinto/kinto-admin#362)
* Fix Kinto/kinto-admin#350: work-in-progress infos (Kinto/kinto-admin#363)
* Fix Kinto/kinto-admin#273: Prevent overriding members list in group edition form. (Kinto/kinto-admin#346)
* Typo in capabilities property name (Kinto/kinto-admin#357)


kinto-fxa
---------

**kinto-fxa 2.2.0 → 2.3.0**: https://github.com/mozilla-services/kinto-fxa/releases/2.3.0

- Compatibility with Kinto 5


1.5 (2016-12-01)
================

- Create a Dockerfile that matches Dockerflow. (#84)


1.4 (2016-11-28)
================

Kinto
-----

**kinto 4.3.4 → 4.3.6**: https://github.com/Kinto/kinto-admin/releases/tag/4.3.6

**Bug fixes**

- Fix crash in permission endpoint when merging permissions from settings and from
  permissions backend (fixes #926)
- Fix crash in PostgreSQL backend when specified bound permissions is empty (fixes #906)
- Fix response status for OPTION request on version redirection (fixes #852)
- Fix crash in authorization policy when object ids contain unicode (fixes #931)
- Permissions are now correctly removed from permission backend when a parent
  object is deleted (fixes #898)
- Add deletion of multiple groups in API docs (#928)
- Fix ``record_id`` attribute in history entries when several records are
  modified via a batch request (fixes #942)


kinto-admin
-----------

**kinto-admin 1.5.0 → 1.5.1**: https://github.com/Kinto/kinto-admin/releases/tag/1.5.1

**Bug fixes**

- Fix #339: Fix server history not saved. (#342)
- Fix #340: Fix broken saved session restore. (#341)
- Fix #332: Display app version number in the footer. (#338)
- Fix broken timeago helper. (#335)
- Fix #336: Fix cannot save bucket attributes upon creation. (#337)


kinto-ldap
----------

**kinto-ldap 0.2.1 → 0.3.0**: https://github.com/Kinto/kinto-ldap/releases/tag/0.3.0

**New features**

- Support login from multiple DN from the same LDAP server (Kinto/kinto-ldap#16)

1.3 (2016-11-18)
================

Kinto
-----

**kinto 4.3.3 → 4.3.4**: https://github.com/Kinto/kinto-admin/releases/tag/4.3.4

**Bug fixes**

- Fix bug when two subfields are selected in partial responses (fixes Kinto/kinto#920)


kinto-admin
-----------

**kinto-admin 1.4.3 → 1.5.0**: https://github.com/Kinto/kinto-admin/releases/tag/1.5.0

**New features**

- Auth form improvements (Kinto/kinto-admin#327, Kinto/kinto-admin#327#328)
- Review workflow UI improvements. (Kinto/kinto-admin#319, Kinto/kinto-admin#322)

**Bug fixes**

- Hide details on review step link when history capability is unavailable. (Kinto/kinto-admin#325)
- Relative time fixes (Kinto/kinto-admin#324)
- Workflow history of changes now only shows records (Kinto/kinto-admin#320)
- Fix lost list of groups when using signoff plugin. (Kinto/kinto-admin#321)


1.2 (2016-11-15)
================

Kinto
-----

**kinto 4.3.2 → 4.3.3**: https://github.com/Kinto/kinto-admin/releases/tag/4.3.3

**Bug fixes**

- Fix crash when querystring parameter contains null string (fixes #882)
- Permissions endpoint now exposes the user permissions defined in settings (fixes #909)
- Fix crash when redirection path contains CRLF character (fixes #887)



kinto-admin
-----------

**kinto-admin 1.4.2 → 1.4.3**: https://github.com/Kinto/kinto-admin/releases/tag/1.4.3

**Bug fixes**

- Fix #311: check object permissions via parents objects too (#312)
- Fix #309: hide server URL from authentication form (#310)


1.1 (2016-11-09)
================

kinto-ldap
----------

**kinto-ldap 0.1.0 → 0.2.1**: https://github.com/Kinto/kinto-ldap/releases/tag/0.2.1

**New features**

- Set default value for ``multiauth.policy.ldap.use`` (fixes #3)
- Add the plugin version in the hello view capabilities.
- Add connection pool settings (fixes #10)

.. code-block:: ini

    # kinto.ldap.pool_size = 10
    # kinto.ldap.pool_retry_max = 3
    # kinto.ldap.pool_retry_delay = .1
    # kinto.ldap.pool_timeout = 30

**Bug fixes**

- Fix heartbeat when server is unreachable (fixes #8)
- Fix heartbeat that would always return False (#14)
- Do not crash and log exception if LDAP when server is unreachable (fixes #9)

kinto-changes
-------------

**kinto-changes 0.3.0 → 0.4.0**: https://github.com/Kinto/kinto-changes/releases/tag/0.4.0

**New features**

- Add the plugin version in the capability (Kinto/kinto-changes#20)
- Add collections in the capability (Kinto/kinto-changes#18)
- Add a specific setting to override global ``http_host`` value (Kinto/kinto-changes#24)

.. code-block:: ini

    kinto.event_listeners.changes.http_host = firefox.settings.services.mozilla.com


kinto-admin
-----------

**kinto-admin 1.4.1 → 1.4.2**: https://github.com/Kinto/kinto-admin/releases/tag/1.4.2

**Bug fixes**

- Fix #299: Fix broken attachment creation. (#305)
- Fix #303: Fix attachment link in records list. (#306)
- Fix #307: Always show hooks on collection records page (#308)


1.0 (2016-10-28)
================

kinto-admin
-----------

**kinto-admin 1.4.1**: https://github.com/Kinto/kinto-admin/releases/tag/v1.4.1

See `changelog for kinto-admin 1.4.0 <https://github.com/Kinto/kinto-admin/releases/tag/v1.4.0>`_


kinto-amo
---------

**kinto-amo 0.2.0 → 0.3.0**: https://github.com/mozilla-services/kinto-amo/releases/tag/0.3.0

- Enable preview XML endpoint:

.. code-block:: ini

    kinto.amo.preview.addons = /buckets/blocklists-preview/collections/addons
    kinto.amo.preview.plugins = /buckets/blocklists-preview/collections/plugins
    kinto.amo.preview.gfx = /buckets/blocklists-preview/collections/gfx
    kinto.amo.preview.certificates = /buckets/blocklists-preview/collections/certificates

Then you can access kinto-amo endpoints:

- ``/v1/preview/3/{3550f703-e582-4d05-9a08-453d09bdfdc6}/47.0/``


kinto-signer
------------

**kinto-signer 0.9.2 → 1.0.0**: https://github.com/Kinto/kinto-signer/releases/tag/1.0.0

- Review and group check features can be set/overriden by collection in settings:

.. code-block:: ini

    kinto.signer.staging_certificates_group_check_enabled = true
    kinto.signer.staging_certificates_to_review_enabled = true
    kinto.signer.staging_certificates_editors_group = certificates-editors
    kinto.signer.staging_certificates_reviewers_group = certificates-reviewers

You can also update the signer to configure preview there:

.. code-block:: ini

    kinto.signer.resources =
      /buckets/staging/collections/addons;/buckets/blocklists-preview/collections/addons;/buckets/blocklists/collections/addons
      /buckets/staging/collections/plugins;/buckets/blocklists-preview/collections/plugins;/buckets/blocklists/collections/plugins
      /buckets/staging/collections/gfx;/buckets/blocklists-preview/collections/gfx;/buckets/blocklists/collections/gfx
      /buckets/staging/collections/certificates;/buckets/blocklists-preview/collections/certificates;/buckets/blocklists/collections/certificates

See `changelog for kinto-dist 0.9.0 <https://github.com/mozilla-services/kinto-dist/releases/tag/0.9.0>`_
or `kinto-signer documentation <https://github.com/Kinto/kinto-signer/>`_
for more details about workflows.


kinto-fxa
---------

**kinto-fxa 2.1.0 → 2.2.0**: https://github.com/mozilla-services/kinto-fxa/releases/2.2.0


0.9.1 (2016-10-06)
==================

Kinto
-----

**kinto 4.3.0 → 4.3.1**: https://github.com/Kinto/kinto/releases/tag/4.3.1

kinto-signer
------------

**kinto-signer 0.9.1 → 0.9.2**: https://github.com/Kinto/kinto-signer/releases/tag/0.9.2


0.9.0 (2016-10-04)
==================

Kinto
-----

**kinto 3.3.2 → 4.3.0**: https://github.com/Kinto/kinto/releases/tag/4.3.0

**Highlights**

- Redis backends were dropped from core, and are now packaged separately in
  `kinto-redis <https://github.com/Kinto/kinto-redis/>`_
- New ``/__version__`` endpoint which reads a ``version.json`` file to expose what version
  has been deployed. Its location can be specified in the ``kinto.version_json_path``
  setting (fixes #830)
- New built-in plugin ``kinto.plugins.history`` to track history of changes per bucket
  from the Kinto Admin UI (*must be added explicity in the ``kinto.includes`` setting*)
- ``kinto migrate`` now accepts a ``--dry-run`` option which details the operations
  to be made without executing them.
- New built-in plugin ``kinto.plugins.quotas`` to set storage quotas per bucket/collection
  (c.f. *Web Extensions* storage)
- The history and quotas plugins execution time is now monitored on StatsD
  (``kinto.plugins.quotas`` and ``kinto.plugins.history``) (#832)
- The permissions attribute is now empty in the response if the user has not
  the permission to write on the object (Kinto/kinto#123)
- Parent attributes are now readable if children creation is allowed (Kinto/kinto#803)
- New ``kinto delete-collection`` command to delete a collection from the command-line.

kinto-admin
-----------

**kinto-admin 1.3.0**: https://github.com/Kinto/kinto-admin/releases/tag/v1.3.0

- Add views for browsing a collection history (#196)
- Updated kinto-http to v2.3.0.
- Activate the signoff plugin to allow triggering a signature from the Admin.

kinto-signer
------------

**kinto-signer 0.7.3 → 0.9.1**: https://github.com/Kinto/kinto-signer/releases/tag/0.9.0

The API can now **optionally** rely on a workflow and can check that users changing collection status
belong to some groups (e.g. ``editors``, ``reviewers``). With that feature enabled,
the signature of the collection will have to follow this workflow:

- an *editor* will request a review by setting the collection status to ``to-review``;
- a preview collection will be updated and signed so that QA can validate the changes
  on the client side;
- a *reviewer* — different from the last editor — will trigger the signature by setting
  the status to ``to-sign`` as before.

In order to enable this feature, the following procedure must be followed:

- Change the resources settings to add a *preview* collection URL (``{source};{preview};{destination}``)

..code-block:: ini

    kinto.signer.resources =
      /buckets/staging/collections/certificates;/buckets/preview/collections/certificates;/buckets/blocklists/collections/certificates

- Enable the review and group check features:

..code-block:: ini

    kinto.signer.to_review_enabled = true
    kinto.signer.group_check_enabled = true

- Last, create ``editors`` and ``reviewers`` groups in the *staging* bucket, and
  add appropriate usernames to it. The groups can now be managed from the
  Kinto Admin UI. Otherwise via the command-line:

..code-block:: bash

    $ echo '{"data": {"members": ["ldap:some@one.com"]}}' | \
        http PUT $SERVER_URL/buckets/staging/groups/editors --auth="admin:token"


    $ echo '{"data": {"members": ["ldap:some@one.com"]}}' | \
        http PUT $SERVER_URL/buckets/staging/groups/editors --auth="admin:token"


0.8.2 (2016-09-12)
==================

**Upgrade to kinto 3.3.3**

**Bug fixes**

- Fix heartbeat transaction locks with PostgreSQL backends (fixes Kinto/kinto#804)


0.8.1 (2016-07-27)
==================

- Add the kinto-dist version in the plugin capability. (#40)

**kinto-signer 0.7.2 → 0.7.3**: https://github.com/Kinto/kinto-signer/releases/tag/0.7.3

**Bug fixes**

- Fix signature inconsistency (timestamp) when several changes are sent from
  the *source* to the *destination* collection.
  Fixed ``e2e.py`` and ``validate_signature.py`` scripts (Kinto/kinto-signer#110)

**Minor change**

- Add the plugin version in the capability. (Kinto/kinto-signer#108)


0.8.0 (2016-07-25)
==================

Kinto
-----

**kinto 3.3.0 → 3.3.2**: https://github.com/Kinto/kinto/releases/tag/3.3.2

**Bug fixes**

- Fix Redis get_accessible_object implementation (kinto/kinto#725)
- Fix bug where the resource events of a request targetting two groups/collection
  from different buckets would be grouped together (kinto/kinto#728)


kinto-signer
------------

**kinto-signer 0.7.1 → 0.7.2**: https://github.com/Kinto/kinto-signer/releases/tag/0.7.2

**Bug fixes**

- Provide the ``old`` value on destination records updates (kinto/kinto-signer#104)
- Send ``create`` event when destination record does not exist yet.
- Events sent by kinto-signer for created/updated/deleted objects in destination now show
  user_id as ``plugin:kinto-signer``


0.7.0 (2016-07-19)
==================

**kinto-admin 1.2.0**: https://github.com/Kinto/kinto-admin/releases/tag/1.2.0

Kinto
-----

**kinto 3.2.2 → 3.3.0**: https://github.com/Kinto/kinto/releases/tag/3.3.0

**API**

- Add new *experimental* endpoint ``GET /v1/permissions`` to retrieve the list of permissions
  granted on every kind of object (#600).
  Requires setting ``kinto.experimental_permissions_endpoint`` to be set to ``true``.

API is now at version **1.8**. See `API changelog <http://kinto.readthedocs.io/en/latest/api/>`_.

**Bug fixes**

- Allow filtering and sorting by any attribute on buckets, collections and groups list endpoints
- Fix crash in memory backend with Python3 when filtering on unknown field


Kinto-attachment
----------------

**kinto-attachment 0.7.0 → 0.8.0**: https://github.com/Kinto/kinto-attachment/releases/tag/0.8.0

**New features**

- Prevent ``attachment`` attributes to be modified manually (fixes Kinto/kinto-attachment#83)

**Bug fixes**

- Fix crash when the file is not uploaded using ``attachment`` field name (fixes Kinto/kinto-attachment#57)
- Fix crash when the multipart content-type is invalid.
- Prevent crash when filename is not provided (fixes Kinto/kinto-attachment#81)
- Update the call to the Record resource to use named attributes. (Kinto/kinto-attachment#97)
- Show detailed error when data is not posted with multipart content-type.
- Fix crash when submitted data is not valid JSON (fixes Kinto/kinto-attachment#104)


0.6.3 (2016-07-21)
==================

- Take the correct Kinto 3.2.4 version.


0.6.2 (2016-07-21)
==================

* Add integration test for every enabled plugins

Kinto
-----

**kinto 3.2.2 → 3.2.4**: https://github.com/Kinto/kinto/releases/tag/3.2.4

**Bug fixes**

- Fix bug where the resource events of a request targetting two groups/collection
  from different buckets would be grouped together (#728).
- Allow filtering and sorting by any attribute on buckets, collections and groups list endpoints
- Fix crash in memory backend with Python3 when filtering on unknown field
- Fix bug in object permissions with memory backend (#708)
- Make sure the tombstone is deleted when the record is created with PUT. (#715)
- Bump ``last_modified`` on record when provided value is equal to previous
  in storage ``update()`` method (#713)


kinto-signer
------------

**kinto-signer 0.7.0 → 0.7.1**: https://github.com/Kinto/kinto-signer/releases/tag/0.7.1

**Bug fix**

- Update the `last_modified` value when updating the collection status and signature
  (kinto/kinto-signer#97)
- Trigger ``ResourceChanged`` events when the destination collection and records are updated
  during signing. This allows plugins like ``kinto-changes`` and ``kinto.plugins.history``
  to catch the changes (kinto/kinto-signer#101)


0.6.1 (2016-07-13)
==================

Kinto
-----

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
-----

**kinto 2.1.2 → 3.2.0**: https://github.com/Kinto/kinto/releases/tag/3.2.0

**API**

- Added the ``GET /contribute.json`` endpoint for open-source information (fixes #607)
- Allow record IDs to be any string instead of just UUIDs (fixes #655).

API is now at version **1.7**. See `API changelog <http://kinto.readthedocs.io/en/latest/api/>`_.

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
----------------

**kinto-attachment 0.5.0 → 0.7.0**: https://github.com/Kinto/kinto-attachment/releases/tag/0.7.0

**Breaking changes**

- When the gzip option is used during upload, the ``original`` attribute  is now within
  the ``attachment`` information.

**New features**

- Kinto 3.0 compatibility update
- Add a ``kinto.attachment.extra.base_url`` settings to be exposed publicly. (#73)
- Add the gzip option to automatically gzip files on upload (#85)


kinto-amo
---------

**kinto-amo 0.1.0 → 0.2.0**: https://github.com/mozilla-services/kinto-amo/releases/tag/0.2.0

- Kinto 3.0 compatibility update


kinto-changes
-------------

**kinto-changes 0.2.0 → 0.3.0**: https://github.com/Kinto/kinto-changes/releases/tag/0.3.0

- Kinto 3.0 compatibility update


kinto-signer
------------

**kinto-signer 0.4.0 → 0.7.0**: https://github.com/Kinto/kinto-signer/releases/tag/0.7.0

**Breaking changes**

- The collection timestamp is now included in the payload prior to signing.
  Old clients won't be able to verify the signature made by this version.

**Bug fixes**

- Do not crash on record deletion if destination was never synced (Kinto/kinto-signer#82)

**New features**

- Raise configuration errors if resources are not configured correctly (Kinto/kinto-signer#88)


kinto-fxa
---------

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
----------

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
