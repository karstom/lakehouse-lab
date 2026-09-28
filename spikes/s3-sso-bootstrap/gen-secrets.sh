#!/usr/bin/env bash
# Generates .secrets.env once (installer step). URL-safe values only (INV_DB_PASSWORDS_URL_SAFE).
set -euo pipefail
cd "$(dirname "$0")"
[ -f .secrets.env ] && exit 0
r() { openssl rand -hex "${1:-24}"; }
umask 077
cat > .secrets.env <<EOT
POSTGRES_PASSWORD=$(r)
KC_DB_PASSWORD=$(r)
KC_ADMIN_PASSWORD=$(r)
SUPERSET_DB_PASSWORD=$(r)
AIRFLOW_DB_PASSWORD=$(r)
LAKEKEEPER_DB_PASSWORD=$(r)
LAKEKEEPER_ENCRYPTION_KEY=$(r 32)
JUPYTERHUB_CLIENT_SECRET=$(r)
SUPERSET_CLIENT_SECRET=$(r)
AIRFLOW_CLIENT_SECRET=$(r)
TRINO_CLIENT_SECRET=$(r)
SUPERSET_SECRET_KEY=$(r 32)
AIRFLOW_JWT_SECRET=$(r 32)
AIRFLOW_FERNET_KEY=$(openssl rand -base64 32 | tr '+/' '-_')
TRINO_SHARED_SECRET=$(r 32)
LAB_USER_PASSWORD=$(r 12)
EOT
echo "generated .secrets.env"
