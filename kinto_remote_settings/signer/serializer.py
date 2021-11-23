import operator

import canonicaljson


def canonical_json(records, last_modified):
    records = (r for r in records if not r.get("deleted", False))
    records = sorted(records, key=operator.itemgetter("id"))

    payload = {"data": records, "last_modified": "%s" % last_modified}

    dump = canonicaljson.dumps(payload)

    return dump
