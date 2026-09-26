"""E3 checkpoint: did Airflow run YOUR daily DAG, and did it write your summary table?

Run it with `lab-tracks check E3` (or `python checkpoint.py`). It checks outcomes, as you:
your DAG folder, and the table your DAG's run wrote (through Trino). The table records which
DAG run wrote it, so the checkpoint can tell a run by Airflow from a table made by hand.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_shared"))

from trackcheck import Checkpoint, Fail, Trino, dag_prefix, dags_dir, prod_prefix, username  # noqa: E402

cp = Checkpoint("E3", "Author and schedule your own Airflow DAG")
S = {}
BATCH_PRINCIPAL = "service-account-lab-batch"


@cp.check("your DAG folder has your DAG file")
def _folder():
    S["user"] = username()
    S["dag_id"] = f"{dag_prefix()}orders_summary"
    S["table"] = f"{prod_prefix()}orders_summary"
    root = os.path.expanduser("~/airflow-dags")
    if not os.path.isdir(root):
        raise Fail("~/airflow-dags is not in your workspace",
                   "User DAGs are for the engineer and lab-admin groups, on the engineer or full "
                   "profile. If you were just added to a group, stop and start your server "
                   "(File > Hub Control Panel).")
    mine = dags_dir()
    files = sorted(f for f in os.listdir(mine) if f.endswith(".py")) if os.path.isdir(mine) else []
    if not files:
        raise Fail(f"no .py file in {mine}",
                   f"Step 3: mkdir -p {mine} and copy orders_summary_dag.py and the jobs/ folder "
                   f"into it (edit the copy there, not the one in ~/tracks).")
    return f"{mine}: {', '.join(files)}"


@cp.check("your DAG ran and wrote its table")
def _table():
    S["trino"] = Trino()
    if not S["trino"].table_exists("analytics", S["table"]):
        raise Fail(f"no table lakehouse.analytics.{S['table']} yet",
                   f"Open Airflow, find the DAG {S['dag_id']} and trigger it (step 6). No DAG "
                   f"there? Look under 'Dag Import Errors' at the top of the Dags page (steps "
                   f"4-5). A run that failed? Open it and read the task log.")
    return f"lakehouse.analytics.{S['table']}"


@cp.check("the table was written by your DAG, as the batch identity")
def _provenance():
    rows = S["trino"].rows(
        f'SELECT DISTINCT dag_id, run_id, run_type, schedule, dag_file, written_by '
        f'FROM lakehouse.analytics."{S["table"]}"')
    if len(rows) != 1:
        raise Fail(f"{len(rows)} different runs in one table", "Trigger the DAG again: each run "
                   "replaces the whole table.")
    dag_id, run_id, run_type, schedule, dag_file, written_by = rows[0]
    S["schedule"] = schedule
    if dag_id != S["dag_id"]:
        raise Fail(f"written by DAG {dag_id!r}, want {S['dag_id']!r}",
                   f"Set dag_id=\"{S['dag_id']}\" (TODO 2).")
    if written_by != BATCH_PRINCIPAL:
        raise Fail(f"written by {written_by}, not by {BATCH_PRINCIPAL}",
                   "The table must come from an Airflow run, which acts as lab-batch. Trigger "
                   "the DAG in Airflow.")
    if f"/user/{S['user']}/" not in (dag_file or ""):
        raise Fail(f"the DAG file was {dag_file}", f"Keep the DAG in ~/airflow-dags/{S['user']}/.")
    return f"run {run_id} ({run_type}) of {dag_id}, as {written_by}"


@cp.check("the DAG runs once a day")
def _schedule():
    if S["schedule"] in (None, "", "None"):
        raise Fail("the DAG that wrote the table had no schedule",
                   "Set schedule=\"@daily\" (TODO 3), wait until Airflow shows the new schedule, "
                   "and trigger the DAG again.")
    if S["schedule"] not in ("@daily", "0 0 * * *"):
        raise Fail(f"schedule is {S['schedule']!r}, want \"@daily\"", "Set schedule=\"@daily\" (TODO 3).")
    return f"schedule {S['schedule']}"


@cp.check("the summary adds up to the source")
def _totals():
    groups, orders = S["trino"].rows(
        f'SELECT count(*), sum(orders) FROM lakehouse.analytics."{S["table"]}"')[0]
    source = S["trino"].one("SELECT count(*) FROM lakehouse.samples.orders")
    if orders != source:
        raise Fail(f"the summary covers {orders} orders, the source has {source}",
                   "The job writes the whole summary in one step; trigger the DAG again.")
    return f"{groups} status/priority groups covering {orders} orders"


if __name__ == "__main__":
    sys.exit(cp.run())
