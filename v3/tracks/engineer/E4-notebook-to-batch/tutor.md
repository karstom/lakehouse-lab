# Tutor notes · E4 From notebook to scheduled job to Spark batch job

For the Phase 5 AI tutor and for human facilitators. Guide the learner to the answer; do not
paste the solution. `lab-tracks check E4` checks the three stages in order.

## Learning objectives

By the end the learner can:

1. Parameterise a notebook (a cell tagged `parameters`) so a scheduler can run it unchanged,
   and explain what papermill does (inject parameters, run top to bottom, save the executed
   copy as a run record).
2. Schedule a notebook with an Airflow DAG and find its output in the task log.
3. Explain **interactive vs. batch identity**: the user's short-lived token in the workspace
   versus the `lab-batch` client credential in Airflow; why scheduled and long-running work
   must not run on a personal login (ADR-017).
4. Explain why a batch Spark session gets a credential rather than a token (Iceberg renews
   tokens itself), and that the credential only reaches the job through its environment.
5. Rewrite a SQL aggregation with the Spark DataFrame API (`groupBy().agg()`), and verify
   that two implementations produce the same numbers.
6. Record provenance (`run_id`, `dag_id`, `written_by`) in output tables, and use it.

## Prerequisites

- Group `engineer` or `lab-admin`; profile `engineer` or `full`.
- E3 done: the learner knows the DAG folder, the `u_<user>_` rule, triggering and task logs.

## Common mistakes and how to guide

| Symptom | Likely cause | Hint to give (in order, stop when they get it) |
|---|---|---|
| Checkpoint step 2 fails: no `eng_<user>.revenue_by_nation` | Notebook not run in the workspace | Run all cells of `revenue_report.ipynb` in the workspace (step 2). |
| Step 2: "written by service-account-lab-batch, not by you" | Learner pointed the DAG at their own namespace, or never ran it themselves | The interactive table must come from their own run; rerun the notebook in the workspace. |
| Papermill task fails: "no target table: the DAG must pass one" | TODO 2 missing | "How does the DAG hand values to the notebook?" → `-p name value` → `"-p", "target", TABLE,`. |
| Import error mentioning `u_TODO-your-username_...` | `ME` not set | Set `ME` in both DAG files. |
| Spark task fails "expected 25 nations, got 15000" | Group-by TODO not done | "How many rows per nation do we want?" → `groupBy("nation").agg(...)` with `orders` and `revenue`. |
| Checkpoint: "N nation(s) ... differ from the source" for the Spark table | Wrong aggregation (e.g. `sum` without `round`, `countDistinct`, wrong column names) | Compare with the notebook's SQL column by column; aliases must be `orders` and `revenue`. |
| Task log: `No such file` for the job | DAG copied without `jobs/revenue_by_nation_spark.py` | `ls -R ~/airflow-dags/$JUPYTERHUB_USER`; copy the job into `jobs/`. |
| Edits have no effect | Editing `~/tracks/...` after copying | Airflow runs the copy in `~/airflow-dags/<user>/`. |
| "Why can't my notebook's Spark session run for 5 hours?" | Good question | Token lifetime; that is exactly what the batch credential solves. |

## Hints ladder for the YOUR TURN steps

- TODO 2 (papermill): "Which parameter does the notebook need in Airflow?" → "papermill takes
  `-p <name> <value>`" → `"-p", "target", TABLE,`.
- Spark group-by: "What does `GROUP BY n.name` become in the DataFrame API?" → "`groupBy`,
  then `agg` with one expression per column" → `joined.groupBy("nation").agg(F.count("*").alias("orders"), F.round(F.sum("totalprice"), 2).alias("revenue"))`.

## Questions to check understanding

- The papermill run and your interactive run wrote the same numbers. Why do their
  `written_by` values differ, and why is that the right design?
- A scheduled job must run for six hours. What breaks if it uses your token, and what does
  the lab do instead?
- Where is the record of what yesterday's papermill run printed?
- When would you move from "scheduled notebook" to "Spark job"? (Data size, run time,
  testability, code review.)

## Facts the tutor can rely on

- Three tables, each 25 rows (one per TPC-H nation), covering all 15000 sample orders:
  `lakehouse.eng_<user>.revenue_by_nation` (written by the user, `run_id` =
  `interactive`), `lakehouse.analytics.u_<user>_revenue_by_nation` (papermill, DAG
  `u_<user>_revenue_report`, written by `service-account-lab-batch`),
  `lakehouse.analytics.u_<user>_revenue_by_nation_spark` (Spark Connect as `lab-batch`, DAG
  `u_<user>_revenue_spark`).
- Executed notebooks are stored in Airflow's data volume at
  `/opt/lab/data/notebooks/u_<user>_revenue_report/<run_id>.ipynb`; the path is in the task
  log. Learners cannot open that volume from their workspace; the task log shows the output.
- The batch job's Spark session uses `spark.sql.catalog.lakehouse.credential` =
  `lab-batch:<secret>` with token refresh on and token exchange off (ADR-017); the secret is
  passed only in the job's environment.
- Both DAGs are `@daily`, `catchup=False`; a new one gets a scheduled run for the latest
  midnight straight away. The Spark DAG has `max_active_runs=1` (shared cluster).
- `lab-tracks reset E4` drops the three tables (plain `DROP TABLE` through Trino), the
  namespace `eng_<user>` if it is then empty, and deletes the notebook, both DAG files and
  the job from the user's DAG folder.
