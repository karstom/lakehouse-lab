# Tutor notes · E3 Author and schedule your own Airflow DAG

For the Phase 5 AI tutor and for human facilitators. Guide the learner to the answer; do not
paste the solution. `lab-tracks check E3` says which check fails first.

## Learning objectives

By the end the learner can:

1. Define DAG, task, dependency (`>>`), DAG run, schedule and `catchup`, and read them off a
   DAG file.
2. Deploy a DAG by saving it into the DAG folder, and find and read an import error.
3. Explain the lab's DAG policy (own folder, `u_<user>_` dag id prefix) and why a shared
   Airflow needs rules like it.
4. Trigger a run, follow it in the Grid view, and read a task log.
5. Explain why the work lives in a separate job script (fast parsing, testable job).
6. Explain idempotent and atomic writes (`CREATE OR REPLACE TABLE ... AS`) and why a
   data-quality task after the build matters.
7. Explain as whom a DAG runs (the batch identity `lab-batch`, not the author), why, and what
   that means for trust (only engineers/lab admins get a DAG folder).

## Prerequisites

- Group `engineer` or `lab-admin`; profile `engineer` or `full` (Airflow exists only there).
- E1/E2 are useful background (tables, commits) but not required.
- Uses a terminal for `mkdir`/`cp`; walk a beginner through step 3 if needed.

## Common mistakes and how to guide

| Symptom | Likely cause | Hint to give (in order, stop when they get it) |
|---|---|---|
| Checkpoint: "~/airflow-dags is not in your workspace" | Not in `engineer`/`lab-admin`, or group added after the server started, or profile `core` | Ask an admin for the group; then stop and start the server (File > Hub Control Panel). |
| Checkpoint: "no .py file in ~/airflow-dags/<user>" | Step 3 not done, or files copied to `~/airflow-dags/` directly | Show `ls -R ~/airflow-dags/$JUPYTERHUB_USER`. |
| Import error "must start with 'u_<user>_'" | TODO 2 not done, or `ME` wrong | Point at the prefix in the message; `ME` must be the exact username. |
| Import error "must be inside your own folder" | File directly in `~/airflow-dags/` | Move it into the username folder. |
| DAG edits "do nothing" | Editing `~/tracks/...` instead of `~/airflow-dags/<user>/` | "Which copy does Airflow read?" |
| DAG missing, no import error | Less than 30 s since saving | Wait, reload. |
| `build_summary` fails: "table must be lakehouse.analytics.u_<you>_..." | `ME` still `TODO-your-username` or capitalised | Fix `ME`. |
| Checkpoint: "the DAG that wrote the table had no schedule" | Triggered before TODO 3 | Save `@daily`, wait until the UI shows the schedule, trigger again (or wait for the automatic scheduled run). |
| Checkpoint: "written by DAG 'x', want 'u_<user>_orders_summary'" | Different dag_id | Use exactly `f"u_{ME}_orders_summary"`. |
| `check_summary` failed | Table changed between build and check, or build failed silently | Read the `check_summary` log; trigger again. |
| "Why does it say service-account-lab-batch, not me?" | Expected | Good question: scheduled work runs as a service identity (see objective 7). |

## Hints ladder

- TODO 1: "What is your username?" → `echo $JUPYTERHUB_USER` → `ME = "<that>"`.
- TODO 2: "What does the import error say the id must start with?" →
  `dag_id=f"u_{ME}_orders_summary"`.
- TODO 3: "How often should this run?" → "Airflow has presets like `@hourly`, `@daily`" →
  `schedule="@daily"`.

## Questions to check understanding

- What would happen if `build_summary` appended rows instead of `CREATE OR REPLACE`, and the
  DAG ran twice?
- Why does `check_summary` run after `build_summary`, and what should happen to consumers of
  the table when it fails?
- Your DAG ran at midnight while you were asleep. How do you find out what it did?
- Why does the lab not let an analyst put a DAG in the shared folder?

## Facts the tutor can rely on

- DAG folder: `~/airflow-dags/<user>/` in the workspace = `/opt/lab/dags/user/<user>/` in
  Airflow (read-only there). Airflow re-reads the folder every 30 s.
- Policy (`config/airflow/policy/airflow_local_settings.py`): file must be in
  `user/<user>/`; dag_id must start with `u_<user>_`; `u_` ids are reserved for user DAGs;
  task owner is set to the user and the tag `user:<user>` is added.
- DAGs are created unpaused in this lab. A new `@daily` DAG with `catchup=False` gets one
  scheduled run for the latest midnight right away.
- Table `lakehouse.analytics.u_<user>_orders_summary`: 15 rows (3 order statuses × 5
  priorities) covering all 15000 sample orders, written by `service-account-lab-batch`, with
  `dag_id`, `run_id`, `run_type`, `schedule`, `dag_file`, `written_by`, `computed_at`.
- Every engineer workspace can write the whole shared DAG folder (same Unix user); the policy
  keeps DAG ids apart, not files. This is a documented trust decision.
- `lab-tracks reset E3` drops the table and deletes `orders_summary_dag.py` and
  `jobs/orders_summary.py` from the user's DAG folder.
