#!/usr/bin/env bash
# Smoke check 18, part "no provider" (CONTRACT Phase 5 exit 3): on a lab where NO AI provider is
# enabled (no mock, no local URL, no hosted key), the gateway answers every model call with
# "AI isn't configured; ask your lab admin." and makes no outbound AI call.
#
#   tests/smoke/ai-no-provider.sh        # run it after: install.sh --non-interactive --no-ai-mock
#
# Checked from inside the running ai-gateway container, with its own admin key (never printed):
#   * GET /v1/models lists no model at all (nothing to route to);
#   * POST /v1/chat/completions for lab-default, local, claude, gpt and mock each gets the
#     "AI isn't configured" answer (HTTP 503, refused before routing by config/ai/lab_hooks.py);
#   * if the test-only mock is still running, it received no request during the check.
# Only metadata and refused calls: no request can reach a model, and none reaches the owner's
# local server (quiet hours).
set -uo pipefail
V3=$(cd -P "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
ENV_FILE="$V3/.env"
[ -f "$ENV_FILE" ] || { echo "ai-no-provider: no $ENV_FILE (run install.sh first)" >&2; exit 2; }
env_get() { sed -n "s/^$2=//p" "$1" | tail -n 1 | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/"; }
# Compose needs LAB_AUTH_URL (derived only by installer/lib.sh, never stored:
# INV_V3_PUBLIC_ORIGIN_SINGLE_SOURCE) and the config hashes; lab_settings exports them, as
# `./lab` does, so this script also works when called directly (nightly CI).
V3_DIR=$V3
# shellcheck source=../../installer/lib.sh
. "$V3/installer/lib.sh"
lab_settings
PROJECT=$(env_get "$ENV_FILE" COMPOSE_PROJECT_NAME); PROJECT=${PROJECT:-lakehouse}
PROFILE=$(env_get "$ENV_FILE" LAB_PROFILE); PROFILE=${PROFILE:-core}
DC=(docker compose --project-directory "$V3" --env-file "$V3/versions.env" --env-file "$ENV_FILE"
    --profile "$PROFILE" --profile ai-mock)
export COMPOSE_PROJECT_NAME="$PROJECT"

for v in LAB_AI_MOCK LAB_AI_LOCAL_URL; do
  val=$(env_get "$ENV_FILE" "$v")
  if [ -n "$val" ] && [ "$val" != false ] && [ "$val" != none ]; then
    echo "[FAIL] 18.ai_no_provider: $v=$val in .env: a provider is enabled; re-install with --no-ai-mock / --ai-local-url none first"
    exit 1
  fi
done
if [ -z "$("${DC[@]}" ps -q --status running ai-gateway 2>/dev/null)" ]; then
  echo "[FAIL] 18.ai_no_provider: ai-gateway is not running (profile $PROFILE)"
  exit 1
fi

mock_count() {   # requests the mock has seen, or "-" when it is not running
  "${DC[@]}" exec -T ai-mock python3 -c \
    'import json,urllib.request as u; print(len(json.load(u.urlopen("http://127.0.0.1:8000/_mock/requests", timeout=5))))' \
    2>/dev/null || echo -
}
before=$(mock_count)
# shellcheck disable=SC2016  # the Python below is single-quoted on purpose
result=$("${DC[@]}" exec -T ai-gateway python3 -c '
import json, os, urllib.error, urllib.request
key = os.environ["LITELLM_MASTER_KEY"]
def call(method, path, body=None):
    req = urllib.request.Request("http://127.0.0.1:4000" + path, method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")
st, body = call("GET", "/v1/models")
models = [m.get("id") for m in json.loads(body).get("data", [])] if st == 200 else None
out = {"models_status": st, "models": models, "calls": {}}
for m in ("lab-default", "local", "claude", "gpt", "mock"):
    st, body = call("POST", "/v1/chat/completions",
                    {"model": m, "messages": [{"role": "user", "content": "hello"}]})
    out["calls"][m] = {"status": st, "not_configured": "configured" in body.lower()}
print(json.dumps(out))
' 2>&1)
after=$(mock_count)
last=$(printf '%s\n' "$result" | tail -n 1)
if python3 - "$last" "$before" "$after" <<'PY'
import json, sys
r = json.loads(sys.argv[1])
before, after = sys.argv[2], sys.argv[3]
ok = (r["models_status"] == 200 and r["models"] == [] and
      all(c["status"] == 503 and c["not_configured"] for c in r["calls"].values()) and
      before == after)
sys.exit(0 if ok else 1)
PY
then
  echo "[PASS] 18.ai_no_provider: $last; mock requests before/after: $before/$after"
  exit 0
fi
echo "[FAIL] 18.ai_no_provider: $last; mock requests before/after: $before/$after"
exit 1
