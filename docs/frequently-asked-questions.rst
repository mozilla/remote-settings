.. _faq:

Frequently Asked Questions
==========================

How do I setup Firefox to pull data from STAGE?
-----------------------------------------------

The recommended way to setup Firefox to pull data from STAGE is to use the `about:remottings <https://github.com/leplatrem/aboutremotesettings>`_ extension: switch the environment in the configuration section and click the *Sync* button.

Alternatively, you can change the `appropriate preferences <https://github.com/leplatrem/remotesettings-pi/blob/0.4.0/data/script.js#L41-L42>`_, restart and trigger a synchronization manually.


How do I preview the changes before approving?
----------------------------------------------

The recommended way to setup Firefox to pull data from the preview collection is to use the `about:remottings <https://github.com/leplatrem/aboutremotesettings>`_ extension: switch the environment in the configuration section and click the *Sync* button.

Alternatively, you can change the ``services.settings.default_bucket`` preference to ``main-preview``, restart and trigger a synchronization manually.


How do I preview the changes before requesting review?
------------------------------------------------------

Currently, this is not possible.

Possible workarounds:

- use a :ref:`local server <tutorial-local-server>` or the :ref:`DEV server <tutorial-dev-server>`
- request review, preview changes, fix up, request review again


How do I trigger a synchronization manually?
--------------------------------------------

See `developer docs <https://firefox-source-docs.mozilla.org/main/latest/services/common/docs/services/RemoteSettings.html#trigger-a-synchronization-manually>`_.


How do I define default data for new profiles?
----------------------------------------------

See `developer docs about initial data <https://firefox-source-docs.mozilla.org/main/latest/services/common/docs/services/RemoteSettings.html#initial-data>`_.


How do I automate the publication of records?
---------------------------------------------

The Remote Settings server is a REST API (namely a `Kinto instance <https://www.kinto-storage.org>`_). Records can be created in batches, and as seen in the :ref:`multi signoff tutorial <tutorial-multi-signoff>` reviews can be requested and approved using ``PATCH`` requests.

If the automation is meant to last (eg. cronjob, AWS lambda) then `request a dedicated Kinto internal account <https://bugzilla.mozilla.org/enter_bug.cgi?product=Cloud%20Services&component=Server%3A%20Remote%20Settings>`_ to be created for you.

If it is a one time run, then you can run the script as if it was you:

1. Authenticate on the Admin UI
2. Using the DevTools, inspect the outgoing requests and copy the ``Authorization`` header (eg. ``Bearer r43yt0956u0yj1``)
3. Use this header in your ``cURL`` commands (or Python/JS/Rust clients etc.)
