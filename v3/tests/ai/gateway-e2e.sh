#!/usr/bin/env bash
# AI gateway end-to-end checks on a running lab (profile full, installed with --ai-mock).
# Mock model only: no step ever sends a request to a real model server.
#
#   v3/tests/ai/gateway-e2e.sh
#
# 1. mock            rendered config and broker/gateway flows through the mock (gateway_e2e.py;
#                    user keys through ai-frontdoor, incl. its refusals and the end-user fix).
#                    Refused before any request unless the gateway's rendered providers are
#                    exactly [mock] (steps 1 and 4 run with the lab's own settings).
#    network         from a container that is only on `lab` (jupyterhub, like a workspace):
#                    ai-gateway:4000 cannot be opened (by name or IP), ai-frontdoor:4000 can
# 2. not-configured  the gateway recreated with NO provider (LAB_AI_* overridden for this
#                    compose call only; .env and .secrets.env are not touched):
#                    - its rendered config has an empty model list;
#                    - AI requests get "AI isn't configured; ask your lab admin.";
#                    - no_egress_probe.py watches the gateway's sockets from its start through
#                      those requests: every peer must be inside the lab's own networks.
# 3. local-via-mock  OPT-IN (LAB_E2E_LOCAL_VIA_MOCK=1; skipped otherwise): the `local`
#                    provider path, with LAB_AI_LOCAL_URL pointed at the mock (never at a
#                    real server) for this compose call only. Off by default, so a run on a
#                    host whose owner forbids configuring the local provider (quiet hours on
#                    the dev host, where a real model server listens) never configures it:
#                    no step then sets LAB_AI_LOCAL_URL to anything but empty. Turn it on
#                    only where no real model server can be reached (e.g. a CI runner).
# 4. the gateway is recreated with the lab's own settings again.
# Exit 0 only if every step that ran passed. Evidence: out/ai-e2e/ (git-ignored).
#
#   LAB_E2E_LOCAL_VIA_MOCK=1 v3/tests/ai/gateway-e2e.sh    # also run step 3
set -uo pipefail
case "${LAB_E2E_LOCAL_VIA_MOCK:-0}" in
  0|1) ;;
  *) echo "LAB_E2E_LOCAL_VIA_MOCK must be 0 or 1 (got '${LAB_E2E_LOCAL_VIA_MOCK}')" >&2; exit 2 ;;
esac
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
# The gateway's own rendered state is what it will call. Steps 1 and 4 run with the lab's
# settings, so they may only ever reach the mock: stop before any request otherwise.
python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1])).get("providers") == ["mock"] else 1)' \
  "$out/state-mock.json" || die "the lab's gateway has providers other than the mock (see $out/state-mock.json); this test runs on a mock-only lab"
run_py mock || rc=1

step "1b. network: only the front door is reachable from the lab network"
gw_ip=$(lab_compose exec -T ai-keys python3 -c 'import socket; print(socket.gethostbyname("ai-gateway"))' | tr -d '\r')
net=$(lab_compose exec -T -e "GW_IP=$gw_ip" jupyterhub python3 -c '
import os, socket
def tcp(h):
    try:
        socket.create_connection((h, 4000), timeout=5).close()
        return "connected"
    except OSError as e:
        return type(e).__name__
print(tcp("ai-gateway"), tcp(os.environ["GW_IP"]) if os.environ["GW_IP"] else "no-ip", tcp("ai-frontdoor"))
' | tr -d '\r')
echo "  from jupyterhub (lab): ai-gateway, $gw_ip, ai-frontdoor -> $net"
read -r by_name by_ip fd_tcp <<<"$net"
if [ "$by_name" != connected ] && [ -n "$gw_ip" ] && [ "$by_ip" != connected ] && [ "$fd_tcp" = connected ]; then
  echo "  ok   ai-gateway is not reachable from the lab network; ai-frontdoor is"
else
  echo "  FAIL network isolation: gateway by name=$by_name by ip=$by_ip, front door=$fd_tcp"; rc=1
fi

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

if [ "${LAB_E2E_LOCAL_VIA_MOCK:-0}" = 1 ]; then
  step "3. local provider path (LAB_AI_LOCAL_URL -> the mock, never a real server)"
  gateway_with LAB_AI_MOCK=false LAB_AI_LOCAL_URL=http://ai-mock:8000/v1 LAB_AI_LOCAL_MODEL=mock-model \
    LAB_AI_ANTHROPIC_API_KEY= LAB_AI_OPENAI_API_KEY= >"$out/recreate-local.log" 2>&1 || rc=1
  local_url=$(lab_compose exec -T ai-gateway printenv LAB_AI_LOCAL_URL | tr -d '\r')
  if [ "$local_url" = "http://ai-mock:8000/v1" ]; then
    run_py local-via-mock || rc=1
  else
    echo "  FAIL refusing to test: LAB_AI_LOCAL_URL is '$local_url', not the mock"; rc=1
  fi
else
  step "3. local provider path: SKIPPED (opt-in: LAB_E2E_LOCAL_VIA_MOCK=1; the local provider was not configured)"
  rm -f "$out/recreate-local.log" "$out/local-via-mock.log"  # no stale step-3 evidence from an older run
fi

step "4. back to the lab's own settings"
lab_compose up -d --wait --force-recreate ai-gateway ai-keys >"$out/restore.log" 2>&1 || { echo "restore failed"; rc=1; }
rendered state.json; echo

step "result"
[ "$rc" = 0 ] && echo "AI GATEWAY E2E: PASS" || echo "AI GATEWAY E2E: FAIL"
exit "$rc"
