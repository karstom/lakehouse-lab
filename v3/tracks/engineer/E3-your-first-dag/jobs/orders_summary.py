"""Job for your E3 DAG: summarise the sample orders by status and priority.

Airflow does not run this file as a DAG (files in a `jobs/` folder are ignored by the DAG
parser). Your DAG's tasks start it as a separate program, in the lab's jobs environment,
with a token of the batch identity `lab-batch` in LAB_BATCH_TOKEN.

    orders_summary.py build TABLE DAG_ID RUN_ID RUN_TYPE SCHEDULE DAG_FILE
    orders_summary.py check TABLE

`build` (re)creates TABLE from lakehouse.samples.orders in one atomic step (CREATE OR
REPLACE TABLE): a reader sees the old table or the new one, never half of it, and running
the same job twice gives the same result. It also stores where the rows came from (the DAG
run), so you can always trace a table back to the run that wrote it.

`check` is a data-quality gate: it fails (exit 1) when the table is empty or its totals do
not match the source, so a bad table is flagged in Airflow instead of being used.
"""
import os
import re
import sys

import trino

TABLE_RE = re.compile(r"^lakehouse\.analytics\.u_[a-z0-9_]+$")


def connect():
    """Trino as the batch identity (the token the DAG passed in)."""
    return trino.dbapi.connect(
        host=os.environ["LAB_TRINO_HOST"], port=int(os.environ["LAB_TRINO_PORT"]),
        http_scheme="https", verify=os.environ.get("SSL_CERT_FILE", True),
        auth=trino.auth.JWTAuthentication(os.environ["LAB_BATCH_TOKEN"]),
        user=os.environ["LAB_BATCH_PRINCIPAL"], catalog="lakehouse")


def run(cur, sql, params=None):
    cur.execute(sql, params) if params is not None else cur.execute(sql)
    return cur.fetchall()


def build(table, dag_id, run_id, run_type, schedule, dag_file):
    cur = connect().cursor()
    me = run(cur, "SELECT current_user")[0][0]      # who Trino says we are
    print(f"[job] acting as {me}", flush=True)
    run(cur, f"""
        CREATE OR REPLACE TABLE {table} AS
        SELECT orderstatus,
               orderpriority,
               count(*)                  AS orders,
               round(sum(totalprice), 2) AS revenue,
               ? AS dag_id, ? AS run_id, ? AS run_type, ? AS schedule, ? AS dag_file,
               ? AS written_by,
               current_timestamp(6)      AS computed_at
        FROM lakehouse.samples.orders
        GROUP BY orderstatus, orderpriority""", [dag_id, run_id, run_type, schedule, dag_file, me])
    n = run(cur, f"SELECT count(*), sum(orders) FROM {table}")[0]
    print(f"[job] wrote {table}: {n[0]} rows covering {n[1]} orders", flush=True)


def check(table):
    cur = connect().cursor()
    rows, orders = run(cur, f"SELECT count(*), coalesce(sum(orders), 0) FROM {table}")[0]
    source = run(cur, "SELECT count(*) FROM lakehouse.samples.orders")[0][0]
    print(f"[check] {table}: {rows} rows, {orders} orders; source has {source} orders", flush=True)
    if rows == 0 or orders != source:
        print("[check] FAILED: the summary does not add up to the source", flush=True)
        sys.exit(1)
    print("[check] OK", flush=True)


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("build", "check"):
        sys.exit(__doc__)
    table = sys.argv[2]
    if not TABLE_RE.match(table):
        sys.exit(f"table must be lakehouse.analytics.u_<you>_<name>, got {table!r}")
    if sys.argv[1] == "build":
        build(table, *sys.argv[3:8])
    else:
        check(table)


if __name__ == "__main__":
    main()
