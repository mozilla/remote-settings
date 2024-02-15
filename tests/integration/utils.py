import random
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
