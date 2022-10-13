class SignerBase(object):
    def healthcheck(self, request):
        """
        Performs a series of checks for this signing backend.
        """
        raise NotImplementedError

    def sign(self, payload):
        """
        Signs the specified `payload` and returns the signature metadata.

        :returns: A mapping with every attributes about the signature
            (e.g. "signature", "hash_algorithm", "signature_encoding"...)
        :rtype: dict
        """
        raise NotImplementedError
