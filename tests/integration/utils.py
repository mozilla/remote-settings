import random
from string import hexdigits

from kinto_http import Client
from kinto_http.patch_type import JSONPatch


def _rand(size: int = 10) -> str:
    return "".join(random.choices(hexdigits, k=size))


def upload_records(client: Client, num: int):
    records = []
    for _ in range(num):
        data = {"one": _rand(1000)}
        record = client.create_record(data=data)
        records.append(record["data"])
    return records


def setup_server(
    setup_client: Client,
    editor_client: Client = None,
    reviewer_client: Client = None,
):
    setup_client.create_bucket(
        permissions={
            "collection:create": ["system.Authenticated"],
        },
        if_not_exists=True,
    )
    setup_client.create_collection(if_not_exists=True)

    if editor_client:
        editor_id = (editor_client.server_info())["user"]["id"]
        data = JSONPatch([{"op": "add", "path": "/data/members/0", "value": editor_id}])
        setup_client.patch_group(
            id=f"{setup_client.collection_name}-editors", changes=data
        )

    if reviewer_client:
        reviewer_id = (reviewer_client.server_info())["user"]["id"]
        data = JSONPatch(
            [{"op": "add", "path": "/data/members/0", "value": reviewer_id}]
        )
        setup_client.patch_group(
            id=f"{setup_client.collection_name}-reviewers", changes=data
        )
