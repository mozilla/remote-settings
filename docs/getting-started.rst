.. _getting-started:

Getting Started
===============

We will help you to use Remote Settings in your application!

.. _go-to-prod:

Create a new official type of Remote Settings
---------------------------------------------

Basically, you will have to go through these 3 steps:

1. Setup the `Mozilla VPN <https://mana.mozilla.org/wiki/display/IT/Mozilla+Corporate+VPN>`_ and request access to the server using `this Bugzilla template <https://bugzilla.mozilla.org/enter_bug.cgi?assigned_to=vpn-acl%40infra-ops.bugs&bug_file_loc=http%3A%2F%2F&bug_ignored=0&bug_severity=normal&bug_status=NEW&cc=mathieu%40mozilla.com&cc=wezhou%40mozilla.com&cf_fx_iteration=---&cf_fx_points=---&comment=Hello%2C%0D%0ACould%20you%20please%20add%20me%20%28LDAP%20user%40mozilla.com%29%20to%20the%20following%20groups%3A%0D%0A-%20%22vpn_kinto1_stage%22%0D%0A-%20%22vpn_kinto1_prod%22%0D%0Ain%20order%20to%20gain%20access%20the%20Remote%20Settings%20Admin%0D%0A%0D%0AThanks%21&component=Mozilla%20VPN%3A%20ACL%20requests&contenttypemethod=list&contenttypeselection=text%2Fplain&defined_groups=1&flag_type-4=X&flag_type-481=X&flag_type-607=X&flag_type-674=X&flag_type-800=X&flag_type-803=X&form_name=enter_bug&groups=mozilla-employee-confidential&maketemplate=Remember%20values%20as%20bookmarkable%20template&op_sys=Unspecified&priority=--&product=Infrastructure%20%26%20Operations&qa_contact=gcox%40mozilla.com&rep_platform=Unspecified&short_desc=VPN%20access%20for%20Remote%20Settings%20https%3A%2F%2Fsettings-writer.%2A.mozaws.net&target_milestone=---&version=Production>`_
2. Design your data model (see below) and prepare the list of colleagues that will be allowed to review your data
3. Request the creation of your collection using `this Bugzilla ticket template <https://bugzilla.mozilla.org/enter_bug.cgi?assigned_to=mathieu%40mozilla.com&bug_file_loc=http%3A%2F%2F&bug_ignored=0&bug_severity=normal&bug_status=NEW&cf_fx_iteration=---&cf_fx_points=---&cf_status_firefox62=---&cf_status_firefox63=---&cf_status_firefox64=---&cf_status_firefox_esr60=---&cf_status_geckoview62=---&cf_tracking_firefox62=---&cf_tracking_firefox63=---&cf_tracking_firefox64=---&cf_tracking_firefox_esr60=---&cf_tracking_firefox_relnote=---&cf_tracking_geckoview62=---&comment=Collection%20name%3A%20_____%20%28eg.%20fingerprint-fonts%2C%20focus-experiments%2C%20...%29%0D%0A%0D%0AList%20of%20LDAP%20emails%20allowed%20to%20change%20the%20records%20%28editors%29%3A%0D%0A%20-%20user1%40mozilla.com%0D%0A%20-%20...%0D%0A%0D%0AList%20of%20LDAP%20emails%20allowed%20to%20approve%20the%20changes%20%28reviewers%29%0D%0A%20-%20user1%40mozilla.com%0D%0A%20-%20...%0D%0A%0D%0A%0D%0A%28optional%29%20Allow%20file%20attachments%20on%20records%3A%20%28yes%2Fno%29%0D%0A%28optional%29%20Are%20attachments%20required%20on%20records%20%28yes%2Fno%29%0D%0A%28optional%29%20List%20of%20fields%20names%20to%20display%20as%20columns%20in%20the%20records%20list%20UI%3A%20%28eg.%20%22name%22%2C%20%22details.size%22%29%0D%0A%28optional%29%20JSON%20schema%20to%20validate%20records%20%28in%20YAML%20format%29%3A%20%28eg.%20https%3A%2F%2Fgist.github.com%2Fleplatrem%2F4d86d5a64a56b5d8990be9af592d0e7f%29%0D%0A%28optional%29%20Manual%20records%20ID%3A%20%28yes%2Fno%29%0D%0A%28optional%29%20JEXL%20target%20filters%3A%20%28yes%2Fno%29%0D%0A&component=Server%3A%20Remote%20Settings&contenttypemethod=list&contenttypeselection=text%2Fplain&defined_groups=1&flag_type-37=X&flag_type-5=X&flag_type-607=X&flag_type-708=X&flag_type-721=X&flag_type-737=X&flag_type-748=X&flag_type-787=X&flag_type-800=X&flag_type-803=X&flag_type-846=X&flag_type-864=X&flag_type-929=X&flag_type-933=X&form_name=enter_bug&groups=mozilla-employee-confidential&maketemplate=Remember%20values%20as%20bookmarkable%20template&op_sys=Unspecified&priority=--&product=Cloud%20Services&rep_platform=Unspecified&short_desc=Please%20create%20the%20new%20collection%20%22_____%22&target_milestone=---&version=unspecified&bug_type=task>`_

Once done, you will be able to login and edit your records on the Admin UIs:

- https://settings-writer.prod.mozaws.net/v1/admin/

The records will then be publicly visible at `<https://firefox.settings.services.mozilla.com/v1/bucket/main/collections/{collection-id}/records>`__

Don't hesitate to contact us (``@delivery`` on Slack) if you're stuck or have questions about the process!

Check out the :ref:`screencast to create, request review and approve changes <screencasts-modify-request-review>`, or :ref:`our FAQ <faq>`!

.. note::

    In order to **try out changes in a real environment**, you can use the **STAGE** instance:

    - https://settings-writer.stage.mozaws.net/v1/admin/ (*Admin UI*)

    In order to switch Firefox from PROD to STAGE, use the `Remote Settings DevTools <https://github.com/mozilla/remote-settings-devtools>`_!

    The records will be publicly visible at `<https://settings.stage.mozaws.net/v1/bucket/main/collections/{collection-id}/records>`__

.. note::

    If you simply **want to play** with the stack or the API, the best way to get started is probably to use our :ref:`DEV server <tutorial-dev-server>`, since everyone is allowed to manipulate data on the server and the multi-signoff workflow is not enabled. Check out the :ref:`dedicated tutorial <tutorial-dev-server>`!


About your data
---------------

Name your collection in lowercase with dashes (eg. ``public-list-suffix``, `examples  <https://firefox.settings.services.mozilla.com/v1/buckets/main/collections?_fields=id>`_).

The Admin UI automatically builds forms based on some metadata for your collection, namely:

- the list of fields to be displayed as the list columns (eg. ``title``, ``comment.author``)
- a JSON schema that will be render as a form to create and edit your records  (`see example <https://bugzilla.mozilla.org/show_bug.cgi?id=1500868>`_)
- whether you want to control the ID field or let the server assign it automatically
- whether you want to be able to attach files on records

.. note::

    If your client code expects to find 0 or 1 record by looking up on a specific field, you should probably use that field as the record ID. ``RemoteSettings("cid").get({filters: {id: "a-value"}})`` will be instantaneous.

By default, all records are made available to all users. If you want to control which users should have a particular entry, you can add a ``filter_expression`` field (see :ref:`target filters <target-filters>`).


Records vs. Attachments?
''''''''''''''''''''''''

Since the diff-based synchronization happens at the record level, it is recommended to keep your Remote Settings records small, especially if you update them often.

It is important to design your data layout carefully, especially if:

* you have too many records (eg. > 2000)
* you have big amounts of data (eg. > 1MB)
* your data cannot be easily broken into pieces
* your updates are likely to overwrite most of the collection content

Consider the following summary table:

+-------------------------------------+--------------------------------------+-------------------------------------+
| Strategy                            | Pros                                 | Cons                                |
+-------------------------------------+--------------------------------------+-------------------------------------+
| Many small records                  | - Efficient sync                     | - Costly lookups in client          |
|                                     | - Easier to review changes in Admin  | - Updates potentially harder to     |
|                                     |   UI                                 |   automate                          |
|                                     |                                      |                                     |
+-------------------------------------+--------------------------------------+-------------------------------------+
| Few big records                     | - Efficient lookups in client        | - Harder to review changes within   |
|                                     |                                      |   records in Admin UI               |
|                                     |                                      | - Memory usage in client            |
|                                     |                                      |                                     |
+-------------------------------------+--------------------------------------+-------------------------------------+
| Attachments                         | - No limit in size & format          | - No partial update                 |
|                                     |                                      | - Packaging attachments in release  |
|                                     |                                      |   binary is feasible but tedious    |
|                                     |                                      |   (source_)                         |
|                                     |                                      |                                     |
+-------------------------------------+--------------------------------------+-------------------------------------+

.. _source: https://searchfox.org/mozilla-central/rev/dd042f25a8da58d565d199dcfebe4f34db64863c/taskcluster/docker/periodic-updates/scripts/periodic_file_updates.sh#309-324

- See our :ref:`tutorial for file attachments <tutorial-attachments>`


.. _collection-manifests:

Collection manifests
--------------------

Both STAGE and PROD collections attributes and permissions are managed via YAML files in the `remote-settings-permissions <https://github.com/mozilla-services/remote-settings-permissions>`_ Github repository.

If you want to accelerate the process of getting your collection deployed or adjust its schema, in STAGE or PROD, you can open a pull-request with the collection, and the definition of ``{collection}-editors`` and ``{collection}-reviewers`` groups. Check out the existing ones that were merged.
