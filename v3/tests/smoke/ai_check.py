"""Smoke check 18 (CONTRACT Phase 5): context-aware AI assist with the MOCK model.

  18  A scripted agent loop (ai_agent_probe.py, run INSIDE the user's workspace kernel) goes
      through the AI gateway (the user's own key, model `mock`, which returns scripted tool
      calls) and the lab's REAL MCP servers (lab-context, dbt-mcp on `analytics`, lab-trino),
      and answers "Which tables feed the 'Revenue by region' dashboard, and when did each last
      load?":
        * as alice: the dashboard's tables come from Superset, the upstream tables from dbt
          lineage, and every load time equals the newest snapshot in Trino's "$snapshots"
          (computed here, independently, with alice's own token); every turn went through the
          gateway; the Trino tool refuses writes, caps rows at 200 and stops at its time
          limit; airflow_runs answers as alice;
        * as victor (viewer): the same loop, plus calls he may not make (alice's private
          draft dashboard; a write): they are refused and nothing of alice's leaks; every
          load time he gets is one he can read with his own token;
        * no output of any tool or of the gateway contains a token or the gateway key;
        * gateway rules (from here, with the gateway's admin key): a model whose provider is
          not enabled is refused and the mock sees no request (no outbound call); a user over
          their budget gets the budget error;
        * tutor mode: `current_lesson` carries the module's tutor.md, and `lab-ai tutor off|on`
          switches it (WORKSPACE-AI's CLI).
        * AI front door (inside alice's workspace): the workspace is pointed at ai-frontdoor,
          cannot open ai-gateway:4000 at all (neither by name nor by its IP), and its own key
          gets 403 there on /health, /model/info and /v1/model/info; the Jupyter AI persona
          list holds only the Lab Assistant, which answers a chat message through the front
          door (tests/workspace/ai_chat_probe.py, mock model).
      Profile `full` only (the gateway, Superset and Airflow are all in `full`).

NEVER a real model: the loop always names the mock model, and the owner's local LLM must not
receive inference requests from tests (quiet-hours rule).
"""
import datetime
import json
import os
import time
import traceback

C18 = "18.ai_assist_mcp_agent_loop"

DASHBOARD = "Revenue by region"
PRIVATE_DASHBOARD = "smoke 18: alice's private draft"
# What the bundled dashboard is built from (config/superset/dashboards + the starter dbt
# project): the answer must name exactly these. The CHECK derives nothing from this list;
# the loop discovers the tables through Superset and dbt, and this is what it must find.
EXPECTED_DATASET_TABLES = {"lakehouse.analytics.dim_customers", "lakehouse.analytics.fct_orders",
                           "lakehouse.analytics.revenue_by_region"}
EXPECTED_SOURCES = {f"lakehouse.samples.{t}" for t in ("customer", "lineitem", "nation",
                                                       "orders", "region")}
MARKER = "SMOKE_AI_RESULT "
HERE = os.path.dirname(os.path.abspath(__file__))

# Phase 5 interfaces (GATEWAY: compose/ai.yaml; WORKSPACE-AI: the hub's key injection):
#   the gateway (LiteLLM) on the lab network; the workspace gets LAB_AI_GATEWAY_URL/LAB_AI_KEY
#   (OPENAI_BASE_URL/OPENAI_API_KEY); `mock` is served only by tests/ai/mock_llm (ai-mock),
#   whose script API the loop uses. The admin key (AI_GATEWAY_MASTER_KEY) reaches this
#   container only through run.sh, by name.
GATEWAY = os.environ.get("LAB_SMOKE_AI_GATEWAY_URL", "http://ai-gateway:4000").rstrip("/")    # admin only
# Every user-key call goes where a workspace's goes: the AI front door (bootstrap/ai_frontdoor.py).
FRONTDOOR = os.environ.get("LAB_SMOKE_AI_FRONTDOOR_URL", "http://ai-frontdoor:4000").rstrip("/")
PERSONA_ID = "jupyter-ai-personas::lakehouse::LabAssistant"     # lakehouse/ai.py PERSONA_ID
CHAT_PROBE = os.environ.get("LAB_SMOKE_CHAT_PROBE", "/opt/tests-workspace/ai_chat_probe.py")
MOCK_CTL = os.environ.get("LAB_SMOKE_AI_MOCK_URL", "http://ai-mock:8000").rstrip("/")
MOCK_MODEL = "mock"          # never anything else (quiet hours: no real model in tests)
HOSTED_OR_LOCAL = ("claude", "gpt", "local")
# The mock costs LAB_AI_MOCK_COST_PER_MTOK (default 1000 USD per million tokens, so budget
# tests overrun fast); the loop's conversation is ~100k tokens, so the check lifts the user's
# budget for its own run and puts budget and spend back afterwards.
LOOP_BUDGET_USD = 1_000_000


def probe_code(params):
    with open(os.path.join(HERE, "ai_agent_probe.py"), encoding="utf-8") as f:
        src = f.read()
    return (src + f"\nprint({MARKER!r} + json.dumps(probe_ai(json.loads("
            f"{json.dumps(json.dumps(params))})), default=str), flush=True)\n")


def parse(stdout):
    for line in reversed((stdout or "").splitlines()):
        if line.startswith(MARKER):
            return json.loads(line[len(MARKER):])
    return None


def _dt(v):
    if v is None:
        return None
    if isinstance(v, datetime.datetime):
        d = v
    else:
        d = datetime.datetime.fromisoformat(str(v).replace("Z", "+00:00").replace(" UTC", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=datetime.timezone.utc)
    return d.astimezone(datetime.timezone.utc)


def truth(S, token, tables):
    """{table: newest snapshot commit time (UTC datetime) or an error string}, straight from
    Trino's "$snapshots" with the given user's token."""
    out = {}
    cur = S.trino_conn(token).cursor()
    for t in sorted(tables):
        c, s, n = t.split(".")
        try:
            cur.execute(f'SELECT max(committed_at) FROM {c}.{s}."{n}$snapshots"')
            out[t] = _dt(cur.fetchall()[0][0])
        except Exception as e:  # noqa: BLE001 - recorded
            out[t] = f"{type(e).__name__}: {str(e)[:160]}"
    return out


def _probe_params(user, gateway_override, extra_calls, extra_checks):
    p = {"user": user, "dashboard": DASHBOARD, "mock_control_url": MOCK_CTL,
         "servers": ["lab-context", "dbt-analytics", "lab-trino"],
         "extra_first": extra_calls, "extra_checks": extra_checks, "tutor": extra_checks,
         "tutor_module": "A1", "tool_timeout": 240}
    p.update(gateway_override.get(user) or {})
    return p


def _gateway_override():
    """Debugging only: LAB_SMOKE_AI_KEYS='alice=k1,victor=k2' (+ LAB_SMOKE_AI_GATEWAY_URL) replace
    the key the hub injected into the workspace."""
    keys = dict(kv.split("=", 1) for kv in os.environ.get("LAB_SMOKE_AI_KEYS", "").split(",") if "=" in kv)
    return {u: {"gateway_url": FRONTDOOR + "/v1", "gateway_key": k} for u, k in keys.items()}


class Gateway:
    """The gateway's admin API (LiteLLM, open-source endpoints) with the master key."""

    def __init__(self, base=GATEWAY, key=None):
        import requests
        self.base = base
        self.key = key if key is not None else os.environ.get("LAB_AI_GATEWAY_MASTER_KEY", "")
        self.s = requests.Session()

    def call(self, method, path, body=None, key=None):
        """With `key` (a user key): through the front door, like a workspace. Without: the
        admin API on the gateway itself (the smoke container is on the `ai` network)."""
        base = FRONTDOOR if key else self.base
        # Connection: close — no idle keep-alive connection to reuse. uvicorn (the gateway)
        # closes idle connections after 5 s and settle_spend polls every 5 s, so a reused
        # socket could be closed under the request: ConnectionResetError (nightly 2026-09-28,
        # REG_V3_SMOKE_KEEPALIVE_IDLE_RACE; same class as the Phase 4 Caddy keepalive 502).
        r = self.s.request(method, base + path, json=body, timeout=120,
                           headers={"Authorization": f"Bearer {key or self.key}",
                                    "Connection": "close"})
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, r.text[:500]

    def user_info(self, user):
        st, body = self.call("GET", f"/user/info?user_id={user}")
        return (body or {}).get("user_info") if st == 200 and isinstance(body, dict) else None

    def lift_budget(self, user):
        """-> what to restore, or None (no admin key / unknown user)."""
        if not self.key:
            return None
        info = self.user_info(user)
        if not info:
            return None
        keep = {"max_budget": info.get("max_budget"), "spend": info.get("spend") or 0}
        self.call("POST", "/user/update", {"user_id": user, "max_budget": LOOP_BUDGET_USD})
        return keep

    def settle_spend(self, user, quiet_s=25, timeout_s=180, poll_s=5):
        """Wait until the gateway has written the user's pending spend. LiteLLM adds spend to
        the database in batches (every ~10 s), so a restore made right after the loop was
        overwritten by the loop's last batch (integration run: victor left at 18.69 of 5 USD,
        so his next real request was refused). -> the settled spend, or None."""
        last, since, deadline = None, time.time(), time.time() + timeout_s
        while time.time() < deadline:
            info = self.user_info(user) or {}
            cur = info.get("spend")
            if cur != last:
                last, since = cur, time.time()
            elif time.time() - since >= quiet_s:
                return cur
            time.sleep(poll_s)
        return last

    def restore_budget(self, user, keep):
        """Budget and spend back to what they were before the loop, once the loop's spend is
        written. -> (HTTP status, spend read back after one more batch interval)."""
        if keep is None:
            return None
        self.settle_spend(user)
        st, _ = self.call("POST", "/user/update", dict(keep, user_id=user))
        time.sleep(15)
        return st, (self.user_info(user) or {}).get("spend")

    def temp_key(self, user):
        """A 30-minute key of gateway user `user` (created if missing) -> (key, created)."""
        if not self.key:
            return None, False
        created = False
        if not self.user_info(user):
            st, _ = self.call("POST", "/user/new", {"user_id": user, "user_role": "internal_user",
                                                    "metadata": {"lab_user": user}})
            created = st < 300
        st, body = self.call("POST", "/key/generate", {"user_id": user, "duration": "30m",
                                                       "metadata": {"purpose": "smoke check 18"}})
        return ((body or {}).get("key") if isinstance(body, dict) else None), created

    def chat(self, key, model, text="hello"):
        return self.call("POST", "/v1/chat/completions", {
            "model": model, "messages": [{"role": "user", "content": text}]}, key=key)


def mock_requests():
    import requests
    try:
        r = requests.get(MOCK_CTL + "/_mock/requests", timeout=30)
        return len(r.json()) if r.ok else None
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- setup through the browser
def setup_superset(S, phase3, browser, ev):
    """Superset knows a user only after one browser login (lab_bearer.py). Alice creates a
    private DRAFT dashboard (owned by her, not published): Superset hides it from victor."""
    alice = phase3.UserSession(S, browser, "alice")
    ss = phase3.Superset(S, alice)
    ss.login()
    old = ss.dashboard(PRIVATE_DASHBOARD)
    if old:
        ss.api("DELETE", f"/dashboard/{old['id']}")
    r = ss.api("POST", "/dashboard/", {"dashboard_title": PRIVATE_DASHBOARD, "published": False})
    body = phase3._json(r) or {}
    ev["private_dashboard"] = {"status": r.status, "id": body.get("id")}
    alice.close()
    victor = phase3.UserSession(S, browser, "victor")
    phase3.Superset(S, victor).login()
    victor.close()
    return body.get("id")


def cleanup_superset(S, phase3, browser, dash_id):
    if not dash_id:
        return None
    alice = phase3.UserSession(S, browser, "alice")
    ss = phase3.Superset(S, alice)
    ss.login()
    st = ss.api("DELETE", f"/dashboard/{dash_id}").status
    alice.close()
    return st


def ensure_analytics(S, phase3, browser, ev):
    """The dashboard reads lakehouse.analytics.*, which the lab_dbt_build DAG writes (check 12
    runs it). When 18 runs alone on a fresh lab, alice triggers it here first."""
    cur = S.trino_conn(S.user_token("alice")).cursor()
    cur.execute("SELECT table_name FROM lakehouse.information_schema.tables "
                "WHERE table_schema = 'analytics'")
    have = {f"lakehouse.analytics.{r[0]}" for r in cur.fetchall()}
    missing = sorted(EXPECTED_DATASET_TABLES - have)
    ev["analytics_missing_before"] = missing
    if not missing:
        return
    alice = phase3.UserSession(S, browser, "alice")
    af = phase3.Airflow(S, alice)
    af.login()
    st, run = af.trigger("lab_dbt_build")
    ev["lab_dbt_build"] = af.wait_run("lab_dbt_build", run.get("dag_run_id", ""), 900) \
        if st in (200, 201) else {"trigger_status": st}
    alice.close()


# ---------------------------------------------------------------- AI front door, from inside
WS_FRONTDOOR_CODE = r"""
import json, os, socket, subprocess, sys, urllib.error, urllib.request
out = {"LAB_AI_GATEWAY_URL": os.environ.get("LAB_AI_GATEWAY_URL"),
       "OPENAI_BASE_URL": os.environ.get("OPENAI_BASE_URL")}
def tcp(host, port):
    try:
        socket.create_connection((host, port), timeout=5).close()
        return "connected"
    except OSError as e:
        return f"{type(e).__name__}: {e}"[:120]
out["direct_gateway_by_name"] = tcp("ai-gateway", 4000)
out["direct_gateway_by_ip"] = tcp(GATEWAY_IP, 4000) if GATEWAY_IP else "no ip"
out["frontdoor_tcp"] = tcp("ai-frontdoor", 4000)
def get(path):
    req = urllib.request.Request(os.environ.get("LAB_AI_GATEWAY_URL", "") + path,
                                 headers={"Authorization": "Bearer " + os.environ.get("LAB_AI_KEY", "")})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:
        return f"{type(e).__name__}: {e}"[:120]
out["status"] = {p: get(p) for p in ("/health", "/model/info", "/v1/model/info", "/v1/models")}
base = os.environ.get("JUPYTERHUB_SERVICE_URL", "").replace("0.0.0.0", "127.0.0.1")
# A NEW chat file: a .chat document keeps every user that ever joined it, so an old file
# would list personas of an earlier image, not the ones this server offers now.
chat_file = os.path.expanduser("~/smoke18/frontdoor.chat")
if os.path.exists(chat_file):
    os.remove(chat_file)
with open(os.path.expanduser("~/.smoke-ai-chat-probe.py"), "w") as f:
    f.write(PROBE_SRC)
p = subprocess.run([sys.executable, os.path.expanduser("~/.smoke-ai-chat-probe.py"), "--base", base,
                    "--token", os.environ.get("JUPYTERHUB_API_TOKEN", ""), "--chat", "smoke18/frontdoor.chat",
                    "--message", "Hello from smoke check 18: which schema is mine?", "--timeout", "240"],
                   capture_output=True, text=True, timeout=300)
try:
    out["chat"] = json.loads(p.stdout.strip().splitlines()[-1])
except Exception:
    out["chat"] = {"ok": False, "stdout": p.stdout[-600:], "stderr": p.stderr[-600:]}
print("SMOKE_AI_FRONTDOOR " + json.dumps(out), flush=True)
"""


def workspace_frontdoor(ws):
    """Run WS_FRONTDOOR_CODE in the user's workspace kernel -> its JSON (or an error dict)."""
    import socket
    try:
        gw_ip = socket.gethostbyname(GATEWAY.split("://", 1)[1].split(":")[0])
    except OSError:
        gw_ip = ""
    try:
        with open(CHAT_PROBE, encoding="utf-8") as f:
            probe_src = f.read()
    except OSError as e:
        return {"error": f"no chat probe at {CHAT_PROBE}: {e}"}
    code = f"GATEWAY_IP = {gw_ip!r}\nPROBE_SRC = {probe_src!r}\n" + WS_FRONTDOOR_CODE
    raw = ws.run(code, timeout=420)
    for line in reversed((raw.get("stdout") or "").splitlines()):
        if line.startswith("SMOKE_AI_FRONTDOOR "):
            res = json.loads(line[len("SMOKE_AI_FRONTDOOR "):])
            res["gateway_ip"] = gw_ip
            return res
    return {"error": "no result", "stderr_tail": (raw.get("stderr") or "")[-800:],
            "stdout_tail": (raw.get("stdout") or "")[-400:]}


def evaluate_frontdoor(fdr):
    fdr = fdr or {}
    st = fdr.get("status") or {}
    chat = fdr.get("chat") or {}
    checks = {
        "workspace_points_at_frontdoor": str(fdr.get("LAB_AI_GATEWAY_URL", "")).startswith("http://ai-frontdoor:")
        and str(fdr.get("OPENAI_BASE_URL", "")).startswith("http://ai-frontdoor:"),
        "gateway_unreachable_by_name": fdr.get("direct_gateway_by_name", "connected") != "connected",
        "gateway_unreachable_by_ip": bool(fdr.get("gateway_ip")) and
        fdr.get("direct_gateway_by_ip", "connected") != "connected",
        "frontdoor_reachable": fdr.get("frontdoor_tcp") == "connected",
        "health_and_model_info_403": all(st.get(p) == 403 for p in ("/health", "/model/info", "/v1/model/info")),
        "models_200": st.get("/v1/models") == 200,
        "persona_list_only_lab_assistant": chat.get("personas") == [PERSONA_ID],
        "persona_answers_through_frontdoor": bool(chat.get("ok")) and chat.get("sender") == PERSONA_ID
        and "mock reply" in str(chat.get("reply", "")),
    }
    return all(checks.values()), {"checks": checks, **{k: v for k, v in fdr.items() if k != "chat"},
                                  "chat": {k: (str(v)[:300] if k == "reply" else v) for k, v in chat.items()}}


# ---------------------------------------------------------------- the check
def _run_user(S, browser, user, params, gw, frontdoor=False):
    from workspace import Workspace
    ws = Workspace(browser, S.url, S.D, user, S.PW)
    keep = None
    info_budget = {}
    try:
        login = ws.login_and_spawn()
        if not login["ok"]:
            return None, {"login_spawn": login}
        # Fallback key (only used when the workspace has none): minted for this user.
        temp_key, created = gw.temp_key(user)
        if temp_key:
            params = dict(params, fallback_gateway_url=FRONTDOOR + "/v1", fallback_gateway_key=temp_key)
        # After the spawn: minting the workspace key (ai-keys) re-applies the lab's budget.
        keep = gw.lift_budget(user)
        info_budget["budget_lifted"] = keep is not None
        raw = ws.run(probe_code(params), timeout=1500)
        if frontdoor:
            info_budget["frontdoor"] = workspace_frontdoor(ws)
        if temp_key:
            gw.call("POST", "/key/delete", {"keys": [temp_key]})
        if created:
            keep = None
            gw.call("POST", "/user/delete", {"user_ids": [user]})
        res = parse(raw.get("stdout"))
        info = {"login_seconds": login["seconds"], "kernel_seconds": raw.get("kernel_seconds"),
                **info_budget}
        if res is None:
            info.update({"no_result": True, "stderr_tail": (raw.get("stderr") or "")[-1500:],
                         "stdout_tail": (raw.get("stdout") or "")[-600:],
                         "timeout": raw.get("timeout"), "error": raw.get("error")})
        return res, info
    finally:
        if keep is not None:
            st_spend = gw.restore_budget(user, keep)
            print(f"[info] {user}'s AI budget restored: HTTP {st_spend and st_spend[0]}, spend "
                  f"now {st_spend and st_spend[1]} (was {keep.get('spend')})", flush=True)
        info_stop = ws.stop_server()
        print(f"[info] {user}'s workspace stopped: {info_stop}", flush=True)
        ws.close()


def _calls(loop):
    return [c for t in (loop or {}).get("turns", []) for c in t.get("calls", [])]


def evaluate_alice(res, truth_alice, private_id):
    """-> (ok, evidence) for alice's run."""
    loop = (res or {}).get("loop") or {}
    ans = loop.get("answer_json") or {}
    rows = {r["table"]: r for r in ans.get("tables", [])}
    st = loop.get("policy_state") or {}
    tables = {t for t, r in rows.items() if r.get("kind") == "table"}
    views = {t for t, r in rows.items() if r.get("kind") == "view"}
    mism = {}
    for t in tables:
        want = truth_alice.get(t)
        got = rows[t].get("last_loaded")
        if not isinstance(want, datetime.datetime) or _dt(got) != want:
            mism[t] = {"answer": got, "trino": str(want)}
    calls = _calls(loop)
    names = [c["tool"] for c in calls]
    airflow = [c for c in calls if c["tool"] == "ctx__airflow_runs"]
    private = [c for c in calls if c["tool"] == "ctx__superset_dashboard_datasets"
               and c["args"].get("dashboard") == PRIVATE_DASHBOARD]
    extra = res.get("extra") or {}
    checks = {
        "every_turn_through_gateway": bool(loop.get("turns")) and all(
            t.get("gateway_status") == 200 for t in loop["turns"]),
        "gateway_returned_the_scripted_turns": bool(loop.get("turns")) and all(
            t.get("matches_script") for t in loop["turns"]),
        "answered": bool(loop.get("answer")) and bool(rows),
        "dataset_tables_from_superset": set(st.get("dataset_tables") or []) == EXPECTED_DATASET_TABLES,
        "tables_in_answer": tables == EXPECTED_DATASET_TABLES | EXPECTED_SOURCES,
        "sources_from_dbt_lineage": EXPECTED_SOURCES <= {
            n.get("relation") for n in (st.get("dbt_nodes") or {}).values()} and any(
            any(i.startswith("source.") for i in ids) for ids in (st.get("lineage") or {}).values()),
        "staging_views_listed": len(views) >= 1,
        "load_times_equal_trino_snapshots": not mism and len(tables) == 8,
        "airflow_runs_as_user": bool(airflow) and not airflow[0]["is_error"],
        "own_private_dashboard_visible": bool(private) and not private[0]["is_error"],
        "no_token_in_outputs": loop.get("jwt_in_outputs") is False and
        loop.get("user_token_in_outputs") is False and loop.get("key_in_outputs") is False,
        "trino_tool_is_alice": extra.get("current_user") == "alice",
        "trino_row_cap_200": (extra.get("row_cap") or {}).get("row_count") == 200 and
        (extra.get("row_cap") or {}).get("truncated") is True,
        "trino_writes_refused": bool(extra.get("writes_refused")) and all(extra["writes_refused"].values()),
        "trino_time_limit": bool((extra.get("time_limit") or {}).get("is_error")) and
        "longer than" in (extra.get("time_limit") or {}).get("text", ""),
    }
    ev = {"checks": checks, "tables": {t: rows[t].get("last_loaded") for t in sorted(rows)},
          "mismatches": mism, "tool_calls": len(calls), "tools_used": sorted(set(names)),
          "turns": len(loop.get("turns", [])), "seconds": loop.get("seconds"),
          "servers": loop.get("servers"), "extra": extra,
          "gateway_key_source": loop.get("gateway_key_source"), "gateway_models": loop.get("gateway_models"),
          "private_dashboard_id": private_id, "errors": st.get("errors"),
          "loop_error": loop.get("error") or res.get("loop_error") if res else "no result"}
    return all(checks.values()), ev


def evaluate_victor(res, truth_victor, private_id):
    loop = (res or {}).get("loop") or {}
    ans = loop.get("answer_json") or {}
    rows = {r["table"]: r for r in ans.get("tables", [])}
    calls = _calls(loop)
    private = [c for c in calls if c["tool"] == "ctx__superset_dashboard_datasets"
               and c["args"].get("dashboard") == PRIVATE_DASHBOARD]
    writes = [c for c in calls if c["tool"] == "trino__trino_query"
              and c["args"].get("sql", "").upper().startswith("INSERT")]
    peek = [c for c in calls if c["tool"] == "trino__trino_query"
            and "system.runtime.queries" in c["args"].get("sql", "")]
    peek_rows = None
    if peek and not peek[0]["is_error"]:
        try:
            peek_rows = json.loads(peek[0]["result_full"])["rows"][0][0]
        except Exception:  # noqa: BLE001
            peek_rows = peek[0]["result_head"]
    readable = {}
    for t, r in rows.items():
        if r.get("kind") != "table" or r.get("last_loaded") is None:
            continue
        want = truth_victor.get(t)
        readable[t] = isinstance(want, datetime.datetime) and _dt(r["last_loaded"]) == want
    blob = json.dumps(loop, default=str)
    checks = {
        "every_turn_through_gateway": bool(loop.get("turns")) and all(
            t.get("gateway_status") == 200 for t in loop["turns"]),
        "answered": bool(loop.get("answer")),
        "private_dashboard_refused": bool(private) and private[0]["is_error"],
        "write_refused": bool(writes) and writes[0]["is_error"],
        "no_other_users_queries": peek_rows == 0,
        "only_what_victor_can_read": bool(readable) and all(readable.values()),
        "nothing_of_alices_private_dashboard": private_id is None or
        f'"id": {private_id}' not in blob,
        "no_token_in_outputs": loop.get("jwt_in_outputs") is False and
        loop.get("user_token_in_outputs") is False and loop.get("key_in_outputs") is False,
    }
    ev = {"checks": checks, "tables": {t: rows[t].get("last_loaded") for t in sorted(rows)},
          "victor_can_read": readable, "denied": [
              {"tool": c["tool"], "args": c["args"], "result": c["result_head"][:200]}
              for c in calls if c["is_error"]],
          "system_runtime_queries_of_alice": peek_rows, "turns": len(loop.get("turns", [])),
          "gateway_key_source": loop.get("gateway_key_source"),
          "tool_calls": len(calls), "seconds": loop.get("seconds"),
          "loop_error": loop.get("error") or (res or {}).get("loop_error")}
    return all(checks.values()), ev


def check_ai(S):
    import phase3
    from playwright.sync_api import sync_playwright
    ev = {"model": MOCK_MODEL, "gateway": GATEWAY}
    override = _gateway_override()
    gw = Gateway()
    ev["gateway_admin_key"] = bool(gw.key)
    if override:
        ev["key_override"] = sorted(override)
    all_tables = EXPECTED_DATASET_TABLES | EXPECTED_SOURCES
    private_id = None
    with sync_playwright() as pw:
        browser = phase3.launch(pw, S)
        try:
            ensure_analytics(S, phase3, browser, ev)
            private_id = setup_superset(S, phase3, browser, ev)
            truth_alice = truth(S, S.user_token("alice"), all_tables)
            ev["truth_alice"] = {t: str(v) for t, v in truth_alice.items()}
            truth_victor = truth(S, S.user_token("victor"), all_tables)
            both = [("ctx__superset_dashboard_datasets", {"dashboard": PRIVATE_DASHBOARD}),
                    ("trino__trino_query", {"sql": "INSERT INTO lakehouse.analytics.fct_orders "
                                                   "SELECT * FROM lakehouse.analytics.fct_orders LIMIT 0"}),
                    ("trino__trino_query", {"sql": "SELECT count(*) FROM system.runtime.queries "
                                                   "WHERE \"user\" = 'alice'"}),
                    ("ctx__airflow_runs", {"dag_id": "lab_dbt_build", "limit": 1})]
            res_a, info_a = _run_user(S, browser, "alice",
                                      _probe_params("alice", override, both, True), gw, frontdoor=True)
            ok_a, ev["alice"] = evaluate_alice(res_a, truth_alice, private_id)
            ok_fd, ev["frontdoor"] = evaluate_frontdoor(info_a.pop("frontdoor", None))
            ev["alice"]["run"] = info_a
            res_v, info_v = _run_user(S, browser, "victor",
                                      _probe_params("victor", override, both, False), gw)
            ok_v, ev["victor"] = evaluate_victor(res_v, truth_victor, private_id)
            ev["victor"]["run"] = info_v
            ev["gateway_rules"] = gateway_rules(gw)
            ev["tutor"] = (res_a or {}).get("tutor")
        finally:
            try:
                ev["private_dashboard_deleted"] = cleanup_superset(S, phase3, browser, private_id)
            except Exception as e:  # noqa: BLE001
                ev["private_dashboard_deleted"] = f"{type(e).__name__}: {e}"[:200]
            browser.close()
    rules = ev["gateway_rules"]
    tutor_ok = bool((ev.get("tutor") or {}).get("ok"))
    S.check(C18, ok_a and ok_v and ok_fd and rules.get("ok") and tutor_ok, ev)


# ---------------------------------------------------------------- gateway rules (smoke side)
def gateway_rules(gw):
    """(1) Models whose provider is not enabled (hosted: off by default; local: not set in a
    test install) are refused, and the mock, the only provider, sees no request: nothing went
    out. (2) A user past their budget gets the budget error. Both with a throwaway gateway user
    and key (admin API), removed again."""
    out = {}
    if not gw.key:
        return {"ok": False, "reason": "no gateway admin key (run.sh passes AI_GATEWAY_MASTER_KEY)"}
    user = f"smoke18-{os.urandom(3).hex()}"
    st, _ = gw.call("POST", "/user/new", {"user_id": user, "max_budget": 0.000001,
                                          "metadata": {"purpose": "smoke check 18"}})
    out["temp_user"] = st
    try:
        st, body = gw.call("POST", "/key/generate", {"user_id": user, "duration": "15m",
                                                     "metadata": {"purpose": "smoke check 18"}})
        key = (body or {}).get("key") if isinstance(body, dict) else None
        if not key:
            return dict(out, ok=False, key_generate=st)
        st, models = gw.call("GET", "/v1/models", key=key)
        if st != 200 or not isinstance(models, dict):
            # Without the model list we cannot know which names are real providers: send nothing.
            return dict(out, ok=False, models_status=st)
        served = sorted(m.get("id") for m in models.get("data", []))
        out["served_models"] = served
        before = mock_requests()
        refused = {}
        for m in HOSTED_OR_LOCAL:
            if m in served:
                refused[m] = "enabled in this lab (not tested: it would be a real call)"
                continue
            st, body = gw.chat(key, m)
            refused[m] = {"status": st, "message": str((body or {}).get("error", body))[:200]
                          if isinstance(body, dict) else str(body)[:200]}
        after = mock_requests()
        out["not_enabled_refused"] = refused
        out["mock_requests_before_after"] = [before, after]
        out["no_outbound"] = before is not None and before == after and all(
            isinstance(v, dict) and v["status"] >= 400 for v in refused.values())
        # Budget: the first call may pass (spend 0 < budget); every call after it must not.
        first = gw.chat(key, MOCK_MODEL)[0]
        st, body = gw.chat(key, MOCK_MODEL)
        msg = json.dumps(body)[:400] if not isinstance(body, str) else body[:400]
        out["budget"] = {"first": first, "second": st, "message": msg,
                         "ok": st >= 400 and "budget" in msg.lower()}
        gw.call("POST", "/key/delete", {"keys": [key]})
    finally:
        out["temp_user_deleted"] = gw.call("POST", "/user/delete", {"user_ids": [user]})[0]
    out["ok"] = bool(out.get("no_outbound")) and bool((out.get("budget") or {}).get("ok"))
    return out


def run(S, want):
    if not want(18):
        return
    import phase3
    if not (phase3.includes(S.PROFILE, "ai") and phase3.includes(S.PROFILE, "superset")):
        S.skip(C18, f"profile {S.PROFILE}: the AI gateway (and Superset) are only in profile full")
        return
    try:
        check_ai(S)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        if C18 not in S.RESULTS:
            S.check(C18, False, f"{type(e).__name__}: {e}"[:500])
