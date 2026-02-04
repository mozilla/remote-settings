import time

import pytest
import requests


SERVER_URL = "https://firefox.settings.services.mozilla.com"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:136.0) Gecko/20100101 Firefox/136.0"
NOW_EPOCH_MS = int(time.time() * 1000)
OLD_EPOCH_MS = NOW_EPOCH_MS - 30 * 86400 * 1000  # 30 days ago


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("/", 307),
        ("/v1", 307),
        ("/v1/", 200),
        ("/v2", 307),
        ("/v2/", 200),
        ("/v1/boo", 406),
        ("/v1/cert-chains", 406),
        ("/v1/buckets", 200),
        ("/v1/buckets/main", 200),
        ("/v1/buckets/main/collections", 200),
        ("/v1/buckets/main/collections/regions", 200),
        ("/v1/buckets/main/collections/regions/records", 200),
        ("/v1/buckets/main/collections/regions/changeset", 400),
        ("/v1/buckets/main/collections/regions/changeset?_expected=0", 200),
        ("/v1/buckets/main/collections/regions/changeset?_expected=0&_since=0", 200),
        (
            f"/v1/buckets/main/collections/regions/changeset?_expected={NOW_EPOCH_MS}",
            200,
        ),
        (
            f'/v1/buckets/main/collections/regions/changeset?_expected="{NOW_EPOCH_MS}"',
            200,
        ),
        (
            f'/v1/buckets/main/collections/regions/changeset?_expected={NOW_EPOCH_MS}&_since="123"',
            200,
        ),
        (
            f"/v1/buckets/main/collections/regions/changeset?_expected={NOW_EPOCH_MS}&_since=123",
            200,
        ),
        (
            f'/v1/buckets/main/collections/regions/changeset?_expected="{NOW_EPOCH_MS}"&_since="123"',
            200,
        ),
        (
            f'/v1/buckets/main/collections/regions/changeset?_expected="{NOW_EPOCH_MS}"&_since=123',
            200,
        ),
        (
            '/v1/buckets/main/collections/regions/changeset?_expected="abc"',
            200,
        ),  # TODO: should be 400
        (
            f'/v1/buckets/main/collections/regions/changeset?_expected="{OLD_EPOCH_MS}"',
            200,
        ),
        ("/v1/buckets/monitor/collections/changes/records", 406),
        ("/v1/buckets/monitor/collections/changes/changeset", 400),
        ("/v1/buckets/monitor/collections/changes/changeset?_expected=abc", 400),
        ("/v1/buckets/monitor/collections/changes/changeset?_expected=0", 200),
        (
            f"/v1/buckets/monitor/collections/changes/changeset?_expected={NOW_EPOCH_MS}",
            200,
        ),
        (
            f'/v1/buckets/monitor/collections/changes/changeset?_expected="{NOW_EPOCH_MS}"',
            200,
        ),
        (
            f'/v1/buckets/monitor/collections/changes/changeset?_expected="{NOW_EPOCH_MS}"&_since="{OLD_EPOCH_MS}"',
            307,
        ),
        (
            f'/v1/buckets/monitor/collections/changes/changeset?_expected={NOW_EPOCH_MS}&_since="{NOW_EPOCH_MS}"',
            200,
        ),
        (
            f"/v1/buckets/monitor/collections/changes/changeset?_expected={NOW_EPOCH_MS}&_since={NOW_EPOCH_MS}",
            200,
        ),
        (
            f'/v1/buckets/monitor/collections/changes/changeset?_expected="{NOW_EPOCH_MS}"&_since="{NOW_EPOCH_MS}"',
            200,
        ),
        (
            f'/v1/buckets/monitor/collections/changes/changeset?_expected="{NOW_EPOCH_MS}"&_since={NOW_EPOCH_MS}',
            200,
        ),
        ("/v2/boo", 406),
        ("/v2/buckets", 404),
        ("/v2/buckets/main", 404),
        ("/v2/buckets/main/collections", 404),
        ("/v2/buckets/main/collections/regions", 404),
        ("/v2/buckets/main/collections/regions/records", 404),
        (
            "/v2/buckets/main/collections/regions/changeset",
            400,
        ),
        ("/v2/buckets/main/collections/regions/changeset?_expected=0", 200),
        (
            f'/v2/buckets/main/collections/regions/changeset?_expected="{NOW_EPOCH_MS}"',
            422,
        ),
        (
            f"/v2/buckets/main/collections/regions/changeset?_expected={NOW_EPOCH_MS}",
            200,
        ),
        (
            f'/v2/buckets/monitor/collections/changes/changeset?_expected="{NOW_EPOCH_MS}"',
            422,
        ),
        (
            f"/v2/buckets/monitor/collections/changes/changeset?_expected={NOW_EPOCH_MS}",
            200,
        ),
        (
            f'/v2/buckets/monitor/collections/changes/changeset?_expected={NOW_EPOCH_MS}&_since="{OLD_EPOCH_MS}"',
            422,
        ),
        (
            f"/v2/buckets/monitor/collections/changes/changeset?_expected={NOW_EPOCH_MS}&_since={OLD_EPOCH_MS}",
            200,
        ),
    ],
)
def test_fastly_vcl_responses(url, expected):
    url = f"{SERVER_URL}{url}"
    resp = requests.head(url, headers={"User-Agent": USER_AGENT}, allow_redirects=False)
    assert resp.status_code == expected, (
        url + f" returned {resp.status_code}, expected {expected}"
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
