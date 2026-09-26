"""Reference solution for E3 (test-only; never copied into homes).

    python solve.py ~/tracks/engineer/E3-your-first-dag

Resets the module, then does what the learner does in the workspace: fills in the three
TODOs of orders_summary_dag.py and copies it, with jobs/, into ~/airflow-dags/<you>/. Then it
waits until an Airflow run of the DAG has written the summary table (see
solvelib.wait_for_runs: a new @daily DAG gets its first scheduled run straight away; the
learner's "Trigger" press is the other way, module.json solution.trigger_dags lists the
DAGs a harness with the learner's Airflow login may trigger). `--no-wait` skips the wait.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_lib"))
import solvelib  # noqa: E402

mod = solvelib.module_dir()
import trackcheck  # noqa: E402  (on sys.path after module_dir())

user = trackcheck.username()
solvelib.reset(mod)
answers = {
    'ME = "TODO-your-username"': f'ME = "{user}"',
    'dag_id="orders_summary",': 'dag_id=f"u_{ME}_orders_summary",',
    "schedule=None,": 'schedule="@daily",',
}
with open(os.path.join(mod, "orders_summary_dag.py"), encoding="utf-8") as f:
    src = f.read()
for old, new in answers.items():
    if src.count(old) != 1:
        raise SystemExit(f"anchor {old!r} found {src.count(old)} times in orders_summary_dag.py")
    src = src.replace(old, new)
dest = trackcheck.dags_dir(user)
os.makedirs(dest, exist_ok=True)
solvelib.copy_into(os.path.join(mod, "jobs", "orders_summary.py"),
                   os.path.join(dest, "jobs", "orders_summary.py"))
tmp = os.path.join(dest, ".orders_summary_dag.py.tmp")
with open(tmp, "w", encoding="utf-8") as f:
    f.write(src)
os.replace(tmp, os.path.join(dest, "orders_summary_dag.py"))  # appears complete, never half-written
print(f"[solve] wrote {dest}/orders_summary_dag.py (dag_id u_{user}_orders_summary, @daily)")
solvelib.wait_for_runs([("analytics", f"{trackcheck.prod_prefix(user)}orders_summary")], timeout=780)
