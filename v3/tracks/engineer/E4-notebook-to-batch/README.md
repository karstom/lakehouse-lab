# E4 · From notebook to scheduled job to Spark batch job

**Time:** about 60 minutes · **Profile:** `engineer` (or `full`) · **You need:** the
`engineer` or `lab-admin` group, and E3 done (you know how to put a DAG in
`~/airflow-dags/<you>/`, trigger it and read its logs).

## Goal

Most pipelines start life as a notebook: someone explores, gets a useful result, and then
everybody wants it **every day**. This module takes one analysis through the three stages
you will meet in real teams:

1. **a notebook** you run by hand, as yourself;
2. **the same notebook, scheduled**: Airflow runs it every day with *papermill*;
3. **a Spark batch job**: the same result as a proper program, running on the cluster as a
   service identity, ready for data too big for one machine or for jobs that run for hours.

At the end, three tables hold the same 25 rows (revenue per nation), and you can say who
wrote each one and why.

You will learn:

- how to make a notebook **parameterised** so a scheduler can run it unchanged;
- what papermill does, and why an executed notebook is a good run record;
- the difference between **interactive** and **batch identities**, and why a long job must
  not run on your personal login;
- how to rewrite SQL as Spark DataFrame code, and run it as a batch job.

## Concepts (read this first, 10 minutes)

**Interactive vs. batch identity.** This is the key idea of the module.

| | Interactive (you, in the workspace) | Batch (Airflow) |
|---|---|---|
| Who | **you**: your Keycloak login | **`lab-batch`**: the lab's service identity |
| Proof of identity | your **access token**, refreshed while you are logged in | a **client credential** (like a password for a program), held by Airflow only |
| Lifetime | a token lasts minutes; a Spark session keeps the token it started with, so it stops working after about an hour | the job fetches **new tokens itself** for as long as it runs |
| Permissions | yours (your namespace `eng_<you>`, read `samples`) | the batch identity's (writes the shared `analytics` namespace) |
| Good for | exploring, trying things, short queries | scheduled, unattended, long-running work |

Why not run the scheduled job as you? Because it must work at 3 a.m. when you are not logged
in, next year when you have left the team, and for five hours when your token lasts five
minutes. The lab's rule (ADR-017) is: **long or scheduled work runs as `lab-batch` through
Airflow**; your personal session is for interactive work.

**Tokens vs. credentials in Spark.** Your notebook's `spark()` session carries **your
token**: when it expires, the session can no longer read or write, and you simply open a new
one. A batch job's Spark session is given the **lab-batch credential** instead, so the
Iceberg client on the cluster renews tokens on its own, for as long as the job runs. The
credential reaches the job only through its environment; it is never printed or stored.

**papermill** runs a notebook from top to bottom in a fresh kernel, like "Restart and run
all". Before it starts, it replaces the values in the cell tagged **`parameters`** with the
values the caller passes (`-p target ...`). It saves the executed copy, with every output,
as a record of that run.

**Why then a Spark job?** The notebook sends one SQL query to Trino, which is perfect for
25 rows. A Spark job runs on the cluster, so it scales to data that does not fit in one
machine, can run for hours as `lab-batch`, and is plain code that can be tested and
reviewed like any other program.

## Steps

### 1. Read the notebook

Open `revenue_report.ipynb` in this folder. Look at:

- the **parameters** cell (`target`, `run_id`, `dag_id`). Click it and open the property
  inspector (the gear icon on the right): it has the tag `parameters`;
- the "Who am I" cell: in Airflow it uses the batch token from its environment; in your
  workspace it uses your own login;
- the last cell: `CREATE OR REPLACE TABLE ... AS`, with columns that record which run wrote
  the rows and as whom (as in E3).

### 2. Run it yourself

Run all cells (**Run > Run All Cells**). Expected, with your own name:

```
running in your workspace as eddie; writing lakehouse.eng_eddie.revenue_by_nation
25 nations
         nation  orders       revenue
0        CANADA     775  1.096180e+08
1         EGYPT     712  1.064101e+08
2          IRAN     745  1.042379e+08
...
lakehouse.eng_eddie.revenue_by_nation: 25 rows, 15000 orders
```

The table shows the top nations by revenue (pandas prints big numbers in scientific
notation: `1.096180e+08` is about 109.6 million). This is stage 1: a useful notebook, run by
hand, as you.

### 3. Look at who wrote it

In a new cell:

```python
cur.execute(f"SELECT DISTINCT run_id, written_by FROM {target}")
print(cur.fetchall())
```

Expected: `[['interactive', 'eddie']]` (your name). Keep this in mind for step 5.

### 4. Schedule the notebook (your turn)

Copy the notebook and its DAG into your DAG folder:

```
cp ~/tracks/engineer/E4-notebook-to-batch/revenue_report.ipynb \
   ~/tracks/engineer/E4-notebook-to-batch/revenue_report_dag.py \
   ~/airflow-dags/$JUPYTERHUB_USER/
```

Open `~/airflow-dags/<you>/revenue_report_dag.py` and read the task: it asks for a batch
token, puts it in the environment, and runs `papermill` on the notebook with `-p run_id` and
`-p dag_id`. **Your turn:**

- **TODO 1:** `ME = "<your username>"`;
- **TODO 2:** pass the production table as the notebook's `target` parameter. Replace the
  TODO line with:

  ```python
              "-p", "target", TABLE,
  ```

Save. Within 30 seconds `u_<you>_revenue_report` appears in Airflow. It is `@daily`, so
Airflow usually starts a first run by itself (as in E3); otherwise press **Trigger**.

### 5. Read the run

Open the run's `run_notebook` task log. You should see the notebook's output, cell by cell,
ending with lines like:

```
running in Airflow (papermill) as service-account-lab-batch; writing lakehouse.analytics.u_eddie_revenue_by_nation
lakehouse.analytics.u_eddie_revenue_by_nation: 25 rows, 15000 orders
[lab] exit 0 after 6.9s
executed notebook saved at /opt/lab/data/notebooks/u_eddie_revenue_report/scheduled__2026-09-26T00_00_00+00_00.ipynb
```

The same notebook, unchanged, ran as **`lab-batch`** and wrote the shared `analytics`
namespace. That is stage 2. Check in a notebook:

```python
cur.execute("SELECT DISTINCT run_id, dag_id, written_by FROM lakehouse.analytics.u_eddie_revenue_by_nation")
print(cur.fetchall())
```

What if you forget TODO 2? The notebook stops with *no target table: the DAG must pass
one*: in Airflow it refuses to guess where to write. Failing loudly is a feature.

### 6. The Spark batch job (your turn)

Open `jobs/revenue_by_nation_spark.py` in this folder. `batch_session()` builds a Spark
Connect session as `lab-batch` **with the credential**, not a token (read its comments).
`revenue_by_nation()` rewrites the notebook's SQL with the DataFrame API: `orders` joined to
`customers` and `nations`. **Your turn:** replace `result = joined` with a group-by that has
the same two columns as the notebook's query:

```python
    result = joined.groupBy("nation").agg(
        F.count("*").alias("orders"),
        F.round(F.sum("totalprice"), 2).alias("revenue"))
```

Then copy the job and its DAG into your DAG folder, and set `ME` in the DAG:

```
mkdir -p ~/airflow-dags/$JUPYTERHUB_USER/jobs
cp ~/tracks/engineer/E4-notebook-to-batch/jobs/revenue_by_nation_spark.py ~/airflow-dags/$JUPYTERHUB_USER/jobs/
cp ~/tracks/engineer/E4-notebook-to-batch/revenue_spark_dag.py ~/airflow-dags/$JUPYTERHUB_USER/
```

(Edit the copies in `~/airflow-dags/<you>/` if you prefer; what counts is what is there.)

Tip: copy the **job first** and the DAG last. A DAG that appears before its job file would
start a run that cannot find the job.

### 7. Run it and compare

`u_<you>_revenue_spark` appears in Airflow and starts (or press **Trigger**). The
`spark_job` log ends with:

```
[spark-job] wrote lakehouse.analytics.u_eddie_revenue_by_nation_spark: 25 rows, run scheduled__2026-09-26T00:00:00+00:00
[lab] exit 0 after 8.1s
```

Compare the two production tables in a notebook:

```python
cur.execute("""
    SELECT count(*) FROM lakehouse.analytics.u_eddie_revenue_by_nation a
    JOIN lakehouse.analytics.u_eddie_revenue_by_nation_spark b ON a.nation = b.nation
    WHERE a.orders = b.orders AND abs(a.revenue - b.revenue) < 0.01""")
print(cur.fetchall())
```

Expected: `[[25]]`: three runs, two engines (Trino and Spark), two identities, the same numbers.

### 8. Check your work

```
lab-tracks check E4
```

A pass:

```
  PASS  step 2: your interactive run wrote your own table, as you: lakehouse.eng_eddie.revenue_by_nation, 25 nations, written by eddie
  PASS  step 5: papermill ran the notebook in Airflow, as lab-batch: run scheduled__... of u_eddie_revenue_report, as service-account-lab-batch
  PASS  step 7: the Spark batch job wrote the same numbers, as lab-batch: run scheduled__... of u_eddie_revenue_spark, as service-account-lab-batch

E4: PASSED (3/3 checks, 2s)
```

## Common mistakes

- **Notebook fails in Airflow with "no target table"**: TODO 2 is missing. Add
  `"-p", "target", TABLE,` to the papermill command.
- **Import error in Airflow about the dag_id**: `ME` is still `TODO-your-username` in one of
  the two DAG files.
- **`spark_job` fails with "expected 25 nations, got 15000"** (or a column error in the
  checkpoint): the group-by TODO is not done, so the job wrote one row per order. Finish
  step 6, copy the job again, trigger again.
- **`No such file` for the job in the task log**: the DAG was copied, the job was not (or not
  into `jobs/`). Check `ls -R ~/airflow-dags/$JUPYTERHUB_USER`.
- **Editing `~/tracks/...` after copying**: Airflow runs the copy in `~/airflow-dags/<you>/`.
  Copy again after each change.
- **Checkpoint: "written by service-account-lab-batch, not by you"** for step 2: the table in
  your own namespace must come from **your** run of the notebook, in your workspace. Run it
  again yourself.
- **Your interactive Spark session stops working after an hour** (E1, E2): that is the token
  lifetime from the concepts section. It is exactly why long jobs go through Airflow.

## Start again

`lab-tracks reset E4` drops `eng_<you>.revenue_by_nation` and your two
`analytics.u_<you>_revenue_by_nation*` tables, deletes the notebook, both DAGs and the job
from your DAG folder, and restores this folder's original files.

## What's next

You have finished the engineer track. Ideas to go further: add a `check` task to the Spark
DAG (as in E3), make the Spark job write only one day of data per run (partitioned by day,
as in E1), or run the E2 maintenance procedures on a schedule.
