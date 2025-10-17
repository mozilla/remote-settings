import datetime
from unittest.mock import MagicMock, patch

import pytest
import responses
from commands.purge_old_attachments import delete_older_files, purge_old_attachments
from google.cloud.storage import Client


@pytest.fixture
def mock_fetch_all_changesets():
    with patch("commands.purge_old_attachments.fetch_all_changesets") as mock_fetch:
        yield mock_fetch


@pytest.fixture
def mock_storage_client():
    with patch("commands.purge_old_attachments.storage.Client") as mock_client:
        mock_bucket = MagicMock(spec=Client)
        mock_client.return_value.bucket.return_value = mock_bucket
        yield mock_bucket


@pytest.fixture
def mock_environment(monkeypatch):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/path/creds.json")


@pytest.fixture
def mock_delete_older_files():
    with patch(
        "commands.purge_old_attachments.delete_older_files"
    ) as mock_delete_older_files:
        yield mock_delete_older_files


@responses.activate
def test_build_bundles(
    mock_fetch_all_changesets,
    mock_delete_older_files,
):
    ts_2023_01_01 = 1672531200000
    ts_2021_06_01 = 1622505600000
    ts_2024_04_02 = 1711929600000

    mock_fetch_all_changesets.return_value = [
        {
            "changes": [
                {"id": "record1", "last_modified": ts_2023_01_01},
                {"id": "record2", "last_modified": ts_2021_06_01},
            ],
            "metadata": {
                "id": "regions",
                "bucket": "main",
            },
        },
        {
            "changes": [],
            "metadata": {
                "id": "intermediates",
                "bucket": "security-state",
            },
        },
        {
            "changes": [
                {
                    "id": "record3",
                    "last_modified": ts_2024_04_02,
                }
            ],
            "metadata": {
                "id": "addons",
                "bucket": "blocklists",
            },
        },
    ]

    purge_old_attachments(None, None)

    mock_delete_older_files.assert_called_with(
        "remote-settings-test-local-attachments",
        {
            "main-workspace/regions/": datetime.datetime(
                2020, 6, 1, tzinfo=datetime.timezone.utc
            ),
            "staging/addons/": datetime.datetime(
                2023, 4, 2, tzinfo=datetime.timezone.utc
            ),
        },
    )


class MockBlob:
    def __init__(self, name: str, updated: tuple[int, int, int], size: int):
        self.name = name
        self.updated = datetime.datetime(*updated, tzinfo=datetime.timezone.utc)
        self.size = size
        self._deleted = False

    def delete(self):
        self._deleted = True


def test_delete_older_files(
    mock_storage_client,
    capsys,
):
    mock_blobs = [
        MockBlob("folder1/file1.txt", (2020, 1, 1), 1024 * 1024),
        MockBlob("folder1/file2.txt", (2022, 1, 1), 2 * 1024 * 1024),
        MockBlob("folder2/file3.txt", (2019, 6, 1), 512 * 1024),
        MockBlob("folder4/", (2015, 6, 1), 0),
    ]

    def list_blobs(prefix):
        return [blob for blob in mock_blobs if blob.name.startswith(prefix)]

    mock_storage_client.list_blobs.side_effect = list_blobs

    folders = {
        "folder1/": datetime.datetime(2021, 1, 1, tzinfo=datetime.timezone.utc),
        "folder2/": datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc),
        "folder3/": datetime.datetime(2022, 1, 1, tzinfo=datetime.timezone.utc),
    }

    delete_older_files("test-bucket", folders)

    captured = capsys.readouterr()
    assert "Deleting gs://test-bucket/folder1/file1.txt" in captured.out
    assert "Deleting gs://test-bucket/folder2/file3.txt" in captured.out
    assert "Finished folder 'folder1/': 1/2 deleted." in captured.out
    assert "Finished folder 'folder2/': 1/1 deleted." in captured.out
    assert "Finished folder 'folder3/': 0/0 deleted." in captured.out
    assert "Total space freed: 1.50 MB" in captured.out

    assert [b.name for b in mock_blobs if b._deleted] == [
        "folder1/file1.txt",
        "folder2/file3.txt",
    ]
