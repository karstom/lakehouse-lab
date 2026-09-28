#!/bin/bash
# superset-db one-shot (profile full): role + database `superset` in the shared Postgres.
# config/postgres/init-dbs.sh runs only on the first start of an empty data volume, so an
# existing lab (upgrade in place, or switching to profile full later) would never get them.
# Idempotent: creates what is missing and keeps the role's password equal to
# SUPERSET_DB_PASSWORD (from .secrets.env via the environment; psql variables keep it out
# of the SQL text and the process list).
set -euo pipefail
export PGHOST=postgres PGUSER=postgres PGDATABASE=postgres PGPASSWORD="$POSTGRES_PASSWORD"
# On a fresh volume Postgres reports healthy (socket) while its init scripts still run on a
# temporary server without TCP; wait for the real server.
for _ in $(seq 1 60); do
  pg_isready -q -t 2 && break
  sleep 1
done
psql -v ON_ERROR_STOP=1 -q -v p="$SUPERSET_DB_PASSWORD" <<'SQL'
SELECT 'CREATE ROLE superset LOGIN'
 WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'superset') \gexec
ALTER ROLE superset LOGIN PASSWORD :'p';
SELECT 'CREATE DATABASE superset OWNER superset'
 WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'superset') \gexec
SQL
echo "[superset-db] role and database superset ready"
