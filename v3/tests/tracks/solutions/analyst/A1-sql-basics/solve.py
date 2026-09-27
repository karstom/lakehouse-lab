#!/usr/bin/env python3
"""Reference solution for A1 (test-only; never copied into homes). Runs inside the user's
workspace, as the user: the same statements a learner runs in step 6 of the lesson."""
import lakehouse

schema = f"dbt_{lakehouse.whoami()}"
cur = lakehouse.trino_connection().cursor()
for sql in (
    f"CREATE SCHEMA IF NOT EXISTS lakehouse.{schema}",
    f"""CREATE OR REPLACE TABLE lakehouse.{schema}.a1_segment_revenue_1996 AS
        SELECT
            c.mktsegment                 AS market_segment,
            count(*)                     AS orders,
            round(sum(o.totalprice), 2)  AS total_price
        FROM lakehouse.samples.orders o
        JOIN lakehouse.samples.customer c ON o.custkey = c.custkey
        WHERE o.orderdate >= DATE '1996-01-01' AND o.orderdate < DATE '1997-01-01'
        GROUP BY c.mktsegment""",
):
    cur.execute(sql)
    cur.fetchall()
cur.execute(f"SELECT * FROM lakehouse.{schema}.a1_segment_revenue_1996 ORDER BY total_price DESC")
for row in cur.fetchall():
    print(row)
