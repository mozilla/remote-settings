import random
from string import hexdigits

from kinto_http import AsyncClient
from kinto_http.patch_type import JSONPatch


def _rand(size: int = 10) -> str:
    return "".join(random.choices(hexdigits, k=size))


async def upload_records(client: AsyncClient, num: int):
    records = []
    for _ in range(num):
        data = {"one": _rand(1000)}
        record = await client.create_record(data=data)
        records.append(record["data"])
    return records


async def setup_server(
    setup_client: AsyncClient,
    editor_client: AsyncClient = None,
    reviewer_client: AsyncClient = None,
):
    await setup_client.create_bucket(
        permissions={
            "collection:create": ["system.Authenticated"],
        },
        if_not_exists=True,
    )
    await setup_client.create_collection(if_not_exists=True)

    if editor_client:
        editor_id = (await editor_client.server_info())["user"]["id"]
        data = JSONPatch([{"op": "add", "path": "/data/members/0", "value": editor_id}])
        await setup_client.patch_group(
            id=f"{setup_client.collection_name}-editors", changes=data
        )

    if reviewer_client:
        reviewer_id = (await reviewer_client.server_info())["user"]["id"]
        data = JSONPatch(
            [{"op": "add", "path": "/data/members/0", "value": reviewer_id}]
        )
        await setup_client.patch_group(
            id=f"{setup_client.collection_name}-reviewers", changes=data
        )
