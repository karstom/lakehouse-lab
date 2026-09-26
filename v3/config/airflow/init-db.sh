#!/bin/bash
# One-shot `airflow-db` (compose/airflow.yaml): Airflow's metadata database in the shared
# Postgres, with its own owner. Idempotent, and it also runs on installs whose postgres-data
# volume already exists (docker-entrypoint-initdb.d only runs on an empty volume, so Airflow
# cannot rely on config/postgres/init-dbs.sh there):
#   * role `airflow` created if missing; its password is (re)set from AIRFLOW_DB_PASSWORD, so
#     .secrets.env stays the only source (INV_ENV_IS_CREDENTIAL_SOURCE);
#   * database `airflow` owned by it, created if missing.
# Passwords travel as psql variables, never in the SQL text or on a command line.
set -euo pipefail
: "${POSTGRES_PASSWORD:?}" "${AIRFLOW_DB_PASSWORD:?}"
export PGHOST=postgres PGUSER=postgres PGDATABASE=postgres PGPASSWORD="$POSTGRES_PASSWORD"

for _ in $(seq 1 60); do pg_isready -q && break; sleep 1; done

psql -v ON_ERROR_STOP=1 -q -v p="$AIRFLOW_DB_PASSWORD" <<'SQL'
SELECT NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'airflow') AS need_role \gset
\if :need_role
  CREATE ROLE airflow LOGIN;
  \echo [airflow-db] created role airflow
\endif
ALTER ROLE airflow WITH LOGIN PASSWORD :'p';
SELECT NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'airflow') AS need_db \gset
\if :need_db
  CREATE DATABASE airflow OWNER airflow;
  \echo [airflow-db] created database airflow
\endif
SQL
echo "[airflow-db] ready (database airflow, owner airflow)"
