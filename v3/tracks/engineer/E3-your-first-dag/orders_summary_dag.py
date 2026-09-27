"""My first DAG (E3): every day, rebuild a summary of the orders, then check it.

Copy this file and the jobs/ folder into ~/airflow-dags/<your username>/ (step 3 of the
lesson), then fill in the three TODOs. Airflow reads the folder every 30 seconds.
"""
from datetime import datetime
from pathlib import Path

from airflow.sdk import dag, get_current_context, task

import lab_batch  # the lab's helpers for the batch identity: tokens, running a job

ME = "TODO-your-username"          # TODO 1: your username, exactly as you log in
HERE = Path(__file__).parent       # the folder this file is in: ~/airflow-dags/<you>/
JOB = str(HERE / "jobs" / "orders_summary.py")
TABLE = f"lakehouse.analytics.u_{ME}_orders_summary"


def run_job(*args):
    """Run the job script as the batch identity lab-batch, with a fresh token."""
    token, claims = lab_batch.batch_token()
    env = lab_batch.job_env({"LAB_BATCH_TOKEN": token,
                             "LAB_BATCH_PRINCIPAL": lab_batch.principal(claims)})
    lab_batch.run_job([lab_batch.JOBS_PYTHON, JOB, *args], env)


@dag(
    dag_id="orders_summary",           # TODO 2: Airflow only accepts ids that start with u_<you>_
    schedule=None,                     # TODO 3: run once a day ("@daily")
    start_date=datetime(2026, 1, 1),
    catchup=False,                     # do not create runs for all the days since start_date
    default_args={"retries": 1},       # a failed task is tried once more before the run fails
    tags=["track-e3"],
)
def orders_summary():

    @task
    def build_summary():
        ctx = get_current_context()
        run_type = ctx["run_id"].split("__")[0]      # "manual" (Trigger) or "scheduled"
        run_job("build", TABLE, ctx["dag"].dag_id, ctx["run_id"], run_type,
                str(ctx["dag"].schedule), ctx["dag"].fileloc)

    @task
    def check_summary():
        run_job("check", TABLE)

    build_summary() >> check_summary()   # check only after build succeeded


orders_summary()
