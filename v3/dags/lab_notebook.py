"""lab_notebook: run a notebook on a schedule with papermill (ADR-009).

Executes dags/notebooks/orders_by_priority.ipynb in the jobs virtualenv's kernel, as the batch
service identity lab-batch (the token reaches the kernel through its environment, never as a
parameter, so it is not stored in the output). The executed notebook, with its outputs, is
kept at /opt/lab/data/notebooks/<dag_id>/<run_id>.ipynb (the airflow-data volume) and its
path is written to the task log.
"""
import os
import re
from datetime import datetime

from airflow.sdk import Param, dag, get_current_context, task

import lab_batch

NOTEBOOK = "orders_by_priority.ipynb"


@dag(dag_id="lab_notebook", schedule=None, start_date=datetime(2026, 1, 1), catchup=False,
     max_active_runs=1, default_args=lab_batch.DEFAULT_ARGS, tags=lab_batch.TAGS + ["papermill"],
     params={"target": Param("lakehouse.analytics.orders_by_priority", type="string",
                             pattern=r"^lakehouse\.analytics\.[A-Za-z_][A-Za-z0-9_]*$",
                             description="Summary table the notebook writes")},
     doc_md=__doc__)
def lab_notebook():
    @task
    def run_notebook():
        ctx = get_current_context()
        lab_batch.log_trigger(ctx)
        run_id = ctx["dag_run"].run_id
        out_dir = os.path.join(lab_batch.DATA_DIR, "notebooks", ctx["dag"].dag_id)
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, re.sub(r"[^A-Za-z0-9_.+-]", "_", run_id) + ".ipynb")
        tok, c = lab_batch.batch_token()
        env = lab_batch.job_env({"LAB_BATCH_TOKEN": tok,
                                 "LAB_BATCH_PRINCIPAL": lab_batch.principal(c)})
        lab_batch.run_job([
            os.path.join(lab_batch.JOBS_BIN, "papermill"),
            os.path.join(lab_batch.NOTEBOOKS_DIR, NOTEBOOK), out,
            "--kernel", "python3", "--log-output", "--no-progress-bar",
            "-p", "run_id", run_id, "-p", "target", ctx["params"]["target"],
        ], env, cwd="/tmp")
        print(f"[lab] executed notebook stored at {out}", flush=True)
        return out

    run_notebook()


lab_notebook()
