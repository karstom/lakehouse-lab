"""End-to-end checks of the AI gateway on a running lab (profile full). Runs INSIDE the
ai-keys container, which has the broker code, the master key and the hub token:

    docker compose exec -T -e E2E_MODE=<mode> ai-keys python3 - < tests/ai/gateway_e2e.py

tests/ai/gateway-e2e.sh drives it; it never talks to a real model: every model call goes to
the gateway's `mock` provider (or `local` only when LAB_AI_LOCAL_URL points at the mock).

Modes:
  mock            (lab with --ai-mock) through the broker as the hub would: mint -> chat
                  (OpenAI and Anthropic shapes, streaming, a scripted tool loop) -> rotate
                  (old key dead) -> a user key cannot manage keys or budgets -> revoke.
                  Budget: a probe user with a tiny budget overruns and gets the lab's
                  message. Everything the test creates is deleted again.
  not-configured  (gateway started with no provider) the model list is empty, and a chat
                  and an Anthropic message both get "AI isn't configured; ask your lab
                  admin." (HTTP 503) while a key still mints.
  local-via-mock  (gateway started with LAB_AI_LOCAL_URL=http://ai-mock:8000/v1 and no
                  mock provider) the `local` provider path end to end, served by the mock.
Last line: E2E_RESULT {"mode", "ok", "checks": {name: bool}, ...}; exit 0 only if all pass.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

from bootstrap import ai_gateway

GW = ai_gateway.GATEWAY_URL
HUB = os.environ["AI_GATEWAY_HUB_TOKEN"]
MASTER = os.environ["LITELLM_MASTER_KEY"]
KEYS = "http://127.0.0.1:8080"
NOT_CONFIGURED = "AI isn't configured; ask your lab admin."
MODE = os.environ.get("E2E_MODE", "mock")
checks, info = {}, {}


def http(method, url, body=None, token=None, raw=False, timeout=60):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            text = r.read().decode()
            return r.status, (text if raw else json.loads(text or "null"))
    except urllib.error.HTTPError as e:
        text = e.read().decode()
        try:
            return e.code, json.loads(text)
        except ValueError:
            return e.code, text


def check(name, ok, detail=None):
    checks[name] = bool(ok)
    if detail is not None:
        info[name] = detail
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f": {detail}" if detail is not None and not ok else ""), flush=True)


def err_message(body):
    if isinstance(body, dict):
        e = body.get("error")
        if isinstance(e, dict):
            return str(e.get("message", ""))
        return str(e or body)
    return str(body)


def mint(user):
    s, b = http("POST", KEYS + "/v1/keys/mint", {"user": user}, HUB)
    if s != 200:
        raise SystemExit(f"mint {user}: HTTP {s} {b}")
    return b


def chat(key, content, model="lab-default", **kw):
    return http("POST", GW + "/v1/chat/completions",
                dict({"model": model, "messages": [{"role": "user", "content": content}]}, **kw), key)


def cleanup_user(user):
    gw = ai_gateway.Gateway(MASTER)
    try:
        gw.delete_keys(gw.lab_keys(user))
    except ai_gateway.GatewayError:
        pass
    http("POST", GW + "/user/delete", {"user_ids": [user]}, MASTER)


def mode_mock():
    user = f"e2e-ai-{int(time.time())}"
    try:
        a = mint(user)
        check("mint returns a key and lab-default", a["key"].startswith("sk-") and a["model"] == "lab-default")
        check("mint says configured (mock enabled)", a["configured"] and "mock" in a["models"], a["models"])
        s, b = chat(a["key"], "hello gateway")
        text = (b.get("choices") or [{}])[0].get("message", {}).get("content", "") if s == 200 else ""
        check("chat through gateway -> mock", s == 200 and text.startswith("mock reply "), (s, b if s != 200 else text))
        s, b = http("POST", GW + "/v1/messages", {"model": "lab-default", "max_tokens": 64,
                                                  "messages": [{"role": "user", "content": "hello anthropic"}]}, a["key"])
        check("Anthropic /v1/messages through gateway -> mock",
              s == 200 and b.get("type") == "message" and "mock reply" in json.dumps(b.get("content")), (s, b))
        s, b = http("POST", GW + "/v1/embeddings", {"model": "lab-default", "input": ["a table"]}, a["key"])
        check("embeddings through gateway -> mock", s == 200 and len(b["data"][0]["embedding"]) == 8, (s, b))
        s, b = http("POST", GW + "/v1/chat/completions", {"model": "lab-default", "stream": True, "messages": [
            {"role": "user", "content": "stream please"}]}, a["key"], raw=True)
        check("streaming", s == 200 and "data: [DONE]" in b and "mock reply" in b, (s, str(b)[:200]))
        s, b = http("POST", GW + "/v1/chat/completions", {"model": "lab-default", "messages": [
            {"role": "user", "content": "#mock:tool-loop-example"}], "tools": [{"type": "function", "function": {
                "name": "catalog_list", "parameters": {"type": "object", "properties": {}}}}]}, a["key"])
        calls = ((b.get("choices") or [{}])[0].get("message") or {}).get("tool_calls") if s == 200 else None
        check("scripted tool call passes through", bool(calls) and calls[0]["function"]["name"] == "catalog_list", (s, b))
        s, b = http("POST", GW + "/key/generate", {"user_id": user}, a["key"])
        check("user key cannot mint keys", s in (401, 403), (s, err_message(b)))
        s, b = http("POST", GW + "/user/update", {"user_id": user, "max_budget": 1e6}, a["key"])
        check("user key cannot raise its budget", s in (401, 403), (s, err_message(b)))
        c = mint(user)
        s, _ = chat(a["key"], "old key")
        check("rotate: the previous key is dead", s == 401, s)
        s, _ = chat(c["key"], "new key")
        check("rotate: the new key works", s == 200, s)
        s, b = http("POST", KEYS + "/v1/keys/mint", {"user": user}, "wrong-token-" + "x" * 30)
        check("broker refuses a wrong hub token", s == 401, s)
        s, b = http("POST", KEYS + "/v1/keys/revoke", {"user": user}, HUB)
        check("revoke", s == 200 and b.get("revoked") == 1, (s, b))
        s, _ = chat(c["key"], "revoked")
        check("revoked key is dead", s == 401, s)
    finally:
        cleanup_user(user)
    budget_check()


def budget_check():
    """A probe user with a tiny budget (set directly with the admin API) overruns it."""
    user = f"e2e-budget-{int(time.time())}"
    gw = ai_gateway.Gateway(MASTER)
    try:
        cfg = dict(ai_gateway.settings(), max_budget=0.05)
        gw.ensure_user(user, cfg)
        key = gw.generate_key(user, cfg)
        s, b = chat(key, "#mock:budget-burner", model="mock")
        check("budget: first request within budget", s == 200, (s, err_message(b)))
        msg, s = "", None
        for _ in range(10):  # spend is recorded asynchronously; a few seconds at most
            s, b = chat(key, "one more")
            if s != 200:
                msg = err_message(b)
                break
            time.sleep(1)
        check("budget: overrun is refused with the lab's message",
              s == 400 and "Your AI budget for this period is used up" in msg, (s, msg))
        info["budget_message"] = msg
        u = gw.get_user(user) or {}
        info["budget_probe_spend"] = u.get("spend")
    finally:
        cleanup_user(user)


def mode_not_configured():
    s, b = http("GET", GW + "/v1/models", token=MASTER)
    check("gateway serves no model", s == 200 and b.get("data") == [], (s, b))
    user = f"e2e-noai-{int(time.time())}"
    try:
        a = mint(user)
        check("mint still works and says not configured",
              a["configured"] is False and a["message"] == NOT_CONFIGURED, a.get("message"))
        s, b = chat(a["key"], "hello?")
        check("chat -> 'AI isn't configured; ask your lab admin.'", s == 503 and err_message(b) == NOT_CONFIGURED, (s, b))
        s, b = http("POST", GW + "/v1/messages", {"model": "lab-default", "max_tokens": 16,
                                                  "messages": [{"role": "user", "content": "hi"}]}, a["key"])
        check("Anthropic shape -> same message", s == 503 and NOT_CONFIGURED in json.dumps(b), (s, b))
        s, b = chat(a["key"], "hi", model="claude")
        check("a named hosted model is refused the same way", s == 503 and err_message(b) == NOT_CONFIGURED, (s, b))
    finally:
        cleanup_user(user)


def mode_local_via_mock():
    s, b = http("GET", GW + "/v1/models", token=MASTER)
    ids = sorted(m["id"] for m in (b or {}).get("data", []))
    check("gateway serves lab-default + local only", ids == ["lab-default", "local"], ids)
    user = f"e2e-local-{int(time.time())}"
    try:
        a = mint(user)
        s, b = chat(a["key"], "hello local", model="local")
        text = (b.get("choices") or [{}])[0].get("message", {}).get("content", "") if s == 200 else ""
        check("local provider path answers (served by the mock)", s == 200 and text.startswith("mock reply "), (s, b))
    finally:
        cleanup_user(user)


def main():
    print(f"[gateway-e2e] mode {MODE}", flush=True)
    {"mock": mode_mock, "not-configured": mode_not_configured, "local-via-mock": mode_local_via_mock}[MODE]()
    ok = bool(checks) and all(checks.values())
    print("E2E_RESULT " + json.dumps({"mode": MODE, "ok": ok, "checks": checks, "info": info}, sort_keys=True,
                                     default=str), flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
