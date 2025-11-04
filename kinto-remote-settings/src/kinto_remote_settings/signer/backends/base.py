class SignerBase(object):
    def healthcheck(self, request):
        """
        Performs a series of checks for this signing backend.
        """
        raise NotImplementedError

    def sign(self, payload) -> list[dict]:
        """
        Signs the specified `payload` and returns the signature metadata.

        :returns: A list of mappings with every attributes about the signatures
            (e.g. "signature", "hash_algorithm", "signature_encoding"...)
        :rtype: list[dict]
        """
        raise NotImplementedError
