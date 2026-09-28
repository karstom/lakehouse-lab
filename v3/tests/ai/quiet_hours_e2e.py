"""End-to-end checks of the local model's quiet hours (CONTRACT Phase 6, AI polish (a)) on a
running lab. Runs INSIDE the ai-keys container (broker code, master key, hub token):

    docker compose exec -T -e E2E_MODE=<mode> -e E2E_TZ=<zone> ai-keys python3 - < tests/ai/quiet_hours_e2e.py

tests/ai/quiet-hours-e2e.sh drives it, with the gateway started so that the MOCK stands in for
the `local` provider (LAB_AI_LOCAL_URL=http://ai-mock:8000/v1, lab-default -> local, the
`mock` provider on as well). No request ever goes to a real model server.

Modes:
  quiet     the window covers now: `local` and `lab-default` (chat, Anthropic messages,
            embeddings) are refused with HTTP 503 and "The lab's local AI model is resting
            until HH:MM <zone> ...", as the admin and through the AI front door with a user
            key; `mock` still answers; the mock's request log proves no refused request
            reached it (refused BEFORE routing).
  outside   the window does not cover now: `local` and `lab-default` answer (served by the
            mock through the local provider).
  off       no quiet hours: the same.
Last line: E2E_RESULT {"mode", "ok", "checks": {name: bool}, ...}; exit 0 only if all pass.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

from bootstrap import ai_gateway

GW = ai_gateway.GATEWAY_URL            # admin (master key)
FD = ai_gateway.CLIENT_URL             # user keys: the AI front door, as a workspace
MOCK = "http://ai-mock:8000"
HUB = os.environ["AI_GATEWAY_HUB_TOKEN"]
MASTER = os.environ["LITELLM_MASTER_KEY"]
KEYS = "http://127.0.0.1:8080"
MODE = os.environ.get("E2E_MODE", "quiet")
TZ = os.environ.get("E2E_TZ", "America/New_York")
RESTING = "The lab's local AI model is resting until "
checks, info = {}, {}


def http(method, url, body=None, token=None, timeout=60):
    h = {"Content-Type": "application/json"} if body is not None else {}
    if token:
        h["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode() or "null"), dict(r.headers)
    except urllib.error.HTTPError as e:
        text = e.read().decode()
        try:
            return e.code, json.loads(text), dict(e.headers)
        except ValueError:
            return e.code, text, dict(e.headers)


def check(name, ok, detail=None):
    checks[name] = bool(ok)
    if detail is not None:
        info[name] = detail
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f": {detail}" if detail is not None and not ok else ""),
          flush=True)


def message(body):
    if isinstance(body, dict):
        e = body.get("error")
        return str(e.get("message", "")) if isinstance(e, dict) else str(e or body)
    return str(body)


def mock_count():
    s, b, _ = http("GET", MOCK + "/_mock/requests")
    return len(b) if s == 200 and isinstance(b, list) else -1


def calls(base, token, model, tag):
    """chat, Anthropic messages and embeddings for `model` -> {kind: (status, body, headers)}."""
    u = f"{tag} {model} {time.time()}"         # unique text: unique mock response ids
    return {
        "chat": http("POST", base + "/v1/chat/completions",
                     {"model": model, "messages": [{"role": "user", "content": "quiet? " + u}]}, token),
        "messages": http("POST", base + "/v1/messages",
                         {"model": model, "max_tokens": 32,
                          "messages": [{"role": "user", "content": "quiet? " + u}]}, token),
        "embeddings": http("POST", base + "/v1/embeddings", {"model": model, "input": ["q " + u]}, token),
    }


def main():
    user = f"e2e-qh-{int(time.time())}"
    gw = ai_gateway.Gateway(MASTER)
    try:
        s, key, _ = http("POST", KEYS + "/v1/keys/mint", {"user": user}, HUB)
        if s != 200:
            raise SystemExit(f"mint: HTTP {s} {key}")
        key = key["key"]
        for who, base, token in (("admin", GW, MASTER), ("user via front door", FD, key)):
            before = mock_count()
            for model in ("local", "lab-default"):
                res = calls(base, token, model, who)
                for kind, (st, body, hdrs) in res.items():
                    name = f"{who}: {model} {kind}"
                    if MODE == "quiet":
                        msg = message(body)
                        check(f"{name} refused (503, resting until ... {TZ})",
                              st == 503 and RESTING in msg and f" {TZ} (quiet hours " in msg, (st, msg[:300]))
                        info[f"{name} retry-after"] = hdrs.get("Retry-After") or hdrs.get("retry-after")
                    else:
                        check(f"{name} answered by the local provider (mock)", st == 200, (st, str(body)[:300]))
            refused_reached = mock_count() - before
            if MODE == "quiet":
                check(f"{who}: no refused request reached the model server (refused before routing)",
                      refused_reached == 0, refused_reached)
            else:
                check(f"{who}: every request reached the model server", refused_reached == 6, refused_reached)
            st, body, _ = http("POST", base + "/v1/chat/completions",
                               {"model": "mock", "messages": [{"role": "user", "content": f"mock {who} {time.time()}"}]},
                               token)
            text = ((body.get("choices") or [{}])[0].get("message") or {}).get("content", "") if st == 200 else ""
            check(f"{who}: another provider (mock) is not affected", st == 200 and text.startswith("mock reply"),
                  (st, str(body)[:300]))
        if MODE == "quiet":
            sample = next((v for k, v in info.items() if k.endswith("retry-after") and v), None)
            info["sample retry-after"] = sample
            s, b, _ = http("POST", FD + "/v1/chat/completions",
                           {"model": "local", "messages": [{"role": "user", "content": "sample"}]}, key)
            info["sample message"] = message(b)
            print(f"  info sample refusal: HTTP {s} {message(b)!r} Retry-After={sample}", flush=True)
    finally:
        try:
            gw.delete_keys(gw.lab_keys(user))
        except ai_gateway.GatewayError:
            pass
        http("POST", GW + "/user/delete", {"user_ids": [user]}, MASTER)
    ok = bool(checks) and all(checks.values())
    print("E2E_RESULT " + json.dumps({"mode": MODE, "ok": ok, "checks": checks, "info": info}, default=str))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
