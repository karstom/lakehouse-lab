#!/usr/bin/env python3
"""A1 checkpoint: your table lakehouse.dbt_<you>.a1_segment_revenue_1996 holds the right answer.

Checks the OUTCOME (the table and its rows, read through Trino as you), not your SQL: any
query that produces the right table passes. The expected rows are computed from
lakehouse.samples at check time, not stored here.

  python3 checkpoint.py [--json]    check        python3 checkpoint.py --reset    start over
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_shared"))
import trackkit as tk  # noqa: E402

TABLE = "a1_segment_revenue_1996"
COLUMNS = ["market_segment", "orders", "total_price"]
REFERENCE = """
SELECT c.mktsegment, count(*), round(sum(o.totalprice), 2)
FROM lakehouse.samples.orders o
JOIN lakehouse.samples.customer c ON o.custkey = c.custkey
WHERE o.orderdate >= DATE '1996-01-01' AND o.orderdate < DATE '1997-01-01'
GROUP BY c.mktsegment
"""


def checks(ck):
    schema = tk.user_schema()
    fq = f"lakehouse.{schema}.{TABLE}"
    if not ck.check(f"your schema lakehouse.{schema} exists", tk.schema_exists(schema),
                    f"there is no schema {schema}",
                    f"run: CREATE SCHEMA IF NOT EXISTS lakehouse.{schema}"):
        return
    kind = tk.table_type(schema, TABLE)
    if not ck.check(f"table {fq} exists", kind is not None, f"no table named {TABLE} in {schema}",
                    "run step 6 (CREATE OR REPLACE TABLE ... AS SELECT). Check the spelling "
                    f"of the name: {TABLE}"):
        return
    cols = [c for c, _ in tk.columns(schema, TABLE)]
    if not ck.check(f"it has the columns {', '.join(COLUMNS)}", cols == COLUMNS,
                    f"found columns: {', '.join(cols) or '(none)'}",
                    "name the columns with AS, in this order: "
                    "c.mktsegment AS market_segment, count(*) AS orders, "
                    "round(sum(o.totalprice), 2) AS total_price"):
        return
    _, got = tk.query(f"SELECT market_segment, orders, total_price FROM {fq}")
    _, want = tk.query(REFERENCE)
    want = {r[0]: (r[1], r[2]) for r in want}
    ck.check("one row per market segment (5 rows)",
             len(got) == len(want) and {r[0] for r in got} == set(want),
             f"found {len(got)} rows: {sorted(str(r[0]) for r in got)[:8]}",
             "GROUP BY c.mktsegment, and join orders to customers so every order has a segment")
    wrong_orders = [r[0] for r in got if r[0] in want and r[1] != want[r[0]][0]]
    if not ck.check("the order counts are the 1996 order counts", not wrong_orders,
                    f"counts differ for {', '.join(map(str, wrong_orders))}",
                    "keep only 1996: WHERE o.orderdate >= DATE '1996-01-01' AND "
                    "o.orderdate < DATE '1997-01-01', and join ON o.custkey = c.custkey"):
        return
    wrong_price = [r[0] for r in got if r[0] in want and not tk.close_enough(r[2], want[r[0]][1])]
    ck.check("the totals are the sum of totalprice", not wrong_price,
             f"totals differ for {', '.join(map(str, wrong_price))}",
             "total_price = round(sum(o.totalprice), 2)")


def reset():
    return [tk.drop_own(TABLE)]


if __name__ == "__main__":
    sys.exit(tk.Checkpoint("A1", "SQL basics").run(checks, reset))
