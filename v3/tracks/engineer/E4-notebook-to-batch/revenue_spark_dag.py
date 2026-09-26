"""E4, part 2: the same report as a Spark batch job, every day, as lab-batch (ADR-017).

Copy this file and the jobs/ folder into ~/airflow-dags/<your username>/ (step 6 of the
lesson), set ME, and finish the TODO in jobs/revenue_by_nation_spark.py.
"""
from datetime import datetime
from pathlib import Path

from airflow.sdk import dag, get_current_context, task

import lab_batch  # the lab's helpers for the batch identity: tokens, running a job

ME = "TODO-your-username"          # TODO: your username, exactly as you log in
HERE = Path(__file__).parent
JOB = str(HERE / "jobs" / "revenue_by_nation_spark.py")
TABLE = f"lakehouse.analytics.u_{ME}_revenue_by_nation_spark"


@dag(
    dag_id=f"u_{ME}_revenue_spark",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,                 # one run at a time on the shared Spark cluster
    default_args={"retries": 1},
    tags=["track-e4", "spark"],
)
def revenue_spark():

    @task
    def spark_job():
        ctx = get_current_context()
        # with_secret=True: the job gets the lab-batch CREDENTIAL (not a token), so Spark can
        # renew its own tokens however long the job runs.
        env = lab_batch.job_env(with_secret=True)
        lab_batch.run_job([lab_batch.JOBS_PYTHON, JOB, TABLE, ctx["dag"].dag_id, ctx["run_id"]], env)

    spark_job()


revenue_spark()
