from datetime import date, timedelta

import requests
from decouple import config
from google.cloud import bigquery


SLACK_CHANNEL = config("SLACK_CHANNEL", default="remote-settings-alerts")
SLACK_WEBHOOK_URL = config("SLACK_WEBHOOK_URL", default=None)

PREVIOUS_PERIOD_DAYS = config("PREVIOUS_PERIOD_DAYS", default=90, cast=int)
LAST_PERIOD_DAYS = config("LAST_PERIOD_DAYS", default=7, cast=int)
MIN_AVG_BYTES = config(
    "MIN_AVG_BYTES", default=500e9, cast=float
)  # 500GB, to filter out noise from small collections.
TOP_N = config("TOP_N", default=5, cast=int)

COLLECTIONS_AVERAGE = """
WITH daily_consumption AS (
    SELECT
        DATE_TRUNC(timestamp, DAY) AS day,
        collection_id,
        SUM(size) AS size
    FROM `mozdata.remote_settings_logs_aggregates.prod_logs_aggregates`
    WHERE timestamp >= TIMESTAMP_SUB(TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(), DAY), INTERVAL {interval_days_start} DAY)
      AND timestamp <  TIMESTAMP_SUB(TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(), DAY), INTERVAL {interval_days_end} DAY)
      AND collection_id IS NOT NULL
    GROUP BY day, collection_id
)
SELECT
    collection_id,
    AVG(size) AS avg_size
FROM daily_consumption
GROUP BY collection_id
"""


def execute_query(client: bigquery.Client, query: str) -> list[dict]:
    rows = client.query(query).result()
    return [dict(row) for row in rows]


def rows_to_dict(rows: list[dict], idxfield: str, valuefield: str) -> dict:
    return {row[idxfield]: row[valuefield] for row in rows}


def consumption_movers() -> None:
    """
    Identify the collections with the biggest increases and decreases in bandwidth consumption,
    and posts a message in Slack to alert the team.
    """
    end_day = date.today() - timedelta(days=1)  # Look at complete days only.
    start_day = end_day - timedelta(days=LAST_PERIOD_DAYS)

    client = bigquery.Client()
    previous_rows = execute_query(
        client,
        COLLECTIONS_AVERAGE.format(
            interval_days_start=PREVIOUS_PERIOD_DAYS + LAST_PERIOD_DAYS,
            interval_days_end=LAST_PERIOD_DAYS,
        ),
    )
    last_rows = execute_query(
        client,
        COLLECTIONS_AVERAGE.format(
            interval_days_start=LAST_PERIOD_DAYS,
            interval_days_end=0,
        ),
    )

    previous = rows_to_dict(previous_rows, "collection_id", "avg_size")
    last = rows_to_dict(last_rows, "collection_id", "avg_size")

    movers = []
    for collection_id, last_avg in last.items():
        if collection_id not in previous:
            # Skip new collections.
            continue

        # Skip small collections to avoid noise.
        if last_avg < MIN_AVG_BYTES and previous[collection_id] < MIN_AVG_BYTES:
            continue

        previous_avg = previous[collection_id]
        delta = last_avg - previous_avg
        pct_change = (last_avg / previous_avg - 1) * 100
        movers.append(
            {
                "collection_id": collection_id,
                "pct_change": pct_change,
                "delta": delta,
            }
        )

    top_increase = sorted(
        [m for m in movers if m["pct_change"] > 0],
        key=lambda m: m["delta"],
        reverse=True,
    )[:TOP_N]

    top_decrease = sorted(
        [m for m in movers if m["pct_change"] < 0], key=lambda m: m["delta"]
    )[:TOP_N]

    message = f"""*Bandwidth Consumption*
Period: {start_day.strftime("%b %-d")} → {end_day.strftime("%b %-d")}"""

    if top_increase:
        message += f"""\n
*Top increases* (Compared against previous {PREVIOUS_PERIOD_DAYS}-day daily average)
{"\n".join(f"- `{m['collection_id']}`: {m['pct_change']:+.1f}% " for m in top_increase)}"""

    if top_decrease:
        message += f"""\n
*Top decreases*
{"\n".join(f"- `{m['collection_id']}`: {m['pct_change']:+.1f}% " for m in top_decrease)}"""

    if not SLACK_WEBHOOK_URL:
        print("SLACK_WEBHOOK_URL is not set; message was not sent")
        print(f"Slack message:\n{message}")
        return

    resp = requests.post(
        SLACK_WEBHOOK_URL,
        json={
            "channel": SLACK_CHANNEL,
            "text": message,
        },
    )
    resp.raise_for_status()
