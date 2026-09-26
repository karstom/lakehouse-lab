#!/usr/bin/env python3
"""A3 checkpoint: your dbt model segment_revenue is built, correct, tested and documented.

Checks OUTCOMES, as you:
  * the table lakehouse.dbt_<you>.segment_revenue exists, with the lesson's columns;
  * its rows are right (the reference is computed from lakehouse.samples now, not stored);
  * its dbt tests exist and pass: the checkpoint runs `dbt test --select segment_revenue` in
    your project (dbt_project/ in this module folder), which tests the table itself;
  * its description reached Trino as the table comment (persist_docs).

  python3 checkpoint.py [--json]    check        python3 checkpoint.py --reset    start over

`--reset` drops only the table segment_revenue in your schema. The starter models dbt also
built there (stg_*, fct_orders, ...) stay: other modules and the starter notebook use them.
Your files (dbt_project/) are put back by `lab-tracks reset A3`, which moves them to
~/.lakehouse/tracks-backup/ first.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_shared"))
import trackkit as tk  # noqa: E402

MODEL = "segment_revenue"
PROJECT = "dbt_project"
COLUMNS = ["market_segment", "order_year", "orders", "customers", "net_revenue"]
# The same numbers from the raw samples (net revenue = extendedprice x (1 - discount), the
# starter's definition), so a model that reads the wrong column or joins wrongly differs.
REFERENCE = """
WITH lines AS (
    SELECT orderkey, sum(extendedprice * (1 - discount)) AS net
    FROM lakehouse.samples.lineitem GROUP BY orderkey)
SELECT c.mktsegment, year(o.orderdate), count(*), count(DISTINCT o.custkey), sum(l.net)
FROM lakehouse.samples.orders o
JOIN lines l ON o.orderkey = l.orderkey
JOIN lakehouse.samples.customer c ON o.custkey = c.custkey
GROUP BY 1, 2
"""


def project_dir():
    return os.path.join(tk.module_dir(), PROJECT)


def run_dbt_tests(proj):
    """`dbt test --select segment_revenue` in the learner's project, as the learner.
    -> (rc, [(test name, status)], output tail)."""
    target = os.path.join(proj, "target")
    results = os.path.join(target, "run_results.json")
    try:
        os.remove(results)
    except OSError:
        pass
    p = subprocess.run(["dbt", "test", "--select", MODEL, "--no-use-colors"], cwd=proj,
                       capture_output=True, text=True, timeout=600)
    tests = []
    try:
        with open(results, encoding="utf-8") as f:
            for r in json.load(f).get("results", []):
                uid = r.get("unique_id", "")
                if uid.startswith("test."):
                    tests.append((uid.split(".")[2], r.get("status")))
    except (OSError, ValueError):
        pass
    tail = "\n".join((p.stdout + p.stderr).strip().splitlines()[-6:])
    return p.returncode, tests, tail


def checks(ck):
    schema = tk.user_schema()
    fq = f"lakehouse.{schema}.{MODEL}"
    kind = tk.table_type(schema, MODEL)
    if not ck.check(f"your model's table {fq} exists", kind is not None,
                    f"no table or view named {MODEL} in {schema}",
                    "steps 3-4: put segment_revenue.sql in dbt_project/models/marts/ and run "
                    "`dbt run --select segment_revenue` in dbt_project/"):
        return
    ck.check("it is a table (the marts folder's materialization)", kind == "BASE TABLE",
             f"it is a {kind}", "keep the model in models/marts/: dbt_project.yml makes "
             "everything there a table")
    cols = [c for c, _ in tk.columns(schema, MODEL)]
    if not ck.check(f"it has the columns {', '.join(COLUMNS)}", cols == COLUMNS,
                    f"found: {', '.join(cols) or '(none)'}",
                    "keep the column names and order of the skeleton in segment_revenue.sql"):
        return
    _, got = tk.query(f"SELECT market_segment, order_year, orders, customers, net_revenue FROM {fq}")
    _, want = tk.query(REFERENCE)
    want = {(r[0], r[1]): r[2:] for r in want}
    got = {(r[0], r[1]): r[2:] for r in got}
    if not ck.check(f"one row per segment and year ({len(want)} rows)", set(got) == set(want),
                    f"found {len(got)} rows", "group by segment and order year (group by 1, 2), "
                    "and join fct_orders to dim_customers on customer_id"):
        return
    bad_counts = sorted(k for k in want if tuple(got[k][:2]) != tuple(want[k][:2]))
    ck.check("orders and customers are counted right", not bad_counts,
             f"counts differ for {len(bad_counts)} rows, e.g. {bad_counts[:2]}",
             "orders = count(*), customers = count(distinct o.customer_id); join ON "
             "o.customer_id = c.customer_id")
    bad_rev = sorted(k for k in want if not tk.close_enough(got[k][2], want[k][2], 0.001))
    ck.check("net_revenue is the sum of the orders' net revenue", not bad_rev,
             f"differs for {len(bad_rev)} rows, e.g. {bad_rev[:1]}",
             "net_revenue = round(sum(o.net_revenue), 2), from ref('fct_orders')")

    proj = project_dir()
    if not ck.check("your dbt project is in dbt_project/", os.path.isfile(
                        os.path.join(proj, "dbt_project.yml")),
                    f"no {tk_pretty(proj)}/dbt_project.yml",
                    "step 1: cp -r /opt/lakehouse/starter/dbt_lakehouse "
                    "~/tracks/analyst/A3-first-dbt-model/dbt_project"):
        return
    rc, tests, tail = run_dbt_tests(proj)
    kinds = {name.split("_segment_revenue")[0] for name, _ in tests}
    ck.check("the model has a not_null and an accepted_values test",
             {"not_null", "accepted_values"} <= kinds,
             f"dbt found {len(tests)} test(s): {', '.join(n for n, _ in tests) or 'none'}"
             + (f"\n               dbt said: {tail}" if not tests else ""),
             "step 5: put segment_revenue.yml next to the model, fill in the ___ parts")
    failed = [n for n, s in tests if s != "pass"]
    ck.check("all of the model's tests pass", tests and not failed and rc == 0,
             f"not passing: {', '.join(failed) or tail}",
             "run `dbt test --select segment_revenue` and read the first FAIL: which "
             "value did accepted_values not expect?")
    _, rows = tk.query(
        "SELECT comment FROM system.metadata.table_comments "
        "WHERE catalog_name = 'lakehouse' AND schema_name = ? AND table_name = ?", [schema, MODEL])
    comment = (rows[0][0] if rows else None) or ""
    ck.check("its description is on the table in Trino (persist_docs)",
             bool(comment.strip()) and "___" not in comment,
             f"table comment: {comment!r}",
             "step 6: write a real description in segment_revenue.yml (no ___ left) and run "
             "`dbt run --select segment_revenue` again: persist_docs writes it at build time")


def tk_pretty(p):
    h = os.path.expanduser("~")
    return "~" + p[len(h):] if p.startswith(h) else p


def reset():
    return [tk.drop_own(MODEL)]


if __name__ == "__main__":
    sys.exit(tk.Checkpoint("A3", "your first dbt model").run(checks, reset))
