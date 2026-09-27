#!/usr/bin/env bash
# AI gateway end-to-end checks on a running lab (profile full, installed with --ai-mock).
# Mock model only: no step ever sends a request to a real model server.
#
#   v3/tests/ai/gateway-e2e.sh
#
# 1. mock            rendered config and broker/gateway flows through the mock (gateway_e2e.py)
# 2. not-configured  the gateway recreated with NO provider (LAB_AI_* overridden for this
#                    compose call only; .env and .secrets.env are not touched):
#                    - its rendered config has an empty model list;
#                    - AI requests get "AI isn't configured; ask your lab admin.";
#                    - no_egress_probe.py watches the gateway's sockets from its start through
#                      those requests: every peer must be inside the lab's own networks.
# 3. local-via-mock  the `local` provider path, with LAB_AI_LOCAL_URL pointed at the mock
#                    (never at a real server) for this compose call only.
# 4. the gateway is recreated with the lab's own settings again.
# Exit 0 only if every step passed. Evidence: out/ai-e2e/ (git-ignored).
set -uo pipefail
V3_DIR=$(cd -P "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
# shellcheck source=../../installer/lib.sh
. "$V3_DIR/installer/lib.sh"
[ -f "$LAB_ENV_FILE" ] || die "no $LAB_ENV_FILE; install the lab first"
lab_settings
profile_includes "$LAB_PROFILE" ai || die "the AI gateway runs on profile full (this lab: $LAB_PROFILE)"
[ "${LAB_AI_MOCK:-false}" = true ] || die "install the lab with --ai-mock first (tests use the mock model only)"
out="$V3_DIR/out/ai-e2e"
mkdir -p "$out"
rc=0
HERE="$V3_DIR/tests/ai"

run_py() {  # run_py MODE -> gateway_e2e.py in ai-keys
  local mode=$1
  lab_compose exec -T -e "E2E_MODE=$mode" -w /opt/lab ai-keys python3 - <"$HERE/gateway_e2e.py" \
    | tee "$out/$mode.log"
  grep -q '^E2E_RESULT {"checks": .*"ok": true' "$out/$mode.log"
}

# gateway_with ENV... -> recreate ai-gateway with these LAB_AI_* values (this call only)
gateway_with() {
  (
    for kv in "$@"; do export "${kv?}"; done
    lab_compose up -d --wait --no-deps --force-recreate ai-gateway
  )
}

rendered() {  # rendered FILE -> the gateway's rendered file (config.yaml or state.json)
  lab_compose exec -T ai-gateway cat "/tmp/lab-ai/$1"
}

step() { printf '\n== %s\n' "$*"; }

step "1. mock provider (the lab as installed)"
rendered state.json | tee "$out/state-mock.json"; echo
run_py mock || rc=1

step "2. no provider: empty model list, clear message, no outbound connection"
# The probe must watch the gateway from its first second, so start the recreate in the
# background and attach the probe as soon as the new container accepts exec.
( gateway_with LAB_AI_MOCK=false LAB_AI_LOCAL_URL= LAB_AI_ANTHROPIC_API_KEY= LAB_AI_OPENAI_API_KEY= \
    >"$out/recreate-noai.log" 2>&1 ) &
recreate=$!
old=$(lab_compose ps -q ai-gateway 2>/dev/null || true)
for _ in $(seq 1 240); do
  cid=$(lab_compose ps -q ai-gateway 2>/dev/null || true)
  if [ -n "$cid" ] && [ "$cid" != "$old" ] &&
     [ "$(docker inspect -f '{{.State.Running}}' "$cid" 2>/dev/null)" = true ]; then
    break
  fi
  sleep 0.25
done
lab_compose exec -T -e PROBE_SECONDS=150 ai-gateway python3 - <"$HERE/no_egress_probe.py" >"$out/egress.log" 2>&1 &
probe=$!
wait "$recreate" || { echo "gateway did not come back without providers"; rc=1; }
rendered config.yaml >"$out/config-noai.json"
rendered state.json | tee "$out/state-noai.json"; echo
if python3 -c 'import json,sys; c=json.load(open(sys.argv[1])); sys.exit(0 if c["model_list"]==[] else 1)' "$out/config-noai.json"; then
  echo "  ok   rendered config: model_list is empty (no provider, nothing to call)"
else
  echo "  FAIL rendered config has models"; rc=1
fi
if lab_compose exec -T ai-gateway sh -c 'env | grep -E "^LAB_AI_(ANTHROPIC|OPENAI|LOCAL)_(API_KEY|URL)=." >/dev/null'; then
  echo "  FAIL gateway environment still carries a provider key or URL"; rc=1
else
  echo "  ok   gateway environment: no provider key or URL"
fi
run_py not-configured || rc=1
wait "$probe"
cat "$out/egress.log"
grep -q '^NO_EGRESS_RESULT {.*"ok": true' "$out/egress.log" && echo "  ok   no connection outside the lab's networks" ||
  { echo "  FAIL outbound connection seen (see $out/egress.log)"; rc=1; }

step "3. local provider path (LAB_AI_LOCAL_URL -> the mock, never a real server)"
gateway_with LAB_AI_MOCK=false LAB_AI_LOCAL_URL=http://ai-mock:8000/v1 LAB_AI_LOCAL_MODEL=mock-model \
  LAB_AI_ANTHROPIC_API_KEY= LAB_AI_OPENAI_API_KEY= >"$out/recreate-local.log" 2>&1 || rc=1
local_url=$(lab_compose exec -T ai-gateway printenv LAB_AI_LOCAL_URL | tr -d '\r')
if [ "$local_url" = "http://ai-mock:8000/v1" ]; then
  run_py local-via-mock || rc=1
else
  echo "  FAIL refusing to test: LAB_AI_LOCAL_URL is '$local_url', not the mock"; rc=1
fi

step "4. back to the lab's own settings"
lab_compose up -d --wait --force-recreate ai-gateway ai-keys >"$out/restore.log" 2>&1 || { echo "restore failed"; rc=1; }
rendered state.json; echo

step "result"
[ "$rc" = 0 ] && echo "AI GATEWAY E2E: PASS" || echo "AI GATEWAY E2E: FAIL"
exit "$rc"
