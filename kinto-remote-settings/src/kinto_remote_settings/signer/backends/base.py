from typing import Any


class SignerBase(object):
    def healthcheck(self, request: Any) -> None:
        """
        Performs a series of checks for this signing backend.
        """
        raise NotImplementedError

    def sign(self, payload: str | bytes) -> list[dict]:
        """
        Signs the specified `payload` and returns the signature metadata.

        :returns: A list of mappings with every attributes about the signatures
            (e.g. "signature", "hash_algorithm", "signature_encoding"...)
        :rtype: list[dict]
        """
        raise NotImplementedError
