from kinto_remote_settings.signer.hasher import compute_hash


def test_compute_hash():
    assert compute_hash("un-bateau") == compute_hash("un-bateau")
    expected_hash = (
        "YofMiNkvyRoLAc/jCwKEgC3krpYFrsC0fzbrtecT4AigzZo" "6BEoHvu2wiLpKfW81"
    )
    assert compute_hash("sont-dans-un-bateau") == expected_hash
