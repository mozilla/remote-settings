.. _getting-started:


Getting Started
===============

We will help you to use Remote Settings in your application!

Use the Dev Server
------------------

If you want to play with the stack or the API, the best way to get started is probably to use our :ref:`Dev Server <tutorial-dev-server>`, since everyone is allowed to manipulate data on the server and the multi-signoff workflow is not enabled.

.. note::

    :ref:`Check out all our tutorials and screencasts! <home>`


Create a new official type of Remote Settings
---------------------------------------------

In Kinto terms, creating a new type of Remote Settings consists in creating a new collection in the ``main-workspace`` bucket.

In STAGE, every staff member is allowed to create new collections. Once ready you file a ticket to get it to PROD (see below).

Mozilla VPN
'''''''''''

The Remote Settings server are only accessible via the `Mozilla VPN <https://mana.mozilla.org/wiki/display/IT/Mozilla+VPN>`_.

Once connected to the VPN, if you cannot reach https://settings-writer.stage.mozaws.net/v1/ (in your browser or via cURL) then you will have to file a request in order to be added in a specific LDAP group, using `this Bugzilla template <https://bugzilla.mozilla.org/enter_bug.cgi?assigned_to=vpn-acl%40infra-ops.bugs&bug_file_loc=http%3A%2F%2F&bug_ignored=0&bug_severity=normal&bug_status=NEW&cc=mathieu%40mozilla.com&cc=eglassercamp%40mozilla.com&cf_fx_iteration=---&cf_fx_points=---&comment=Hello%2C%0D%0ACould%20you%20please%20me%20%28LDAP%20user%40mozilla.com%29%20o%20get%20VPN%20access%20to%20get%20access%20to%20Remote%20Settings%3F%0D%0AThe%20VPN%20group%20is%20%22vpn_kinto1_stage%22.%0D%0AThanks%21&component=Mozilla%20VPN%3A%20ACL%20requests&contenttypemethod=list&contenttypeselection=text%2Fplain&defined_groups=1&flag_type-4=X&flag_type-481=X&flag_type-607=X&flag_type-674=X&flag_type-800=X&flag_type-803=X&form_name=enter_bug&groups=mozilla-employee-confidential&maketemplate=Remember%20values%20as%20bookmarkable%20template&op_sys=Unspecified&priority=--&product=Infrastructure%20%26%20Operations&qa_contact=gcox%40mozilla.com&rep_platform=Unspecified&short_desc=VPN%20access%20for%20https%3A%2F%2Fsettings-writer.prod.mozaws.net&target_milestone=---&version=Production>`_.


Admin UI
''''''''

Now that your VPN is all set, you should be able to login to the STAGE Admin UI at https://settings-writer.stage.mozaws.net/v1/admin/

In the Admin UI, go create your new collection in the *Collections* tab of the main-workspace bucket:

.. image:: images/screenshot-create-collection.png

.. note::

    We usually name the collections in lowercase with dashes (eg. ``public-list-suffix``, `examples  <https://settings.stage.mozaws.net/v1/buckets/main/collections?_fields=id>`_).

When a collection is created, the ``{collection-name}-editors`` and ``{collection-name}-reviewers`` groups are automatically created. The user (you!) that created the collection is automatically added as a member of those two groups.

But since users cannot signoff their own changes, you must add at least one collaborator to the ``{collection-name}-reviewers`` group. This comrade will have to approve the data changes made by the others (you).

In the Admin UI, add this new member (with format ``ldap:{email}``) to the appropriate group in the *Groups* tab of the main-workspace bucket.

.. image:: images/screenshot-group-add-member.png

You are now ready, check out the :ref:`tutorials <tutorial-multi-signoff>` or :ref:`screencasts <screencasts>` that will guide you for the records creation, changes approval etc.!

.. note::

    If your entries all share a structure, it is recommended to define a JSON schema on the collection attributes. It can be edited via the Admin UI.

    * The data will be validated when posted on the server
    * the schema will be used to build the forms in the Admin UI.


.. _go-to-prod:

Go to prod!
-----------

In PROD, we rely on OPS to create new collections and manage groups and permissions.

You will require:

* the list of LDAP handles that you want to assign as editors/reviewers
* (optional) the JSON schema to validate records and build the UI form (`see example <https://gist.github.com/leplatrem/4d86d5a64a56b5d8990be9af592d0e7f>`_)
* (optional) the list of fields to be displayed in the records list UI
* (optional) whether you want file attachments on your records or not, and whether they are required

And create `a Bugzilla ticket with this template <https://bugzilla.mozilla.org/enter_bug.cgi?assigned_to=wezhou%40mozilla.com&bug_file_loc=http%3A%2F%2F&bug_ignored=0&bug_severity=normal&bug_status=NEW&cc=mathieu%40mozilla.com&cf_fx_iteration=---&cf_fx_points=---&cf_status_firefox62=---&cf_status_firefox63=---&cf_status_firefox64=---&cf_status_firefox_esr60=---&cf_status_geckoview62=---&cf_tracking_firefox62=---&cf_tracking_firefox63=---&cf_tracking_firefox64=---&cf_tracking_firefox_esr60=---&cf_tracking_firefox_relnote=---&cf_tracking_geckoview62=---&comment=Collection%20name%3A%20_____%20%28eg.%20fingerprint-fonts%2C%20focus-experiments%2C%20...%29%0D%0A%0D%0AList%20of%20LDAP%20emails%20allowed%20to%20change%20the%20entries%20%28editors%29%3A%0D%0A%20-%20user1%40mozilla.com%0D%0A%20-%20...%0D%0A%0D%0AList%20of%20LDAP%20emails%20allowed%20to%20approve%20the%20changes%20%28reviewers%29%0D%0A%20-%20user1%40mozilla.com%0D%0A%20-%20...%0D%0A%0D%0A%0D%0A%28optional%29%20Allow%20file%20attachments%20on%20entries%3A%20%28yes%2Fno%29%0D%0A%28optional%29%20Are%20attachments%20required%20on%20records%20%28yes%2Fno%29%0D%0A%28optional%29%20List%20of%20fields%20names%20to%20display%20as%20columns%20in%20the%20records%20list%20UI%3A%20%28eg.%20%22name%22%2C%20%22details.size%22%29%0D%0A%28optional%29%20JSON%20schema%20to%20validate%20entries%20%28in%20YAML%20format%29%3A%20%28eg.%20https%3A%2F%2Fgist.github.com%2Fleplatrem%2F4d86d5a64a56b5d8990be9af592d0e7f%29%0D%0A&component=Server%3A%20Remote%20Settings&contenttypemethod=list&contenttypeselection=text%2Fplain&defined_groups=1&flag_type-37=X&flag_type-5=X&flag_type-607=X&flag_type-708=X&flag_type-721=X&flag_type-737=X&flag_type-748=X&flag_type-787=X&flag_type-800=X&flag_type-803=X&flag_type-846=X&flag_type-864=X&flag_type-929=X&flag_type-933=X&form_name=enter_bug&groups=mozilla-employee-confidential&maketemplate=Remember%20values%20as%20bookmarkable%20template&op_sys=Unspecified&priority=--&product=Cloud%20Services&rep_platform=Unspecified&short_desc=Please%20create%20the%20new%20collection%20%22_____%22&target_milestone=---&version=unspecified>`_

If you have permissions on the `CloudOps Github repo <https://github.com/mozilla-services/cloudops-deployment>`_, you could **give us a hand and accelerate the process** of getting your collection out! Just open a pull-request with the reference to the bug and the required modifications on the YAML *manifests* (`see this example PR <https://github.com/mozilla-services/cloudops-deployment/pull/2516/>`_).

It's also cool if you update the list of use-cases in https://wiki.mozilla.org/Firefox/RemoteSettings

.. note::

    * `Operational docs for OPS <https://mana.mozilla.org/wiki/pages/viewpage.action?pageId=66655528>`_
