# E2 · Table maintenance: snapshots, time travel, compaction, expiry

**Time:** about 45 minutes · **Profile:** `engineer` (or `full`) · **You need:** the
`engineer` or `lab-admin` group. E1 helps (you know what a snapshot is), but this module
creates its own table and does not need E1's.

## Goal

A table that is written to all day slowly gets into trouble: someone makes a mistake, the
data is spread over thousands of tiny files, and old versions pile up in storage. By the end
of this module you can **undo a bad change**, **read the table as it was**, **compact** small
files and **expire** old snapshots, and you know why each one matters.

You will learn:

- what a snapshot is and why it makes undo and time travel almost free;
- how to query an old version (`VERSION AS OF`) and why a snapshot is **not** a backup;
- how to roll back a bad write (`rollback_to_snapshot`);
- the *small files problem*, and how compaction (`rewrite_data_files`) fixes it;
- why you must **expire** snapshots (`expire_snapshots`), and what you lose when you do.

## Concepts (read this first, 5 minutes)

**A snapshot is a list of files.** Iceberg never changes a data file. Every commit writes
*new* files and a new **snapshot**: a small metadata file that lists every data file of the
table at that moment. The table's "current" pointer then moves to the new snapshot. The old
snapshot still lists the old files, so the old version is still complete.

```
  snapshot 1 ──► file A
  snapshot 2 ──► file A, file B            (an INSERT added B)
  snapshot 3 ──► file A', file B           (a DELETE rewrote A as A' without some rows)
                 ▲
            current pointer
```

That picture explains the whole module:

- **Time travel** = read the files an older snapshot lists (`VERSION AS OF <id>`).
- **Rollback** = move the current pointer back to an older snapshot. No data is copied.
- **Compaction** = write the same rows into fewer, bigger files, as a new snapshot
  (operation `replace`). Queries get faster; the data does not change.
- **Expiry** = forget old snapshots and delete the files that only they still use. This is
  the only step that frees storage, and it ends time travel to those snapshots.

**Procedures.** Maintenance jobs are Iceberg *procedures*, run from Spark with `CALL`:
`CALL lakehouse.system.<procedure>(...)`. The table name you pass has **no catalog part**:
`'eng_eddie.readings'`, not `'lakehouse.eng_eddie.readings'`.

**Why not keep every snapshot forever?** Because a deleted row is never really gone while an
old snapshot still points at its file: storage grows without end, and data you were asked to
delete (think personal data) is still readable with time travel. Real teams keep a few days
of history, then expire.

## Steps

Open `notebook.ipynb` in this folder and run the cells from top to bottom with
**Shift+Enter**. Each step here matches a heading in the notebook. Three cells are marked
**YOUR TURN**.

### 1. Connect and create the table

The cell opens a Spark session as you and creates `lakehouse.eng_<you>.readings` (sensor
readings: batch number, device, time, temperature). Expected:

```
ready: lakehouse.eng_eddie.readings
```

### 2. One hour of small batches

Twelve `INSERT`s of 100 rows, like a sensor job that writes every 5 minutes. Expected:

```
1200 rows
```

Run this cell **once**. Running it again adds another 1200 rows (see "Common mistakes").

### 3. Look at the history

```
+-----------------------+-------------------+---------+
|committed_at           |snapshot_id        |operation|
+-----------------------+-------------------+---------+
|2026-09-26 13:26:56.49 |2666056742001641252|append   |
|...                    |...                |append   |   (12 rows in all)
+-----------------------+-------------------+---------+
first snapshot: 2666056742001641252
data files now: 12
```

Twelve commits, twelve snapshots, twelve small files. Your ids and times differ.

### 4. Time travel (your turn)

The first cell reads the table as of the first snapshot: `rows_then` is **100** (only batch 1
existed then). **Your turn:** in the next cell, change

```sql
SELECT * FROM {table}   -- TODO: read the table as of the first snapshot
```

to

```sql
SELECT * FROM {table} VERSION AS OF {first_snapshot}
```

and run it. Expected: `100 rows (want 100)`. You just saved an old version into a **new
table**. Why bother? Because step 8 deletes the old snapshots, and with them the old version.
A snapshot is not a backup.

### 5. An accident

A cleanup job deletes every reading above 30 °C. Expected:

```
rows now: 872 | snapshot before the delete: 3117519442735059631
```

328 good rows are gone from the current version. The snapshot id printed is the last one
before the delete; it still lists the files with those rows.

### 6. Roll back (your turn)

Replace `TODO_SNAPSHOT_ID` with `{before_delete}` (the variable from step 5, inside the
f-string) and run the cell. Expected:

```
+--------------------+-------------------+
|previous_snapshot_id|current_snapshot_id|
+--------------------+-------------------+
|  257526259761400300|3117519442735059631|
+--------------------+-------------------+
rows now: 1200 (want 1200)
```

The rollback wrote no data: it only moved the current pointer back.

### 7. Compact the small files

`rewrite_data_files` reads the 12 small files and writes one bigger file. Expected (shortened):

```
|rewritten_data_files_count|added_data_files_count|...
|12                        |1                     |...
data files now: 1
```

The row count is still 1200. Only the layout changed.

### 8. Expire old snapshots

`expire_snapshots` with `older_than => current_timestamp()` and `retain_last => 1` keeps
only the current snapshot. Expected: one snapshot left, with operation `replace` (the
compaction). The next cell tries time travel to the first snapshot again:

```
as expected: Cannot find snapshot with ID 2666056742001641252
readings_first_batch still has 100 rows
```

History is gone, but the copy you made in step 4 is safe.

### 9. Check your work

Run the checkpoint cell, or in a terminal: `lab-tracks check E2`. A pass:

```
  PASS  the readings table exists: lakehouse.eng_eddie.readings
  PASS  all 12 batches are there, and the deleted readings are back: 1200 rows, 12 batches, 328 readings above 30 C
  PASS  the first batch is saved in its own table: 100 rows of batch 1
  PASS  small files are compacted: 1 data file(s) after rewrite_data_files
  PASS  old snapshots are expired: 1 snapshot(s) left, current operation: replace

E2: PASSED (5/5 checks, 2s)
```

Then run `s.stop()` to close your Spark session.

## Common mistakes

- **Order matters.** Expire (step 8) *before* rollback (step 6) and the snapshot you need is
  gone: the deleted rows are lost for good. That is the real-world lesson. Here, start again
  with `lab-tracks reset E2`.
- **Step 2 run twice**: 2400 rows, every batch twice. The checkpoint says "2400 rows in 12
  batches, want 1200 rows in 12 batches". Reset the module and run each cell once.
- **Step 4 without `VERSION AS OF`**: the copy has 1200 rows of all batches. Drop it with a
  plain `s.sql(f"DROP TABLE lakehouse.{ns}.readings_first_batch")` and run the cell again
  (`CREATE TABLE IF NOT EXISTS` never replaces an existing table).
- **`TODO_SNAPSHOT_ID` left as it is**: Spark says it cannot resolve `TODO_SNAPSHOT_ID`.
  Write `{before_delete}`, with the braces, inside the f-string.
- **Catalog name in a procedure**: `CALL ...('lakehouse.eng_eddie.readings', ...)` fails.
  Procedures take `'<namespace>.<table>'`, which is what `'{ns}.readings'` gives.
- **Session errors after an hour** (`NotAuthorized`, `token expired`): your Spark session
  carries your login token. Run the step 1 cell again for a new session.
- **Never** `DROP TABLE ... PURGE` in this lab. The catalog deletes a dropped table's files
  itself; Spark's `PURGE` fails after the table is gone. A plain `DROP TABLE` is right.

## Start again

`lab-tracks reset E2` drops `readings` and `readings_first_batch` in your namespace (and the
namespace itself if nothing else is left in it) and restores this folder's original files.

## What's next

**E3 · Your first Airflow DAG**: stop running things by hand. Write a pipeline that Airflow
runs for you every day.
