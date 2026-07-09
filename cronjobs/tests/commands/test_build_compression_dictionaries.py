from compression.zstd import ZstdDecompressor, ZstdDict
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest
from commands.build_compression_dictionaries import (
    DictPair,
    build_compression_dictionaries,
    compressed_filename,
    find_missing_compressed_files,
    records_to_compress,
    scan_existing_attachments,
    zstd_compress,
)
from google.cloud import storage


@pytest.fixture
def mock_fetch_all_changesets():
    with patch(
        "commands.build_compression_dictionaries.fetch_all_changesets"
    ) as mock_fetch:
        yield mock_fetch


@pytest.fixture
def mock_blob():
    with patch("commands.build_compression_dictionaries.storage.Blob") as mock_blob:
        yield mock_blob


@pytest.fixture
def mock_storage_bucket():
    with patch("commands.build_compression_dictionaries.storage.Client") as mock_client:
        mock_bucket = MagicMock()
        mock_client.return_value.bucket.return_value = mock_bucket
        yield mock_bucket


@pytest.fixture
def mock_kinto_client():
    with patch("commands.build_compression_dictionaries.KintoClient") as mock_client:
        yield mock_client


@pytest.fixture
def mock_environment(monkeypatch):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/path/creds.json")


def test_records_to_compress():
    changesets = [
        {
            "metadata": {"bucket": "bid", "id": "no-flags", "flags": []},
            "changes": [
                {
                    "id": "abc",
                    "attachment": {},
                }
            ],
        },
        {
            "metadata": {
                "bucket": "bid",
                "id": "no-records",
                "flags": ["compression-dictionaries"],
            },
            "changes": [],
        },
        {
            "metadata": {
                "bucket": "bid",
                "id": "no-attachments",
                "flags": ["compression-dictionaries"],
            },
            "changes": [{"id": "abc"}],
        },
        {
            "metadata": {
                "bucket": "bid",
                "id": "cid",
                "flags": ["compression-dictionaries"],
            },
            "changes": [{"id": "rid", "attachment": {"mimetype": "plain/text"}}],
        },
    ]
    to_compress = records_to_compress(changesets)

    assert to_compress == [("bid", "cid", {"rid": "plain/text"})]


def test_scan_existing_attachments():
    fake_bucket = mock.MagicMock(spec=storage.Bucket)
    fake_bucket.list_blobs.return_value = [
        storage.Blob(bucket=fake_bucket, name="bid/cid/some-file.txt"),
        storage.Blob(bucket=fake_bucket, name="bid/cid/20260601--rid1--file1.txt"),
        storage.Blob(bucket=fake_bucket, name="bid/cid/20260401--rid1--file2.txt"),
        storage.Blob(bucket=fake_bucket, name="bid/cid/20260201--rid1--file3.txt"),
        storage.Blob(bucket=fake_bucket, name="bid/cid/20260201--rid2--file1.txt"),
        storage.Blob(bucket=fake_bucket, name="bid/cid/20260201--rid2--file2.txt"),
        storage.Blob(
            bucket=fake_bucket, name="bid/cid/20260630--deleted-rid--file.txt"
        ),
    ]

    attachments = scan_existing_attachments(
        fake_bucket,
        [
            ("bid", "cid", {"rid1": "text/plain", "rid2": "plain/text"}),
        ],
    )

    assert list(attachments) == [
        (
            "bid",
            "cid",
            [
                "bid/cid/20260601--rid1--file1.txt",
                "bid/cid/20260401--rid1--file2.txt",
                "bid/cid/20260201--rid1--file3.txt",
            ],
            "text/plain",
        ),
        (
            "bid",
            "cid",
            ["bid/cid/20260201--rid2--file1.txt", "bid/cid/20260201--rid2--file2.txt"],
            "plain/text",
        ),
    ]

    fake_bucket.list_blobs.assert_called_with(prefix="bid/cid/")


def test_find_missing_compressed_files(mock_blob):
    fake_client = mock.MagicMock(spec=storage.Client)
    fake_bucket = mock.MagicMock(spec=storage.Bucket)

    mock_blob.return_value.exists.side_effect = [True, False]

    missing = find_missing_compressed_files(
        fake_client,
        fake_bucket,
        [
            DictPair(
                "bid",
                "cid",
                "bid/cid/20260401--rid1--file2.txt",
                "bid/cid/20260601--rid1--file1.txt",
                "plain/text",
            ),
            DictPair(
                "bid",
                "cid",
                "bid/cid/20260201--rid1--file2.txt",
                "bid/cid/20260601--rid1--file1.txt",
                "plain/text",
            ),
        ],
    )

    assert missing == [
        DictPair(
            "bid",
            "cid",
            "bid/cid/20260201--rid1--file2.txt",
            "bid/cid/20260601--rid1--file1.txt",
            "plain/text",
        )
    ]


def test_compressed_filename():
    # `new` is the file being compressed (target), `old` is the dictionary it
    # is compressed against (from).
    filename = compressed_filename(
        DictPair(
            "bid",
            "cid",
            "bid/cid/20260201--rid1--file2.txt",
            "bid/cid/20260601--rid1--file1.txt",
            "plain/text",
        )
    )
    assert (
        filename
        == "cdt/bid/cid/compressed/target-20260601--rid1--file1/dcz/from-20260201--rid1--file2.dcz"
    )


def test_zstd_compress(tmp_path):
    dict_content = b"the quick brown fox jumps over the lazy dog\n" * 50
    file_content = b"the quick brown fox jumps over the lazy dog\n" * 200

    dict_path = tmp_path / "dictionary.txt"
    dict_path.write_bytes(dict_content)
    file_path = tmp_path / "attachment.txt"
    file_path.write_bytes(file_content)

    destination_path = tmp_path / "compressed.dcz"
    with open(destination_path, "wb") as destination:
        zstd_compress(dict_path, file_path, destination)

    compressed = destination_path.read_bytes()
    assert 0 < len(compressed) < len(file_content)

    zdict = ZstdDict(dict_content, is_raw=True)
    decompressed = ZstdDecompressor(zstd_dict=zdict).decompress(compressed)
    assert decompressed == file_content


def _blob_with_name(name):
    blob = mock.Mock()
    blob.name = name
    return blob


def test_build_compression_dictionaries(
    mock_kinto_client, mock_fetch_all_changesets, mock_storage_bucket, mock_blob
):
    # One enabled collection with a record that has two attachment versions.
    mock_fetch_all_changesets.return_value = [
        {
            "metadata": {
                "bucket": "bid",
                "id": "cid",
                "flags": ["compression-dictionaries"],
            },
            "changes": [{"id": "rid1", "attachment": {"mimetype": "plain/text"}}],
        },
    ]
    mock_storage_bucket.list_blobs.return_value = [
        _blob_with_name("bid/cid/20260101--rid1--file.txt"),
        _blob_with_name("bid/cid/20260601--rid1--file.txt"),
    ]
    # The compressed file does not exist yet, so it must be built.
    mock_blob.return_value.exists.return_value = False
    # Downloads write some compressible content to the destination file.
    mock_blob.return_value.download_to_file.side_effect = lambda fd, client: fd.write(
        b"the quick brown fox\n" * 100
    )

    build_compression_dictionaries()

    mock_blob.assert_any_call(
        bucket=mock_storage_bucket,
        name="cdt/bid/cid/compressed/target-20260601--rid1--file/dcz/from-20260101--rid1--file.dcz",
    )
    # The compressed file is stored with the original attachment's mime type.
    mock_blob.return_value.upload_from_file.assert_called_once_with(
        mock.ANY,
        content_type="plain/text",
        client=mock.ANY,
    )


def test_build_compression_dictionaries_up_to_date(
    mock_kinto_client, mock_fetch_all_changesets, mock_storage_bucket, mock_blob
):
    mock_fetch_all_changesets.return_value = [
        {
            "metadata": {
                "bucket": "bid",
                "id": "cid",
                "flags": ["compression-dictionaries"],
            },
            "changes": [{"id": "rid1", "attachment": {}}],
        },
    ]
    mock_storage_bucket.list_blobs.return_value = [
        _blob_with_name("bid/cid/20260101--rid1--file.txt"),
        _blob_with_name("bid/cid/20260601--rid1--file.txt"),
    ]
    # Every compressed file already exists: nothing to build or upload.
    mock_blob.return_value.exists.return_value = True

    build_compression_dictionaries()

    mock_blob.return_value.download_to_file.assert_not_called()
    mock_blob.return_value.upload_from_file.assert_not_called()
