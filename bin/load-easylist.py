import os

import psycopg2
from psycopg2.extras import Json


with open("easylist.txt") as f:
    rules = [line.strip() for line in f if line.strip()]

conn = psycopg2.connect(os.getenv("DSN"))

with conn:
    with conn.cursor() as cur:
        for rule in rules:
            cur.execute(
                """
                INSERT INTO objects(resource_name, parent_id, id, data)
                VALUES (%s, %s, gen_random_uuid(), %s)
                """,
                (
                    "record",
                    "/buckets/main-workspace/collections/easylist",
                    Json({"rule": rule}),
                ),
            )
