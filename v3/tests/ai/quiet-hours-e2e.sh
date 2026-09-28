#!/usr/bin/env bash
# Local-model quiet hours, end to end on a running lab (CONTRACT Phase 6, AI polish (a)).
# The MOCK stands in for the local model server: LAB_AI_LOCAL_URL points at ai-mock for the
# gateway recreates below (this script's compose calls only; .env and .secrets.env are not
# touched). No step ever sends anything to a real model server.
#
#   LAB_E2E_LOCAL_VIA_MOCK=1 v3/tests/ai/quiet-hours-e2e.sh
#
# OPT-IN like gateway-e2e.sh step 3: configuring the `local` provider (even pointed at the mock)
# is off unless LAB_E2E_LOCAL_VIA_MOCK=1; without it the script only prints SKIPPED. It also
# refuses to run unless the lab's gateway renders providers exactly [mock] (a mock-only test
# install), so it can never be pointed at a lab with a real provider configured.
#
# 1. quiet    window around now (LAB_AI_QUIET_HOURS = now-1h..now+1h in E2E_TZ): `local` and
#             `lab-default` (-> local) refused before routing, mock unaffected
#             (quiet_hours_e2e.py, as admin and with a user key through ai-frontdoor)
# 2. outside  a window that does not cover now: local and lab-default answer (via the mock)
# 3. off      no quiet hours: the same
# 4. the gateway is recreated with the lab's own settings (providers [mock] again)
# Exit 0 only if every step passed. Evidence: out/ai-quiet-hours/ (git-ignored).
set -uo pipefail
case "${LAB_E2E_LOCAL_VIA_MOCK:-0}" in
  1) ;;
  0) echo "quiet-hours e2e: SKIPPED (opt-in: LAB_E2E_LOCAL_VIA_MOCK=1; the local provider was not configured)"; exit 0 ;;
  *) echo "LAB_E2E_LOCAL_VIA_MOCK must be 0 or 1 (got '${LAB_E2E_LOCAL_VIA_MOCK}')" >&2; exit 2 ;;
esac
E2E_TZ=${E2E_TZ:-America/New_York}
V3_DIR=$(cd -P "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
# shellcheck source=../../installer/lib.sh
. "$V3_DIR/installer/lib.sh"
[ -f "$LAB_ENV_FILE" ] || die "no $LAB_ENV_FILE; install the lab first"
lab_settings
profile_includes "$LAB_PROFILE" ai || die "the AI gateway runs on profile full (this lab: $LAB_PROFILE)"
[ "${LAB_AI_MOCK:-false}" = true ] || die "install the lab with --ai-mock first (tests use the mock model only)"
out="$V3_DIR/out/ai-quiet-hours"
mkdir -p "$out"
rc=0
HERE="$V3_DIR/tests/ai"
MOCK_URL=http://ai-mock:8000/v1

step() { printf '\n== %s\n' "$*"; }
rendered() { lab_compose exec -T ai-gateway cat "/tmp/lab-ai/$1"; }

# gateway_with ENV... -> recreate ai-gateway with these values (this compose call only)
gateway_with() {
  (
    for kv in "$@"; do export "${kv?}"; done
    lab_compose up -d --wait --no-deps --force-recreate ai-gateway
  )
}

# local_via_mock WINDOW -> the gateway with local = the mock, lab-default -> local, and
# LAB_AI_QUIET_HOURS=WINDOW in E2E_TZ. Refuses unless the local URL really is the mock.
local_via_mock() {
  gateway_with LAB_AI_MOCK=true LAB_AI_LOCAL_URL="$MOCK_URL" LAB_AI_LOCAL_MODEL=mock-model \
    LAB_AI_LOCAL_API_KEY= LAB_AI_ANTHROPIC_API_KEY= LAB_AI_OPENAI_API_KEY= \
    LAB_AI_DEFAULT_PROVIDER=local LAB_AI_QUIET_HOURS="$1" LAB_AI_QUIET_TZ="$E2E_TZ" \
    >>"$out/recreate.log" 2>&1 || return 1
  [ "$(lab_compose exec -T ai-gateway printenv LAB_AI_LOCAL_URL | tr -d '\r')" = "$MOCK_URL" ]
}

run_py() {  # run_py MODE -> quiet_hours_e2e.py in ai-keys
  lab_compose exec -T -e "E2E_MODE=$1" -e "E2E_TZ=$E2E_TZ" -w /opt/lab ai-keys python3 - \
    <"$HERE/quiet_hours_e2e.py" | tee "$out/$1.log"
  grep -q '^E2E_RESULT {"mode": "'"$1"'", "ok": true' "$out/$1.log"
}

# window OFFSET_MIN LENGTH_MIN -> HH:MM-HH:MM in E2E_TZ, starting OFFSET_MIN from now
window() {
  python3 - "$E2E_TZ" "$1" "$2" <<'PY'
import datetime as dt, sys, zoneinfo
now = dt.datetime.now(zoneinfo.ZoneInfo(sys.argv[1]))
a = now + dt.timedelta(minutes=int(sys.argv[2]))
b = a + dt.timedelta(minutes=int(sys.argv[3]))
print(f"{a:%H:%M}-{b:%H:%M}")
PY
}

state_is() {  # state_is PYTHON_EXPR -> the rendered state.json satisfies it (as `s`)
  rendered state.json >"$out/state.json"
  python3 -c 'import json,sys; s=json.load(open(sys.argv[1])); sys.exit(0 if eval(sys.argv[2]) else 1)' \
    "$out/state.json" "$1"
}

: >"$out/recreate.log"
step "0. precondition: a mock-only lab"
rendered state.json | tee "$out/state-before.json"; echo
python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1])).get("providers") == ["mock"] else 1)' \
  "$out/state-before.json" || die "the lab's gateway has providers other than the mock; this test runs on a mock-only lab"

for mode in quiet outside off; do
  case "$mode" in
    quiet)   win=$(window -60 120) ;;
    outside) win=$(window 120 60) ;;
    off)     win="" ;;
  esac
  step "$mode: LAB_AI_QUIET_HOURS='$win' $E2E_TZ; local = the mock; lab-default -> local"
  if ! local_via_mock "$win"; then
    echo "  FAIL refusing to test: the gateway did not come up with the local URL pointed at the mock"; rc=1; break
  fi
  if [ -n "$win" ]; then
    want="s['quiet_hours']=={'window':'$win','tz':'$E2E_TZ'} and s['local_models']==['lab-default','local'] and s['providers']==['mock','local']"
  else
    want="s['quiet_hours'] is None and s['providers']==['mock','local']"
  fi
  if state_is "$want"; then echo "  ok   rendered state: $(cat "$out/state.json")"
  else echo "  FAIL rendered state: $(cat "$out/state.json")"; rc=1; fi
  run_py "$mode" || rc=1
done
lab_compose logs --no-color --since 30m ai-gateway 2>/dev/null | grep -E 'quiet hours|providers:' | tail -n 6 >"$out/gateway-log.txt" || true
cat "$out/gateway-log.txt"

step "4. back to the lab's own settings"
lab_compose up -d --wait --force-recreate ai-gateway ai-keys >"$out/restore.log" 2>&1 || { echo "  FAIL restore"; rc=1; }
if state_is "s['providers']==['mock'] and s.get('local_models')==[]"; then echo "  ok   providers [mock] again (no local provider)"
else echo "  FAIL after restore: $(cat "$out/state.json")"; rc=1; fi

step "result"
[ "$rc" = 0 ] && echo "QUIET HOURS E2E: PASS" || echo "QUIET HOURS E2E: FAIL"
exit "$rc"
