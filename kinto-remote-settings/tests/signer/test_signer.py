import os
import tempfile
import unittest
from base64 import urlsafe_b64decode, urlsafe_b64encode
from unittest import mock

import pytest
import requests
import responses
from kinto_remote_settings.signer.backends import (
    autograph,
    base,
    exceptions,
    local_ecdsa,
)


SIGNATURE = (
    "ikfq6qOV85vR7QaNCTldVvvtcNpPIICqqMp3tfyiT7fHCgFNq410SFnIfjAPgSa"
    "jEtxxyGtZFMoI_BzO_1y5oShLtX0LH4wx_Wft7wz17T7fFqpDQ9hFZzTOPBwZUIbx"
)


def save_key(key, key_name):
    fd, tmp = tempfile.mkstemp(suffix=key_name)
    os.close(fd)
    with open(tmp, "wb+") as tmp_file:
        tmp_file.write(key)
    return tmp


class BaseSignerTest(unittest.TestCase):
    def test_base_method_raises_unimplemented(self):
        signer = base.SignerBase()
        with pytest.raises(NotImplementedError):
            signer.sign("TEST")


class ECDSASignerTest(unittest.TestCase):
    @classmethod
    def get_backend(cls, **options):
        return local_ecdsa.ECDSASigner(**options)

    @classmethod
    def setUpClass(cls):
        sk, vk = local_ecdsa.ECDSASigner.generate_keypair()
        cls.sk_location = save_key(sk, "signing-key")
        cls.vk_location = save_key(vk, "verifying-key")
        cls.signer = cls.get_backend(private_key=cls.sk_location)

    @classmethod
    def tearDownClass(cls):
        os.remove(cls.sk_location)
        os.remove(cls.vk_location)

    def test_keyloading_fails_if_no_settings(self):
        backend = self.get_backend(public_key=self.vk_location)
        with pytest.raises(ValueError, match="specify the private_key location"):
            backend.load_private_key()

    def test_key_loading_works(self):
        key = self.signer.load_private_key()
        assert key is not None

    def test_signer_roundtrip(self):
        signatures = self.signer.sign("this is some text")
        self.signer.verify("this is some text", signatures[0])

    def test_signer_signs_every_payload(self):
        signatures = self.signer.sign("some text", "other text")

        assert len(signatures) == 2
        self.signer.verify("some text", signatures[0])
        self.signer.verify("other text", signatures[1])

    def test_base64url_encoding(self):
        signature_bundles = self.signer.sign("this is some text")
        b64signature = signature_bundles[0]["signature"]

        decoded_signature = urlsafe_b64decode(b64signature.encode("utf-8"))
        b64urlsignature = urlsafe_b64encode(decoded_signature).decode("utf-8")
        signature_bundles[0]["signature"] = b64urlsignature
        signature_bundles[0]["signature_encoding"] = "rs_base64url"

        self.signer.verify("this is some text", signature_bundles[0])

    def test_wrong_signature_raises_an_error(self):
        signature_bundle = {"signature": SIGNATURE, "mode": "p384ecdsa", "ref": ""}

        with pytest.raises(exceptions.BadSignatureError):
            self.signer.verify("Text not matching with the sig.", signature_bundle)

    def test_signer_returns_a_base64_string(self):
        signature = self.signer.sign("this is some text")[0]["signature"]
        urlsafe_b64decode(signature.encode("utf-8"))  # Raise if wrong.

    def test_load_private_key_raises_if_no_key_specified(self):
        with pytest.raises(ValueError, match="Please, specify either"):
            self.get_backend().load_private_key()

    def test_public_key_can_be_loaded_from_public_key_pem(self):
        signer = self.get_backend(public_key=self.vk_location)
        signer.load_public_key()

    def test_public_key_can_be_loaded_from_private_key_pem(self):
        signer = self.get_backend(private_key=self.sk_location)
        signer.load_public_key()

    def test_load_public_key_raises_an_error_if_missing_settings(self):
        with pytest.raises(ValueError, match="Please, specify either") as excinfo:
            self.get_backend()
        msg = "Please, specify either a private_key or public_key location."
        assert str(excinfo.value) == msg

    @mock.patch("kinto_remote_settings.signer.backends.local_ecdsa.ECDSASigner")
    def test_load_from_settings(self, mocked_signer):
        local_ecdsa.load_from_settings(
            {
                "settings_prefix": "kinto",
                "signer.ecdsa.private_key": mock.sentinel.private_key,
                "signer.ecdsa.public_key": mock.sentinel.public_key,
            },
            prefix="signer.",
        )

        mocked_signer.assert_called_with(
            private_key=mock.sentinel.private_key, public_key=mock.sentinel.public_key
        )

    def test_load_from_settings_fails_if_no_public_or_private_key(self):
        with pytest.raises(ValueError, match="Please specify either") as excinfo:
            local_ecdsa.load_from_settings({"settings_prefix": "kinto"}, "")
        msg = (
            "Please specify either kinto.signer.ecdsa.private_key or "
            "kinto.signer.ecdsa.public_key in the settings."
        )
        assert str(excinfo.value) == msg


class AutographSignerTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch("backoff._sync.time.sleep")
        self.sleep = patcher.start()
        self.addCleanup(patcher.stop)

    @mock.patch("kinto_remote_settings.signer.backends.autograph.requests")
    def test_request_is_being_crafted_with_payload_as_input(self, requests):
        response = mock.MagicMock()
        response.json.return_value = [{"signature": SIGNATURE, "x5u": "", "ref": ""}]
        requests.post.return_value = response

        signer = autograph.AutographSigner(
            hawk_id="alice",
            hawk_secret="fs5wgcer9qj819kfptdlp8gm227ewxnzvsuj9ztycsx08hfhzu",
            server_url="http://localhost:8000",
            keyids=["remote-settings"],
        )
        signature_bundles = signer.sign("test data")
        requests.post.assert_called_with(
            "http://localhost:8000/sign/data",
            auth=signer.auth,
            json=[
                {
                    "input": "dGVzdCBkYXRh",
                    "keyid": "remote-settings",
                }
            ],
        )
        assert signature_bundles[0]["signature"] == SIGNATURE

    @mock.patch("kinto_remote_settings.signer.backends.autograph.requests")
    def test_payloads_and_key_ids_are_signed_in_a_single_request(self, requests):
        requests.post.return_value.json.return_value = [
            {"signature": f"sign-{i}", "x5u": f"x5u-{i}", "ref": f"ref-{i}"}
            for i in range(4)
        ]
        signer = autograph.AutographSigner(
            hawk_id="alice",
            hawk_secret="fs5wgcer9",  # pragma: allowlist secret
            server_url="http://localhost:8000",
            keyids=["key1", "key2"],
        )

        signatures = signer.sign("test data", "other data")

        requests.post.assert_called_once_with(
            "http://localhost:8000/sign/data",
            auth=signer.auth,
            json=[
                {"input": "dGVzdCBkYXRh", "keyid": "key1"},
                {"input": "dGVzdCBkYXRh", "keyid": "key2"},
                {"input": "b3RoZXIgZGF0YQ==", "keyid": "key1"},
                {"input": "b3RoZXIgZGF0YQ==", "keyid": "key2"},
            ],
        )
        assert signatures == [
            {"signature": f"sign-{i}", "x5u": f"x5u-{i}", "ref": f"ref-{i}"}
            for i in range(4)
        ]

    @mock.patch("kinto_remote_settings.signer.backends.autograph.requests")
    def test_sign_raises_if_signatures_are_missing(self, requests):
        requests.post.return_value.json.return_value = [
            {"signature": "sig", "x5u": "x5u", "ref": "ref"}
        ]

        with pytest.raises(ValueError, match="Expected 2 signatures"):
            self._signer().sign("test data", "other data")

    def _signer(self):
        return autograph.AutographSigner(
            hawk_id="alice",
            hawk_secret="fs5wgcer9",  # pragma: allowlist secret
            server_url="http://localhost:8000",
            keyids=["key1"],
        )

    @responses.activate
    def test_sign_is_retried_on_server_errors(self):
        url = "http://localhost:8000/sign/data"
        responses.post(url, status=503)
        responses.post(url, body=requests.ConnectionError("boom"))
        responses.post(url, json=[{"signature": "sig", "x5u": "x5u", "ref": "ref"}])

        signatures = self._signer().sign("test data")

        assert signatures[0]["signature"] == "sig"
        assert len(responses.calls) == 3
        assert self.sleep.call_count == 2
        # Hawk headers are regenerated on each attempt (fresh nonce).
        auth_headers = {c.request.headers["Authorization"] for c in responses.calls}
        assert len(auth_headers) == 3

    @responses.activate
    def test_sign_raises_after_max_attempts(self):
        responses.post("http://localhost:8000/sign/data", status=502)

        with pytest.raises(requests.HTTPError):
            self._signer().sign("test data")

        assert len(responses.calls) == autograph.DEFAULT_MAX_RETRIES + 1

    @responses.activate
    def test_sign_retries_can_be_configured(self):
        responses.post("http://localhost:8000/sign/data", status=502)
        signer = self._signer()
        signer.max_retries = 0

        with pytest.raises(requests.HTTPError):
            signer.sign("test data")

        assert len(responses.calls) == 1

    @responses.activate
    def test_sign_is_not_retried_on_client_errors(self):
        responses.post("http://localhost:8000/sign/data", status=401)

        with pytest.raises(requests.HTTPError):
            self._signer().sign("test data")

        assert len(responses.calls) == 1
        self.sleep.assert_not_called()

    @mock.patch("kinto_remote_settings.signer.backends.autograph.AutographSigner")
    def test_load_from_settings(self, mocked_signer):
        autograph.load_from_settings(
            {
                "settings_prefix": "kinto",
                "signer.autograph.server_url": mock.sentinel.server_url,
                "signer.autograph.hawk_id": mock.sentinel.hawk_id,
                "signer.autograph.hawk_secret": mock.sentinel.hawk_secret,
            },
            prefix="signer.",
        )

        mocked_signer.assert_called_with(
            server_url=mock.sentinel.server_url,
            hawk_id=mock.sentinel.hawk_id,
            hawk_secret=mock.sentinel.hawk_secret,
            keyids=["remote-settings"],
            max_retries=autograph.DEFAULT_MAX_RETRIES,
        )

    @mock.patch("kinto_remote_settings.signer.backends.autograph.AutographSigner")
    def test_load_max_retries_from_settings(self, mocked_signer):
        autograph.load_from_settings(
            {
                "settings_prefix": "kinto",
                "signer.autograph.server_url": mock.sentinel.server_url,
                "signer.autograph.hawk_id": mock.sentinel.hawk_id,
                "signer.autograph.hawk_secret": mock.sentinel.hawk_secret,
                "signer.autograph.max_retries": "5",
            },
            prefixes=["signer."],
        )

        assert mocked_signer.call_args.kwargs["max_retries"] == 5
