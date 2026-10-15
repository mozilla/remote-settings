import operator
from typing import Iterable

import canonicaljson


def canonical_json(
    records: Iterable[dict], last_modified: int, collection: str | None = None
) -> str:
    records = (r for r in records if not r.get("deleted", False))
    records = sorted(records, key=operator.itemgetter("id"))

    payload = {"data": records, "last_modified": "%s" % last_modified}
    if collection is not None:
        payload["collection"] = collection

    dump = canonicaljson.dumps(payload)  # ty: ignore[unresolved-attribute]

    return dump
