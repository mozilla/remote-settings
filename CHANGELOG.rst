CHANGELOG
#########

This document describes changes between each past release as well as
the version control of each dependency.

1.12.1 (2017-02-08)
===================

kinto
'''''

**kinto 5.3.4 → 5.3.5**: https://github.com/Kinto/kinto/releases/tag/5.3.5

**Bug fixes**

- Prevent injections in the PostgreSQL permission backend (#1061)


1.12.0 (2017-02-02)
===================

kinto
'''''

**kinto 5.3.2 → 5.3.4**: https://github.com/Kinto/kinto/releases/tag/5.3.4

**Bug fixes**

- Update the upsert query to use an INSERT or UPDATE on CONFLICT behavior (Kinto/kinto#1055)

kinto-attachment
''''''''''''''''

**kinto-attachment 1.0.1 → 1.1.2**: https://github.com/Kinto/kinto-attachment/releases/tag/1.1.2

**New features**

- Expose the gzipped settings value in the capability (Kinto/kinto-attachment#117)

**Bug fixes**

- Fixes crash when adding attachment to existing record with Kinto 5.3 (Kinto/kinto-attachment#120)
- Fix invalid request when attaching a file on non UUID record id (Kinto/kinto-attachment#122)


1.11 (2017-01-31)
=================

kinto
'''''

**kinto 5.3.1 → 5.3.2**: https://github.com/Kinto/kinto/releases/tag/5.3.2

**Bug fixes**

- Retries to set value in PostgreSQL cache backend in case of BackendError (Kinto/kinto#1052)


1.10 (2017-01-30)
=================

kinto
'''''

**kinto 5.3.0 → 5.3.1**: https://github.com/Kinto/kinto/releases/tag/5.3.1


**Bug fixes**

- Retries to set value in PostgreSQL cache backend in case of IntegrityError (Kinto/kinto#1035)
- Display Kinto-Admin version number in the footer. (Kinto/kinto#1040)
- Configure the Kinto Admin auth methods from the server configuration (Kinto/kinto#1042)


kinto-emailer
'''''''''''''

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
'''''''''

**kinto-fxa 2.3.0 → 2.3.1**: https://github.com/Kinto/kinto-fxa/releases/tag/2.3.0

**Bug fixes**

- Make sure that caching of token verification nevers prevents from authenticating
  requests (see Mozilla/PyFxA#48)


1.9 (2017-01-24)
================

kinto-signer
''''''''''''

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
'''''''''''''

**kinto-changes 0.4.0 → 0.5.0**: https://github.com/Kinto/kinto-changes/releases/tag/0.5.0

**Bug fixes**

- Do not force the timestamp of monitored entries, to avoid possible integrity errors (Kinto/kinto-changes#27)


kinto-signer
''''''''''''

**kinto-signer 1.0.0 → 1.1.1**: https://github.com/Kinto/kinto-signer/releases/tag/1.1.1

**Bug fixes**

- Fix consistency of setting names for per-collection workflows configuration (Kinto/kinto-signer#149)
- Remove recursivity of events when requesting review (Kinto/kinto-signer#158)


1.7 (2017-01-12)
================


Kinto
'''''

**kinto 5.1.0 → 5.2.0**: https://github.com/Kinto/kinto/releases/tag/5.2.0

**Protocol**

- Add an `OpenAPI specification <https://kinto.readthedocs.io/en/latest/api/1.x/openapi.html>`_ for the HTTP API on ``/__api__`` (Kinto/kinto#997)

**New features**

- When admin is enabled, ``/v1/admin`` does not return ``404`` anymore, but now redirects to
  ``/v1/admin/`` (with trailing slash).

**Bug fixes**

- Add missing ``Total-Records`` field on ``DELETE`` header with plural endpoints (fixes Kinto/kinto#1000)


kinto-admin
'''''''''''

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
'''''

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
'''''''''''

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
'''''''''

**kinto-fxa 2.2.0 → 2.3.0**: https://github.com/mozilla-services/kinto-fxa/releases/2.3.0

- Compatibility with Kinto 5


1.5 (2016-12-01)
================

- Create a Dockerfile that matches Dockerflow. (#84)


1.4 (2016-11-28)
================

Kinto
'''''

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
'''''''''''

**kinto-admin 1.5.0 → 1.5.1**: https://github.com/Kinto/kinto-admin/releases/tag/1.5.1

**Bug fixes**

- Fix #339: Fix server history not saved. (#342)
- Fix #340: Fix broken saved session restore. (#341)
- Fix #332: Display app version number in the footer. (#338)
- Fix broken timeago helper. (#335)
- Fix #336: Fix cannot save bucket attributes upon creation. (#337)


kinto-ldap
''''''''''

**kinto-ldap 0.2.1 → 0.3.0**: https://github.com/Kinto/kinto-ldap/releases/tag/0.3.0

**New features**

- Support login from multiple DN from the same LDAP server (Kinto/kinto-ldap#16)

1.3 (2016-11-18)
================

Kinto
'''''

**kinto 4.3.3 → 4.3.4**: https://github.com/Kinto/kinto-admin/releases/tag/4.3.4

**Bug fixes**

- Fix bug when two subfields are selected in partial responses (fixes Kinto/kinto#920)


kinto-admin
'''''''''''

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
'''''

**kinto 4.3.2 → 4.3.3**: https://github.com/Kinto/kinto-admin/releases/tag/4.3.3

**Bug fixes**

- Fix crash when querystring parameter contains null string (fixes #882)
- Permissions endpoint now exposes the user permissions defined in settings (fixes #909)
- Fix crash when redirection path contains CRLF character (fixes #887)



kinto-admin
'''''''''''

**kinto-admin 1.4.2 → 1.4.3**: https://github.com/Kinto/kinto-admin/releases/tag/1.4.3

**Bug fixes**

- Fix #311: check object permissions via parents objects too (#312)
- Fix #309: hide server URL from authentication form (#310)


1.1 (2016-11-09)
================

kinto-ldap
''''''''''

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
'''''''''''''

**kinto-changes 0.3.0 → 0.4.0**: https://github.com/Kinto/kinto-changes/releases/tag/0.4.0

**New features**

- Add the plugin version in the capability (Kinto/kinto-changes#20)
- Add collections in the capability (Kinto/kinto-changes#18)
- Add a specific setting to override global ``http_host`` value (Kinto/kinto-changes#24)

.. code-block:: ini

    kinto.event_listeners.changes.http_host = firefox.settings.services.mozilla.com


kinto-admin
'''''''''''

**kinto-admin 1.4.1 → 1.4.2**: https://github.com/Kinto/kinto-admin/releases/tag/1.4.2

**Bug fixes**

- Fix #299: Fix broken attachment creation. (#305)
- Fix #303: Fix attachment link in records list. (#306)
- Fix #307: Always show hooks on collection records page (#308)


1.0 (2016-10-28)
================

kinto-admin
'''''''''''

**kinto-admin 1.4.1**: https://github.com/Kinto/kinto-admin/releases/tag/v1.4.1

See `changelog for kinto-admin 1.4.0 <https://github.com/Kinto/kinto-admin/releases/tag/v1.4.0>`_


kinto-amo
'''''''''

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
''''''''''''

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
'''''''''

**kinto-fxa 2.1.0 → 2.2.0**: https://github.com/mozilla-services/kinto-fxa/releases/2.2.0


0.9.1 (2016-10-06)
==================

Kinto
'''''

**kinto 4.3.0 → 4.3.1**: https://github.com/Kinto/kinto/releases/tag/4.3.1

kinto-signer
''''''''''''

**kinto-signer 0.9.1 → 0.9.2**: https://github.com/Kinto/kinto-signer/releases/tag/0.9.2


0.9.0 (2016-10-04)
==================

Kinto
'''''

**kinto 3.3.2 → 4.3.0**: https://github.com/Kinto/kinto/releases/tag/4.3.0

**Highlights**

- Redis backends were dropped from core, and are now packaged separately in
  `kinto-redis <https://github.com/Kinto/kinto-redis/>`_
- New ``/__version__`` endpoint which reads a ``version.json`` file to expose what version
  has been deployed. Its location can be specified in the ``kinto.version_json_path``
  setting (fixes #830)
- New built-in plugin ``kinto.plugins.history`` to track history of changes per bucket
  from the Kinto Admin UI (*must be added explicity in the ``kinto.includes`` setting)
- ``kinto migrate`` now accepts a ``--dry-run`` option which details the operations
  to be made without executing them.
- New built-in plugin ``kinto.plugins.quotas```to set storage quotas per bucket/collection
  (c.f. *Web Extensions* storage)
- The history and quotas plugins execution time is now monitored on StatsD
  (``kinto.plugins.quotas`` and ``kinto.plugins.history``) (#832)
- The permissions attribute is now empty in the response if the user has not
  the permission to write on the object (Kinto/kinto#123)
- Parent attributes are now readable if children creation is allowed (Kinto/kinto#803)
- New ``kinto delete-collection`` command to delete a collection from the command-line.

kinto-admin
'''''''''''

**kinto-admin 1.3.0**: https://github.com/Kinto/kinto-admin/releases/tag/v1.3.0

- Add views for browsing a collection history (#196)
- Updated kinto-http to v2.3.0.
- Activate the signoff plugin to allow triggering a signature from the Admin.

kinto-signer
''''''''''''

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
'''''

**kinto 3.3.0 → 3.3.2**: https://github.com/Kinto/kinto/releases/tag/3.3.2

**Bug fixes**

- Fix Redis get_accessible_object implementation (kinto/kinto#725)
- Fix bug where the resource events of a request targetting two groups/collection
  from different buckets would be grouped together (kinto/kinto#728)


kinto-signer
''''''''''''

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
'''''

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
''''''''''''''''

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
'''''

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
''''''''''''

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
