#!/usr/bin/env python3
"""Reference solution for A2 (test-only; never copied into homes). Runs inside the user's
workspace, as the user: explores with DuckDB (step 6, the vended-credential ATTACH), then
publishes the same query through Trino (step 7), and checks both engines agree.

  python solve.py [<module dir>]
"""
import lakehouse

SELECT = """
SELECT shipmode                                                        AS ship_mode,
       count(*)                                                        AS line_items,
       count(*) FILTER (WHERE receiptdate > commitdate)                AS late_items,
       round(100.0 * count(*) FILTER (WHERE receiptdate > commitdate)
             / count(*), 1)                                            AS late_pct
FROM lakehouse.samples.lineitem
GROUP BY shipmode
"""


def main():
    duck = lakehouse.duckdb_connect()
    explored = sorted(duck.sql(SELECT).fetchall())
    schema = f"dbt_{lakehouse.whoami().lower()}"
    cur = lakehouse.trino_connection().cursor()
    for sql in (f"CREATE SCHEMA IF NOT EXISTS lakehouse.{schema}",
                f"CREATE OR REPLACE TABLE lakehouse.{schema}.a2_late_by_shipmode AS {SELECT}"):
        cur.execute(sql)
        cur.fetchall()
    cur.execute(f"SELECT * FROM lakehouse.{schema}.a2_late_by_shipmode")
    published = sorted(cur.fetchall())
    for a, b in zip(explored, published):
        print(a, b)
    assert [r[:3] for r in explored] == [tuple(r[:3]) for r in published], "engines disagree"


if __name__ == "__main__":
    main()
