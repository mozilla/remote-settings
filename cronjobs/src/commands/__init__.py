import concurrent.futures
import os

import backoff
import kinto_http
import requests
from requests.adapters import TimeoutSauce


PARALLEL_REQUESTS = int(os.getenv("PARALLEL_REQUESTS", 4))
REQUESTS_TIMEOUT_SECONDS = float(os.getenv("REQUESTS_TIMEOUT_SECONDS", 2))
REQUESTS_NB_RETRIES = int(os.getenv("REQUESTS_NB_RETRIES", 4))
DRY_MODE = os.getenv("DRY_RUN", "0") in "1yY"

retry_timeout = backoff.on_exception(
    backoff.expo,
    (requests.exceptions.Timeout, requests.exceptions.ConnectionError),
    max_tries=REQUESTS_NB_RETRIES,
)


class CustomTimeout(TimeoutSauce):
    def __init__(self, *args, **kwargs):
        if kwargs["connect"] is None:
            kwargs["connect"] = REQUESTS_TIMEOUT_SECONDS
        if kwargs["read"] is None:
            kwargs["read"] = REQUESTS_TIMEOUT_SECONDS
        super().__init__(*args, **kwargs)


requests.adapters.TimeoutSauce = CustomTimeout


class KintoClient(kinto_http.Client):
    """
    This Kinto client will retry the requests if they fail for timeout, and
    if the server replies with a 5XX.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("retry", REQUESTS_NB_RETRIES)
        kwargs.setdefault("dry_mode", DRY_MODE)
        super().__init__(*args, **kwargs)

    @retry_timeout
    def server_info(self, *args, **kwargs):
        return super().server_info(*args, **kwargs)

    @retry_timeout
    def get_collection(self, *args, **kwargs):
        return super().get_collection(*args, **kwargs)

    @retry_timeout
    def get_records(self, *args, **kwargs):
        return super().get_records(*args, **kwargs)

    @retry_timeout
    def get_records_timestamp(self, *args, **kwargs):
        return super().get_records_timestamp(*args, **kwargs)

    @retry_timeout
    def get_changeset(self, *args, **kwargs):
        return super().get_changeset(*args, **kwargs)

    @retry_timeout
    def approve_changes(self, *args, **kwargs):
        return super().approve_changes(*args, **kwargs)

    @retry_timeout
    def request_review(self, *args, **kwargs):
        return super().request_review(*args, **kwargs)

    @retry_timeout
    def purge_history(self, *args, **kwargs):
        return super().purge_history(*args, **kwargs)


def call_parallel(func, args_list, max_workers=PARALLEL_REQUESTS):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(func, *args) for args in args_list]
        results = [future.result() for future in futures]
    return results


def fetch_all_changesets(client, with_workspace_buckets: bool = False):
    """
    Return the `/changeset` responses for all collections listed
    in the `monitor/changes` endpoint.
    The result contains the metadata and all the records of all collections
    for both preview and main buckets.
    """
    monitor_changeset = client.get_changeset("monitor", "changes", bust_cache=True)
    print("%s collections" % len(monitor_changeset["changes"]))
    args_list = [
        (c["bucket"], c["collection"], c["last_modified"])
        for c in monitor_changeset["changes"]
    ]

    if with_workspace_buckets:
        # For each collection exposed in the monitor/changes endpoint,
        # we will look for its corresponding workspace bucket using the
        # info exposed in the `signer` capability.
        server_info = client.server_info()
        try:
            resources = server_info["capabilities"]["signer"]["resources"]
        except KeyError:
            raise RuntimeError(
                "Cannot fetch workspace buckets: signer not enabled on server"
            )

        # Walk through all monitored changesets, and for each one,
        # add the corresponding workspace collection. We do this only using the
        # destination, not the preview, to avoid adding them twice.
        for monitored_changeset in monitor_changeset["changes"]:
            bucket = monitored_changeset["bucket"]
            for resource in resources:
                if bucket == resource["destination"]["bucket"]:
                    source_bucket = resource["source"]["bucket"]
                    args_list.append(
                        # _expected=0 for workspace collections.
                        (source_bucket, monitored_changeset["collection"], 0)
                    )
                    break

    all_changesets = call_parallel(
        lambda bid, cid, ts: client.get_changeset(bid, cid, _expected=ts), args_list
    )
    return all_changesets
