import logging
import os

import requests.auth

from . import KintoClient


logger = logging.getLogger(__name__)


BROADCASTER_ID = "remote-settings"
CHANNEL_ID = "monitor_changes"


class BearerAuth(requests.auth.AuthBase):
    def __init__(self, token):
        self.token = token

    def __eq__(self, rhs):
        return self.token == rhs.token

    def __call__(self, r):
        r.headers["Authorization"] = "Bearer {}".format(self.token)
        return r


class Megaphone:
    def __init__(self, url, reader_auth, broadcaster_auth, broadcaster_id):
        self.url = url.rstrip("/")
        self.reader_auth = BearerAuth(reader_auth)
        self.broadcaster_auth = BearerAuth(broadcaster_auth)
        self.broadcaster_id = broadcaster_id

    def send_version(self, version):
        url = f"{self.url}/broadcasts/{self.broadcaster_id}"
        resp = requests.put(url, auth=self.broadcaster_auth, data=version)
        resp.raise_for_status()
        logger.info(
            "Sent version {} to megaphone. Response was {}".format(
                version, resp.status_code
            )
        )

    def get_version(self):
        url = f"{self.url}/broadcasts"
        resp = requests.get(url, auth=self.reader_auth)
        resp.raise_for_status()
        broadcasts = resp.json()
        etag = broadcasts["broadcasts"][self.broadcaster_id]
        return etag.strip('"')


def get_remotesettings_timestamp(uri):
    client = KintoClient(server_url=uri)
    changeset = client.get_changeset(
        bucket="monitor", collection="changes", bust_cache=True
    )
    # We want to filter out preview entries, because we don't want to notify all clients
    # when a review is requested. Therefore we can't use the `timestamp` field and must
    # get it from filtered entries.
    # https://github.com/mozilla/remote-settings/blob/45841c04/kinto-remote-settings/src/kinto_remote_settings/changes/views.py#L40-L44
    return str(
        max(
            e["last_modified"]
            for e in changeset["changes"]
            if "preview" not in e["bucket"]
        )
    )


def sync_megaphone(event, context):
    rs_server = event.get("server") or os.getenv("SERVER")
    rs_timestamp = get_remotesettings_timestamp(rs_server)

    megaphone_url = event.get("megaphone_url") or os.getenv("MEGAPHONE_URL")
    megaphone_reader_auth = event.get("megaphone_reader_auth") or os.getenv(
        "MEGAPHONE_READER_AUTH"
    )
    megaphone_broadcaster_auth = event.get("megaphone_broadcaster_auth") or os.getenv(
        "MEGAPHONE_BROADCASTER_AUTH"
    )
    broadcaster_id = event.get("broadcaster_id") or os.getenv(
        "BROADCASTER_ID", BROADCASTER_ID
    )
    channel_id = event.get("channel_id") or os.getenv("CHANNEL_ID", CHANNEL_ID)
    broadcast_id = f"{broadcaster_id}/{channel_id}"

    megaphone_client = Megaphone(
        megaphone_url, megaphone_reader_auth, megaphone_broadcaster_auth, broadcast_id
    )
    megaphone_timestamp = megaphone_client.get_version()
    logger.info(f"Remote Settings: {rs_timestamp}; Megaphone: {megaphone_timestamp}")

    if int(rs_timestamp) <= int(megaphone_timestamp):
        logger.info("Timestamps are in sync. Nothing to do.")
        return

    megaphone_client.send_version(f'"{rs_timestamp}"')
