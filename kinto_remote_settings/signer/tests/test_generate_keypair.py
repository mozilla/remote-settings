import tempfile
import unittest

from kinto_remote_settings.signer.backends.local_ecdsa import ECDSASigner
from kinto_remote_settings.signer.generate_keypair import generate_keypair


class KeyPairGeneratorTest(unittest.TestCase):
    def test_generated_keypairs_can_be_loaded(self):
        private_key_location = tempfile.mktemp("private_key")
        public_key_location = tempfile.mktemp("public_key")

        generate_keypair(private_key_location, public_key_location)
        backend = ECDSASigner(private_key=private_key_location)
        backend.sign("test")
