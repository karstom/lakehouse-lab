#!/usr/bin/env python3
"""A2 checkpoint: your table lakehouse.dbt_<you>.a2_late_by_shipmode holds the right answer.

Checks the OUTCOME (the published table and its rows, read through Trino as you), not your
notebook: any query that produces the right table passes. The expected numbers are computed
from lakehouse.samples at check time, not stored here.

  python3 checkpoint.py [--json]    check        python3 checkpoint.py --reset    start over
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_shared"))
import trackkit as tk  # noqa: E402

TABLE = "a2_late_by_shipmode"
COLUMNS = ["ship_mode", "line_items", "late_items", "late_pct"]
REFERENCE = """
SELECT shipmode, count(*), count(*) FILTER (WHERE receiptdate > commitdate),
       100.0 * count(*) FILTER (WHERE receiptdate > commitdate) / count(*)
FROM lakehouse.samples.lineitem
GROUP BY shipmode
"""


def checks(ck):
    schema = tk.user_schema()
    fq = f"lakehouse.{schema}.{TABLE}"
    if not ck.check(f"your schema lakehouse.{schema} exists", tk.schema_exists(schema),
                    f"there is no schema {schema}",
                    f"step 7: run CREATE SCHEMA IF NOT EXISTS lakehouse.{schema} (the %%sql trino cell)"):
        return
    if not ck.check(f"table {fq} exists", tk.table_type(schema, TABLE) is not None,
                    f"no table named {TABLE} in {schema}",
                    "step 7: publish your step-6 query with CREATE OR REPLACE TABLE ... AS "
                    f"SELECT, in a %%sql trino cell. Check the name: {TABLE}"):
        return
    cols = [c for c, _ in tk.columns(schema, TABLE)]
    if not ck.check(f"it has the columns {', '.join(COLUMNS)}", cols == COLUMNS,
                    f"found columns: {', '.join(cols) or '(none)'}",
                    "keep the names (AS ship_mode, AS line_items, AS late_items, AS late_pct) "
                    "and their order from step 6"):
        return
    _, got = tk.query(f"SELECT ship_mode, line_items, late_items, late_pct FROM {fq}")
    _, want = tk.query(REFERENCE)
    want = {r[0]: r[1:] for r in want}
    if not ck.check(f"one row per shipping mode ({len(want)} rows)",
                    len(got) == len(want) and {r[0] for r in got} == set(want),
                    f"found {len(got)} rows: {sorted(str(r[0]) for r in got)[:8]}",
                    "GROUP BY shipmode, over the whole table (no WHERE)"):
        return
    wrong = [r[0] for r in got if (r[1], r[2]) != tuple(want[r[0]][:2])]
    if not ck.check("line_items and late_items are right", not wrong,
                    f"counts differ for {', '.join(wrong)}",
                    "line_items = count(*); late means receiptdate > commitdate (strictly later): "
                    "count(*) FILTER (WHERE receiptdate > commitdate)"):
        return
    bad_pct = [r[0] for r in got
               if r[3] is None or abs(float(r[3]) - float(want[r[0]][2])) > 0.051]
    ck.check("late_pct is the percentage late, rounded to 1 decimal", not bad_pct,
             f"late_pct differs for {', '.join(bad_pct)} (e.g. {got[0][3]!r})",
             "late_pct = round(100.0 * late items / all items, 1): a percentage (63.1), not a "
             "fraction (0.631). Write 100.0, not 100, so the division keeps its decimals")


def reset():
    return [tk.drop_own(TABLE)]


if __name__ == "__main__":
    sys.exit(tk.Checkpoint("A2", "exploratory analysis with DuckDB").run(checks, reset))
