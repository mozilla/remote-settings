import json

from kinto_remote_settings.signer.serializer import canonical_json

#
# Kinto specific
#


def test_supports_records_as_iterators():
    records = iter([{"bar": "baz", "last_modified": "45678", "id": "1"}])
    canonical_json(records, "45678")


def test_provides_records_in_data_along_last_modified():
    records = [{"bar": "baz", "last_modified": "45678", "id": "1"}]
    serialized = json.loads(canonical_json(records, "45678"))
    assert "data" in serialized
    assert "last_modified" in serialized


def test_orders_records_by_id():
    records = [
        {"bar": "baz", "last_modified": "45678", "id": "2"},
        {"foo": "bar", "last_modified": "12345", "id": "1"},
    ]
    serialized = json.loads(canonical_json(records, "45678"))
    assert serialized["last_modified"] == "45678"
    assert serialized["data"][0]["id"] == "1"
    assert serialized["data"][1]["id"] == "2"


def test_removes_deleted_items():
    record = {"bar": "baz", "last_modified": "45678", "id": "2"}
    deleted_record = {"deleted": True, "last_modified": "12345", "id": "1"}
    records = [deleted_record, record]
    serialized = canonical_json(records, "42")
    assert [record] == json.loads(serialized)["data"]


#
# Standard
#


def test_does_not_alter_records():
    records = [
        {"foo": "bar", "last_modified": "12345", "id": "1"},
        {"bar": "baz", "last_modified": "45678", "id": "2"},
    ]
    canonical_json(records, "45678")

    assert records == [
        {"foo": "bar", "last_modified": "12345", "id": "1"},
        {"bar": "baz", "last_modified": "45678", "id": "2"},
    ]


def test_preserves_data():
    records = [
        {"foo": "bar", "last_modified": "12345", "id": "1"},
        {"bar": "baz", "last_modified": "45678", "id": "2"},
    ]
    serialized = canonical_json(records, "45678")
    assert records == json.loads(serialized)["data"]
