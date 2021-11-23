import base64
import hashlib


def compute_hash(string):
    h = hashlib.new("sha384")
    h.update(string.encode("utf-8"))
    b64hash = base64.b64encode(h.digest())
    return b64hash.decode("utf-8")
