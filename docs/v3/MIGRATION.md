# V2 → V3 Migration

> Draft · 2026-09-25. V3 is a new stack, not an in-place upgrade. Migration copies data
> out of V2 and into V3, and V2 is left untouched until the user removes it.

## Principles

- **Never modify V2 volumes.** Migration only reads from them, so the user can always roll back by
  starting V2 again.
- **Side-by-side.** V3 installs into a new directory with its own named volumes and
  subdomains. Both stacks can run at once if the host has the RAM; otherwise stop V2 first.
- **Resumable and verified.** Every step records progress and checks counts and checksums
  before moving on.

## What moves

| V2 asset | V3 destination | How |
|---|---|---|
| MinIO buckets (raw files, Parquet) | SeaweedFS `landing` bucket | `rclone sync` (S3 → S3), then compare object counts and sizes |
| V2 Iceberg tables (path-based, if the Iceberg overlay was used) | Lakekeeper-registered tables | `register_table` for each table's current metadata file after the copy |
| Parquet/CSV datasets used as tables | Iceberg tables | Optional: `CREATE TABLE … AS SELECT` via Trino, or left as landing files |
| Postgres `lakehouse` analytics DB | Postgres in V3 (same DB name) | `pg_dump` / `pg_restore` |
| Airflow DAGs | V3 DAGs folder | Copy, then run a lint that flags Airflow 2 → 3 API breaks |
| Airflow metadata (run history) | — | Not migrated. Start fresh on Airflow 3 |
| Superset dashboards/charts | Superset 6 | Export/import bundles; database connections remapped to Trino |
| Jupyter notebooks | User's workspace home | Copy into `~/migrated-from-v2/` for the mapped user |
| Users and passwords | Keycloak | Users recreated from `provision-user.sh` records; everyone resets their password at first login |
| `.env` credentials | — | Not migrated. V3 uses SSO and credential vending |

## Steps (the `lakehouse migrate-from-v2` command)

1. **Preflight.** Find the V2 install, its volumes and MinIO credentials; estimate data size
   and check free disk.
2. **Snapshot.** Record bucket listings, row counts for Postgres tables, and Iceberg table
   snapshot IDs.
3. **Copy object data.** `rclone sync` MinIO → SeaweedFS, resumable, with a bandwidth cap option.
4. **Register tables.** Register copied Iceberg tables in Lakekeeper; list Parquet
   datasets and offer to convert them.
5. **Copy databases and assets.** Postgres dump/restore, DAGs, notebooks, Superset exports.
6. **Verify.** Compare step 2's snapshot with V3: object counts, row counts, and a sample
   query per table through Trino.
7. **Report.** A summary of what moved, what needs manual follow-up (e.g. DAG API changes),
   and how to remove V2 once the user is satisfied.

## Known gaps

- Airflow 2 DAGs that use removed APIs need hand edits; the lint lists them.
- Notebooks that hardcode MinIO endpoints or `minio123`-style keys must be updated to use
  the catalog. The lint flags them.
- Superset charts built on DuckDB or Spark SQL connections need re-pointing to Trino.
- Multi-TB migrations: plan for `rclone` throughput on local disk; the tool reports
  progress and can resume.
