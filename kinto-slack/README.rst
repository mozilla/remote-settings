Kinto Slack
###########

Setup
=====

In the `Kinto <http://kinto.readthedocs.io/>`_ settings:

.. code-block:: ini

    kinto.includes = kinto_slack

    slack.webhook_url = https://hooks.slack.com/services/...

The webhook URL is the incoming webhook URL of your Slack app, the same kind
used in GitHub Actions with ``webhook-type: incoming-webhook``.

The setting can also be provided as the ``KINTO_SLACK_WEBHOOK_URL`` environment
variable (or ``SLACK_WEBHOOK_URL``), which takes precedence over the ini file value.


Usage
=====

The metadata on the collection (or the bucket) must look like this:

.. code-block:: json

    {
      "kinto-slack": {
        "hooks": [{
          "template": "Something happened!"
        }]
      }
    }

In the above example, every action on the collection metadata or any record in
that collection will trigger a Slack notification.

The collection metadata takes precedence over bucket metadata; they are not merged.


Selection
---------

It is possible to define several *hooks* and filter on conditions. For example,
to notify whenever a review is requested on any collection:

.. code-block:: json

    {
      "kinto-slack": {
        "hooks": [{
          "event": "kinto_remote_settings.signer.events.ReviewRequested",
          "template": "{user_id} requested review of {collection_id} ({root_url}{uri})"
        }]
      }
    }

The possible filters are:

* ``event``: ``kinto_remote_settings.signer.events.ReviewRequested``,
  ``kinto_remote_settings.signer.events.ReviewApproved``,
  ``kinto_remote_settings.signer.events.ReviewRejected``,
  or ``kinto.core.events.AfterResourceChanged`` (default: all)
* ``resource_name``: ``record`` or ``collection`` (default: all)
* ``action``: ``create``, ``update``, ``delete`` (default: all)
* ``collection_id`` (default: all)
* ``record_id`` (default: all)

If a filter value starts with ``^``, it is treated as a regular expression.

For example, to match only collections whose id starts with ``experiment-``:

.. code-block:: json

    {
      "kinto-slack": {
        "hooks": [{
          ...,
          "collection_id": "^experiment-.*"
        }]
      }
    }


Template
--------

The template string can contain the following placeholders:

* ``bucket_id``
* ``collection_id``
* ``record_id``
* ``id``: record or collection ``id``
* ``user_id``
* ``resource_name``
* ``uri``
* ``action``
* ``timestamp``
* ``root_url``
* ``client_address``

For example:

``{user_id} has {action}d {resource_name} {id} in {bucket_id}/{collection_id}.``


Slack Channel Routing
---------------------

Slack Webhooks URLs are bound to a specific Slack channel. By default, all
notifications will be sent to the Slack channel configured globally in the
``kinto.slack.webhook_url`` setting.

In order to send a Slack notification to a specific channel, start with adding the `channel` field
to the collection metadata:

.. code-block:: json

    {
      "kinto-slack": {
          "hooks": [{
            ...
            "channel": "#fxmonitor-alerts"
          }]
      }
    }

The Webhook URL for this channel can now be configured via ``.ini`` config:

.. code-block:: ini

    kinto.slack.fxmonitor-alerts.webhook_url = https://...

or the ``KINTO_SLACK_FXMONITOR_ALERTS_WEBHOOK_URL`` environment variable (safer).

In order to obtain the Webhook URL, `see official Slack docs <https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/>`_.
