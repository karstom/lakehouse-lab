"""lab_dbt_build: `dbt build` of the starter project with target `analytics`.

Builds lakehouse.analytics (fct_orders, dim_customers, revenue_by_region and the staging
views) from lakehouse.samples, as the batch service identity lab-batch: dbt-trino sends a
client-credentials token fetched right before dbt starts (config/airflow/dbt/profiles.yml).
The analytics schema is the shared, production-style output that Superset's dashboard reads.
"""
from datetime import datetime

from airflow.sdk import dag, get_current_context, task

import lab_batch


@dag(dag_id="lab_dbt_build", schedule=None, start_date=datetime(2026, 1, 1), catchup=False,
     max_active_runs=1, default_args=lab_batch.DEFAULT_ARGS, tags=lab_batch.TAGS + ["dbt"],
     doc_md=__doc__)
def lab_dbt_build():
    @task
    def dbt_build():
        ctx = get_current_context()
        lab_batch.log_trigger(ctx)
        tok, c = lab_batch.batch_token()
        env = lab_batch.job_env({"LAB_BATCH_TOKEN": tok,
                                 "LAB_BATCH_PRINCIPAL": lab_batch.principal(c)})
        lab_batch.run_python_job("dbt_build.py", ctx["dag_run"].run_id, env=env)

    dbt_build()


lab_dbt_build()
