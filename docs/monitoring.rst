.. _monitoring:

Monitoring
==========

Delivery Checks
---------------

The Remote Settings ecosystem can be monitored from the `Delivery Checks dashboard <https://telescope.prod.webservices.mozgcp.net/>`_.

Each environment has its own set of checks, and generally speaking if the checks pass, the service is operating without issues.

.. note::

    This is an instance of `Telescope <https://github.com/mozilla-services/telescope>`_, a generic health check service that you can use for your services!

All endpoints return JSON that can be used from the command line. For example:

.. code-block:: bash

    # Latest approvals for a specific collection
    curl -s https://telescope.prod.webservices.mozgcp.net/checks/remotesettings-prod/latest-approvals | jq '
        .data[]
            | select(.source | contains("-amp"))
            | .datetime + " "
            + .source + ": "
            + " +" + ((.changes.create // 0) | tostring)
            + " ~" + ((.changes.update // 0) | tostring)
            + " -" + ((.changes.delete // 0) | tostring)' | head -n 5


Server Metrics
--------------

Servers send live metrics which are visible in Grafana.

We have `Yardstick dashboards <https://yardstick.mozilla.org>`_ for nonprod and prod, as well as alerts.

Random notes
''''''''''''

* Counters are cumulative, so you need to use ``rate()`` or ``increase()`` to get the increase over time.
* The ``$__range`` variable resolves to the whole time range you are showing, basically end time of your graph minus start time. 
* For the increase since the previous data point in the graph, i.e. the interval between datapoints, use ``$__interval``.
* The ``group by(...)`` function always returns a vector with all values set to 1. For counts, you most likely want ``sum by(...)``
* ``increase()`` will sometimes miss individual events. Use subqueries as a workaround. ``some_metric[$__interval]`` evaluates to all datapoints for ``some_metric`` within the previous X seconds (eg. 120s). The function then computes the increase between the first and the last datapoint in the vector it sees, while accounting for possible counter resets. The function then extrapolates this to the whole 120 seconds interval by multiplying with ``120s / (timestamp of last datapoint in vector - timestamp of first datapoint in vector)``. The ``increase()`` function will thus miss the increases between two consecutive intervals, and it will "make up" for this by extrapolation. On average, this will be correct, but only on average.
* In order to work for sporadic counter events, use a subquery like this one: ``sum(sum_over_time((some_metric{field="val"} - some_metric{field="val"} offset 30s >= 0 or sum without(__name__) (some_metric{field="val"}))[$__interval:30s]))``. It will get rather slow when used over longer time periods, so if we really want to use this on long period, we should probably set up recording rules for the counter increase.

Links
'''''

* `About count and sum observations <https://prometheus.io/docs/practices/histograms/#count-and-sum-of-observations>`_


Server Logs
-----------

Servers logs are available in the Google Cloud Console `Logs Explorer <https://console.cloud.google.com/logs/>`_.

Application logs are visible in the ``webservices- high-prod`` project (since they run on the ``webservices-high-prod`` GKE cluster).


::

    resource.labels.container_name="remote-settings"

Logs are also exposed to `yardstick <https://yardstick.mozilla.org/d/aeogevsa6rxfkf/cronjob-dashboard-examples?orgId=1&from=now-6h&to=now&timezone=browser>`_ via bigquery. This is useful for creating log-based dashboards/alerts, or if you don't have access to the ``webservices-high`` projects in GCP.

.. code-block:: sql

		SELECT timestamp, JSON_VALUE(json_payload, '$.Type') Type, 
		  JSON_VALUE(json_payload, '$.Fields.path') Path,
		  JSON_VALUE(json_payload, '$.Fields.msg') Msg
		FROM `moz-fx-remote-settings-prod.gke_remote_settings_prod_log_linked._AllLogs` l
		WHERE JSON_VALUE(resource.labels, '$.container_name') = 'remote-settings'
		AND $__timeFilter(timestamp)
		ORDER BY timestamp DESC
		LIMIT 100;


Writer Instances
''''''''''''''''

This shows Nginx logs combined with application logs:

::

    resource.type="k8s_container"
    labels."k8s-pod/app_kubernetes_io/component"="writer"

To filter out request summaries, and see application logs only:

::

    -jsonPayload.Type="request.summary"

Specific status codes, for example errors:

::

    jsonPayload.Fields.code=~"^(4|5)\d{2,2}$"


Reader Instances
''''''''''''''''

::

    labels."k8s-pod/app_kubernetes_io/component"="reader"


Cronjobs
''''''''

Via log explorer:
::

    labels."k8s-pod/app_kubernetes_io/component"=~"^cron-<my-github-repo-name>$"

Via `yardstick <https://yardstick.mozilla.org/d/aeogevsa6rxfkf/cronjob-dashboard-examples?orgId=1&from=now-6h&to=now&timezone=browser>`_:

.. code-block:: sql

		SELECT timestamp, text_payload
		FROM `moz-fx-remote-settings-prod.gke_remote_settings_prod_log_linked._AllLogs` l
		WHERE JSON_VALUE(resource.labels, '$.container_name') = 'cron-<my-github-repo-name>'
		AND $__timeFilter(timestamp)
		ORDER BY timestamp DESC
		LIMIT 100;



Attachments CDN Logs
''''''''''''''''''''

::

    httpRequest.requestUrl =~ "attachments"


CDN Requests Logs in BiqQuery
'''''''''''''''''''''''''''''

The requests are sampled at 1 per 100, `as configured here <https://github.com/mozilla-it/webservices-infra/blob/03e515b70a08caaaf4d41bc91a5294d517e61977/remote-settings/tf/prod/logs.tf#L1-L5>`_.

In order to unify the requests of the attachments CDN and the API CDN, we can use the following query:

.. code-block:: sql

    WITH attachments_urls AS (
        SELECT
            'attachments' AS source,
            http_request.request_url AS url,
            http_request.response_size AS size,
            *
        FROM `moz-fx-remote-settings-prod.remote_settings_prod_default_log_linked._AllLogs`
    ),
    api_urls AS (
        SELECT
            'api' AS source,
            http_request.request_url AS url,
            http_request.response_size AS size,
            *
        FROM `moz-fx-remote-settings-prod.gke_remote_settings_prod_log_linked._AllLogs`
    ),
    urls AS (
        SELECT * FROM attachments_urls
        UNION ALL
        SELECT * FROM api_urls
    )
    SELECT *
    FROM urls
    WHERE timestamp >= TIMESTAMP(DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH))
        AND timestamp < TIMESTAMP(DATE_TRUNC(CURRENT_DATE(), MONTH))
        AND http_request.status = 200;


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
