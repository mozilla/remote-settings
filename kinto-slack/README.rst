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


Usage
=====

The metadata on the collection (or the bucket) must look like this:

.. code-block:: json

    {
      "kinto-slack": {
        "hooks": [{
          "channel": "#general",
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
to notify ``#team-component`` whenever a review is requested on any collection:

.. code-block:: json

    {
      "kinto-slack": {
        "hooks": [{
          "event": "kinto_remote_settings.signer.events.ReviewRequested",
          "channel": "#team-component",
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
