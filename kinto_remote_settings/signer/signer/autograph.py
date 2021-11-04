import base64
import warnings
from urllib.parse import urljoin

import requests
from kinto import logger
from requests_hawk import HawkAuth

from ..utils import get_first_matching_setting
from .base import SignerBase

SIGNATURE_FIELDS = ["signature", "x5u"]
EXTRA_SIGNATURE_FIELDS = ["mode", "public_key", "type", "signer_id", "ref"]


class AutographSigner(SignerBase):
    def __init__(self, server_url, hawk_id, hawk_secret):
        self.server_url = server_url
        self.auth = HawkAuth(id=hawk_id, key=hawk_secret)

    def sign(self, payload):
        if isinstance(payload, str):  # pragma: nocover
            payload = payload.encode("utf-8")

        b64_payload = base64.b64encode(payload)
        url = urljoin(self.server_url, "/sign/data")
        resp = requests.post(
            url, auth=self.auth, json=[{"input": b64_payload.decode("utf-8")}]
        )
        resp.raise_for_status()
        signature_bundle = resp.json()[0]

        # Critical fields must be present, will raise if missing.
        infos = {field: signature_bundle[field] for field in SIGNATURE_FIELDS}
        # Other fields are returned and will be stored as part of the signature.
        # but client won't break if they are missing, so don't raise.
        infos.update(
            **{
                field: signature_bundle[field]
                for field in EXTRA_SIGNATURE_FIELDS
                if field in signature_bundle
            }
        )
        logger.info(
            "Obtained %s response from Autograph %s"
            % (resp.status_code, signature_bundle["ref"])
        )
        return infos


def load_from_settings(settings, prefix="", *, prefixes=None):
    if prefixes is None:
        prefixes = [prefix]

    if prefix != "":
        message = (
            "signer.load_from_settings `prefix` parameter is deprecated, please "
            "use `prefixes` instead."
        )
        warnings.warn(message, DeprecationWarning)

    return AutographSigner(
        server_url=get_first_matching_setting(
            "autograph.server_url", settings, prefixes
        ),
        hawk_id=get_first_matching_setting("autograph.hawk_id", settings, prefixes),
        hawk_secret=get_first_matching_setting(
            "autograph.hawk_secret", settings, prefixes
        ),
    )
