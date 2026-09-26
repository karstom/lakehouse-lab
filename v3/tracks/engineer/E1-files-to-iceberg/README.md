# E1 · Files to Iceberg with Spark

**Time:** about 45 minutes · **Profile:** `engineer` (or `full`) · **You need:** to be in the
`engineer` or `lab-admin` group, and your workspace open at `jupyter.<your lab domain>`.

## Goal

A delivery partner sends you one CSV file per day. By the end of this module those files are
**one Iceberg table**, with real column types and one partition per day, that anyone in the
lab can query from Spark, Trino, DuckDB or Superset.

You will learn:

- why a folder of CSV files is not yet a table, and what Iceberg adds;
- how Spark Connect works (your notebook is a client, the cluster does the work);
- how to give data **types** on the way in, and why that must be deliberate;
- what **partitioning** is, and how Iceberg's *hidden partitioning* works;
- that every write is a **snapshot**, which you can look at like a table.

## Concepts (read this first, 5 minutes)

**File vs. table.** A CSV file is just text: no types, no rules about what may be in it, and
no record of what changed. A *table format* such as **Apache Iceberg** keeps data in
efficient Parquet files and adds **metadata** next to them: the schema (column names and
types), the partitioning, and the list of files that make up each version of the table.

**Catalog.** Engines find Iceberg tables through a **catalog** (here: Lakekeeper, at
`lakehouse`). The catalog knows where every table is and who may read or change it. Because
Spark, Trino and DuckDB all ask the same catalog, a table you write with Spark is immediately
readable in Trino. Names have three parts: `lakehouse.<namespace>.<table>`.

**Your namespace.** A namespace groups tables, like a folder. In this track you work in
your own: `eng_<your username>` (for example `eng_eddie`). The notebook works out the name
for you.

**Spark Connect.** Spark runs as a shared server in the lab. Your notebook opens a
*session* on it with `spark()`, as **you**: the catalog checks your permissions on every
table. Your notebook only sends instructions; the server reads and writes the data. One
consequence you will meet in step 6: **the server cannot see the files in your home folder.**

**Types.** When you read a CSV, everything is text. You decide the types (`BIGINT`,
`DOUBLE`, `TIMESTAMP_NTZ`...) once, in the table definition, and convert the data to match.
Get this wrong and every later query pays for it: text sorts `"10" < "9"`, and you cannot sum
it.

**Partitioning.** A partitioned table stores its rows in groups by a value, here the **day**
a parcel shipped. A query for one day then reads one group and skips the rest. Iceberg's
*hidden partitioning* computes the day from `shipped_at` itself: you never add a separate
`ship_date` column, and a query that filters on `shipped_at` gets the speed-up without
knowing the table is partitioned.

**Snapshots.** Every write (a *commit*) creates a new **snapshot**: a complete, consistent
version of the table. Readers never see half a write. Module E2 is all about snapshots.

## Steps

Open `notebook.ipynb` in this folder (double-click it in the file browser on the left). Run
the cells from top to bottom with **Shift+Enter**. Each step below matches a heading in the
notebook.

### 1. Create the input files

Run the first code cell. `make_data.py` writes three files into `data/`. Expected output:

```
wrote data/shipments_2026-03-01.csv (400 rows)
wrote data/shipments_2026-03-02.csv (400 rows)
wrote data/shipments_2026-03-03.csv (400 rows)
```

### 2. Look at a raw file

The cell reads one file with pandas, *as text*, and shows its first rows:

```
  shipment_id orderkey carrier           shipped_at weight_kg      status
0      100001    54626     DPD  2026-03-01 11:23:28     28.85   delivered
1      100002    25319  PostNL  2026-03-01 16:57:54     27.43   delivered
```

Every column's type is text (`str`). That is the point: types are your decision.

### 3. Connect to Spark

```
Spark 4.1.3 | you are eddie | your namespace: eng_eddie
```

(with your own name). If this cell fails, see "Common mistakes" below.

### 4. Create your namespace

`CREATE NAMESPACE IF NOT EXISTS lakehouse.eng_<you>`. The list printed afterwards shows every
namespace you can see, yours included.

### 5. Create the table (your turn)

The cell creates `lakehouse.eng_<you>.shipments` with a column type for each field. **Your
turn:** replace the line `-- TODO: partition by the day of shipped_at` with

```sql
PARTITIONED BY (days(shipped_at))
```

and run the cell. The printed definition must contain `PARTITIONED BY (days(shipped_at))`.

Why `TIMESTAMP_NTZ`? The file gives local times with no time zone ("NTZ" = no time zone).
Storing them as written avoids silent shifts by a server's time zone.

### 6. Load the first file

`load_file()` reads a CSV with pandas, converts each column to its type, and sends the rows to
Spark with `createDataFrame`, then `writeTo(table).append()` commits them. Expected:

```
loaded 400 rows; the table now has 400 rows
```

Why not `spark.read.csv("data/...")`? That path would be read **on the Spark server**, where
your home folder does not exist ("Path does not exist"). Sending the rows from the notebook
works for small files like these. In production, files land in object storage first, and the
cluster reads them there.

### 7. What did Iceberg write?

Append `.snapshots`, `.files` or `.partitions` to a table name to read its metadata:

```
+-------------------+---------+----------+
|snapshot_id        |operation|added_rows|
+-------------------+---------+----------+
|2326046722305522228|append   |400       |
+-------------------+---------+----------+
+------------+------------+----------+
|partition   |record_count|file_count|
+------------+------------+----------+
|{2026-03-01}|400         |1         |
+------------+------------+----------+
```

One commit, one snapshot, one partition (your snapshot id will differ).

### 8. Load the other two days (your turn)

Add one `load_file(...)` call for each of the files of 2026-03-02 and 2026-03-03, then run
the cell **once**. Expected:

```
the table now has 1200 rows (want 1200)
+------------+------------+
|partition   |record_count|
+------------+------------+
|{2026-03-01}|400         |
|{2026-03-02}|400         |
|{2026-03-03}|400         |
+------------+------------+
```

### 9. Query it with Spark and with Trino

Parcels per carrier with Spark, then the same table joined with `lakehouse.samples.orders`
in Trino, which shows that the table lives in the catalog, not in Spark:

```
+-------+-------+------+
|carrier|parcels|avg_kg|
+-------+-------+------+
|  FedEx|    259|  17.7|
| PostNL|    252|  17.1|
...
['1-URGENT', 192]
['2-HIGH', 224]
```

### 10. Check your work

Run the checkpoint cell, or in a terminal (**File > New > Terminal**):

```
lab-tracks check E1
```

A pass looks like this:

```
  PASS  your namespace exists: lakehouse.eng_eddie
  PASS  the shipments table exists: lakehouse.eng_eddie.shipments
  PASS  columns have real types (not all strings): shipment_id bigint, ...
  PASS  the table is partitioned by day of shipped_at: partitioning = day(shipped_at)
  PASS  all three files are loaded, each exactly once: 1200 rows, 1200 shipments, 3 days, ...
  PASS  one partition per day: 3 partitions

E1: PASSED (6/6 checks, 2s)
```

A failed check prints a `hint:` line that tells you what to do. Finally run `s.stop()`.

## Common mistakes

- **A file loaded twice.** Running the step 8 cell twice appends the same rows again (1600 or
  2000 rows). The checkpoint says "some rows are there twice". Fix: delete the rows and load
  each file once:
  `s.sql(f"DELETE FROM {table}")`, then run steps 6 and 8 again. (Or start over with
  `lab-tracks reset E1`.) In production you make loads *idempotent*, so a rerun cannot
  duplicate data; you will see `CREATE OR REPLACE` do that in E3.
- **No partitioning.** You ran step 5 before editing the TODO. `CREATE TABLE IF NOT EXISTS`
  does not change an existing table, so drop it first with a plain
  `s.sql(f"DROP TABLE {table}")`, then run steps 5, 6 and 8 again.
- **Everything is a string.** Passing the raw pandas frame (all text) with no schema creates
  text columns. Always pass `schema=s.table(table).schema`, and convert the columns first.
- **"Path does not exist"** from `spark.read.csv`: the Spark server cannot read your home
  folder (step 6).
- **Session errors after an hour** (`NotAuthorized`, `token expired`): a Spark session
  carries your login token, which lasts about an hour. Run `s = spark("E1")` again.
- **Never** `DROP TABLE ... PURGE` in Spark. The lab's catalog deletes the data of a dropped
  table itself; Spark's `PURGE` tries to delete the files from the client side after the
  table is gone, and fails. A plain `DROP TABLE` is right.

## Start again

`lab-tracks reset E1` drops your `shipments` table (and your namespace, if it is then empty),
deletes `data/`, and restores this folder's original files.

## What's next

**E2 · Table maintenance**: undo a bad delete with snapshots, compact small files and clean
up old snapshots.
