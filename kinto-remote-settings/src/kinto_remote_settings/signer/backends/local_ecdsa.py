import base64
import warnings
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)

from ..utils import get_first_matching_setting
from .base import SignerBase
from .exceptions import BadSignatureError


# Autograph uses this prefix prior to signing.
SIGN_PREFIX = b"Content-Signature:\x00"

# Signatures are the raw concatenation of r and s, each 48 bytes on P-384.
COORDINATE_SIZE = 48


class ECDSASigner(SignerBase):
    def __init__(
        self, private_key: str | None = None, public_key: str | None = None
    ) -> None:
        if private_key is None and public_key is None:
            msg = "Please, specify either a private_key or public_key location."
            raise ValueError(msg)
        self.private_key = private_key
        self.public_key = public_key

    def healthcheck(self, request: Any) -> None:
        pass

    @classmethod
    def generate_keypair(cls) -> tuple[bytes, bytes]:
        sk = ec.generate_private_key(ec.SECP384R1())
        sk_pem = sk.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
        vk_pem = sk.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return sk_pem, vk_pem

    def load_private_key(self) -> ec.EllipticCurvePrivateKey:
        if self.private_key is None:
            msg = "Please, specify the private_key location."
            raise ValueError(msg)

        with open(self.private_key, "rb") as key_file:
            key = serialization.load_pem_private_key(key_file.read(), password=None)
        return key

    def load_public_key(self) -> ec.EllipticCurvePublicKey | None:
        # Check settings validity
        if self.private_key:
            private_key = self.load_private_key()
            return private_key.public_key()
        if self.public_key:
            with open(self.public_key, "rb") as key_file:
                key = serialization.load_pem_public_key(key_file.read())
            return key
        return None

    def sign(self, *payloads: str | bytes) -> list[dict]:
        private_key = self.load_private_key()
        signatures = []
        for payload in payloads:
            if isinstance(payload, str):  # pragma: no cover
                payload = payload.encode("utf-8")

            payload = SIGN_PREFIX + payload
            der_signature = private_key.sign(payload, ec.ECDSA(hashes.SHA384()))
            r, s = decode_dss_signature(der_signature)
            signature = r.to_bytes(COORDINATE_SIZE, "big") + s.to_bytes(
                COORDINATE_SIZE, "big"
            )
            x5u = ""
            enc_signature = base64.urlsafe_b64encode(signature).decode("utf-8")
            signatures.append(
                {"signature": enc_signature, "x5u": x5u, "mode": "p384ecdsa"}
            )
        return signatures

    def verify(self, payload: str | bytes, signature_bundle: dict) -> None:
        if isinstance(payload, str):  # pragma: no cover
            payload = payload.encode("utf-8")

        payload = SIGN_PREFIX + payload
        signature = signature_bundle["signature"]
        if isinstance(signature, str):  # pragma: no cover
            signature = signature.encode("utf-8")

        signature_bytes = base64.urlsafe_b64decode(signature)

        public_key = self.load_public_key()
        assert public_key is not None
        try:
            if len(signature_bytes) != 2 * COORDINATE_SIZE:
                raise ValueError(f"Invalid signature length: {len(signature_bytes)}")
            r = int.from_bytes(signature_bytes[:COORDINATE_SIZE], "big")
            s = int.from_bytes(signature_bytes[COORDINATE_SIZE:], "big")
            public_key.verify(
                encode_dss_signature(r, s), payload, ec.ECDSA(hashes.SHA384())
            )
        except Exception as e:
            raise BadSignatureError(e)


def load_from_settings(
    settings: dict, prefix: str = "", *, prefixes: list[str] | None = None
) -> "ECDSASigner":
    if prefixes is None:
        prefixes = [prefix]

    if prefix != "":
        message = (
            "signer.load_from_settings `prefix` parameter is deprecated, please "
            "use `prefixes` instead."
        )
        warnings.warn(message, DeprecationWarning)

    private_key = get_first_matching_setting("ecdsa.private_key", settings, prefixes)
    public_key = get_first_matching_setting("ecdsa.public_key", settings, prefixes)
    try:
        return ECDSASigner(private_key=private_key, public_key=public_key)
    except ValueError:
        msg = (
            "Please specify either kinto.signer.ecdsa.private_key or "
            "kinto.signer.ecdsa.public_key in the settings."
        )
        raise ValueError(msg)
