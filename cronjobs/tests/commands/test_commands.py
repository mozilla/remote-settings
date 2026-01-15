import responses
from commands import KintoClient, fetch_all_changesets


@responses.activate
def test_fetch_all_changesets():
    responses.add(
        responses.GET,
        "http://testserver:9999/v1/",
        json={
            "capabilities": {
                "signer": {
                    "resources": [
                        {
                            "source": {
                                "bucket": "main-workspace",
                            },
                            "preview": {
                                "bucket": "main-preview",
                            },
                            "destination": {
                                "bucket": "main",
                            },
                        }
                    ]
                }
            }
        },
    )
    responses.add(
        responses.GET,
        "http://testserver:9999/v1/buckets/monitor/collections/changes/changeset",
        json={
            "changes": [
                {
                    "id": "a",
                    "bucket": "main",
                    "collection": "search-config",
                    "last_modified": 1620000000000,
                },
                {
                    "id": "b",
                    "bucket": "main-preview",
                    "collection": "search-config",
                    "last_modified": 1620000001000,
                },
            ]
        },
    )

    for i, bucket in enumerate(["main-workspace", "main-preview", "main"]):
        responses.add(
            responses.GET,
            f"http://testserver:9999/v1/buckets/{bucket}/collections/search-config/changeset",
            json={
                "changes": [
                    {"id": f"record-{i}", "last_modified": i},
                ]
            },
        )

    client = KintoClient(
        server_url="http://testserver:9999/v1/",
        auth=("user", "pass"),
    )
    results = fetch_all_changesets(client, with_workspace_buckets=True)

    assert results == [
        {
            "changes": [
                {"id": "record-2", "last_modified": 2},
            ]
        },
        {
            "changes": [
                {"id": "record-1", "last_modified": 1},
            ]
        },
        {
            "changes": [
                {"id": "record-0", "last_modified": 0},
            ]
        },
    ]
