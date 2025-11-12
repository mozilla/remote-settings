from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import responses
from commands.expire_orphan_attachments import expire_orphan_attachments
from google.cloud.storage import Client


@pytest.fixture
def mock_fetch_all_changesets():
    with patch("commands.expire_orphan_attachments.fetch_all_changesets") as mock_fetch:
        yield mock_fetch


@pytest.fixture
def mock_storage_client():
    with patch("commands.expire_orphan_attachments.storage.Client") as mock_client:
        mock_bucket = MagicMock(spec=Client)
        mock_bucket.default_event_based_hold = True
        mock_client.return_value.bucket.return_value = mock_bucket
        yield mock_bucket


@pytest.fixture
def mock_environment(monkeypatch):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/path/creds.json")


@responses.activate
def test_expire_orphan_attachments(mock_fetch_all_changesets, mock_storage_client):
    mock_fetch_all_changesets.return_value = [
        {
            "changes": [
                {
                    "id": "record1",
                    "last_modified": 1672531200000,
                    "attachment": {"location": "folder1/att.bin", "size": 12345},
                }
            ]
        },
        {
            "changes": [
                {
                    "id": "record1",
                    "last_modified": 1672531200000,
                    "attachment": {"location": "folder2/file.txt", "size": 12345},
                }
            ]
        },
        {
            "changes": [
                {
                    "id": "record1",
                    "last_modified": 1672531200000,
                    "attachment": {"location": "folder2/img.png", "size": 12345},
                }
            ]
        },
    ]

    patched_blobs = set()

    class MockBlob:
        def __init__(self, name: str, custom_time: datetime | None = None):
            self.name = name
            self.custom_time = custom_time

        def patch(self):
            patched_blobs.add(self.name)

    mock_storage_client.list_blobs.return_value = [
        MockBlob("folder1/att.bin"),  # referenced
        MockBlob("folder1/orphan1.bin"),  # orphan
        MockBlob("folder2/file.txt"),  # referenced
        MockBlob("folder2/img.png"),  # referenced
        MockBlob("folder2/orphan2.png"),  # orphan
        MockBlob("folder2/already.json", custom_time=datetime.now()),  # already marked
        MockBlob(
            "bundles/startup.mozlz4", custom_time=datetime.now()
        ),  # already marked
    ]

    expire_orphan_attachments(None, None)

    assert patched_blobs == {"folder1/orphan1.bin", "folder2/orphan2.png"}


@responses.activate
def test_expire_orphan_attachments_dry_run(
    mock_fetch_all_changesets, mock_storage_client
):
    from commands import expire_orphan_attachments

    expire_orphan_attachments.DRY_RUN = True

    mock_fetch_all_changesets.return_value = []

    class MockBlob:
        def __init__(self, name: str):
            self.name = name
            self.custom_time = None

        def patch(self):
            raise ValueError("Should not call patch in dry run mode")

    mock_storage_client.list_blobs.return_value = [
        MockBlob("folder1/orphan.bin"),
    ]

    expire_orphan_attachments.expire_orphan_attachments(None, None)
