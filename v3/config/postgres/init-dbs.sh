#!/bin/bash
# Runs once, on the first start of an empty postgres-data volume (docker-entrypoint-initdb.d).
# One database + owner per service. Passwords come from .secrets.env via the environment
# (INV_ENV_IS_CREDENTIAL_SOURCE); psql variables keep them out of the SQL text.
#   keycloak   -> Keycloak
#   lakekeeper -> Lakekeeper catalog
#   openfga    -> OpenFGA datastore for Lakekeeper authorization (OQ-5); owned by the
#                 lakekeeper role, since OpenFGA only ever serves Lakekeeper.
set -euo pipefail

mk_role() { # name password
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" -v u="$1" -v p="$2" <<'SQL'
CREATE ROLE :"u" LOGIN PASSWORD :'p';
SQL
}
mk_db() { # db owner
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" -v d="$1" -v o="$2" <<'SQL'
CREATE DATABASE :"d" OWNER :"o";
SQL
}

mk_role keycloak "$KEYCLOAK_DB_PASSWORD"
mk_role lakekeeper "$LAKEKEEPER_DB_PASSWORD"
mk_db keycloak keycloak
mk_db lakekeeper lakekeeper
mk_db openfga lakekeeper
