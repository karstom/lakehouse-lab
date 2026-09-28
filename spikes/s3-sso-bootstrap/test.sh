#!/usr/bin/env bash
# S-3 test: run ON THE SERVER from this directory.
#   ./test.sh          full cycle: down -v -> up (no manual steps) -> checks -> browser SSO tests
#   FAST=1 ./test.sh   skip the down -v / rebuild, test the running stack
# Exit 0 only if every pass criterion holds. The stack is left running.
set -uo pipefail
cd "$(dirname "$0")"
./gen-secrets.sh >/dev/null
set -a; . ./lab.env; set +a
DC=./dc.sh
FAIL=0
pass() { echo "[PASS] $*"; }
fail() { echo "[FAIL] $*"; FAIL=1; }
mkdir -p out

if [ "${FAST:-0}" != 1 ]; then
  echo "== C1: down -v, then up from nothing"
  $DC --profile test down -v --remove-orphans
  $DC build --quiet
  t0=$(date +%s)
  if $DC up -d --wait --wait-timeout 900; then
    pass "C1 stack up with no manual steps in $(( $(date +%s) - t0 ))s (docker compose up --wait)"
  else
    fail "C1 compose up --wait failed"
    $DC ps -a
  fi
else
  echo "== FAST=1: testing the running stack (C1 not re-proven)"
fi

echo "== stack state"
$DC ps -a --format 'table {{.Service}}\t{{.State}}\t{{.Status}}'
for svc in trust-init airflow-init lakekeeper-migrate; do
  code=$(docker inspect -f '{{.State.ExitCode}}' "$($DC ps -a -q "$svc")" 2>/dev/null || echo missing)
  [ "$code" = 0 ] && pass "one-shot $svc exited 0" || fail "one-shot $svc exit=$code"
done

echo "== hard rules: published ports and memory"
ports=$(docker ps --filter label=com.docker.compose.project=v3-s3 --format '{{.Ports}}' | grep -o '0.0.0.0:[0-9]*' | sort -u | tr '\n' ' ')
[ "$ports" = "0.0.0.0:${LAB_PORT} " ] && pass "only published port: $ports" || fail "published ports: '$ports'"
mem=$(docker ps -aq --filter label=com.docker.compose.project=v3-s3 | xargs docker inspect -f '{{.HostConfig.Memory}}' | awk '{s+=$1; if ($1==0) z++} END {printf "%.1f %d", s/1024/1024/1024, z}')
read -r gb zero <<<"$mem"
[ "$zero" = 0 ] && awk "BEGIN{exit !($gb <= 16)}" && pass "mem_limit on every container, total ${gb} GB" || fail "memory: total=${gb}GB unlimited=${zero}"

echo "== TLS through the published port, verified against Caddy's root CA only"
$DC exec -T caddy cat /data/caddy/pki/authorities/local/root.crt > out/caddy-root.crt
openssl x509 -in out/caddy-root.crt -noout -subject -enddate
for svc in auth jupyter superset airflow trino catalog; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --cacert out/caddy-root.crt "https://${svc}.${LAB_DOMAIN}:${LAB_PORT}/")
  [[ "$code" =~ ^[23] ]] && pass "https://${svc}.${LAB_DOMAIN}:${LAB_PORT}/ -> $code (cert verified)" || fail "$svc -> $code"
done

echo "== Keycloak realm imported from template"
iss=$(curl -s --cacert out/caddy-root.crt "https://auth.${LAB_DOMAIN}:${LAB_PORT}/realms/lakehouse/.well-known/openid-configuration" | python3 -c 'import sys,json; print(json.load(sys.stdin)["issuer"])')
[ "$iss" = "https://auth.${LAB_DOMAIN}:${LAB_PORT}/realms/lakehouse" ] && pass "issuer $iss" || fail "issuer '$iss'"

echo "== C2/C3/C4: headless browser through Keycloak"
if $DC --profile test run --rm --build tester; then
  pass "browser SSO checks (see out/results.json, out/*.png)"
else
  fail "browser SSO checks (see out/results.json, out/*.png)"
fi

echo "== OQ-3 evidence (informational)"
$DC --profile test run --rm --entrypoint python3 tester /opt/tester/oq3_probe.py 2>&1 | grep '^OQ3'

echo
[ "$FAIL" = 0 ] && echo "S-3 RESULT: PASS" || echo "S-3 RESULT: FAIL"
exit "$FAIL"
