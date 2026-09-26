"""E4 checkpoint: one report, three runs (you, papermill, Spark batch), the same numbers.

Run it with `lab-tracks check E4` (or `python checkpoint.py`). It checks outcomes, as you,
through Trino: the three tables, who wrote each one, and that their numbers agree with the
source.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_shared"))

from trackcheck import Checkpoint, Fail, Trino, dag_prefix, namespace, prod_prefix, username  # noqa: E402

cp = Checkpoint("E4", "Notebook to scheduled job to Spark batch")
S = {}
BATCH_PRINCIPAL = "service-account-lab-batch"
TRUTH = """
    SELECT n.name AS nation, count(*) AS orders, round(sum(o.totalprice), 2) AS revenue
    FROM lakehouse.samples.orders o
    JOIN lakehouse.samples.customer c ON c.custkey = o.custkey
    JOIN lakehouse.samples.nation n ON n.nationkey = c.nationkey
    GROUP BY n.name"""


def compare(schema, table, how_to_fix):
    """The table's (nation, orders, revenue) must match the source; returns its provenance."""
    t = S["trino"]
    if not t.table_exists(schema, table):
        raise Fail(f"no table lakehouse.{schema}.{table}", how_to_fix)
    cols = t.columns(schema, table)
    missing = [c for c in ("nation", "orders", "revenue", "run_id", "dag_id", "written_by") if c not in cols]
    if missing:
        raise Fail(f"lakehouse.{schema}.{table} has no column(s) {', '.join(missing)}",
                   "Keep the columns the lesson's code writes. " + how_to_fix)
    bad = t.one(f"""
        SELECT count(*) FROM ({TRUTH}) truth
        FULL OUTER JOIN lakehouse."{schema}"."{table}" mine ON mine.nation = truth.nation
        WHERE mine.nation IS NULL OR truth.nation IS NULL
           OR mine.orders <> truth.orders OR abs(mine.revenue - truth.revenue) > 0.05""")
    if bad:
        raise Fail(f"{bad} nation(s) in lakehouse.{schema}.{table} differ from the source "
                   f"(want 25 rows: nation, number of orders, revenue)", how_to_fix)
    return t.rows(f'SELECT DISTINCT run_id, dag_id, written_by FROM lakehouse."{schema}"."{table}"')


@cp.check("step 2: your interactive run wrote your own table, as you")
def _interactive():
    S["user"], S["trino"] = username(), Trino()
    prov = compare(namespace(), "revenue_by_nation",
                   "Run revenue_report.ipynb in your workspace, top to bottom (step 2).")
    who = {r[2] for r in prov}
    if who != {S["user"]}:
        raise Fail(f"written by {', '.join(sorted(who))}, not by you",
                   "Run the notebook yourself, in your workspace (step 2).")
    return f"lakehouse.{namespace()}.revenue_by_nation, 25 nations, written by {S['user']}"


@cp.check("step 5: papermill ran the notebook in Airflow, as lab-batch")
def _papermill():
    dag = f"{dag_prefix()}revenue_report"
    prov = compare("analytics", f"{prod_prefix()}revenue_by_nation",
                   f"Put revenue_report_dag.py and revenue_report.ipynb in ~/airflow-dags/{S['user']}/, "
                   f"finish its TODOs and trigger {dag} in Airflow (steps 4-5).")
    run_id, dag_id, who = prov[0]
    if len(prov) != 1 or dag_id != dag or who != BATCH_PRINCIPAL:
        raise Fail(f"written by DAG {dag_id!r} as {who}; want DAG {dag!r} as {BATCH_PRINCIPAL}",
                   f"The table must come from a run of {dag} in Airflow.")
    return f"run {run_id} of {dag_id}, as {who}"


@cp.check("step 7: the Spark batch job wrote the same numbers, as lab-batch")
def _spark():
    dag = f"{dag_prefix()}revenue_spark"
    prov = compare("analytics", f"{prod_prefix()}revenue_by_nation_spark",
                   f"Finish the TODO in jobs/revenue_by_nation_spark.py (group by nation), copy the "
                   f"DAG and jobs/ into ~/airflow-dags/{S['user']}/ and trigger {dag} (steps 6-7). "
                   f"A run that failed? Read its task log in Airflow.")
    run_id, dag_id, who = prov[0]
    if len(prov) != 1 or dag_id != dag or who != BATCH_PRINCIPAL:
        raise Fail(f"written by DAG {dag_id!r} as {who}; want DAG {dag!r} as {BATCH_PRINCIPAL}",
                   f"The table must come from a run of {dag} in Airflow.")
    return f"run {run_id} of {dag_id}, as {who}"


if __name__ == "__main__":
    sys.exit(cp.run())
