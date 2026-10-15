import base64
import datetime
import logging
import warnings
from typing import Any
from urllib.parse import urljoin

import backoff
import requests
from pyramid.settings import aslist
from requests_hawk import HawkAuth

from ..utils import fetch_cert, get_first_matching_setting
from .base import SignerBase


logger = logging.getLogger(__name__)


SIGNATURE_FIELDS = ["signature", "x5u"]
EXTRA_SIGNATURE_FIELDS = ["mode", "public_key", "type", "signer_id", "ref"]
DEFAULT_MAX_RETRIES = 2


def _is_client_error(e: Exception) -> bool:
    # Do not retry on client errors (eg. bad credentials or key id).
    return (
        isinstance(e, requests.HTTPError)
        and e.response is not None
        and e.response.status_code < 500
    )


class AutographSigner(SignerBase):
    def __init__(
        self,
        server_url: str,
        hawk_id: str,
        hawk_secret: str,
        keyids: list[str],
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self.server_url = server_url
        self.auth = HawkAuth(id=hawk_id, key=hawk_secret)
        # List of keys to use for signing.
        self.key_ids = keyids
        self.max_retries = max_retries

    def healthcheck(self, request: Any) -> None:
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
        clamped_minimum = int(
            min(max_remaining_days, max(min_remaining_days, relative_minimum))
        )
        if remaining_days <= clamped_minimum:
            msg = "Only %s days before Autograph certificate expires (%s)"
            logger.warning(msg, remaining_days, end)

        logger.info(
            f"Certificate lasts {lifespan} days and ends in {remaining_days} days "
            f"({remaining_days - clamped_minimum} days before alert)."
        )

    def sign(self, *payloads: str | bytes) -> list[dict]:
        post_sign_with_retry = backoff.on_exception(
            backoff.expo,
            (requests.ConnectionError, requests.Timeout, requests.HTTPError),
            max_tries=self.max_retries + 1,
            giveup=_is_client_error,
        )(self._post_sign)

        # Sign every payload with every configured key, in a single batched
        # request. Autograph returns the signatures in the order of the request.
        sign_requests = []
        for payload in payloads:
            if isinstance(payload, str):  # pragma: no cover
                payload = payload.encode("utf-8")
            b64_payload = base64.b64encode(payload).decode("utf-8")
            for key_id in self.key_ids:
                logger.info(
                    "Sign %s bytes using Autograph with key %r",
                    len(b64_payload),
                    key_id,
                )
                sign_requests.append({"input": b64_payload, "keyid": key_id})

        resp = post_sign_with_retry(json=sign_requests)

        signatures = []
        for signature_bundle in resp.json():
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
                "Obtained %s response from Autograph %s",
                resp.status_code,
                signature_bundle["ref"],
            )
            signatures.append(infos)
        if len(signatures) != len(sign_requests):
            msg = "Expected %s signatures from Autograph, got %s"
            raise ValueError(msg % (len(sign_requests), len(signatures)))
        return signatures

    def _post_sign(self, json: list[dict]) -> requests.Response:
        url = urljoin(self.server_url, "/sign/data")
        resp = requests.post(url, auth=self.auth, json=json)
        resp.raise_for_status()
        return resp


def load_from_settings(
    settings: dict, prefix: str = "", *, prefixes: list[str] | None = None
) -> AutographSigner:
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
        keyids=aslist(
            get_first_matching_setting(
                "autograph.key_ids",
                settings,
                prefixes,
                default="remote-settings",
            )
        ),
        max_retries=int(
            get_first_matching_setting(
                "autograph.max_retries",
                settings,
                prefixes,
                default=DEFAULT_MAX_RETRIES,
            )
        ),
    )
