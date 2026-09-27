"""Reference solution for E4 (test-only; never copied into homes).

    python solve.py ~/tracks/engineer/E4-notebook-to-batch

Resets the module, runs revenue_report.ipynb interactively (as the learner), then fills in the
TODOs of the two DAGs and the Spark job and copies them, with the notebook, into
~/airflow-dags/<you>/, and waits until Airflow runs of both DAGs have written their tables
(solvelib.wait_for_runs; module.json solution.trigger_dags lists the DAGs a harness with the
learner's Airflow login may trigger instead). `--no-wait` skips the wait.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_lib"))
import solvelib  # noqa: E402

mod = solvelib.module_dir()
import trackcheck  # noqa: E402  (on sys.path after module_dir())

user = trackcheck.username()
solvelib.reset(mod)

# Step 2: the prototype, run in the workspace as the learner (no answers needed).
nb = solvelib.solve_notebook(mod, "revenue_report.ipynb", {})
print(solvelib.outputs_text(nb)[-1500:])

ME = ('ME = "TODO-your-username"', f'ME = "{user}"')
EDITS = {
    "revenue_report_dag.py": [
        ME,
        ("            # TODO 2: pass the production table as the notebook's `target` parameter\n",
         '            "-p", "target", TABLE,\n'),
    ],
    "revenue_spark_dag.py": [ME],
    "jobs/revenue_by_nation_spark.py": [
        ("    result = joined\n",
         '    result = joined.groupBy("nation").agg(\n'
         '        F.count("*").alias("orders"),\n'
         '        F.round(F.sum("totalprice"), 2).alias("revenue"))\n'),
    ],
}
dest = trackcheck.dags_dir(user)
os.makedirs(os.path.join(dest, "jobs"), exist_ok=True)
# The notebook and the job first, the DAG files last: a DAG never sees a missing file.
solvelib.copy_into(os.path.join(mod, "revenue_report.ipynb"), os.path.join(dest, "revenue_report.ipynb"))
for rel in ("jobs/revenue_by_nation_spark.py", "revenue_report_dag.py", "revenue_spark_dag.py"):
    with open(os.path.join(mod, rel), encoding="utf-8") as f:
        src = f.read()
    for old, new in EDITS[rel]:
        if src.count(old) != 1:
            raise SystemExit(f"anchor {old!r} found {src.count(old)} times in {rel}")
        src = src.replace(old, new)
    tmp = os.path.join(dest, rel + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(src)
    os.replace(tmp, os.path.join(dest, rel))
    print(f"[solve] wrote {dest}/{rel}")
prod = trackcheck.prod_prefix(user)
solvelib.wait_for_runs([("analytics", f"{prod}revenue_by_nation"),
                        ("analytics", f"{prod}revenue_by_nation_spark")], timeout=1000)
