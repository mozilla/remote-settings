import random
from base64 import b64encode
from string import hexdigits

from kinto_http import Client


def _rand(size: int = 10) -> str:
    return "".join(random.choices(hexdigits, k=size))


def upload_records(client: Client, num: int):
    records = []
    for _ in range(num):
        data = {"one": _rand(1000)}
        record = client.create_record(data=data)
        records.append(record["data"])
    return records


# Playwright it expects a 401 returned on the first request if auth is provided, which does not work in kinto.
def create_extra_headers(username: str, password: str):
    return {
        "Authorization": "Basic "
        + b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    }
