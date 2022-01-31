import sys

from .backends.local_ecdsa import ECDSASigner


def generate_keypair(private_key_location, public_key_location):
    private_key, public_key = ECDSASigner.generate_keypair()

    with open(private_key_location, "wb+") as tmp_file:
        tmp_file.write(private_key)

    with open(public_key_location, "wb+") as tmp_file:
        tmp_file.write(public_key)


if __name__ == "__main__":  # pragma: no cover
    if len(sys.argv) != 3:
        print(
            "Usage: python -m kinto_remote_settings.signer.generate_keypair "
            "{private_key} {public_key}"
        )
        sys.exit(0)
    generate_keypair(sys.argv[1], sys.argv[2])
