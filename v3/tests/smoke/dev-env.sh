#!/usr/bin/env bash
# DEV ONLY: create throwaway .env, .secrets.env and state/ca for testing the CORE stack
# without the installer. The real generator is install.sh (INSTALLER workstream).
# Never overwrites existing files. Usage:
#   tests/smoke/dev-env.sh [LAB_DOMAIN] [HTTPS_PORT] [HTTP_PORT] [PROJECT]
set -euo pipefail
V3=$(cd -P "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
domain=${1:-lab.localhost}; https=${2:-443}; http=${3:-80}; project=${4:-lakehouse}
cd "$V3"

if [ ! -f .env ]; then
  cat >.env <<EOT
COMPOSE_PROJECT_NAME=$project
LAB_DOMAIN=$domain
LAB_HTTPS_PORT=$https
LAB_HTTP_PORT=$http
LAB_PROFILE=core
LAB_STATE_DIR=./state
LAB_TZ=UTC
LAB_SEED_TEST_USERS=true
EOT
  echo "wrote .env"
fi
if [ "$https" = 443 ]; then auth_url="https://auth.$domain"; else auth_url="https://auth.$domain:$https"; fi
echo "raw 'docker compose' needs: export LAB_AUTH_URL=$auth_url   (./lab and ./install.sh derive it)"

if [ ! -f .secrets.env ]; then
  hex() { openssl rand -hex "$1"; }
  alnum() { LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c "$1"; }
  (
    umask 077
    cat >.secrets.env <<EOT
POSTGRES_PASSWORD=$(hex 24)
KEYCLOAK_DB_PASSWORD=$(hex 24)
LAKEKEEPER_DB_PASSWORD=$(hex 24)
KC_ADMIN_USER=kcadmin
KC_ADMIN_PASSWORD=$(alnum 24)
LAB_ADMIN_USER=labadmin
LAB_ADMIN_PASSWORD=$(alnum 20)
SEAWEEDFS_ADMIN_ACCESS_KEY=LAB$(alnum 17 | tr '[:lower:]' '[:upper:]')
SEAWEEDFS_ADMIN_SECRET_KEY=$(alnum 40)
SEAWEEDFS_STS_SIGNING_KEY=$(openssl rand -base64 32 | tr -d '\n')
LAKEKEEPER_PG_ENCRYPTION_KEY=$(alnum 40)
OIDC_CLIENT_SECRET_TRINO=$(alnum 32)
OIDC_CLIENT_SECRET_LAKEKEEPER=$(alnum 32)
OIDC_CLIENT_SECRET_CONSOLE=$(alnum 32)
TRINO_INTERNAL_SECRET=$(hex 32)
LAB_TEST_USER_PASSWORD=$(alnum 16)
EOT
  )
  echo "wrote .secrets.env"
fi

if [ ! -f state/ca/root.crt ]; then
  mkdir -p state/ca && chmod 700 state/ca
  (
    umask 077
    openssl ecparam -name prime256v1 -genkey -noout -out state/ca/ec.key
    openssl pkcs8 -topk8 -nocrypt -in state/ca/ec.key -out state/ca/root.key
    rm -f state/ca/ec.key
    openssl req -x509 -new -sha256 -key state/ca/root.key -days 3650 \
      -subj "/O=Lakehouse Lab/CN=Lakehouse Lab DEV CA $(hex 3)" \
      -addext "basicConstraints=critical,CA:TRUE" -addext "keyUsage=critical,keyCertSign,cRLSign" \
      -out state/ca/root.crt
  )
  chmod 644 state/ca/root.crt
  echo "wrote state/ca/root.{crt,key}"
fi
