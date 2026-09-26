"""lab_spark_batch: a long-running Spark job as the batch service identity (ADR-017).

Runs dags/jobs/spark_batch.py on the shared Spark Connect server as lab-batch. The Spark
session gets the client CREDENTIAL (not a token), so the Iceberg client and the S3 signer
renew their own tokens: the job may run for hours, far past one token lifetime. It reads
lakehouse.samples.orders and writes `target_table` (in lakehouse.analytics), taking at least
`min_runtime_s` seconds, and commits once at the end.

Interactive Spark sessions in a workspace carry the user's own token instead and are bounded
by it; long work belongs here. Only engineers and lab admins can trigger this DAG; the run
records who did.
"""
from datetime import datetime

from airflow.sdk import Param, dag, get_current_context, task

import lab_batch


@dag(dag_id="lab_spark_batch", schedule=None, start_date=datetime(2026, 1, 1), catchup=False,
     max_active_runs=1, default_args=lab_batch.DEFAULT_ARGS, tags=lab_batch.TAGS + ["spark"],
     params={
         "min_runtime_s": Param(30, type="integer", minimum=1, maximum=86400,
                                description="Minimum run time of the write (seconds)"),
         "target_table": Param("lakehouse.analytics.spark_batch_runs", type="string",
                               pattern=r"^lakehouse\.analytics\.[A-Za-z_][A-Za-z0-9_]*$",
                               description="Iceberg table the job appends to"),
     },
     doc_md=__doc__)
def lab_spark_batch():
    @task
    def spark_batch():
        ctx = get_current_context()
        lab_batch.log_trigger(ctx)
        p = ctx["params"]
        env = lab_batch.job_env(with_secret=True)
        lab_batch.run_python_job("spark_batch.py", ctx["dag_run"].run_id,
                                 str(p["min_runtime_s"]), p["target_table"], env=env)

    spark_batch()


lab_spark_batch()
