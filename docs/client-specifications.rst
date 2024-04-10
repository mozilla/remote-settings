.. _client-specifications:

Client Specifications
=====================

Foreword
--------

During years, the sole and unique client was Gecko (the platform behind Firefox, Thunderbird..). In order to reach out new platforms and products, a fully-featured Rust client was built, using the application-services components (Viaduct, NSS, ...).
Unfortunately, this cross-platform was not leveraged by the experimentation team, which built another ad-hoc client. In front of this situation, we are obliged to admit that our idea of having a single client of reference is dead. Instead, we are going to provide specifications for Remote Settings clients, to at least mitigate the consequences of clients fragmentation.

That being said, we still **strongly discourage** the implementation of ad-hoc clients.

We distinguish two major use-cases:

- authenticated write operations, ie. publish data;
- anonymous read operations, ie. fetch data from within our products.

Since the former does not take place on clients, it matters less than the latter, which has a major impact on traffic and our servers load.

Existing Clients
----------------

<TODO table with checkboxes>

Gecko
remote-settings-client
application-services/remote-settings
kinto-http.py
kinto.js

Specifications
--------------

Remote Settings is a layer on top of the Kinto API. Although every read-only operation offered by Kinto is technically available on the Remote Settings server, clients must take into consideration that once ran on millions of devices, the impact on our infrastructure can be significant.

Clients developers MUST keep their implementation as close as possible to the existing ones, or at least get in touch with us if there is a solid reason to derive from it.

Endpoints
'''''''''

Clients MUST set their ``User-Agent`` request header, mentioning application name and version.

Clients SHOULD leverage Gzip transport using the ``Accept-Encoding: gzip`` request header.

The following two endpoints MUST be used to retrieve data. Clients SHOULD not use other endpoints.

**Fetch collection**:

``GET /v1/buckets/{bid}/collections/{cid}/changeset?_expected={timestamp}``.

Returns the following response for the collection ``{cid}`` in the bucket ``{bid}`` (likely ``main``):

- ``changes``: list of records, optionally filtered with ``?_since="{timestamp}"``
- ``metadata``: collection attributes
- ``timestamp``: records timestamp

.. note::

    The ``_expected={}`` querystring parameter is mandatory but can be set to ``0`` if unknown. See section below about cache busting.

Examples:

* `get_changeset() in remote-settings-client <https://github.com/mozilla-services/remote-settings-client/blob/2538d6a07c28a3966b996d52596807df8c37130d/src/client/kinto_http.rs#L108-L128>`_
* `fetch_changeset() in Gecko <https://searchfox.org/mozilla-central/rev/c09764753ea40725eb50decad2c51edecbd33308/services/settings/RemoteSettingsClient.sys.mjs#1187-1209>`_

Clients SHOULD NOT rely on arbitrary server side filtering. In Remote Settings, collections are quite small anyway, and can usually be fetched entirely to be filtered on the client side. This helps us reduce our CDN cache cardinality.


**Poll for changes**:

``GET /v1/buckets/monitor/collections/changes/changeset?_expected={timestamp}``.

Returns the list of collections and their current timestamp.

- ``changes``: list of collections and their timestamp, optionally filtered with ``?_since="{timestamp}"``
- ``tiemstamp``: highest collections timestamp

.. note::

    The ``_expected={}`` querystring parameter is mandatory but can be set to ``0`` if unknown. See next section about cache busting.

Examples:

* `get_latest_change_timestamp() in remote-settings-client <https://github.com/mozilla-services/remote-settings-client/blob/2538d6a07c28a3966b996d52596807df8c37130d/src/client/kinto_http.rs#L79-L105>`
* `fetchLatestChanges() in Gecko <https://searchfox.org/mozilla-central/rev/1f27a4022f9f1269d897526c1c892a57743e650c/services/settings/Utils.sys.mjs#376-457>`_


Cache Busting
'''''''''''''

Using push notifications:

<sequence diagram>

Without push notifications:

<sequence diagram>


Environment Switching
'''''''''''''''''''''

Clients MAY offer a convenient way to switch before DEV, STAGE, or PROD environments, in order to facilitate the work of QA teams.

Clients SHOULD use PROD by default. And for security reasons, they must be some protection in place to prevent users to switch environments.


Signature Verification
''''''''''''''''''''''

Clients SHOULD verify the integrity of the downloaded data.

Overlook of implementation

TODO mention attachment incident


Attachments
'''''''''''

The attachments base URL is obtained on the root URL of the server:

``GET /v1/``

Returns the metadata of the server.

- ``capabilities.attachments.base_url``: the base URL for attachments with a trailing ``/``

Records with an attachment have the necessary metadata to download and verify it.

- ``attachment.location``: path to the attachment, to be concatenated with the ``base_url``
- ``attachment.hash``: SHA-256 of the file
- ``attachment.size``: size of the file in bytes

Clients MAY verify the size and hash of their downloaded copy.

Examples:

* `fetch_attachment() in remote-settings-client <https://github.com/mozilla-services/remote-settings-client/blob/2538d6a07c28a3966b996d52596807df8c37130d/src/client.rs#L645-L718>`_
* `fetchAttachment() in Gecko <https://searchfox.org/mozilla-central/rev/1f27a4022f9f1269d897526c1c892a57743e650c/services/settings/Attachments.sys.mjs#198-314>`_


Backoff Headers
'''''''''''''''


Deprecation Headers
'''''''''''''''''''


Local Cache
'''''''''''
