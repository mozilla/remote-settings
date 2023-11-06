.. _monitoring:

Monitoring
==========

Delivery Checks
---------------

The Remote Settings ecosystem can be monitored from the `Delivery Checks dashboard <https://delivery-checks.prod.mozaws.net/>`_.

Each environment has its own set of checks, and generally speaking if the checks pass, the service is operating without issues.

.. note::

    This is an instance of `Telescope <https://github.com/mozilla-services/telescope>`_, a generic health check service that you can use for your services!

Server Metrics
--------------

Servers send live metrics which are visible in Grafana.

We have a `remote-settings folder <https://earthangel-b40313e5.influxcloud.net/dashboards/f/09aCU2uVk/remote-settings>`_ with the main dashboards.

Server Logs
-----------

Servers logs are available in the Google Cloud Console `Logs Explorer <https://console.cloud.google.com/logs/>`_.


Writer Instances
''''''''''''''''

This shows Nginx logs combined with application logs:

::

    resource.type="k8s_container"
    labels."k8s-pod/app_kubernetes_io/component"="writer"

To filter out request summaries, and see application logs only:

::

    jsonPayload.Type!="request.summary"

Specific status codes, for example errors:

::

    jsonPayload.Fields.code=~"^(4|5)\d{2,2}$"


Reader Instances
''''''''''''''''

::

    labels."k8s-pod/app_kubernetes_io/component"="reader"


Cronjobs / Lambdas
''''''''''''''''''

Filter ``labels."k8s-pod/app_kubernetes_io/component"`` with one of the following values:

- ``cron-backport-records``
- ``cron-backport-records-normandy``
- ``cron-cookie-banner-rules-list``
- ``cron-refresh-signature``
- ``cron-remote-settings-mdn-browser-compat-data``
- ``cron-sync-megaphone``


Attachments CDN Logs
''''''''''''''''''''

::

    httpRequest.requestUrl =~ "attachments"


Clients Telemetry
-----------------

Clients send us uptake statuses, that we can query and graph over time in Redash.

Redash Queries
''''''''''''''

- `Signature errors by version <https://sql.telemetry.mozilla.org/queries/82717>`_
- `Sync error investigation (last 36H) <https://sql.telemetry.mozilla.org/queries/67923>`_
- `Synchronization errors distribution <https://sql.telemetry.mozilla.org/queries/68824>`_
- `Remote Settings clients stuck in the past <https://sql.telemetry.mozilla.org/queries/81955>`_
- `Profiles with broken sync (last 120H) <https://sql.telemetry.mozilla.org/queries/85521>`_

.. note::

    Most queries filter on the last X hours with ``WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {{X}} HOUR)``
    but it's possible to query a specific time window with:

    ::
        WHERE timestamp > timestamp '2023-10-24 06:00:00'
          AND timestamp < timestamp '2023-10-24 22:00:00'

.. note::

    These queries may require permissions, don't hesitate to request access on Slack in ``#delivery``.

Telescope Check Queries
'''''''''''''''''''''''

These queries can be used as models when troubleshooting with Redash:

- `Events per period of 10min <https://github.com/mozilla-services/telescope/blob/641587b5a37c7f1ae8fa911dbd516bcb4bf102c7/checks/remotesettings/uptake_error_rate.py#L27-L63>`_
- `Percentiles on sync duration and age of pulled data <https://github.com/mozilla-services/telescope/blob/641587b5a37c7f1ae8fa911dbd516bcb4bf102c7/checks/remotesettings/uptake_max_age.py#L16-L62>`_
