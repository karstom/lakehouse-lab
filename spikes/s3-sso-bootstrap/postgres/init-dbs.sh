#!/bin/bash
# One database + owner per service. Passwords come from the environment (.secrets.env).
set -euo pipefail
mk() {
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" -v u="$1" -v p="$2" <<'SQL'
CREATE ROLE :"u" LOGIN PASSWORD :'p';
CREATE DATABASE :"u" OWNER :"u";
SQL
}
mk keycloak "$KC_DB_PASSWORD"
mk superset "$SUPERSET_DB_PASSWORD"
mk airflow "$AIRFLOW_DB_PASSWORD"
mk lakekeeper "$LAKEKEEPER_DB_PASSWORD"
