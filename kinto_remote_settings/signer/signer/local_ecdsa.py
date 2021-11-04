import base64
import hashlib
import warnings

import ecdsa
from ecdsa import NIST384p, SigningKey, VerifyingKey

from ..utils import get_first_matching_setting
from .base import SignerBase
from .exceptions import BadSignatureError

# Autograph uses this prefix prior to signing.
SIGN_PREFIX = b"Content-Signature:\x00"


class ECDSASigner(SignerBase):
    def __init__(self, private_key=None, public_key=None):
        if private_key is None and public_key is None:
            msg = "Please, specify either a private_key or public_key " "location."
            raise ValueError(msg)
        self.private_key = private_key
        self.public_key = public_key

    @classmethod
    def generate_keypair(cls):
        sk = SigningKey.generate(curve=NIST384p)
        vk = sk.get_verifying_key()
        return sk.to_pem(), vk.to_pem()

    def load_private_key(self):
        if self.private_key is None:
            msg = "Please, specify the private_key location."
            raise ValueError(msg)

        with open(self.private_key, "rb") as key_file:
            return SigningKey.from_pem(key_file.read())

    def load_public_key(self):
        # Check settings validity
        if self.private_key:
            private_key = self.load_private_key()
            return private_key.get_verifying_key()
        elif self.public_key:
            with open(self.public_key, "rb") as key_file:
                return VerifyingKey.from_pem(key_file.read())

    def sign(self, payload):
        if isinstance(payload, str):  # pragma: nocover
            payload = payload.encode("utf-8")

        payload = SIGN_PREFIX + payload
        private_key = self.load_private_key()
        signature = private_key.sign(
            payload, hashfunc=hashlib.sha384, sigencode=ecdsa.util.sigencode_string
        )
        x5u = ""
        enc_signature = base64.urlsafe_b64encode(signature).decode("utf-8")
        return {"signature": enc_signature, "x5u": x5u, "mode": "p384ecdsa"}

    def verify(self, payload, signature_bundle):
        if isinstance(payload, str):  # pragma: nocover
            payload = payload.encode("utf-8")

        payload = SIGN_PREFIX + payload
        signature = signature_bundle["signature"]
        if isinstance(signature, str):  # pragma: nocover
            signature = signature.encode("utf-8")

        signature_bytes = base64.urlsafe_b64decode(signature)

        public_key = self.load_public_key()
        try:
            public_key.verify(
                signature_bytes,
                payload,
                hashfunc=hashlib.sha384,
                sigdecode=ecdsa.util.sigdecode_string,
            )
        except Exception as e:
            raise BadSignatureError(e)


def load_from_settings(settings, prefix="", *, prefixes=None):
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
