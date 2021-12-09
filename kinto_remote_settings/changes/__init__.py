from pyramid.settings import aslist

from .. import __version__

MONITOR_BUCKET = "monitor"
MONITOR_BUCKET_PATH = "/buckets/{}".format(MONITOR_BUCKET)
CHANGES_COLLECTION = "changes"
CHANGES_COLLECTION_PATH = "{}/collections/{}".format(
    MONITOR_BUCKET_PATH, CHANGES_COLLECTION
)
CHANGES_RECORDS_PATH = "{}/records".format(CHANGES_COLLECTION_PATH)
CHANGESET_PATH = "/buckets/{bid}/collections/{cid}/changeset"


def includeme(config):
    settings = config.get_settings()
    collections = settings.get("changes.resources", [])

    config.add_api_capability(
        "changes",
        description="Track modifications of records in Kinto and store"
        " the collection timestamps into a specific bucket"
        " and collection.",
        url="http://kinto.readthedocs.io/en/latest/tutorials/"
        "synchronisation.html#polling-for-remote-changes",
        version=__version__,
        collections=aslist(collections),
    )

    config.scan("kinto_remote_settings.changes.views")
