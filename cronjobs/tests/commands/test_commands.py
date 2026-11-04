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


@responses.activate
def test_kinto_client_retries_on_chunked_encoding_error():
    import requests

    responses.add(
        responses.GET,
        "http://testserver:9999/v1/buckets/monitor/collections/changes/changeset",
        body=requests.exceptions.ChunkedEncodingError(
            "Connection broken: ConnectionResetError(104)"
        ),
    )
    responses.add(
        responses.GET,
        "http://testserver:9999/v1/buckets/monitor/collections/changes/changeset",
        json={"changes": []},
    )

    client = KintoClient(
        server_url="http://testserver:9999/v1/",
        auth=("user", "pass"),
    )
    result = client.get_changeset("monitor", "changes")
    assert result == {"changes": []}
    assert len(responses.calls) == 2


@responses.activate
def test_kinto_client_retries_on_transient_502():
    responses.add(
        responses.GET,
        "http://testserver:9999/v1/buckets/monitor/collections/changes/changeset",
        status=502,
        body="Bad Gateway",
    )
    responses.add(
        responses.GET,
        "http://testserver:9999/v1/buckets/monitor/collections/changes/changeset",
        json={"changes": []},
    )

    client = KintoClient(
        server_url="http://testserver:9999/v1/",
        auth=("user", "pass"),
    )
    result = client.get_changeset("monitor", "changes")
    assert result == {"changes": []}
    assert len(responses.calls) == 2


@responses.activate
def test_kinto_client_gives_up_on_client_error_404():
    import kinto_http.exceptions
    import pytest

    responses.add(
        responses.GET,
        "http://testserver:9999/v1/buckets/monitor/collections/changes/changeset",
        status=404,
        body="Not Found",
    )

    client = KintoClient(
        server_url="http://testserver:9999/v1/",
        auth=("user", "pass"),
    )
    with pytest.raises(kinto_http.exceptions.KintoException):
        client.get_changeset("monitor", "changes")

    assert len(responses.calls) == 1
