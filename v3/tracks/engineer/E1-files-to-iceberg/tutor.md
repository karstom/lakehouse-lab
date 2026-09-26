# Tutor notes · E1 Files to Iceberg with Spark

For the Phase 5 AI tutor and for human facilitators. Guide the learner to the answer; do not
paste the solution. The checkpoint output (`lab-tracks check E1`) says which step is wrong.

## Learning objectives

By the end the learner can:

1. Explain the difference between a data file (CSV, Parquet) and a table (Iceberg: files +
   metadata + a catalog entry).
2. Explain that a Spark Connect notebook is a client: the server does the work and cannot
   read the client's local files.
3. Choose column types deliberately and convert text data to them before writing.
4. Create a partitioned Iceberg table with hidden partitioning (`days(ts)`), and say why a
   day partition suits data that is queried by date.
5. Read a table's metadata tables (`.snapshots`, `.files`, `.partitions`) and relate
   snapshots to commits.
6. Query the same table from a second engine (Trino) and explain why that works (catalog).

## Prerequisites

- Group `engineer` or `lab-admin`; profile `engineer` or `full` (Spark exists only there).
- Knows how to run notebook cells. No Spark knowledge needed.

## Common mistakes and how to guide

| Symptom | Likely cause | Hint to give (in order, stop when they get it) |
|---|---|---|
| Checkpoint: "some rows are there twice" / 1600 or 2000 rows | Step 8 (or 6) run more than once | 1. "What does `append` do if you run it again?" 2. Look at `.snapshots`: more than 3 appends. 3. `DELETE FROM` the table, then load each file once. Name the idea: idempotent loads. |
| Checkpoint: no `day(shipped_at)` partitioning | Ran step 5 before editing the TODO; `IF NOT EXISTS` kept the old table | 1. "Does `CREATE TABLE IF NOT EXISTS` change a table that exists?" 2. Plain `DROP TABLE`, recreate, reload. |
| Columns are `varchar` | `createDataFrame(raw)` without schema/conversion | Ask what type pandas gave the columns in step 2; point at `schema=s.table(table).schema`. |
| `Path does not exist` | `spark.read.csv` on a home-folder path | Ask where the code runs (client vs server). Point at step 6's explanation. |
| `ForbiddenException` / `can_create_table` on `samples` | Wrote into a namespace that is not theirs | Use `lakehouse.{ns}` from step 3. Viewers and analysts cannot write with Spark at all. |
| `NotAuthorizedException` / expired token after ~1 h | Spark session token expired | `s = spark("E1")` again (sessions carry the user's token, about 1 h). |
| `ModuleNotFoundError: trackcheck` | Notebook moved out of the module folder, or step 3 skipped | Run cells in order from the module folder. |
| Wants `DROP TABLE ... PURGE` | Habit from other Spark setups | Never in this lab: the catalog deletes the data; Spark's client-side purge fails. |
| 3 partitions but total weight wrong | Converted `weight_kg` with rounding or `int` | Compare with step 2's raw text; use `float64`. |

## Hints ladder for the two YOUR TURN cells

- Step 5: "Where in the CREATE TABLE statement does partitioning go?" → "Iceberg has transforms
  like `days(...)`, `months(...)`" → the exact line `PARTITIONED BY (days(shipped_at))`.
- Step 8: "Which function loads one file?" → "Call it once per remaining file" → two calls.

## Questions to check understanding

- Why does a query for one day read less data from this table than from one big CSV?
- If you delete `data/` now, is the table affected? (No: the table's files are in object
  storage, managed through the catalog.)
- Where did the 3 snapshots come from?
- Why can Trino read a table Spark wrote?

## Facts the tutor can rely on

- Table: `lakehouse.eng_<user>.shipments`, 1200 rows, 1200 distinct `shipment_id`, 3 days
  (2026-03-01..03), total `weight_kg` 21041.41, partitioning `day(shipped_at)`.
- `make_data.py` is deterministic; rerunning rewrites identical files.
- `lab-tracks reset E1` drops the table (and the namespace if empty) and deletes `data/`.
