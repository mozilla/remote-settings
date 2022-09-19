import base64
import datetime
import warnings
from urllib.parse import urljoin

import requests
from kinto import logger
from requests_hawk import HawkAuth

from ..utils import fetch_cert, get_first_matching_setting
from .base import SignerBase


SIGNATURE_FIELDS = ["signature", "x5u"]
EXTRA_SIGNATURE_FIELDS = ["mode", "public_key", "type", "signer_id", "ref"]


class CertificateExpiresSoonError(Exception):
    """Error raised when the Autograph certificate is about to expire."""


class AutographSigner(SignerBase):
    def __init__(self, server_url, hawk_id, hawk_secret):
        self.server_url = server_url
        self.auth = HawkAuth(id=hawk_id, key=hawk_secret)

    def healthcheck(self, request):
        if not self.server_url.startswith("https"):
            # No certificate to check if not connected via HTTPs.
            return

        settings = request.registry.settings
        percentage_remaining_validity = int(
            settings.get(
                "signer.heartbeat_certificate_percentage_remaining_validity", 5
            )
        )
        min_remaining_days = int(
            settings.get("signer.heartbeat_certificate_min_remaining_days", 10)
        )
        max_remaining_days = int(
            settings.get("signer.heartbeat_certificate_max_remaining_days", 30)
        )

        # Check the server certificate validity.
        cert = fetch_cert(self.server_url)
        start = cert.not_valid_before.replace(tzinfo=datetime.timezone.utc)
        end = cert.not_valid_after.replace(tzinfo=datetime.timezone.utc)
        utcnow = datetime.datetime.now(datetime.timezone.utc)
        remaining_days = (end - utcnow).days
        lifespan = (end - start).days

        # The minimum remaining days depends on the certificate lifespan.
        relative_minimum = lifespan * percentage_remaining_validity / 100
        # We don't want to alert to much in advance, nor too late, hence we bound it.
        bounded_minimum = int(
            min(max_remaining_days, max(min_remaining_days, relative_minimum))
        )
        if remaining_days <= bounded_minimum:
            raise CertificateExpiresSoonError(
                f"Only {remaining_days} days before Autograph certificate expires"
            )

        logger.debug(
            f"Certificate lasts {lifespan} days and ends in {remaining_days} days "
            f"({remaining_days - bounded_minimum} days before alert)."
        )

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
