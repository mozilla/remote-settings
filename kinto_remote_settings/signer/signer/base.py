class SignerBase(object):
    def sign(self, payload):
        """
        Signs the specified `payload` and returns the signature metadata.

        :returns: A mapping with every attributes about the signature
            (e.g. "signature", "hash_algorithm", "signature_encoding"...)
        :rtype: dict
        """
        raise NotImplementedError
