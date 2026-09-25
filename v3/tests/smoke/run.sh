#!/usr/bin/env bash
# Lakehouse Lab V3 end-to-end smoke test (CONTRACT.md "Test contract"). `./lab test` runs it.
# Against the RUNNING stack; exits 0 only if all seven checks pass:
#   1. the stack is healthy                                            (here, on the host)
#   2. headless browser logs in as alice through auth. and reaches the Trino UI
#   3. with alice's Keycloak token, Trino creates a namespace + Iceberg table, inserts, reads
#   4. PyIceberg loads that table through Lakekeeper with vended credentials, which are
#      denied on a sibling prefix
#   5. victor (viewer) is denied a write in Trino
#   6. no static S3 key in Trino's config or environment                (here, on the host)
#   7. a group change made through the Keycloak admin API (as in the Keycloak UI) reaches
#      Trino automatically via identity-sync, granting and then revoking (OQ-20)
# Checks 2-5 and 7 run in the `smoke` container (profile test) on the lab network: smoke.py.
#
# Usage: tests/smoke/run.sh [--no-build]
# Env:   LAB_SMOKE_OUT  where screenshots/results.json go (default: tests/smoke/out)
set -uo pipefail

V3=$(cd -P "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
ENV_FILE="$V3/.env"
SECRETS_FILE="$V3/.secrets.env"
[ -f "$ENV_FILE" ] || { echo "smoke: no $ENV_FILE (run install.sh first)" >&2; exit 2; }
[ -f "$SECRETS_FILE" ] || { echo "smoke: no $SECRETS_FILE (run install.sh first)" >&2; exit 2; }

# env_get FILE KEY -> value of KEY in a dotenv file (last assignment wins; no shell eval).
env_get() { sed -n "s/^$2=//p" "$1" | tail -n 1 | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/"; }

PROJECT=$(env_get "$ENV_FILE" COMPOSE_PROJECT_NAME); PROJECT=${PROJECT:-lakehouse}
PROFILE=$(env_get "$ENV_FILE" LAB_PROFILE); PROFILE=${PROFILE:-core}
export COMPOSE_PROJECT_NAME="$PROJECT"
DC=(docker compose --project-directory "$V3" --env-file "$V3/versions.env" --env-file "$ENV_FILE"
    --profile "$PROFILE")

FAILED=()
pass() { printf '[PASS] %s: %s\n' "$1" "$2"; }
fail() { printf '[FAIL] %s: %s\n' "$1" "$2"; FAILED+=("$1"); }

# ---------------------------------------------------------------- 1. stack healthy
echo "== 1. stack health (project $PROJECT, profile $PROFILE)"
bad=()
while IFS='|' read -r svc state health code; do
  [ -n "$svc" ] || continue
  if [ "$state" = running ]; then
    [ "$health" = healthy ] || bad+=("$svc:running/${health:-no-healthcheck}")
  elif [ "$state" = exited ]; then
    [ "$code" = 0 ] || bad+=("$svc:exited($code)")
  else
    bad+=("$svc:$state")
  fi
done < <("${DC[@]}" ps -a --format '{{.Service}}|{{.State}}|{{.Health}}|{{.ExitCode}}')
expected=$("${DC[@]}" config --services | sort)
present=$("${DC[@]}" ps -a --format '{{.Service}}' | sort)
missing=$(comm -23 <(echo "$expected") <(echo "$present") | tr '\n' ' ')
if [ ${#bad[@]} -eq 0 ] && [ -z "${missing// /}" ]; then
  pass "1.stack_healthy" "$(echo "$present" | wc -l) services healthy or completed"
else
  fail "1.stack_healthy" "problems: ${bad[*]:-none}; missing: ${missing:-none}"
fi

# ---------------------------------------------------------------- 6. no static S3 key in Trino
echo "== 6. no static S3 key in Trino config or environment"
cid=$("${DC[@]}" ps -q trino)
if [ -z "$cid" ]; then
  fail "6.no_static_s3_key_in_trino" "trino container not found"
else
  rendered=$( {
    "${DC[@]}" config --no-interpolate trino 2>/dev/null | sed -n '/^  trino:/,/^  [a-z]/p'
    docker exec "$cid" sh -c 'cat /etc/trino/config.properties /etc/trino/catalog/*.properties' 2>/dev/null
    docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$cid"
  } )
  lines=$(printf '%s\n' "$rendered" | wc -l)
  pat='aws-access-key|aws-secret-key|s3\.access-key|s3\.secret-key|aws_access_key_id|aws_secret_access_key|AWS_ACCESS_KEY|AWS_SECRET|SEAWEEDFS_ADMIN'
  hits=$(printf '%s\n' "$rendered" | grep -vE '^\s*#' | grep -inE "$pat" || true)
  ak=$(env_get "$SECRETS_FILE" SEAWEEDFS_ADMIN_ACCESS_KEY)
  sk=$(env_get "$SECRETS_FILE" SEAWEEDFS_ADMIN_SECRET_KEY)
  leak=no
  if [ -n "$ak" ] && [ -n "$sk" ] && printf '%s\n' "$rendered" | grep -qF -e "$ak" -e "$sk"; then leak=yes; fi
  if [ "$lines" -gt 20 ] && [ -z "$hits" ] && [ "$leak" = no ]; then
    pass "6.no_static_s3_key_in_trino" "0 key settings and no admin key value in $lines lines of Trino compose config, properties and env"
  else
    fail "6.no_static_s3_key_in_trino" "lines=$lines admin_key_value_found=$leak settings: ${hits:-none}"
  fi
fi

# ---------------------------------------------------------------- 2-5. in the smoke container
echo "== 2-5. browser login, Trino, PyIceberg, viewer denial (smoke container on the lab network)"
out=${LAB_SMOKE_OUT:-$V3/tests/smoke/out}
mkdir -p "$out"
build=(--build)
[ "${1:-}" = "--no-build" ] && build=()
if LAB_SMOKE_OUT="$out" "${DC[@]}" --profile test run --rm "${build[@]}" \
     --user "$(id -u):$(id -g)" -e HOME=/tmp/smoke-home smoke; then
  :
else
  FAILED+=("2-5,7 (see [FAIL] lines above, $out/results.json)")
fi

echo
if [ ${#FAILED[@]} -eq 0 ]; then
  echo "SMOKE: PASS (7/7)"
  exit 0
fi
echo "SMOKE: FAIL: ${FAILED[*]}"
exit 1
