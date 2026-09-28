# Moving from V2 to V3

V3 is a new stack, not an in-place upgrade, and there is no migration tool. You copy your
files out of V2's MinIO into V3's storage, then load the datasets you want as Iceberg tables.
Everything else starts fresh.

V2 is only ever read. Leave it running until you are happy with V3; you can always go back
to it.

The commands below were run end to end against a throwaway MinIO with synthetic data. The
scripts and results are in [`v3/tests/migration/`](../v3/tests/migration/).

## What moves, and how

| From V2 | To V3 | How |
|---|---|---|
| MinIO buckets (CSV, Parquet, anything) | SeaweedFS bucket `landing`, under `v2/<bucket>/` | `rclone copy` (steps 1–4) |
| Datasets you want to query | Iceberg tables, e.g. `lakehouse.v2.trips` | A notebook in your workspace (step 6) |
| Postgres `lakehouse` database | A dump you keep, plus CSVs of the tables you need | [Optional](#postgres) |
| Notebooks and DAGs | `~/migrated-from-v2/` in a user's workspace | [Optional](#notebooks-and-dags) |
| Superset dashboards | Superset 6 | [Optional](#superset-dashboards), re-pointed at Trino |

These are **not** migrated:

- **Users and passwords.** Create the users in Keycloak and add them to groups.
- **V2's `.env` credentials.** V3 uses single sign-on and the catalog hands out storage access.
- **Airflow run history.**
- **Services V3 doesn't have** (LanceDB, Vizro, Homepage, Portainer). If you need their
  data, back up their volumes.

## Before you start

- Install V3 **next to** V2, in a new directory (see the [README](../README.md)). Any
  profile works. The Spark example in step 6 needs `engineer` or `full`.
- You need **Docker 25 or newer** (`docker version`): the copy container joins V2's and
  V3's networks at the same time.
- You need enough free disk for a second copy of your data. Step 2 shows its size.
- The examples use these names. Change them to match your machine:

```bash
V2_ENV=~/lakehouse-lab/.env        # V2's .env (MINIO_ROOT_USER, MINIO_ROOT_PASSWORD)
V3_DIR=~/lakehouse-lab-v3/v3       # the v3/ folder of your V3 install
V2_NET=lakehouse-lab_lakehouse     # V2's network:  docker network ls | grep lakehouse
V3_NET=lakehouse_lab               # <COMPOSE_PROJECT_NAME>_lab, see $V3_DIR/.env
```

**About credentials.** V2's MinIO root key and V3's SeaweedFS admin key can both read and
change everything. Keep them in one file that only you can read (mode 600), and hand that
file to Docker with `--env-file`. Never type a key on a command line (it shows up in `ps`
and in your shell history), and never put the admin key in a notebook. Step 5 creates a
separate, read-only key for notebooks. Delete everything at the end (step 7).

## 1. Create the credentials file

```bash
mkdir -p ~/lab-migration && chmod 700 ~/lab-migration
envget() { sed -n "s/^$2=//p" "$1" | tail -n 1 | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/"; }
( umask 077
  cat > ~/lab-migration/rclone.env <<EOF
RCLONE_CONFIG_V2_TYPE=s3
RCLONE_CONFIG_V2_PROVIDER=Minio
RCLONE_CONFIG_V2_ENDPOINT=http://minio:9000
RCLONE_CONFIG_V2_ACCESS_KEY_ID=$(envget "$V2_ENV" MINIO_ROOT_USER)
RCLONE_CONFIG_V2_SECRET_ACCESS_KEY=$(envget "$V2_ENV" MINIO_ROOT_PASSWORD)
RCLONE_CONFIG_V3_TYPE=s3
RCLONE_CONFIG_V3_PROVIDER=SeaweedFS
RCLONE_CONFIG_V3_ENDPOINT=http://seaweedfs:8333
RCLONE_CONFIG_V3_ACCESS_KEY_ID=$(envget "$V3_DIR/.secrets.env" SEAWEEDFS_ADMIN_ACCESS_KEY)
RCLONE_CONFIG_V3_SECRET_ACCESS_KEY=$(envget "$V3_DIR/.secrets.env" SEAWEEDFS_ADMIN_SECRET_KEY)
EOF
)
```

If V2's `.env` has no `MINIO_ROOT_USER`, V2 used `minio`. Put that in the file by hand.

Then define `rc`, which runs a pinned rclone on both networks:

```bash
. "$V3_DIR/versions.env"
rc() { docker run --rm --network "$V2_NET" --network "$V3_NET" --env-file ~/lab-migration/rclone.env \
         "rclone/rclone:${RCLONE_IMAGE_TAG}@${RCLONE_IMAGE_DIGEST}" --config "" "$@"; }
```

If V2 runs on **another machine**, drop `--network "$V2_NET"` and set the endpoint in the
file to `http://<v2-host>:9000`. This variant was not part of the tested run.

## 2. Look at what V2 has

```bash
rc lsd v2:              # the buckets
rc size v2:lakehouse    # object count and size of one bucket
```

## 3. Copy into `landing`

Each V2 bucket goes to `landing/v2/<bucket>/`, a clearly named place of its own. Nothing is
ever copied into `warehouse`: that bucket belongs to the catalog.

```bash
rc mkdir v3:landing
for b in $(rc lsf --dirs-only v2: | tr -d /); do
  echo "--- copying $b"
  rc copy "v2:$b" "v3:landing/v2/$b" --transfers 8 --stats 30s --stats-one-line --stats-log-level NOTICE
done
```

Use `copy` only, never `sync` or `move`: those can delete files. If the copy is interrupted,
run the same loop again. It only transfers what is missing. For a multi-TB copy, add
`--bwlimit 50M` to leave bandwidth for other work.

## 4. Check the copy

```bash
for b in $(rc lsf --dirs-only v2: | tr -d /); do
  echo "== $b"
  rc size "v2:$b" --json; rc size "v3:landing/v2/$b" --json     # the same count and bytes
  rc check "v2:$b" "v3:landing/v2/$b" --one-way                  # "0 differences found"
done
```

- `rc check` compares sizes, and MD5s where both sides know them. A line like **`N hashes
  could not be checked`** means that for N files only the size was compared. This happens
  with large files that V2's tools uploaded in parts. To compare those byte for byte, run
  the check again with `--download` (it reads the data on both sides):
  `rc check "v2:big-files" "v3:landing/v2/big-files" --one-way --download`.
- **Empty "folders"** made in the MinIO Console are not copied. They hold no data.
- Keys with spaces, `#`, `%`, `&`, `+`, `?`, `*`, quotes, tabs or non-Latin characters copy
  unchanged. `rc` shows a tab as `␉`, but the key itself still contains the tab.

## 5. A read-only key for loading

The notebook in step 6 needs to read `landing`, but it must not get the admin key. Create an
identity that can only read and list `landing`. The keys are passed on standard input, so
they stay off every command line. Use `<COMPOSE_PROJECT_NAME>-seaweedfs-1` as the container
name (the default is shown):

```bash
AK=landing$(openssl rand -hex 8); SK=$(openssl rand -hex 24)
printf 's3.configure -user=landing-reader -actions=Read,List -buckets=landing -access_key=%s -secret_key=%s -apply\n' "$AK" "$SK" |
  docker exec -i lakehouse-seaweedfs-1 weed shell >/dev/null
( umask 077; printf 'access key: %s\nsecret key: %s\n' "$AK" "$SK" > ~/lab-migration/landing-reader.txt )
```

With this key a notebook can read `landing`. It is refused when it tries to write there,
or to list or read the `warehouse` bucket (tested). The identity survives restarts, so
remove it when you are done (step 7).

## 6. Load datasets as Iceberg tables

This works like engineer track module [E1](../v3/tracks/engineer/E1-files-to-iceberg/README.md):

- decide on the column types once, in the table definition;
- load one file at a time with `createDataFrame(..., schema=<the table's schema>)`;
- commit with `writeTo(table).append()`;
- check the result.

Only the source is different: the files come from `landing` instead of your home folder.

Log in to `jupyter.<your lab domain>` **as a lab admin**, open a notebook and run these
cells. The example is a V2 folder of Parquet files, `raw-data/trips/…`.

```python
# 1. Open landing with the read-only key (step 5); paste the key when asked.
import getpass
from pyarrow import fs

landing = fs.S3FileSystem(
    access_key=input("landing-reader access key: "),
    secret_key=getpass.getpass("landing-reader secret key: "),
    endpoint_override="http://seaweedfs:8333",
    region="us-east-1")
```

```python
# 2. The table: your types, partitioned by day (profile engineer or full).
from lakehouse import spark

s = spark("migrate trips")
s.sql("CREATE NAMESPACE IF NOT EXISTS lakehouse.v2")
table = "lakehouse.v2.trips"
s.sql(f"""
CREATE TABLE IF NOT EXISTS {table} (
    trip_id     BIGINT,
    vendor      STRING,
    pickup_at   TIMESTAMP_NTZ,
    dropoff_at  TIMESTAMP_NTZ,
    distance_km DOUBLE,
    fare        DOUBLE)
USING iceberg
PARTITIONED BY (days(pickup_at))
""")
```

```python
# 3. Load every file, one commit per file.
import pandas as pd

def load_file(path):
    """Read one Parquet file from landing, keep the table's columns, append it."""
    with landing.open_input_file(path) as f:
        pdf = pd.read_parquet(f, columns=s.table(table).columns)
    df = s.createDataFrame(pdf, schema=s.table(table).schema)
    df.writeTo(table).append()
    return len(pdf)

files = sorted(i.path for i in landing.get_file_info(
    fs.FileSelector("landing/v2/lakehouse/raw-data/trips", recursive=True))
    if i.path.endswith(".parquet"))
for path in files:
    print(path, load_file(path), "rows")
print("the table now has", s.table(table).count(), "rows")
```

```python
# 4. Check it from Trino: compare with a count/sum you took in V2.
from lakehouse import trino_connection

cur = trino_connection().cursor()
cur.execute("SELECT count(*), round(sum(fare), 2) FROM lakehouse.v2.trips")
print(cur.fetchall())
```

For CSV files, read with `pd.read_csv(f, dtype=str)`, then convert the columns as E1 does.

The rows pass through your notebook. The tested files had 100,000 rows each. For very large
files, read them in batches and append each batch.

A Spark session keeps its token for at least 30 minutes. For a longer load, call `spark()`
again to get a new session.

**Profile `core` (no Spark):** create the table in Trino and append with PyIceberg.

```python
import pyarrow.csv as pacsv
from lakehouse import catalog, trino_connection

cur = trino_connection().cursor()
cur.execute("CREATE SCHEMA IF NOT EXISTS lakehouse.v2"); cur.fetchall()
cur.execute("""
CREATE TABLE IF NOT EXISTS lakehouse.v2.orders (
    order_id   BIGINT,
    customer   VARCHAR,
    order_date DATE,
    amount     DECIMAL(12, 2),
    status     VARCHAR)"""); cur.fetchall()

tbl = catalog().load_table("v2.orders")
schema = tbl.schema().as_arrow()
with landing.open_input_stream("landing/v2/lakehouse/raw-data/sample_orders.csv") as f:
    data = pacsv.read_csv(f, convert_options=pacsv.ConvertOptions(column_types=schema))
tbl.append(data.select(schema.names).cast(schema))
```

PyIceberg in the workspace cannot write to a table partitioned by a transform such as
`month(...)`: it fails with "pyiceberg_core needs to be installed". Use Spark for those
tables, or leave small tables unpartitioned.

**Iceberg tables from V2** (the `iceberg-warehouse/` overlay) cannot be registered in V3.
Their metadata points at V2's paths. While V2 still runs, write each table you want to keep
out as Parquet, for example
`spark.table("iceberg.db.t").write.parquet("s3a://lakehouse/export/db/t")`. Then copy it
and load it like any other Parquet. This was not part of the tested run.

## 7. Clean up

```bash
printf 's3.configure -user=landing-reader -delete -apply\n' | docker exec -i lakehouse-seaweedfs-1 weed shell >/dev/null
rm -r ~/lab-migration      # the keys, and any dump you did not move somewhere safe
```

- `landing/v2/` stays in V3 for as long as you want it.
- Once everything you need is in V3, stop V2 with `docker compose down`, **without `-v`**.
  That keeps V2's volumes, so you can still go back. Delete them only when you are sure.

## Optional steps

### Postgres

Take a full dump of V2's `lakehouse` database for safekeeping (a read-only operation on
V2):

```bash
docker exec lakehouse-lab-postgres-1 pg_dump -U postgres -Fc lakehouse > ~/lab-migration/v2-lakehouse.dump
```

V3's Postgres runs the platform (Keycloak, the catalog, Airflow, Superset). Don't restore
your data into it. Instead, move the tables you need into the lakehouse: copy each one as a
CSV into `landing`, then load it as in step 6.

```bash
docker exec lakehouse-lab-postgres-1 psql -U postgres -d lakehouse -c "\copy customers TO STDOUT WITH (FORMAT csv, HEADER)" |
  docker run --rm -i --network "$V2_NET" --network "$V3_NET" --env-file ~/lab-migration/rclone.env \
    "rclone/rclone:${RCLONE_IMAGE_TAG}@${RCLONE_IMAGE_DIGEST}" --config "" rcat v3:landing/v2/postgres/customers.csv
```

### Notebooks and DAGs

A user's V3 home folder is the Docker volume `<COMPOSE_PROJECT_NAME>-home-<username>`. It
exists after that user's first login. The commands below copy V2's shared notebooks and
DAGs into it, under `~/migrated-from-v2/`, as the workspace user (1000:100), so the user
owns the files. V2's volumes are mounted read-only.

```bash
IMG="rclone/rclone:${RCLONE_IMAGE_TAG}@${RCLONE_IMAGE_DIGEST}"   # any image with sh and cp
docker run --rm --user 1000:100 -v lakehouse-lab_jupyter_notebooks:/from:ro -v lakehouse-home-alice:/to \
  --entrypoint sh "$IMG" -c 'mkdir -p /to/migrated-from-v2/notebooks && cp -R /from/. /to/migrated-from-v2/notebooks/'
docker run --rm --user 1000:100 -v lakehouse-lab_airflow_dags:/from:ro -v lakehouse-home-alice:/to \
  --entrypoint sh "$IMG" -c 'mkdir -p /to/migrated-from-v2/dags && cp -R /from/. /to/migrated-from-v2/dags/'
```

If you used V2's multi-user JupyterHub, each user's files are in
`lakehouse-lab_jupyterhub_users`. Copy one folder per user the same way.

Before you use the copied notebooks, fix two things:

- Notebooks that set a MinIO endpoint or keys must read tables through the catalog instead.
  See `from lakehouse import spark, trino_connection, duckdb_connect` in any track notebook.
- `minio:9000` paths become table names.

**DAGs: from Airflow 2 to 3.** Don't copy DAGs straight into `~/airflow-dags/`. Fix them in
`~/migrated-from-v2/dags/` first, then move them. Module [E3](../v3/tracks/engineer/E3-your-first-dag/README.md)
shows what a V3 DAG looks like. Check each DAG for these changes:

- **Imports.** `PythonOperator` and `BashOperator` now come from
  `airflow.providers.standard.operators.*`. `DummyOperator` is now `EmptyOperator`. Import
  `DAG` and `task` from `airflow.sdk`. `airflow.contrib` is gone.
- **Schedule.** `schedule_interval=` and `timetable=` became `schedule=`, and `catchup` now
  defaults to `False`.
- **Context.** `execution_date`, `next_ds`, `prev_ds`, `tomorrow_ds` and `yesterday_ds` were
  removed. Use `logical_date` or the data interval. `days_ago()` was removed too.
- **Removed features.** SubDAGs and SLAs no longer exist. Datasets are now called Assets.
- **No database access from tasks.** Tasks can no longer open Airflow's metadata database
  (`settings.Session`, `@provide_session` inside a task).
- **Hard-coded storage.** MinIO endpoints and keys have no V3 equivalent. Read and write
  tables through the catalog.

This checklist was not run against real V2 DAGs. The tested run only copied the files.

### Superset dashboards

This section was not part of the tested run.

1. In V2, go to **Dashboards**, select the dashboards, then **Export**. You get a ZIP file.
2. In V3's Superset, go to **Dashboards → Import**.
3. The exported datasets point at V2's databases (DuckDB, Postgres). In V3 every dataset
   reads from Trino (`lakehouse`), so edit each dataset to use Trino and the new table
   names.

V2 ran `apache/superset:latest`, so an export may not import into Superset 6. If it doesn't,
rebuild the charts on the new tables. That is usually quick.

## If something goes wrong

Nothing here changes V2. To start the move over, remove what you added to V3:

- the `landing-reader` identity (step 7);
- `landing/v2/…`: `rc purge v3:landing/v2`;
- tables: `DROP TABLE lakehouse.v2.<name>` in Trino.

Then repeat from step 3.
