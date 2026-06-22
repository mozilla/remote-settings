import operator
from typing import Iterable

import canonicaljson


def canonical_json(records: Iterable[dict], last_modified: int) -> str:
    records = (r for r in records if not r.get("deleted", False))
    records = sorted(records, key=operator.itemgetter("id"))

    payload = {"data": records, "last_modified": "%s" % last_modified}

    dump = canonicaljson.dumps(payload)  # ty: ignore[unresolved-attribute]

    return dump
