"""E4, part 1: run the revenue_report notebook every day with papermill.

Copy this file and revenue_report.ipynb into ~/airflow-dags/<your username>/ (step 4 of
the lesson) and fill in the two TODOs.

papermill runs the notebook top to bottom in a fresh kernel, replaces the values in its
`parameters` cell, and saves the executed copy, with every output, as a record of the run.
"""
import os
import re
from datetime import datetime
from pathlib import Path

from airflow.sdk import dag, get_current_context, task

import lab_batch  # the lab's helpers for the batch identity: tokens, running a job

ME = "TODO-your-username"          # TODO 1: your username, exactly as you log in
HERE = Path(__file__).parent
NOTEBOOK = str(HERE / "revenue_report.ipynb")
TABLE = f"lakehouse.analytics.u_{ME}_revenue_by_nation"


@dag(
    dag_id=f"u_{ME}_revenue_report",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={"retries": 1},
    tags=["track-e4"],
)
def revenue_report():

    @task
    def run_notebook():
        ctx = get_current_context()
        # Where the executed notebook goes: Airflow's data volume, one file per run.
        out_dir = os.path.join(lab_batch.DATA_DIR, "notebooks", ctx["dag"].dag_id)
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, re.sub(r"[^A-Za-z0-9_.+-]", "_", ctx["run_id"]) + ".ipynb")
        # The notebook finds the batch identity's token in its environment, never as a parameter
        # (parameters are saved in the executed notebook).
        token, claims = lab_batch.batch_token()
        env = lab_batch.job_env({"LAB_BATCH_TOKEN": token,
                                 "LAB_BATCH_PRINCIPAL": lab_batch.principal(claims)})
        lab_batch.run_job([
            os.path.join(lab_batch.JOBS_BIN, "papermill"), NOTEBOOK, out,
            "--kernel", "python3", "--log-output", "--no-progress-bar",
            "-p", "run_id", ctx["run_id"],
            "-p", "dag_id", ctx["dag"].dag_id,
            # TODO 2: pass the production table as the notebook's `target` parameter
        ], env, cwd="/tmp")
        print(f"executed notebook saved at {out}")

    run_notebook()


revenue_report()
