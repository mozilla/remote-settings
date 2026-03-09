import time

import pytest
import requests


SERVER_URL = "https://firefox.settings.services.mozilla.com"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:136.0) Gecko/20100101 Firefox/136.0"
NOW_EPOCH_MS = int(time.time() * 1000)
OLD_EPOCH_MS = NOW_EPOCH_MS - 30 * 86400 * 1000  # 30 days ago

print(f"Testing {SERVER_URL} with User-Agent: {USER_AGENT}")
print("Current time (epoch ms):", NOW_EPOCH_MS)
print("Old time (epoch ms):", OLD_EPOCH_MS)


@pytest.mark.parametrize(
    ("url", "expected", "message"),
    [
        ("/", 307, "Root URL redirects to /v1/"),
        ("/v1", 307, "Trailing slash is required for /v1/"),
        ("/v1/", 200, "Base API URL should be accessible"),
        ("/v2", 307, "Trailing slash is required for /v2/"),
        ("/v2/", 200, "Base API URL should be accessible"),
        ("/v1/boo", 406, "Unknown endpoint should return 406"),
        ("/v1/cert-chains", 406, "Unknown endpoint should return 406"),
        ("/v1/buckets", 200, "Buckets list"),
        ("/v1/buckets/main", 200, "Main bucket"),
        ("/v1/buckets/main/collections", 200, "Collections list"),
        ("/v1/buckets/main/collections/regions", 200, "Collection metadata"),
        ("/v1/buckets/main/collections/regions/records", 200, "Collection records"),
        (
            "/v1/buckets/main/collections/regions/changeset",
            400,
            "Missing _expected should return 400",
        ),
        (
            "/v1/buckets/main/collections/regions/changeset?_expected=0",
            200,
            "Changeset with expected=0",
        ),
        (
            "/v1/buckets/main/collections/regions/changeset?_expected=0&_since=0",
            200,
            "Changeset with expected=0 and since=0",
        ),
        (
            f"/v1/buckets/main/collections/regions/changeset?_expected={NOW_EPOCH_MS}",
            200,
            "Changeset with current timestamp as _expected should return 200",
        ),
        (
            f'/v1/buckets/main/collections/regions/changeset?_expected="{NOW_EPOCH_MS}"',
            200,
            "Changeset with current timestamp as _expected (quoted) should return 200",
        ),
        (
            f'/v1/buckets/main/collections/regions/changeset?_expected={NOW_EPOCH_MS}&_since="123"',
            200,
            "Changeset with current timestamp as _expected and quoted _since should return 200",
        ),
        (
            f"/v1/buckets/main/collections/regions/changeset?_expected={NOW_EPOCH_MS}&_since=123",
            200,
            "Changeset with current timestamp as _expected and unquoted _since should return 200",
        ),
        (
            f'/v1/buckets/main/collections/regions/changeset?_expected="{NOW_EPOCH_MS}"&_since="123"',
            200,
            "Changeset with current timestamp as quoted _expected and quoted _since should return 200",
        ),
        (
            f'/v1/buckets/main/collections/regions/changeset?_expected="{NOW_EPOCH_MS}"&_since=123',
            200,
            "Changeset with current timestamp as quoted _expected and unquoted _since should return 200",
        ),
        (
            '/v1/buckets/main/collections/regions/changeset?_expected="abc"',
            200,
            "TODO: should be 400",
        ),
        (
            f'/v1/buckets/main/collections/regions/changeset?_expected="{OLD_EPOCH_MS}"',
            200,
            "Changeset with old timestamp as quoted _expected should return 307",
        ),
        (
            "/v1/buckets/monitor/collections/changes/records",
            406,
            "Decommissioned monitor/changes records",
        ),
        (
            "/v1/buckets/monitor/collections/changes/changeset",
            400,
            "Missing _expected should return 400 for monitor/changes changeset",
        ),
        (
            "/v1/buckets/monitor/collections/changes/changeset?_expected=abc",
            400,
            "Non-numeric _expected should return 400 for monitor/changes changeset",
        ),
        (
            "/v1/buckets/monitor/collections/changes/changeset?_expected=0",
            200,
            "Changeset with expected=0 should return 200 for monitor/changes changeset",
        ),
        (
            f"/v1/buckets/monitor/collections/changes/changeset?_expected={NOW_EPOCH_MS}",
            200,
            "Changeset with current timestamp as _expected should return 200 for monitor/changes changeset",
        ),
        (
            f'/v1/buckets/monitor/collections/changes/changeset?_expected="{NOW_EPOCH_MS}"',
            200,
            "Changeset with current timestamp as quoted _expected should return 200 for monitor/changes changeset",
        ),
        (
            f'/v1/buckets/monitor/collections/changes/changeset?_expected="{NOW_EPOCH_MS}"&_since="{OLD_EPOCH_MS}"',
            307,
            "Changeset with current timestamp as quoted _expected and old timestamp as quoted _since should return 307 for monitor/changes changeset",
        ),
        (
            f'/v1/buckets/monitor/collections/changes/changeset?_expected={NOW_EPOCH_MS}&_since="{NOW_EPOCH_MS}"',
            200,
            "Changeset with current timestamp as _expected and quoted current timestamp as _since should return 200 for monitor/changes changeset",
        ),
        (
            f"/v1/buckets/monitor/collections/changes/changeset?_expected={NOW_EPOCH_MS}&_since={NOW_EPOCH_MS}",
            200,
            "Changeset with current timestamp as _expected and current timestamp as _since should return 200 for monitor/changes changeset",
        ),
        (
            f'/v1/buckets/monitor/collections/changes/changeset?_expected="{NOW_EPOCH_MS}"&_since="{NOW_EPOCH_MS}"',
            200,
            "Changeset with current timestamp as quoted _expected and quoted current timestamp as _since should return 200 for monitor/changes changeset",
        ),
        (
            f'/v1/buckets/monitor/collections/changes/changeset?_expected="{NOW_EPOCH_MS}"&_since={NOW_EPOCH_MS}',
            200,
            "Changeset with current timestamp as quoted _expected and current timestamp as _since should return 200 for monitor/changes changeset",
        ),
        ("/v2/boo", 406, "Unknown endpoint should return 406"),
        ("/v2/buckets", 404, "Buckets endpoint should return 404 in v2"),
        ("/v2/buckets/main", 404, "Main bucket should return 404 in v2"),
        (
            "/v2/buckets/main/collections",
            404,
            "Collections endpoint should return 404 in v2",
        ),
        (
            "/v2/buckets/main/collections/regions",
            404,
            "Collection metadata endpoint should return 404 in v2",
        ),
        (
            "/v2/buckets/main/collections/regions/records",
            404,
            "Records endpoint should return 404 in v2",
        ),
        (
            "/v2/buckets/main/collections/regions/changeset",
            400,
            "Missing _expected should return 400 for v2 changeset",
        ),
        (
            "/v2/buckets/main/collections/regions/changeset?_expected=0",
            200,
            "Changeset with expected=0 should return 200 for v2 changeset",
        ),
        (
            f'/v2/buckets/main/collections/regions/changeset?_expected="{NOW_EPOCH_MS}"',
            422,
            "Quoted _expected should return 422 for v2 changeset",
        ),
        (
            f"/v2/buckets/main/collections/regions/changeset?_expected={NOW_EPOCH_MS}",
            200,
            "Unquoted _expected should return 200 for v2 changeset",
        ),
        (
            f'/v2/buckets/monitor/collections/changes/changeset?_expected="{NOW_EPOCH_MS}"',
            422,
            "Quoted _expected should return 422 for monitor/changes changeset in v2",
        ),
        (
            f"/v2/buckets/monitor/collections/changes/changeset?_expected={NOW_EPOCH_MS}",
            200,
            "Unquoted _expected should return 200 for monitor/changes changeset in v2",
        ),
        (
            f'/v2/buckets/monitor/collections/changes/changeset?_expected={NOW_EPOCH_MS}&_since="{OLD_EPOCH_MS}"',
            422,
            "Quoted _since should return 422 for monitor/changes changeset in v2",
        ),
        (
            f"/v2/buckets/monitor/collections/changes/changeset?_expected={NOW_EPOCH_MS}&_since={OLD_EPOCH_MS}",
            200,
            "Unquoted _since should return 200 for monitor/changes changeset in v2",
        ),
    ],
)
def test_fastly_vcl_responses(url, expected, message):
    url = f"{SERVER_URL}{url}"
    resp = requests.head(url, headers={"User-Agent": USER_AGENT}, allow_redirects=False)
    assert resp.status_code == expected, (
        message
        + "\n"
        + url
        + f" returned {resp.status_code}, expected {expected} (Location: {resp.headers.get('Location', '')})"
    )


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_relative_urls(version):
    server_info = requests.get(
        f"{SERVER_URL}/{version}/", headers={"User-Agent": USER_AGENT}
    ).json()

    regions_url = (
        f"{SERVER_URL}/{version}/buckets/main/collections/regions/changeset?_expected=0"
    )
    regions = requests.get(regions_url, headers={"User-Agent": USER_AGENT}).json()

    cert_url = regions["metadata"]["signatures"][0]["x5u"]
    assert (
        requests.head(cert_url, headers={"User-Agent": USER_AGENT}).status_code == 200
    )

    attachments_base_url = server_info["capabilities"]["attachments"]["base_url"]
    region_url = regions["changes"][0]["attachment"]["location"]
    assert (
        requests.head(
            f"{attachments_base_url}{region_url}", headers={"User-Agent": USER_AGENT}
        ).status_code
        == 200
    )
