#!/usr/bin/env bash
# Lakehouse Lab V3 end-to-end smoke test (CONTRACT.md "Test contract"). `./lab test` runs it.
# Against the RUNNING stack; exits 0 only if every check passes (skipped ones aside):
#   1. the stack is healthy                                            (here, on the host)
#   2. headless browser logs in as alice through auth. and reaches the Trino UI
#   3. with alice's Keycloak token, Trino creates a namespace + Iceberg table, inserts, reads
#   4. PyIceberg loads that table through Lakekeeper with vended credentials, which are
#      denied on a sibling prefix
#   5. victor (viewer) is denied a write in Trino
#   6. no static S3 key in Trino's config or environment                (here, on the host)
#  11. the Docker socket proxy refuses out-of-scope requests (in the jupyterhub container)
#   7. a group change made through the Keycloak admin API (as in the Keycloak UI) reaches
#      Trino automatically via identity-sync, granting and then revoking (OQ-20)
#   8. alice logs into jupyter. in the browser, her workspace spawns, and INSIDE it (her
#      kernel, her lab_token()) Trino reads lakehouse.samples.orders, DuckDB ATTACHes the
#      catalog with vended credentials, and `dbt build` of the starter project passes
#   9. victor's workspace is denied a Trino write
#  10. profile engineer only (a [SKIP] line on core): Spark Connect, from alice's workspace,
#      creates and reads an Iceberg table
#  12. engineer/full: Airflow roles (alice Admin, victor read-only, eddie edits) and the four
#      lab_* DAGs succeed when alice triggers them
#  13. engineer/full with --long (LAB_SMOKE_LONG=1): ADR-017, lab_spark_batch runs >= 300 s
#      with lab-batch tokens cut to 120 s and commits after the first one expired
#  14. full: Superset login, SQL Lab runs in Trino as alice, "Revenue by region" chart data
#      has rows, victor cannot write
#  15. Console tiles differ for alice and victor; Spark UI 200 for alice, 403 for victor
#  16. external IdP (mock realm as alias github-mock): first login has no group and is
#      refused; access follows an admin's group change; no linking by e-mail
#  17. learning tracks (tracks.py): per selected module, as its seeded test user in their own
#      workspace, the reference solution passes the checkpoint and `lab-tracks reset` brings
#      back the start state (LAB_SMOKE_TRACKS: first (default) | all | none | E1,A3)
# Checks 2-5, 7-10 and 12-17 run in the `smoke` container (profile test) on the lab network:
# smoke.py, with workspace.py driving the workspace and kernel_probe.py running inside it.
#
# Usage: tests/smoke/run.sh [--no-build] [--long] [--tracks SPEC]
# Env:   LAB_SMOKE_OUT  where screenshots/results.json go (default: tests/smoke/out)
#        LAB_SMOKE_ONLY debugging only: comma list of in-container checks to run (e.g. 8,9)
#        LAB_SMOKE_LONG=1 same as --long (nightly CI)
#        LAB_SMOKE_TRACKS same as --tracks: modules for check 17 (first | all | none | E1,A3)
set -uo pipefail

build=(--build)
LAB_SMOKE_LONG=${LAB_SMOKE_LONG:-}
LAB_SMOKE_TRACKS=${LAB_SMOKE_TRACKS:-first}
usage="usage: tests/smoke/run.sh [--no-build] [--long] [--tracks first|all|none|ID,...]"
while [ $# -gt 0 ]; do
  case "$1" in
    --no-build) build=() ;;
    --long) LAB_SMOKE_LONG=1 ;;
    --tracks) [ $# -ge 2 ] || { echo "$usage" >&2; exit 2; }; LAB_SMOKE_TRACKS=$2; shift ;;
    --tracks=*) LAB_SMOKE_TRACKS=${1#--tracks=} ;;
    *) echo "$usage" >&2; exit 2 ;;
  esac
  shift
done
[[ "$LAB_SMOKE_TRACKS" =~ ^[A-Za-z0-9,_-]+$ ]] || { echo "run.sh: bad --tracks '$LAB_SMOKE_TRACKS'" >&2; exit 2; }

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
HOST_PASSED=0 HOST_FAILED=0
pass() { printf '[PASS] %s: %s\n' "$1" "$2"; HOST_PASSED=$((HOST_PASSED + 1)); }
fail() { printf '[FAIL] %s: %s\n' "$1" "$2"; FAILED+=("$1"); HOST_FAILED=$((HOST_FAILED + 1)); }

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
echo "== 2-5, 7-10, 12-17. browser login, Trino, PyIceberg, viewer denial, group sync, workspaces, Phase 3 apps and IdP, learning tracks (smoke container on the lab network)"
out=${LAB_SMOKE_OUT:-$V3/tests/smoke/out}
mkdir -p "$out"
rm -f "$out/summary.env" "$out/results.json"
if LAB_SMOKE_OUT="$out" "${DC[@]}" --profile test run --rm ${build[@]+"${build[@]}"} \
     --user "$(id -u):$(id -g)" -e HOME=/tmp/smoke-home -e LAB_PROFILE="$PROFILE" \
     -e LAB_SMOKE_ONLY="${LAB_SMOKE_ONLY:-}" -e LAB_SMOKE_LONG="$LAB_SMOKE_LONG" \
     -e LAB_SMOKE_TRACKS="$LAB_SMOKE_TRACKS" \
     -v "$V3/tracks:/opt/tracks:ro" -v "$V3/tests/tracks:/opt/tracks-tests:ro" smoke; then
  :
else
  FAILED+=("in-container checks (see [FAIL] lines above, $out/results.json)")
fi

# ---------------------------------------------------------------- 11. Docker proxy scope
echo "== 11. Docker socket proxy refuses out-of-scope requests (from inside jupyterhub)"
if probe=$("${DC[@]}" exec -T jupyterhub python3 - <"$V3/tests/smoke/proxy_probe.py" 2>&1); then
  pass "11.docker_proxy_scope" "$(printf '%s' "$probe" | tail -n 1)"
else
  fail "11.docker_proxy_scope" "$(printf '%s' "$probe" | tail -n 3 | tr '\n' ' ')"
fi

# Totals: host checks (1, 6, 11) + the container's summary. Skipped checks are not counted.
c_pass=0 c_fail=0 c_skip=0 c_skipped=""
if [ -f "$out/summary.env" ]; then
  c_pass=$(env_get "$out/summary.env" CONTAINER_PASSED)
  c_fail=$(env_get "$out/summary.env" CONTAINER_FAILED)
  c_skip=$(env_get "$out/summary.env" CONTAINER_SKIPPED)
  c_skipped=$(env_get "$out/summary.env" CONTAINER_SKIPPED_NAMES)
else
  FAILED+=("no $out/summary.env: the smoke container did not finish")
  c_fail=1
fi
passed=$((HOST_PASSED + ${c_pass:-0}))
total=$((passed + HOST_FAILED + ${c_fail:-0}))
skipped=""
[ "${c_skip:-0}" -gt 0 ] && skipped=", ${c_skip} skipped: ${c_skipped}"

echo
if [ ${#FAILED[@]} -eq 0 ] && [ "${c_fail:-0}" = 0 ]; then
  echo "SMOKE: PASS (${passed}/${total}${skipped}; profile $PROFILE)"
  exit 0
fi
echo "SMOKE: FAIL (${passed}/${total} passed${skipped}; profile $PROFILE): ${FAILED[*]}"
exit 1
