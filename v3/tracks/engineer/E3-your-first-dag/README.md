# E3 · Author and schedule your own Airflow DAG

**Time:** about 50 minutes · **Profile:** `engineer` (or `full`) · **You need:** the
`engineer` or `lab-admin` group (only those groups get the DAG folder `~/airflow-dags`).

## Goal

Until now you ran every step yourself, in a notebook. Real pipelines run **without you**:
every night, in the right order, with a record of every run and a clear failure when
something is wrong. That is what an orchestrator such as **Apache Airflow** does.

By the end of this module your own DAG runs in the lab's Airflow once a day: it rebuilds a
summary table of the sample orders, then checks it.

You will learn:

- what a DAG, a task, a run and a schedule are;
- how Airflow finds your DAG file, and what an *import error* looks like;
- why the job is written to be **idempotent** (safe to run twice) and **atomic**;
- the difference between the *DAG file* (the plan) and the *job* (the work);
- **as whom** your DAG runs, and why that is not you.

## Concepts (read this first, 10 minutes)

**DAG.** A *Directed Acyclic Graph*: a set of **tasks** plus the order they run in
(`build_summary >> check_summary`: check only after build succeeded). "Acyclic" means no
loops: a task never waits for itself. A DAG is a Python file that Airflow reads; it describes
the work, it does not do it.

**Run.** Each time the DAG executes, Airflow creates a **DAG run** with an id such as
`manual__2026-09-26T14:02:11+00:00` (you pressed Trigger) or
`scheduled__2026-09-26T00:00:00+00:00` (the schedule started it). Every task of every run has
its own log.

**Schedule.** `schedule="@daily"` runs the DAG once a day at midnight (UTC). `catchup=False`
tells Airflow not to create runs for all the past days since `start_date`: only the most
recent one.

**The DAG folder.** Airflow reads DAG files from its DAG folder. In this lab you have your
own part of it: `~/airflow-dags/<your username>/` in your workspace is the same folder that
Airflow sees at `dags/user/<your username>/`. Save a file there and Airflow picks it up
within about 30 seconds.

**House rules (a DAG policy).** Many people share one Airflow, so the lab enforces two rules:

1. your DAG files live in **your own** folder, `~/airflow-dags/<your username>/`;
2. your DAG ids start with **`u_<your username>_`** (for eddie: `u_eddie_orders_summary`).

A file that breaks a rule is refused as a whole, and Airflow shows why under **Dag Import
Errors**. You will see this on purpose in step 4.

**Who runs your DAG?** Not you. Airflow runs every task as the lab's **batch identity**,
`lab-batch`, whatever person wrote or triggered the DAG. That is normal for scheduled work:
at 3 a.m. nobody is logged in, and a pipeline must not stop working when its author leaves
the team. So your DAG's tables are written by `service-account-lab-batch`, into the shared
`analytics` namespace, with names that start with `u_<you>_`. Airflow still records who
triggered each run.

> **Trust note.** Anything your DAG does, it does with the batch identity's permissions,
> which are wider than yours. That is why only engineers and lab admins get a DAG folder.
> Every engineer's workspace can write the whole shared DAG folder (they all run as the same
> Unix user), so stay in your own folder, and treat other people's DAGs as you would their
> code in a shared repository.

**Plan vs. work.** `orders_summary_dag.py` only says *what* runs *when*. The real work is in
`jobs/orders_summary.py`, which each task starts as a separate program with a fresh
lab-batch token. Keeping the work out of the DAG file keeps Airflow fast (it re-reads DAG
files every 30 seconds) and lets you test the job on its own.

**Idempotent and atomic.** The job builds the table with `CREATE OR REPLACE TABLE ... AS
SELECT`: one commit that swaps in the whole new result. Run it twice and you get the same
table (idempotent); a reader sees the old table or the new one, never half of it (atomic).
Compare E1, where running a cell twice appended the same rows again.

## Steps

### 1. Read the starter files

Open `orders_summary_dag.py` and `jobs/orders_summary.py` in this folder. Find:

- the two tasks, `build_summary` and `check_summary`, and the line that orders them;
- the three `TODO`s in the DAG file;
- in the job, the `CREATE OR REPLACE TABLE` statement and the columns that record which run
  wrote the rows (`dag_id`, `run_id`, `written_by`, ...);
- the `check` step: it fails the run when the summary does not add up to the source.

### 2. Find your username and open Airflow

Open a terminal (**File > New > Terminal**) and run:

```
echo $JUPYTERHUB_USER
ls ~/airflow-dags
```

The first line is your username (for example `eddie`). The second shows the shared DAG
folder; it may be empty or list other people's folders. If `ls` says *No such file or
directory*, you are not in the `engineer` or `lab-admin` group, or the lab runs the `core`
profile (no Airflow): ask your lab admin.

In a new browser tab, open `https://airflow.<your lab domain>/` and log in (the same login as
Jupyter). You see the lab's own DAGs (`lab_ingest`, `lab_dbt_build`, ...).

### 3. Copy the starter into your DAG folder

```
mkdir -p ~/airflow-dags/$JUPYTERHUB_USER
cp -r ~/tracks/engineer/E3-your-first-dag/orders_summary_dag.py \
      ~/tracks/engineer/E3-your-first-dag/jobs \
      ~/airflow-dags/$JUPYTERHUB_USER/
ls -R ~/airflow-dags/$JUPYTERHUB_USER
```

Expected:

```
/home/jovyan/airflow-dags/eddie:
jobs  orders_summary_dag.py

/home/jovyan/airflow-dags/eddie/jobs:
orders_summary.py
```

From now on, edit the files **in `~/airflow-dags/<you>/`**: that is the copy Airflow reads.
(In JupyterLab's file browser, `airflow-dags` is in your home folder.)

### 4. See Airflow refuse it (on purpose)

Wait 30 seconds and reload the Airflow **Dags** page. Your DAG is not in the list. Instead,
a **Dag Import Errors** notice appears at the top; open it and find your file:

```
AirflowClusterPolicyViolation: DAG 'orders_summary' in eddie/orders_summary_dag.py: the dag_id
of a DAG in eddie/ must start with 'u_eddie_', for example 'u_eddie_my_pipeline'. Rename the
dag_id and save the file.
```

This is the house rule from the concepts section. An import error means Airflow could not
load the file at all: none of its DAGs exist until you fix it.

### 5. Fix TODO 1 and TODO 2

In `~/airflow-dags/<you>/orders_summary_dag.py`:

- **TODO 1:** `ME = "eddie"` (your username, exactly as printed in step 2);
- **TODO 2:** `dag_id=f"u_{ME}_orders_summary",`

Save (**Ctrl+S**), wait 30 seconds, reload the Dags page. The import error is gone and
`u_eddie_orders_summary` is listed, with the tags `track-e3` and `user:eddie`, and you as its
owner.

### 6. Trigger a run and read the logs

Click your DAG, then **Trigger** (the play button) and confirm. Watch the two tasks turn
green in the **Grid** view (about a minute). Click `build_summary`, then **Logs**. You should
find lines like:

```
[lab] $ /opt/lab/jobs/bin/python /opt/lab/dags/user/eddie/jobs/orders_summary.py build ...
[job] acting as service-account-lab-batch
[job] wrote lakehouse.analytics.u_eddie_orders_summary: 15 rows covering 15000 orders
```

and in `check_summary`:

```
[check] lakehouse.analytics.u_eddie_orders_summary: 15 rows, 15000 orders; source has 15000 orders
[check] OK
```

`acting as service-account-lab-batch`: the job ran as the batch identity, not as you.

### 7. Schedule it (TODO 3)

Set `schedule="@daily",` (TODO 3) and save. After about 30 seconds the DAG page shows the
schedule `@daily` and the next run time.

You will probably also see a new run appear **by itself**, with a run id that starts with
`scheduled__` and today's date at midnight. That is `catchup=False` at work: Airflow skips
all the days since `start_date` and runs only the most recent one it missed. If no run
appears within a minute, press **Trigger** again: the checkpoint needs one run made with the
`@daily` version of the file.

### 8. Look at the result

In a notebook (or with `%%sql` in JupySQL), as you:

```python
from lakehouse import trino_connection
cur = trino_connection().cursor()
cur.execute("""SELECT orderstatus, orderpriority, orders, revenue, run_id, schedule, written_by
               FROM lakehouse.analytics.u_eddie_orders_summary
               ORDER BY orderstatus, orderpriority LIMIT 3""")
for row in cur.fetchall():
    print(row)
```

Expected (with your own name; your run id differs):

```
['F', '1-URGENT', 1468, 206109274.76, 'manual__2026-09-26T14:58:37.016843+00:00', '@daily', 'service-account-lab-batch']
['F', '2-HIGH', 1483, 211278198.4, 'manual__2026-09-26T14:58:37.016843+00:00', '@daily', 'service-account-lab-batch']
['F', '3-MEDIUM', 1445, 202158746.39, 'manual__2026-09-26T14:58:37.016843+00:00', '@daily', 'service-account-lab-batch']
```

Every row says which run wrote it. When a number looks wrong next month, you can find the
exact run, and its logs, that produced it.

### 9. Check your work

In the terminal:

```
lab-tracks check E3
```

A pass:

```
  PASS  your DAG folder has your DAG file: /home/jovyan/airflow-dags/eddie: orders_summary_dag.py
  PASS  your DAG ran and wrote its table: lakehouse.analytics.u_eddie_orders_summary
  PASS  the table was written by your DAG, as the batch identity: run manual__2026-09-26T14:58:37... (manual) of u_eddie_orders_summary, as service-account-lab-batch
  PASS  the DAG runs once a day: schedule @daily
  PASS  the summary adds up to the source: 15 status/priority groups covering 15000 orders

E3: PASSED (5/5 checks, 1s)
```

## Common mistakes

- **Editing the copy in `~/tracks/...`** instead of `~/airflow-dags/<you>/`. Airflow only
  reads the DAG folder. Check with `ls -l ~/airflow-dags/$JUPYTERHUB_USER`.
- **Import error "must start with 'u_eddie_'"**: TODO 2 not done, or a typo in `ME`. The
  message tells you the exact prefix.
- **Import error "must be inside your own folder"**: the file is directly in
  `~/airflow-dags/`, not in `~/airflow-dags/<you>/`. Move it.
- **The DAG does not appear, and there is no import error**: wait 30 seconds and reload. Files
  are re-read every 30 seconds.
- **`build_summary` fails with "table must be lakehouse.analytics.u_<you>_..."**: `ME` still
  says `TODO-your-username`, or has capital letters.
- **"the DAG that wrote the table had no schedule"**: you triggered before TODO 3. Save the
  `@daily` version, wait for Airflow to show the schedule, and trigger again.
- **Copying someone else's DAG** into your folder: Airflow refuses it, because its dag_id has
  their prefix, not yours.

## Start again

`lab-tracks reset E3` drops your table `analytics.u_<you>_orders_summary`, deletes
`orders_summary_dag.py` and `jobs/orders_summary.py` from your DAG folder, and restores this
folder's original files. Airflow removes the DAG from its list within a minute; the history
of its old runs stays in Airflow.

## What's next

**E4 · Notebook to scheduled job to Spark batch job**: take a notebook you wrote by hand,
run it every day with papermill, then turn it into a Spark batch job.
