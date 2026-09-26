#!/usr/bin/env bash
# Validate v3/compose.yaml the way the stack is started (CONTRACT.md, runtime contract):
#   docker compose --project-directory v3 --env-file v3/versions.env --env-file v3/.env \
#     --profile core config -q
# It runs on a throwaway copy of v3/ with a generated .env (contract defaults) and a
# generated .secrets.env (the installer's own generator when available, else random hex
# for every key the contract lists), so real per-install files are never read or touched.
# Fails on any "variable is not set" warning: every interpolated variable must come from
# versions.env or .env.
# Usage: v3/tools/compose-check.sh [--with-pins] [--profile NAME] [--json-out FILE]
#   --with-pins      also pass v3/.pins/*.env (pending pins not yet promoted by the lead)
#   --json-out FILE  also write 'config --format json' to FILE, with paths mapped back to
#                    the real v3/ (v3-images.yml reads build contexts from it)
set -euo pipefail
V3_DIR=$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

with_pins=0
profile=core
json_out=""
while [ $# -gt 0 ]; do
  case "$1" in
    --with-pins) with_pins=1 ;;
    --profile) profile=${2:?--profile needs a value}; shift ;;
    --json-out) json_out=${2:?--json-out needs a file}; shift ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

[ -f "$V3_DIR/compose.yaml" ] || { echo "compose-check: $V3_DIR/compose.yaml not found" >&2; exit 1; }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
work="$tmp/v3"
mkdir -p "$work"
# Copy the tree without per-install files or state.
tar -C "$V3_DIR" --exclude=./.env --exclude=./.secrets.env --exclude=./state --exclude='*/out' -cf - . | tar -C "$work" -xf -

cat >"$work/.env" <<ENV
COMPOSE_PROJECT_NAME=lakehouse-compose-check
LAB_DOMAIN=lab.localhost
LAB_HTTPS_PORT=443
LAB_HTTP_PORT=80
LAB_PROFILE=${profile}
LAB_STATE_DIR=./state
LAB_TZ=UTC
LAB_SEED_TEST_USERS=true
ENV

gen_secrets_fallback() {
  local k
  umask 077
  : >"$1"
  for k in POSTGRES_PASSWORD KEYCLOAK_DB_PASSWORD LAKEKEEPER_DB_PASSWORD KC_ADMIN_USER \
           KC_ADMIN_PASSWORD LAB_ADMIN_USER LAB_ADMIN_PASSWORD SEAWEEDFS_ADMIN_ACCESS_KEY \
           SEAWEEDFS_ADMIN_SECRET_KEY SEAWEEDFS_STS_SIGNING_KEY LAKEKEEPER_PG_ENCRYPTION_KEY \
           OIDC_CLIENT_SECRET_TRINO OIDC_CLIENT_SECRET_LAKEKEEPER OIDC_CLIENT_SECRET_CONSOLE OIDC_CLIENT_SECRET_SYNC \
           OIDC_CLIENT_SECRET_JUPYTERHUB JUPYTERHUB_CRYPT_KEY TRINO_INTERNAL_SECRET LAB_TEST_USER_PASSWORD \
           OIDC_CLIENT_SECRET_AIRFLOW OIDC_CLIENT_SECRET_BATCH AIRFLOW_DB_PASSWORD AIRFLOW_FERNET_KEY \
           AIRFLOW_JWT_SECRET OIDC_CLIENT_SECRET_SUPERSET SUPERSET_SECRET_KEY SUPERSET_DB_PASSWORD \
           CONSOLE_COOKIE_SECRET; do
    printf '%s=%s\n' "$k" "$(openssl rand -hex 16)" >>"$1"
  done
}
if [ -f "$work/installer/lib.sh" ] && [ -f "$work/installer/secrets.sh" ] &&
   ( V3_DIR=$work
     # shellcheck source=/dev/null
     . "$work/installer/lib.sh"
     # shellcheck source=/dev/null
     . "$work/installer/secrets.sh"
     declare -F ensure_secrets >/dev/null && ensure_secrets "$work/.secrets.env" >/dev/null ); then
  echo "compose-check: .secrets.env from installer/secrets.sh"
else
  gen_secrets_fallback "$work/.secrets.env"
  echo "compose-check: .secrets.env from the contract key list"
fi
mkdir -p "$work/state/ca"

env_files=(--env-file "$work/versions.env")
if [ "$with_pins" = 1 ]; then
  for f in "$work"/.pins/*.env; do [ -f "$f" ] && env_files+=(--env-file "$f"); done
fi
env_files+=(--env-file "$work/.env")

# Run with a clean environment for interpolation, so nothing from the caller's shell
# (or CI) can satisfy a variable that versions.env/.env should provide.
clean_env=(PATH="$PATH" HOME="${HOME:-/tmp}" COMPOSE_PROJECT_NAME=lakehouse-compose-check
           LAB_AUTH_URL=https://auth.lab.localhost)  # what installer/lib.sh derives for the .env above
for v in DOCKER_HOST DOCKER_CONTEXT DOCKER_CONFIG; do
  [ -n "${!v:-}" ] && clean_env+=("$v=${!v}")
done
compose=(env -i "${clean_env[@]}" docker compose --project-directory "$work" "${env_files[@]}" --profile "$profile")
set +e
out=$("${compose[@]}" config -q 2>&1)
rc=$?
set -e
[ -z "$out" ] || printf '%s\n' "$out" | sed "s#$work#v3#g"
if [ $rc -ne 0 ]; then
  echo "compose-check: FAIL (docker compose config exited $rc)" >&2
  exit 1
fi
if printf '%s\n' "$out" | grep -qiE 'variable is not set|not set\. Defaulting'; then
  echo "compose-check: FAIL (unset variables; define them in versions.env or .env)" >&2
  exit 1
fi
if [ -n "$json_out" ]; then
  "${compose[@]}" config --format json 2>/dev/null | sed "s#$work#$V3_DIR#g" >"$json_out"
fi
echo "compose-check: OK (profile $profile)"
