#!/bin/bash
# ai-gateway-db one-shot (profile full, Phase 5): role + database `ai_gateway` in the shared
# Postgres, for LiteLLM's virtual keys, users, budgets and spend. Same pattern as superset-db:
# config/postgres/init-dbs.sh runs only on the first start of an empty data volume, so an
# existing lab (upgrade in place, or switching to profile full later) would never get them.
# Idempotent: creates what is missing and keeps the role's password equal to
# AI_GATEWAY_DB_PASSWORD (from .secrets.env via the environment; psql variables keep it out
# of the SQL text and the process list). The gateway applies its own schema migrations.
set -euo pipefail
export PGHOST=postgres PGUSER=postgres PGDATABASE=postgres PGPASSWORD="$POSTGRES_PASSWORD"
# On a fresh volume Postgres reports healthy (socket) while its init scripts still run on a
# temporary server without TCP; wait for the real server.
for _ in $(seq 1 60); do
  pg_isready -q -t 2 && break
  sleep 1
done
psql -v ON_ERROR_STOP=1 -q -v p="$AI_GATEWAY_DB_PASSWORD" <<'SQL'
SELECT 'CREATE ROLE ai_gateway LOGIN'
 WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ai_gateway') \gexec
ALTER ROLE ai_gateway LOGIN PASSWORD :'p';
SELECT 'CREATE DATABASE ai_gateway OWNER ai_gateway'
 WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ai_gateway') \gexec
SQL
echo "[ai-gateway-db] role and database ai_gateway ready"
