from datetime import datetime, timedelta, timezone

from decouple import Csv, config

from . import KintoClient as Client


DEFAULT_USER_IDS = (
    "account:admin, account:cloudservices_kinto_prod, plugin:remote-settings"
)
DEFAULT_BUCKETS = "staging, security-state-staging, main-workspace"


def utcnow():
    return datetime.now(timezone.utc)


def purge_history(*args, **kwargs):
    """Purge old history entries on a regular basis."""
    server_url = config("SERVER", default="http://localhost:8888/v1")
    auth = config("AUTH", default="admin:s3cr3t")
    max_age_days = config("MAX_AGE_DAYS", default=365 * 2, cast=int)
    user_ids = config("USER_IDS", default=DEFAULT_USER_IDS, cast=Csv())
    buckets = config("BUCKETS", default=DEFAULT_BUCKETS, cast=Csv())

    limit_date = utcnow() - timedelta(days=max_age_days)
    limit_timestamp = f'"{int(limit_date.timestamp() * 1000)}"'

    client = Client(server_url=server_url, auth=auth)

    for bucket in buckets:
        for user_id in user_ids:
            deleted = client.purge_history(
                bucket=bucket, _before=limit_timestamp, user_id=user_id
            )
            print(f"{len(deleted)} entries purged from history.")
