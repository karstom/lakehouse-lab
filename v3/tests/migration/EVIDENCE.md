# Migration guide: proof runs

2026-09-27, on the dev host (Docker 29.1, API 1.52). Throwaway V3 install: project
`v3-p6-migration`, profile `engineer`, seeded test users. Throwaway V2: `minio/minio`
`RELEASE.2024-12-18T13-15-44Z` (V2's release) and `postgres:${POSTGRES_VERSION}`, on network
`v3-p6-migration-v2src`. rclone `1.75.1` by digest. The production V2 on the same host was
never used. Every run used the mock AI model only; `engineer` has no AI.

Host names and addresses are left out on purpose.

## Runs

| Run | What | Result |
|---|---|---|
| 1 | Clean V3 (`./lab reset --yes`, then `./install.sh --non-interactive`), then `tests/migration/run.sh all` | **ALL_RC=0** in 3 min 29 s (18:15:20 to 18:18:49 UTC). Every step passed |
| 2 | `run.sh all` again on the same install, with the final scripts (only a variable rename and two `\|\| return 1` changed since run 1) | **ALL_RC=0** in 2 min 28 s. The re-seeded 300 MiB object had new content and was copied again; the unchanged files were skipped |
| 3 | `./lab test` (the smoke test) on the same install after both runs | See "The lab still passes its smoke test" below |

Development runs before these found two things, both now in the guide:
- PyIceberg cannot write to a table partitioned by `month(...)`: pyiceberg-core is missing
  from the workspace image.
- Keys with a tab are shown as `␉` by rclone, but they are stored unchanged.

## Synthetic V2 content (`seed`)

```
{"orders": {"rows": 5000, "amount_sum": 403548.67}, "trips": {"rows": 300000, "fare_sum": 5406552.26},
 "weird_keys": 6, "report_files": 60, "big_bytes": 314572800}
buckets: analytics-exports, big-files, lakehouse
```

In the throwaway V2:

- `big-files` holds `backups/blob-300MiB.bin`, uploaded by rclone in parts, and
  `exports/from-mc-150MiB.bin`, uploaded by MinIO's `mc pipe` (in parts, no MD5).
- `lakehouse` has an empty Console-style folder, `raw-data/empty-folder/`.
- The notebook volume holds `examples/sub dir/Analysis (v2) ü.ipynb` and `helpers.py`,
  owned by 1000:100.
- The DAG volume holds `v2_example_dag.py`, owned by 50000:0.
- Postgres has `lakehouse.public.customers` with 1,000 rows.

## Copy and check (guide steps 1–4), run 1

```
-rw------- …/out/lab-migration/rclone.env
--- copying analytics-exports
NOTICE:     2.074 KiB / 2.074 KiB, 100%, 2.073 KiB/s, ETA 0s
--- copying big-files
NOTICE:       450 MiB / 450 MiB, 100%, 113.327 MiB/s, ETA 0s
--- copying lakehouse
NOTICE:     8.583 MiB / 8.583 MiB, 100%, 0 B/s, ETA -
copy took 13s
--- re-run (resume check: nothing left to transfer)
INFO  : There was nothing to transfer      (x3)

== analytics-exports
  V2: {"count":60,"bytes":2124,"sizeless":0}
  V3: {"count":60,"bytes":2124,"sizeless":0}
NOTICE: S3 bucket landing path v2/analytics-exports: 0 differences found
NOTICE: S3 bucket landing path v2/analytics-exports: 60 matching files
== big-files
  V2: {"count":2,"bytes":471859200,"sizeless":0}
  V3: {"count":2,"bytes":471859200,"sizeless":0}
NOTICE: S3 bucket landing path v2/big-files: 0 differences found
NOTICE: S3 bucket landing path v2/big-files: 1 hashes could not be checked
NOTICE: S3 bucket landing path v2/big-files: 2 matching files
== lakehouse
  V2: {"count":10,"bytes":8999450,"sizeless":0}
  V3: {"count":10,"bytes":8999450,"sizeless":0}
NOTICE: S3 bucket landing path v2/lakehouse: 0 differences found
NOTICE: S3 bucket landing path v2/lakehouse: 10 matching files
--- special-character keys, as listed in V3:
100% & more+plus=eq.txt
café ☕ #1 (copy).csv
deep/er/est/ümlaut ñ 日本語.txt
question?mark*star@at!bang.txt
semi;colon,comma'quote.json
tab␉here and  double  spaces.txt
--- the large objects: MD5 as each side reports it (empty = not known without reading)
                                  exports/from-mc-150MiB.bin        (V2: mc upload, no MD5)
358f669d479fbb920a100283c523b5fe  backups/blob-300MiB.bin
1eafbc6ee819037213bcec8cdbe35cf1  exports/from-mc-150MiB.bin        (V3)
358f669d479fbb920a100283c523b5fe  backups/blob-300MiB.bin
--- byte-for-byte check of big-files (guide: check --download)
NOTICE: S3 bucket landing path v2/big-files: 0 differences found
NOTICE: S3 bucket landing path v2/big-files: 2 matching files
--- the empty folder marker (not copied: no data)
V2: empty-folder/ trips/ weird names/      V3: trips/ weird names/
VERIFY: PASS
```

`fs.ls` in `weed shell` and `mc ls --json` both showed the tab key with a real tab byte
(`t a b \t h e r e …`). rclone only displays it as `␉`.

## Read-only key, Postgres, files (guide step 5 and the optional sections)

```
landing-reader created; key in …/out/lab-migration/landing-reader.txt (600)
9284 bytes …/out/lab-migration/v2-lakehouse.dump
3420; 0 16385 TABLE DATA public customers postgres
customers.csv in landing: 1000 rows (V2 table: 1000)
POSTGRES: PASS
-rw-r--r--    1 1000     100             76 ./dags/v2_example_dag.py
-rw-r--r--    1 1000     100             66 ./notebooks/examples/sub dir/Analysis (v2) ü.ipynb
-rw-r--r--    1 1000     100              9 ./notebooks/helpers.py
```

In a development run, the `landing-reader` identity survived a restart of the `seaweedfs`
container: the filer keeps it in the data volume. The static admin identity kept working
next to it, and so did the credentials Lakekeeper vends (Trino read the loaded tables).

## Load as Iceberg tables (guide step 6), in alice's own workspace, run 2

```
landing/v2/lakehouse/raw-data/trips/year=2025/month=01/part-0.parquet: 100000 rows
landing/v2/lakehouse/raw-data/trips/year=2025/month=02/part-0.parquet: 100000 rows
landing/v2/lakehouse/raw-data/trips/year=2025/month=03/part-0.parquet: 100000 rows
the table now has 300000 rows
appended 5000 rows
spark_trips:            spark_count 300000, partitions 84 (days(pickup_at): 28 days x 3 months)
trino_pyiceberg_orders: appended 5000 (unpartitioned; Trino CREATE TABLE, PyIceberg append)
trino_verify:           trips 300000 / sum(fare) 5406552.26, orders 5000 / sum(amount) 403548.67
                        -> matches_source: true (equal to make_data.py's sums)
landing_key_scope:      write landing   -> denied (ACCESS_DENIED)
                        list warehouse  -> denied (ACCESS_DENIED during ListObjectsV2)
                        read a warehouse data file -> denied
home:                   files [dags/v2_example_dag.py, notebooks/examples/sub dir/Analysis (v2) ü.ipynb,
                        notebooks/helpers.py], not_owned [], writable true
LOAD: PASS
```

## Clean-up (guide step 7) and reset

```
InvalidAccessKeyId
StatusCode: 403
READER-DELETE: PASS (the deleted key is refused)
source-down: left over (should be empty above)   <- no container or volume labelled lab.test=migration
```

## The lab still passes its smoke test

Run 3 was `./lab test` on the same install, after runs 1 and 2. Both runs had created and
deleted the `landing-reader` identity, and the install still held `landing/` and the
`lakehouse.v2.*` tables:

```
SMOKE: PASS (15/15, 3 skipped: 13.airflow_spark_batch_outlives_token,14.superset_user_identity_and_dashboard,18.ai_assist_…)
```

The three skips are expected: check 13 is the slow `--long` check, and checks 14 and 18 run
only on profile `full`. The checks that passed include 4 (PyIceberg with vended credentials,
refused on a sibling prefix), 6 (no static S3 key in Trino) and 10 (Spark Connect as alice).

## Docker safety

- Every object the test created is named `v3-p6-migration-v2src*` and labelled
  `lab.test=migration`. `source-down` removes them.
- At the end, the V3 install was removed with `./lab reset --all --yes`, and its directory
  was deleted. No container, volume or network of `v3-p6-migration*` was left.
- The first audit found three anonymous volumes. The throwaway Postgres had created them for
  its data directory, and `docker rm -f` had kept them. They were removed, and
  `source-down` now uses `docker rm -f -v`. A separate check (start the same image, then
  `rm -f -v`) left the volume count unchanged (45 → 46 → 45).
- The lists of non-`v3-` containers (ID, name, image, created), volumes and networks on the
  host, taken before the work and after the clean-up, are **identical**. The production
  `lakehouse-lab` project was never addressed, and `v3-p1` (27 containers) was left alone.
