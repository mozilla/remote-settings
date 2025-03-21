.. _target-filters:

Target filters
==============

By default all records in a collection are made available.  However, there are some use cases where it is more practical to use a single server side collection and filter record visibility in the browser.  Target filters allows for these use cases.

Filters are conditional expressions evaluated in the client's browser and, if they pass, the corresponding record is available. Filters have access to information about the user, such as their locale, addons, and Firefox version.

.. important::
   All records are downloaded to Firefox.  Filters only control what is returned by ``.get()`` or the ``sync`` event.

.. important::
   The ideal use case for target filters is to use a single collection to service a small number (dozens) of different groups of users.  Filtering by channel, browser version or locale are good use cases.


How?
----

When a record has a string in the ``filter_expression`` field, it is evaluated and the record is potentially filtered for some users.

In order to restrict a setting to a particular audience, just write the proper filter string in the Admin UI and save the record.

::

    {
        id: "68b19efa-1067-401b-b1c1-8d7b4263bb86",
        last_modified: 1531762863373,
        title: "Not for Android users",
        filter_expression: "env.appinfo.OS != 'Android'"
    }

When calling ``RemoteSettings("key").get()`` or listening to ``sync`` events, you will only see the settings entries whose ``filter_expression`` resolved to a truthy value (and those who don't have any as by default).

See :ref:`the dedicated section about testing and debugging <target-filters-debugging>`.


Filter Expressions
------------------

Filter expressions are written using a language called JEXL_. JEXL is an open-source expression language that is given a context (in this case, information about the user's browser) and evaluates a statement using that context. JEXL stands for "JavaScript Expression Language" and uses JavaScript syntax for several (but not all) of its features.

.. note:: The rest of this document includes examples of JEXL syntax that has
   comments inline with the expressions. JEXL does **not** have any support for
   comments in statements, but we're using them to make understanding our
   examples easier.

.. _JEXL: https://github.com/TechnologyAdvice/Jexl

JEXL Basics
~~~~~~~~~~~
The `JEXL Readme`_ describes the syntax of the language in detail; the following
section covers the basics of writing valid JEXL expressions.

.. note:: Normally, JEXL doesn't allow newlines or other whitespace besides
   spaces in expressions, but filter expressions in Remote Settings allow arbitrary
   whitespace.

A JEXL expression evaluates down to a single value. JEXL supports several basic
types, such as numbers, strings (single or double quoted), and booleans. JEXL
also supports several operators for combining values, such as arithmetic,
boolean operators, comparisons, and string concatenation.

.. code-block:: javascript

   // Arithmetic
   2 + 2 - 3 // == 1

   // Numerical comparisons
   5 > 7 // == false

   // Boolean operators
   false || 5 > 4 // == true

   // String concatenation
   "Mozilla" + " " + "Firefox" // == "Mozilla Firefox"

Expressions can be grouped using parenthesis:

.. code-block:: javascript

   ((2 + 3) * 3) - 3 // == 7

JEXL also supports lists and objects (known as dictionaries in other languages)
 as attribute access:

.. code-block:: javascript

   [1, 2, 1].length // == 3
   {foo: 1, bar: 2}.foo // == 1

Unlike JavaScript, JEXL supports an ``in`` operator for checking if a substring
is in a string or if an element is in an array:

.. code-block:: javascript

   "bar" in "foobarbaz" // == true
   3 in [1, 2, 3, 4] // == true

The context passed to JEXL can be expressed using identifiers, which also
support attribute access:

.. code-block:: javascript

   env.locale == 'en-US' // == true if the client's locale is en-US

Another unique feature of JEXL is transforms, which modify the value given to
them. Transforms are applied to a value using the ``|`` operator, and may take
additional arguments passed in the expression:

.. code-block:: javascript

   '1980-01-07'|date // == a date object
   env.version|versionCompare("110.0a1") >= 0

.. _JEXL Readme: https://github.com/TechnologyAdvice/Jexl#jexl---

.. _filter-context:

Context
~~~~~~~
This section defines the context passed to filter expressions when they are
evaluated. In other words, this is the client information available within
filter expressions.

.. js:data:: env

   The ``env`` object contains general information about the client.

.. js:attribute:: env.version

   **Example:** ``'47.0.1'``

   String containing the user's Firefox version.

.. js:attribute:: env.channel

   String containing the update channel. Valid values include, but are not
   limited to:

   * ``'release'``
   * ``'aurora'``
   * ``'beta'``
   * ``'nightly'``
   * ``'default'`` (self-built or automated testing builds)

   **Example:** ``env.channel == 'default' || env.channel == 'nightly'``

.. js:attribute:: env.locale

   **Example:** ``'en-US'``

   String containing the user's locale.

.. js:attribute:: env.appinfo.OS

   String containing the Operating System identifier:

   * ``Android``
   * ``Darwin``
   * ``iOS``
   * ``Linux``
   * ``WINNT``

   **Example:** ``env.appinfo.OS != 'Android'``

.. important::

   **How to add a new field?**

   1. Put Remote Settings stakeholders in the loop (would allow to avoid disparities like casing, etc.)
   2. Add the field on Gecko `in the environment object <https://searchfox.org/mozilla-central/rev/dd8b5213e4e7760b5fe5743fbc313398b85f8a14/toolkit/components/utils/ClientEnvironment.sys.mjs#31>`_ (even as constant or empty value)
   3. Add the field on Application-Services RS component `in the RemoteSettingsContext struct <https://github.com/mozilla/application-services/blob/43aa6da9690b2f52d1b3e6255ab2d698f46f47a8/components/remote_settings/src/lib.rs#L43-L78>`_
   4. Add the field on the Android app `in the RemoteSettingsAppContext <https://searchfox.org/mozilla-central/rev/dd8b5213e4e7760b5fe5743fbc313398b85f8a14/mobile/android/android-components/components/support/remotesettings/src/main/java/mozilla/components/support/remotesettings/RemoteSettingsService.kt#47-69>`_
   5. Add the field on the iOS app `in the RemoteSettingsContext object <https://github.com/mozilla-mobile/firefox-ios/blob/3a2cbe040acb999c6f1589d128f1cfc749e993e5/firefox-ios/Providers/Profile.swift#L782-L799>`_
   6. Mention the field in `this documentation <https://github.com/mozilla/remote-settings/blob/ee84d042261c27cbe7c8c433f646183d82dde3a9/docs/target-filters.rst>`_

Transforms
~~~~~~~~~~
This section describes the transforms available to filter expressions, and what
they do. They're documented as functions, and the first parameter to each
function is the value being transformed.

.. js:function:: versionCompare(v1, v2)

   Compares v1 to v2 and returns 0 if they are equal, a negative number if v1 < v2 or a positive number if v1 > v2.

   :param v1:
      Input version.

   :param v2:
      Version to compare it with.

   .. code-block:: javascript

      // Evaluates to 1
      '128.0.1'|versionCompare('127.0a1')


Examples
~~~~~~~~
This section lists some examples of commonly-used filter expressions.

.. code-block:: javascript

   // Match users using the en-US locale
   env.locale == 'en-US'

   // Match users in any English locale using Firefox Beta
   (
      env.locale in ['en-US', 'en-AU', 'en-CA', 'en-GB', 'en-NZ', 'en-ZA']
      && env.channel == 'beta'
   )

   // Specific version range
   env.version|versionCompare('137.0a1') >= 0 && env.version|versionCompare('138.0a1') < 0


.. _target-filters-debugging:

Advanced: Testing Filter Expressions in the Browser Console
-----------------------------------------------------------

#. Open the browser console

   * Tools > Web Developer > Browser Console
   * :kbd:`Cmd + Shift + J`

#. Run the following in the console:

   .. code-block:: javascript

        const { RemoteSettings } = ChromeUtils.import("resource://services-settings/remote-settings.js", {});
        const client = RemoteSettings("a-key");

   The following lines create a local record with a filter expression field and fetch the current settings list.

   .. code-block:: javascript

        let FILTER_TO_TEST = `
            env.locale == "fr-FR"
        `;

        (
          async function () {
            await client.db.clear();
            await client.db.importChanges({}, 42);

            const record = await client.db.create({
              id: "68b19efa-1067-401b-b1c1-8d7b4263bb86",  // random uuidgen
              filter_expression: FILTER_TO_TEST
            };

            const filtered = await client.get();
            console.log(filtered.length == 1);
          }
        )();

#. The console will log ``true`` or ``false`` depending on whether the expression passed for your client or not.


Advanced: Platform Specific Fields and Transforms
-------------------------------------------------

.. warning::

   The use of fields, operators, and transforms described in this section is **not recommended**,
   until they are implemented in all clients (See `Bug 1944609 <https://bugzilla.mozilla.org/show_bug.cgi?id=1944609>`_).


Application Services Only
~~~~~~~~~~~~~~~~~~~~~~~~~

(*as of 2025-03-21*)

.. js:attribute:: env.appName

   * ``'Firefox Fenix'``
   * ``'Firefox iOS'``

.. js:attribute:: env.appId

   * ``'org.mozilla.fenix.debug'``
   * ``'org.mozilla.ios.FennecEnterprise'``

.. js:attribute:: env.appVersion

   * ``138.0a1``

.. js:attribute:: env.appBuild
.. js:attribute:: env.architecture

   * ``'x86_64'``

.. js:attribute:: env.deviceManufacturer

   * ``'Apple'``

.. js:attribute:: env.os

   * ``'Android'``

.. js:attribute:: env.osVersion

   * ``14``

.. js:attribute:: env.androidSdkVersion

   * ``34``

.. js:attribute:: env.debugTag

   * ``null``

.. js:attribute:: env.installationDate

   * ``1718396105298``

.. js:attribute:: env.form_factor

   * ``'phone'``
   * ``'tablet'``
   * ``'desktop'``

.. js:attribute:: env.homeDirectory

   * ``null``

.. js:attribute:: env.country

   * ``'US'``
   * ``'GB'``

Desktop Only
~~~~~~~~~~~~

(*as of 2025-03-21*)

.. js:attribute:: env.isDefaultBrowser

   Boolean specifying whether Firefox is set as the user's default browser.

.. js:attribute:: env.appinfo.ID

   String containing the XUL application ID

   * ``"{ec8030f7-c20a-464f-9b0e-13a3a9e97384}"`` (Firefox)
   * ``"{3550f703-e582-4d05-9a08-453d09bdfdc6}"`` (Thunderbird)

.. js:attribute:: env.appinfo.version

   The version of the XUL application.

   It is different than the version of the XULRunner platform. Be careful about which one you want.

.. js:attribute:: env.appinfo.platformVersion

   The version of the XULRunner platform

.. js:attribute:: env.appinfo.platformBuildID

   The version of the XULRunner platform

.. js:attribute:: env.searchEngine

   **Example:** ``'google'``

   String containing the user's default search engine identifier. Identifiers
   are lowercase, and may be locale-specific (Wikipedia, for example, often has
   locale-specific codes like ``'wikipedia-es'``).

   The default identifiers included in Firefox are:

   * ``'google'``
   * ``'yahoo'``
   * ``'amazondotcom'``
   * ``'bing'``
   * ``'ddg'``
   * ``'twitter'``
   * ``'wikipedia'``

.. js:attribute:: env.syncSetup

   Boolean containing whether the user has set up Firefox Sync.

.. js:attribute:: env.syncDesktopDevices

   Integer specifying the number of desktop clients the user has added to their
   Firefox Sync account.

.. js:attribute:: env.syncMobileDevices

   Integer specifying the number of mobile clients the user has added to their
   Firefox Sync account.

.. js:attribute:: env.syncTotalDevices

   Integer specifying the total number of clients the user has added to their
   Firefox Sync account.

.. js:attribute:: env.plugins

   An object mapping of plugin names to plugin objects describing
   the plugins installed on the client.

.. js:attribute:: env.distribution

   String set to the user's distribution ID. This is commonly used to target
   funnelcake builds of Firefox.

   On Firefox versions prior to 48.0, this value is set to ``undefined``.

.. js:attribute:: env.telemetry

   Object containing data for the most recent Telemetry_ packet of each type.
   This allows you to target recipes at users based on their Telemetry data.

   The object is keyed off the ping type, as documented in the
   `Telemetry data documentation`_ (see the ``type`` field in the packet
   example). The value is the contents of the ping.

   .. code-block:: javascript

      // Target clients that are running Firefox on a tablet
      env.telemetry.main.env.system.device.isTablet

      // Target clients whose last crash had a BuildID of "201403021422"
      env.telemetry.crash.payload.metadata.BuildID == '201403021422'

   .. _Telemetry: https://firefox-source-docs.mozilla.org/toolkit/components/telemetry/telemetry/index.html#
   .. _Telemetry data documentation: https://firefox-source-docs.mozilla.org/toolkit/components/telemetry/telemetry/data/index.html

.. js:attribute:: env.doNotTrack

   Boolean specifying whether the user has enabled Do Not Track.

.. js:attribute:: env.addons

   Object containing information about installed add-ons. The keys on this
   object are add-on IDs. The values contain the following attributes:

   .. js:attribute:: addon.id

      String ID of the add-on.

   .. js:attribute:: addon.installDate

      Date object indicating when the add-on was installed.

   .. js:attribute:: addon.isActive

      Boolean indicating whether the add-on is active (disabling an add-on but
      not uninstalling it will set this to ``false``).

   .. js:attribute:: addon.name

      String containing the user-visible name of the add-on.

   .. js:attribute:: addon.type

      String indicating the add-on type. Common values are ``extension``,
      ``theme``, and ``plugin``.

   .. js:attribute:: addon.version

      String containing the add-on's version number.

   .. code-block:: javascript

      // Target users with a specific add-on installed
      env.addons["shield-recipe-client@mozilla.org"]

      // Target users who have at least one of a group of add-ons installed
      env.addons|keys intersect [
         "shield-recipe-client@mozilla.org",
         "some-other-addon@example.com"
      ]

.. js:function:: preferenceValue(prefKey, defaultValue)

   :param prefKey:
      Full dotted-path name of the preference to read.
   :param defaultValue:
      The value to return if the preference does not have a value. Defaults to
      ``undefined``.
   :returns:
      The value of the preference.

   .. code-block:: javascript

      // Match users with more than 2 content processes
      'dom.ipc.processCount'|preferenceValue > 2

.. js:function:: intersect(list1, list2)

   Returns an array of all values in ``list1`` that are also present in
   ``list2``. Values are compared using strict equality. If ``list1`` or
   ``list2`` are not arrays, the returned value is ``undefined``.

   :param list1:
      The array to the left of the operator.
   :param list2:
      The array to the right of the operator

   .. code-block:: javascript

      // Evaluates to [2, 3]
      [1, 2, 3, 4] intersect [5, 6, 2, 7, 3]

.. js:function:: stableSample(input, rate)

   Randomly returns ``true`` or ``false`` based on the given sample rate. Used
   to sample over the set of matched users.

   Sampling with this transform is stable over the input, meaning that the same
   input and sample rate will always result in the same return value.

   :param input:
      A value for the sample to be stable over.
   :param rate:
      A number between ``0`` and ``1`` with the sample rate. For example,
      ``0.5`` would be a 50% sample rate.

   .. code-block:: javascript

      // True 50% of the time, stable per-version per-locale.
      [env.locale, env.version]|stableSample(0.5)

.. js:function:: bucketSample(input, start, count, total)

   Returns ``true`` or ``false`` if the current user falls within a "bucket" in
   the given range.

   Bucket sampling randomly groups users into a list of "buckets", in this case
   based on the input parameter. Then, you specify which range of available
   buckets you want your sampling to match, and users who fall into a bucket in
   that range will be matched by this transform. Buckets are stable over the
   input, meaning that the same input will always result in the same bucket
   assignment.

   Importantly, this means that you can use an independent input across
   several settings to ensure they do not get delivered to the same users. For
   example, if you have two settings that are variants of each other, you
   can ensure they are not shown to the same cohort:

   .. code-block:: javascript

      // Half of users will match the first filter and not the
      // second one, while the other half will match the second and not
      // the first, even across multiple settings.
      [env.locale]|bucketSample(0, 5000, 10000)
      [env.locale]|bucketSample(5000, 5000, 10000)

   The range to check wraps around the total bucket range. This means that if
   you have 100 buckets, and specify a range starting at bucket 70 that is 50
   buckets long, this function will check buckets 70-99, and buckets 0-19.

   :param input:
      A value for the bucket sampling to be stable over.
   :param start:
      The bucket at the start of the range to check. Bucket indexes larger than
      the total bucket count wrap to the start of the range, e.g. bucket 110 and
      bucket 10 are the same bucket if the total bucket count is 100.
   :param count:
      The number of buckets to check, starting at the start bucket. If this is
      large enough to cause the range to exceed the total number of buckets, the
      search will wrap to the start of the range again.
   :param total:
      The number of buckets you want to group users into.

.. js:function:: date(dateString)

   Parses a string as a date and returns a Date object. Date strings should be
   in `ISO 8601`_ format.

   :param dateString:
      String to parse as a date.

   .. code-block:: javascript

      '2011-10-10T14:48:00'|date // == Date object matching the given date

   .. _ISO 8601: https://www.w3.org/TR/NOTE-datetime

.. js:function:: keys(obj)

   Return an array of the given object's own keys (specifically, its enumerable
   properties). Similar to `Object.keys`_, except that if given a non-object,
   ``keys`` will return ``undefined``.

   :param obj:
      Object to get the keys for.

   .. code-block:: javascript

      // Evaluates to ['foo', 'bar']
      {foo: 1, bar:2}|keys

   .. _Object.keys: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/keys

.. js:function:: values(obj)

   Return an array of the given object's own values (specifically, its enumerable
   properties values). Similar to `Object.values`_, except that if given a non-object,
   ``values`` will return ``undefined``.

   :param obj:
      Object to get the values for.

   .. code-block:: javascript

      // Evaluates to [1, 2]
      {foo: 1, bar:2}|values

   .. _Object.values: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/values

.. js:function:: length(arr)

   Return the length of an array or ``undefined`` if given a non-array.

   :param arr:
      Array to get the length for.

   .. code-block:: javascript

      // Evaluates to 2
      [1, 2]|length

.. js:function:: mapToProperty(arr, prop)

   Given an input array and property name, return an array with each element of
   the original array replaced with the given property of that element.
   Return ``undefined`` if given a non-array.

   :param arr:
      Array to extract the properties from.

   :param prop:
      Properties name.

   .. code-block:: javascript

      // Evaluates to ["foo", "bar"]
      [{"name": "foo"}, {"name": "bar"}]|mapToProperty("name")

.. js:function:: regExpMatch(str, pattern, flags)

   Matches a string against a regular expression. Returns null if there are no matches or an Array of matches.

   :param str:
      Input string.

   :param pattern:
      Regular expression.

   :param flags:
      `JS regexp flags <regexpFlags>`_

   .. code-block:: javascript

      // Evaluates to ["abbBBC"]
      "abbBBC"|regExpMatch("ab+c", "i")

      .. _regexpFlags: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Regular_expressions#advanced_searching_with_flags

.. js:function:: preferenceIsUserSet(prefKey)

   :param prefKey:
      Full dotted-path name of the preference to read.
   :returns:
      ``true`` if the preference has a value that is different than its default
      value, or ``false`` if it does not.

   .. code-block:: javascript

      // Match users who have modified add-on signature checks
      'xpinstall.signatures.required'|preferenceIsUserSet

.. js:function:: preferenceExists(prefKey)

   :param prefKey:
      Full dotted-path name of the preference to read.
   :returns:
      ``true`` if the preference has *any* value (whether it is the default
      value or a user-set value), or ``false`` if it does not.

   .. code-block:: javascript

      // Match users with an HTTP proxy
      'network.proxy.http'|preferenceExists

