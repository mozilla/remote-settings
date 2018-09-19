.. _getting-started:


Getting Started
===============

We will help you to use Remote Settings in your application!

Basically, Remote Settings consists of two components: a remote server (REST API) and a client (Gecko API).

Once everything in place, a typical workflow would be the following:

1. Connect to the UI on the VPN
2. Make some changes
3. Request a review (with an optional comment)

The people designated as reviewers will receive a notification email.

4. As a reviewer, you can preview the changes in a real browser
5. Once you verified that the changes have the expected effects, you can approve (or reject) the changes from the Admin UI
6. Changes will then be pulled by every Firefox clients on the next synchronization


Try Remote Settings!
--------------------

If you want to play with the stack or the API, the best way to get started is probably to :ref:`use the Dev Server <tutorial-dev-server>`.

Everyone is allowed to manipulate data on the server and the multi-signoff workflow is not enabled.


Create a new official type of Remote Settings
---------------------------------------------

In Kinto terms, creating a new type of Remote Settings consists in creating a new collection in the ``main-workspace`` bucket.

In STAGE, every staff member is allowed to create new collections.

1. First, you must connect to the VPN (`request access <https://bugzilla.mozilla.org/show_bug.cgi?id=1469514>`_)
2. Make sure you can reach the server https://settings-writer.stage.mozaws.net/v1
3. And that you can login to the Admin UI https://settings-writer.stage.mozaws.net/v1/admin/

In the Admin UI, create your new collection in the *Collections* tab of the main-workspace bucket:

.. image:: images/screenshot-create-collection.png

When a collection is created, the ``{collection-name}-editors`` and ``{collection-name}-reviewers`` groups are automatically created. The user (you!) that created the collection is automatically added as a member of those two groups. But since users cannot signoff their own changes, you must add at least one collaborator to the ``{collection-name}-reviewers`` group. This user will be able to approve the data changes made by the other user (you).

In the Admin UI, add a new member (with format ``ldap:{email}``) to the appropriate group in the *Groups* tab of the main-workspace bucket.

.. image:: images/screenshot-group-add-member.png

You are now ready, check out the :ref:`tutorials <tutorial-multi-signoff>` or :ref:`screencasts <screencasts>` that will guide you for the records creation, changes approval etc.!


Go to prod!
-----------

In PROD, we rely on OPS to create new collections and manage groups and permissions.

You will require:

* the list of LDAP handles that you want to assign as editors/reviewers
* (optional) the JSON schema to validate records and build the UI form (`example <https://gist.github.com/leplatrem/4d86d5a64a56b5d8990be9af592d0e7f>`_)
* (optional) whether you want file attachments on your records or not

And create `a Bugzilla ticket with this template <https://bugzilla.mozilla.org/enter_bug.cgi?assigned_to=wezhou%40mozilla.com&bug_file_loc=http%3A%2F%2F&bug_ignored=0&bug_severity=normal&bug_status=NEW&cc=mathieu%40mozilla.com&cf_blocking_fennec=---&cf_fx_iteration=---&cf_fx_points=---&cf_status_firefox60=---&cf_status_firefox61=---&cf_status_firefox62=---&cf_status_firefox_esr52=---&cf_status_firefox_esr60=---&cf_tracking_firefox60=---&cf_tracking_firefox61=---&cf_tracking_firefox62=---&cf_tracking_firefox_esr52=---&cf_tracking_firefox_esr60=---&cf_tracking_firefox_relnote=---&comment=Collection%20name%3A%20_____%20%28eg.%20fingerprint-fonts%2C%20focus-experiments%2C%20...%29%0D%0A%0D%0AList%20of%20LDAP%20emails%20allowed%20to%20change%20the%20entries%20%28editors%29%3A%0D%0A%20-%20user1%40mozilla.com%0D%0A%20-%20...%0D%0A%0D%0AList%20of%20LDAP%20emails%20allowed%20to%20approve%20the%20changes%20%28reviewers%29%0D%0A%20-%20user1%40mozilla.com%0D%0A%20-%20...%0D%0A%0D%0A%0D%0A%28optional%29%20Allow%20file%20attachments%20on%20entries%3A%20%28yes%2Fno%29%0D%0A%28optional%29%20Is%20attachment%20a%20required%20field%20%28yes%2Fno%29%0D%0A%28optional%29%20List%20of%20fields%20names%20to%20display%20as%20columns%20in%20the%20records%20list%20UI%3A%20%28eg.%20%22name%22%2C%20%22details.size%22%29%0D%0A%28optional%29%20JSON%20schema%20to%20validate%20entries%20%28in%20YAML%20format%29%3A%20%28eg.%20https%3A%2F%2Fgist.github.com%2Fleplatrem%2F4d86d5a64a56b5d8990be9af592d0e7f%29%0D%0A%0D%0A%20%20%0D%0A%0D%0A%0D%0A&component=Server%3A%20Remote%20Settings&contenttypemethod=autodetect&contenttypeselection=text%2Fplain&defined_groups=1&flag_type-37=X&flag_type-4=X&flag_type-5=X&flag_type-607=X&flag_type-708=X&flag_type-721=X&flag_type-737=X&flag_type-787=X&flag_type-800=X&flag_type-803=X&flag_type-846=X&flag_type-864=X&flag_type-914=X&flag_type-929=X&form_name=enter_bug&groups=mozilla-employee-confidential&maketemplate=Remember%20values%20as%20bookmarkable%20template&op_sys=Unspecified&priority=--&product=Cloud%20Services&rep_platform=Unspecified&short_desc=Please%20create%20the%20new%20collection%20%22_____%22&target_milestone=---&version=unspecified>`_

If you want to give a hand and accelerate the process of getting your collection out, you can open a pull-request on the CloudOps repo with the modifications on the permissions YAML file: `example PR <https://github.com/mozilla-services/cloudops-deployment/pull/2516/>`_.

It's also cool if you update the list of use-cases in https://wiki.mozilla.org/Firefox/RemoteSettings
