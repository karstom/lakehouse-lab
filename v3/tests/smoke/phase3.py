"""Smoke checks 12-16 (CONTRACT Phase 3), run by smoke.py in the `smoke` container.

  12  Airflow (engineer, full): one Keycloak login; alice (lab-admin) is Admin, victor (viewer)
      is read-only (trigger refused); lab_ingest, lab_dbt_build, lab_notebook and
      lab_spark_batch all succeed when alice triggers them.
  13  ADR-017 long run (engineer, full; only with LAB_SMOKE_LONG=1): with the `lab-batch`
      client's access-token lifespan cut to 120 s, lab_spark_batch runs >= 300 s and commits
      after its first token expired.
  14  Superset (full): alice's SQL Lab query runs in Trino as alice, the bundled
      "Revenue by region" dashboard's chart data returns rows, victor cannot write.
  15  Console (every profile): alice sees more tiles than victor, both see a health summary;
      Spark UI (engineer, full) is 200 for alice and eddie (engineer; also the Spark Connect
      application UI through the master's proxy) and 403 for victor, and from victor's own
      workspace kernel spark-master:8080, spark-worker:8081 and spark-connect:4040 do not
      connect at all (internal `spark` network), while Spark Connect's gRPC 15002 does.
  16  External IdP (every profile): a throwaway realm `mock-idp` acts as the OIDC provider,
      brokered into realm lakehouse as alias `github-mock` with bootstrap's
      `lab-first-broker-login` flow (the flow the real GitHub IdP uses). A first login creates
      a user with NO group who is refused by Trino and Jupyter; after an admin adds group
      engineer, access follows within the identity-sync budget. A provider account that
      shows alice's e-mail is NOT linked to alice: Keycloak asks for alice's password.
      Everything it creates is removed again, even when the check fails.

Every check prints one [PASS]/[FAIL]/[SKIP] line through smoke.check/skip. `plan()` decides
what runs from the profile (pure; unit-tested).
"""
import json
import os
import re
import secrets
import socket
import time
import traceback
import urllib.parse

import requests

C12 = "12.airflow_roles_and_lab_dags"
C13 = "13.airflow_spark_batch_outlives_token"
C14 = "14.superset_user_identity_and_dashboard"
C15 = "15.console_tiles_and_spark_ui"
C16 = "16.external_idp_no_group_no_email_link"
ALL = (C12, C13, C14, C15, C16)

LAB_DAGS = ("lab_ingest", "lab_dbt_build", "lab_notebook", "lab_spark_batch")
DAG_TIMEOUT_S = {"lab_ingest": 600, "lab_dbt_build": 900, "lab_notebook": 900,
                 "lab_spark_batch": 900}
BATCH_CLIENT = "lab-batch"
LONG_TOKEN_LIFESPAN_S = 120
LONG_MIN_RUNTIME_S = 300
LONG_TABLE = "lakehouse.analytics.smoke_batch_longrun"
DASHBOARD_TITLE = "Revenue by region"

MOCK_REALM = "mock-idp"
MOCK_ALIAS = "github-mock"
MOCK_CLIENT = "lakehouse-broker"
MOCK_USER_PREFIX = "ghmock-"
FIRST_BROKER_FLOW = "lab-first-broker-login"
FORBIDDEN_FLOW_PROVIDERS = ("idp-auto-link", "idp-email-verification")


def includes(profile, feature):
    """Same table as installer/lib.sh profile_includes."""
    return (feature, profile) in {("spark", "engineer"), ("spark", "full"),
                                  ("airflow", "engineer"), ("airflow", "full"),
                                  ("superset", "full")}


def plan(profile, long_on):
    """{check: None (run) | reason to skip}."""
    out = {}
    out[C12] = None if includes(profile, "airflow") else \
        f"profile {profile}: Airflow is only in profiles engineer and full"
    if not includes(profile, "airflow"):
        out[C13] = f"profile {profile}: Airflow is only in profiles engineer and full"
    elif not long_on:
        out[C13] = "slow check (>= 5 min): set LAB_SMOKE_LONG=1 or 'lab test --long' (always on in nightly CI)"
    else:
        out[C13] = None
    out[C14] = None if includes(profile, "superset") else \
        f"profile {profile}: Superset is only in profile full"
    out[C15] = None
    out[C16] = None
    return out


# ---------------------------------------------------------------- browser sessions
def launch(pw, S, blackhole=()):
    """Chromium with every lab hostname pinned to Caddy (the *.localhost workaround,
    REG_V3_CHROMIUM_LOCALHOST_LOOPBACK, as in check 2). Hostnames in `blackhole` resolve to
    an unused loopback port instead, so a redirect to them is seen but never delivered."""
    caddy_ip = socket.gethostbyname(f"auth.{S.D}")
    rules = [f"MAP {h} 127.0.0.1:9" for h in blackhole] + [f"MAP *.{S.D} {caddy_ip}"]
    return pw.chromium.launch(args=[f"--host-resolver-rules={', '.join(rules)}"])


LOGINISH = re.compile(r"(^|/)(login|oauth2|oauth-authorized|oauth_login|oauth_callback|login_callback|callback)(/|$)")


class UserSession:
    """One user's browser (fresh context). Logs into Keycloak when its form shows up, at most
    once per session (a second prompt means the password was rejected)."""

    def __init__(self, S, browser, user, password=None):
        self.S = S
        self.user = user
        self.password = password if password is not None else S.PW
        self.ctx = browser.new_context()
        self.page = self.ctx.new_page()
        self.prompts = 0
        self.nav_status = {}
        self.page.on("response", self._on_response)

    def _on_response(self, r):
        try:
            if r.request.is_navigation_request() and r.frame == self.page.main_frame:
                self.nav_status[r.url] = r.status
        except Exception:  # noqa: BLE001 - diagnostics only
            pass

    def close(self):
        try:
            self.ctx.close()
        except Exception:  # noqa: BLE001
            pass

    def _kc_form(self):
        cur = urllib.parse.urlparse(self.page.url)
        return cur.hostname == f"auth.{self.S.D}" and self.page.locator("#username").count() > 0 \
            and self.page.locator("#password").count() > 0

    def open(self, target, host=None, timeout=120):
        """Go to `target`, log in if asked, and wait until the page settles on `host` outside
        any login/callback path. Returns (final_url, http status of the final navigation)."""
        page = self.page
        host = host or urllib.parse.urlparse(target).hostname
        page.goto(target, wait_until="domcontentloaded")
        deadline = time.time() + timeout
        while time.time() < deadline:
            cur = urllib.parse.urlparse(page.url)
            if self._kc_form():
                self.prompts += 1
                if self.prompts > 1:
                    raise RuntimeError(f"Keycloak asked {self.user} for the password twice")
                page.fill("#username", self.user)
                page.fill("#password", self.password)
                page.click("#kc-login")
                page.wait_for_load_state("domcontentloaded")
                continue
            if cur.hostname == host and not LOGINISH.search(cur.path):
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:  # noqa: BLE001 - long-polling pages never go idle
                    pass
                return page.url, self.nav_status.get(page.url)
            page.wait_for_timeout(500)
        raise TimeoutError(f"{self.user}: stuck at {page.url} while opening {target}")

    def shot(self, name):
        try:
            os.makedirs("/out", exist_ok=True)
            self.page.screenshot(path=f"/out/{name}-{self.user}.png")
        except Exception:  # noqa: BLE001 - evidence only
            pass


def _json(resp):
    try:
        return resp.json()
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- 12/13 Airflow
class Airflow:
    def __init__(self, S, session):
        self.S = S
        self.s = session

    def login(self):
        # Start at /auth/login: "/" is the SPA, which redirects to the login only client-side,
        # after open() has already seen a non-login airflow. URL and returned (not logged in).
        return self.s.open(self.S.url("airflow", "/auth/login"), f"airflow.{self.S.D}")

    def api(self, method, path, body=None, relogin=True):
        req = self.s.page.request
        u = self.S.url("airflow", f"/api/v2{path}")
        kw = {"headers": {"Content-Type": "application/json"}}
        if body is not None:
            kw["data"] = json.dumps(body)
        r = req.fetch(u, method=method, **kw)
        if r.status == 401 and relogin:  # the UI token expired: log in again (SSO, no prompt)
            self.login()
            r = req.fetch(u, method=method, **kw)
        return r

    def dag_ids(self):
        r = self.api("GET", "/dags?limit=200")
        return r.status, sorted(d["dag_id"] for d in (_json(r) or {}).get("dags", []))

    def trigger(self, dag_id, conf=None):
        self.api("PATCH", f"/dags/{dag_id}", {"is_paused": False})
        r = self.api("POST", f"/dags/{dag_id}/dagRuns", {"logical_date": None, "conf": conf or {}})
        return r.status, _json(r) or {}

    def wait_run(self, dag_id, run_id, timeout):
        t0 = time.time()
        rid = urllib.parse.quote(run_id, safe="")
        state, run = None, {}
        while time.time() - t0 < timeout:
            r = self.api("GET", f"/dags/{dag_id}/dagRuns/{rid}")
            run = _json(r) or {}
            state = run.get("state")
            if state in ("success", "failed"):
                break
            time.sleep(10)
        out = {"state": state or "timeout", "seconds": round(time.time() - t0, 1),
               "start_date": run.get("start_date"), "end_date": run.get("end_date")}
        if state != "success":
            r = self.api("GET", f"/dags/{dag_id}/dagRuns/{rid}/taskInstances")
            out["tasks"] = {t.get("task_id"): t.get("state")
                            for t in (_json(r) or {}).get("task_instances", [])}
        return out


def _run_seconds(run):
    from datetime import datetime
    try:
        a = datetime.fromisoformat(run["start_date"].replace("Z", "+00:00"))
        b = datetime.fromisoformat(run["end_date"].replace("Z", "+00:00"))
        return round((b - a).total_seconds(), 1), a
    except Exception:  # noqa: BLE001
        return None, None


def check_airflow(S):
    from playwright.sync_api import sync_playwright
    ev = {}
    with sync_playwright() as pw:
        browser = launch(pw, S)
        try:
            alice = UserSession(S, browser, "alice")
            af = Airflow(S, alice)
            ev["alice_login"] = af.login()[0]
            status, ids = af.dag_ids()
            ev["alice_list_dags"] = status
            ev["missing_dags"] = [d for d in LAB_DAGS if d not in ids]
            pool = f"smoke_{secrets.token_hex(3)}"
            r = af.api("POST", "/pools", {"name": pool, "slots": 1})
            ev["alice_admin_create_pool"] = r.status
            if r.status in (200, 201):
                af.api("DELETE", f"/pools/{pool}")

            victor = UserSession(S, browser, "victor")
            vf = Airflow(S, victor)
            vf.login()
            ev["victor_list_dags"] = vf.dag_ids()[0]
            ev["victor_trigger"] = vf.api("POST", f"/dags/{LAB_DAGS[0]}/dagRuns",
                                          {"logical_date": None, "conf": {}}).status
            ev["victor_unpause"] = vf.api("PATCH", f"/dags/{LAB_DAGS[0]}", {"is_paused": False}).status
            victor.close()

            eddie = UserSession(S, browser, "eddie")
            ef = Airflow(S, eddie)
            ef.login()
            ev["eddie_engineer_edit_dag"] = ef.api("PATCH", f"/dags/{LAB_DAGS[0]}",
                                                   {"is_paused": False}).status
            eddie.close()

            runs = {}
            for dag in LAB_DAGS:  # in order: ingest -> dbt -> notebook -> spark batch
                if dag in ev["missing_dags"]:
                    runs[dag] = {"state": "missing"}
                    continue
                st, run = af.trigger(dag)
                if st not in (200, 201):
                    runs[dag] = {"state": f"trigger HTTP {st}", "body": str(run)[:300]}
                    continue
                runs[dag] = af.wait_run(dag, run["dag_run_id"], DAG_TIMEOUT_S[dag])
                print(f"[info] airflow {dag}: {runs[dag]['state']} in {runs[dag]['seconds']}s", flush=True)
            ev["runs"] = runs
            alice.shot("airflow")
            alice.close()
        finally:
            browser.close()
    ok = (ev["alice_list_dags"] == 200 and not ev["missing_dags"]
          and ev["alice_admin_create_pool"] in (200, 201)
          and ev["victor_list_dags"] == 200 and ev["victor_trigger"] == 403
          and ev["victor_unpause"] == 403 and ev["eddie_engineer_edit_dag"] == 200
          and all(r.get("state") == "success" for r in ev["runs"].values()))
    S.check(C12, ok, ev)


def _kc(S):
    base = S.url("auth", "/admin/realms/lakehouse")
    return base, {"Authorization": f"Bearer {S.kc_admin_token()}"}


def _set_token_lifespan(S, client_id, value):
    """-> previous value of the client's access.token.lifespan attribute ('' if unset)."""
    base, h = _kc(S)
    c = requests.get(f"{base}/clients", params={"clientId": client_id}, headers=h,
                     verify=S.CA, timeout=30).json()
    if not c:
        raise RuntimeError(f"Keycloak client {client_id!r} not found (bootstrap creates it)")
    c = c[0]
    attrs = c.get("attributes") or {}
    before = attrs.get("access.token.lifespan", "")
    attrs["access.token.lifespan"] = str(value)
    c["attributes"] = attrs
    requests.put(f"{base}/clients/{c['id']}", json=c, headers=h, verify=S.CA,
                 timeout=30).raise_for_status()
    return before


def check_airflow_long_run(S):
    """ADR-017: the batch job must outlive its catalog token. lab-batch's access tokens are
    cut to 120 s, then lab_spark_batch is asked to run >= 300 s and write LONG_TABLE; the
    Iceberg commit must land after the first token expired."""
    from playwright.sync_api import sync_playwright
    ev = {"token_lifespan_s": LONG_TOKEN_LIFESPAN_S, "min_runtime_s": LONG_MIN_RUNTIME_S,
          "table": LONG_TABLE}
    before = _set_token_lifespan(S, BATCH_CLIENT, LONG_TOKEN_LIFESPAN_S)
    ev["lifespan_before"] = before or "(realm default)"
    try:
        with sync_playwright() as pw:
            browser = launch(pw, S)
            try:
                alice = UserSession(S, browser, "alice")
                af = Airflow(S, alice)
                af.login()
                st, run = af.trigger("lab_spark_batch", {"min_runtime_s": LONG_MIN_RUNTIME_S,
                                                         "target_table": LONG_TABLE})
                ev["trigger"] = st
                if st in (200, 201):
                    ev["run"] = af.wait_run("lab_spark_batch", run["dag_run_id"],
                                            LONG_MIN_RUNTIME_S + 1200)
                alice.close()
            finally:
                browser.close()
    finally:
        _set_token_lifespan(S, BATCH_CLIENT, before)
    run = ev.get("run") or {}
    secs, started = _run_seconds(run) if run.get("end_date") else (None, None)
    ev["run_seconds"] = secs
    commit_after = None
    if run.get("state") == "success":
        cur = S.trino_conn(S.user_token("alice")).cursor()
        schema, table = LONG_TABLE.split(".")[1:]
        rows = S.run(cur, f'SELECT max(committed_at) FROM lakehouse.{schema}."{table}$snapshots"')
        last = rows[0][0] if rows else None
        ev["last_commit"] = str(last)
        if last is not None and started is not None:
            commit_after = (last - started).total_seconds()
        ev["commit_seconds_after_start"] = commit_after
        S.run(cur, f"DROP TABLE IF EXISTS {LONG_TABLE}")
    S.check(C13, run.get("state") == "success" and secs is not None and secs >= LONG_MIN_RUNTIME_S
            and commit_after is not None and commit_after > LONG_TOKEN_LIFESPAN_S, ev)


# ---------------------------------------------------------------- 14 Superset
def rison_page(n=100):
    return urllib.parse.quote(f"(page_size:{n})")


class Superset:
    def __init__(self, S, session):
        self.S = S
        self.s = session
        self.csrf = None

    def login(self):
        return self.s.open(self.S.url("superset", "/login/keycloak"), f"superset.{self.S.D}")

    def api(self, method, path, body=None):
        req = self.s.page.request
        h = {"Referer": self.S.url("superset", "/")}
        if method != "GET":
            if self.csrf is None:
                r = req.get(self.S.url("superset", "/api/v1/security/csrf_token/"))
                self.csrf = ((_json(r) or {}).get("result")) or ""
            h.update({"X-CSRFToken": self.csrf, "Content-Type": "application/json"})
        kw = {"headers": h}
        if body is not None:
            kw["data"] = json.dumps(body)
        return req.fetch(self.S.url("superset", f"/api/v1{path}"), method=method, **kw)

    def roles(self):
        r = self.api("GET", "/me/roles/")
        return sorted(((_json(r) or {}).get("result") or {}).get("roles", {}).keys()) if r.ok else r.status

    def trino_db(self):
        r = self.api("GET", f"/database/?q={rison_page()}")
        dbs = (_json(r) or {}).get("result") or []
        for d in dbs:
            if d.get("backend") == "trino" or "trino" in (d.get("sqlalchemy_uri") or ""):
                return d
        return None

    def sqllab(self, db_id, sql):
        r = self.api("POST", "/sqllab/execute/", {
            # Superset 6.1's ExecutePayloadSchema rejects unknown fields (e.g. the old "json").
            "database_id": db_id, "sql": sql, "catalog": "lakehouse", "schema": "analytics",
            "runAsync": False, "client_id": secrets.token_hex(5), "tab": "smoke",
            "queryLimit": 10})
        return r.status, _json(r) or {}

    def dashboard(self, title):
        r = self.api("GET", f"/dashboard/?q={rison_page()}")
        for d in (_json(r) or {}).get("result") or []:
            if d.get("dashboard_title") == title:
                return d
        return None

    def chart_rows(self, chart_id, datasource=None):
        """Rows the chart's query returns: its saved query context first (what the chart
        endpoint serves), else a samples query on its dataset."""
        r = self.api("GET", f"/chart/{chart_id}/data/?format=json&force=true")
        how = "saved query_context"
        if not r.ok and datasource:
            r = self.api("POST", "/chart/data", {
                "datasource": datasource, "force": True, "result_type": "samples",
                "queries": [{"row_limit": 10}]})
            how = "samples of its dataset"
        body = _json(r) or {}
        res = body.get("result") or []
        n = sum(int(q.get("rowcount") or len(q.get("data") or [])) for q in res) if res else 0
        return {"status": r.status, "rows": n, "via": how}


def _first_value(payload):
    rows = payload.get("data") or []
    if rows and isinstance(rows[0], dict):
        return next(iter(rows[0].values()), None)
    return None


def check_superset(S):
    from playwright.sync_api import sync_playwright
    ev = {}
    with sync_playwright() as pw:
        browser = launch(pw, S)
        try:
            alice = UserSession(S, browser, "alice")
            ss = Superset(S, alice)
            ss.login()
            me = _json(ss.api("GET", "/me/")) or {}
            ev["alice_username"] = (me.get("result") or {}).get("username")
            ev["alice_roles"] = ss.roles()
            db = ss.trino_db()
            ev["trino_database"] = db and {"id": db.get("id"), "name": db.get("database_name")}
            if db:
                st, res = ss.sqllab(db["id"], "SELECT current_user AS u")
                ev["sqllab"] = {"status": st, "current_user": _first_value(res),
                                "error": (res.get("errors") or res.get("message") or None)}
            dash = ss.dashboard(DASHBOARD_TITLE)
            ev["dashboard"] = dash and {"id": dash.get("id"), "title": dash.get("dashboard_title")}
            charts = []
            if dash:
                r = ss.api("GET", f"/dashboard/{dash['id']}/charts")
                for c in ((_json(r) or {}).get("result") or [])[:5]:
                    fd = c.get("form_data") or {}
                    ds = None
                    m = re.match(r"^(\d+)__(\w+)$", str(fd.get("datasource") or ""))
                    if m:
                        ds = {"id": int(m.group(1)), "type": m.group(2)}
                    charts.append({"id": c.get("id"), "name": c.get("slice_name"),
                                   **ss.chart_rows(c.get("id"), ds)})
            ev["charts"] = charts
            alice.shot("superset")
            alice.close()

            victor = UserSession(S, browser, "victor")
            vs = Superset(S, victor)
            vs.login()
            ev["victor_roles"] = vs.roles()
            if db:
                ev["victor_sqllab"] = vs.sqllab(db["id"], "SELECT 1")[0]
            if dash:
                ev["victor_edit_dashboard"] = vs.api(
                    "PUT", f"/dashboard/{dash['id']}", {"dashboard_title": "smoke: victor was here"}).status
            victor.close()
            if dash:  # the bundled dashboard is unchanged
                a2 = UserSession(S, browser, "alice")
                s2 = Superset(S, a2)
                s2.login()
                ev["dashboard_title_after"] = (s2.dashboard(DASHBOARD_TITLE) or {}).get("dashboard_title")
                a2.close()
        finally:
            browser.close()
    admin_ok = isinstance(ev.get("alice_roles"), list) and "Admin" in ev["alice_roles"]
    victor_roles = ev.get("victor_roles")
    ok = (ev.get("alice_username") == "alice" and admin_ok
          and (ev.get("sqllab") or {}).get("current_user") == "alice"
          and ev.get("dashboard") is not None and any(c["rows"] > 0 for c in ev["charts"])
          and isinstance(victor_roles, list) and "Admin" not in victor_roles
          and "sql_lab" not in victor_roles
          and ev.get("victor_sqllab") in (401, 403)
          and ev.get("victor_edit_dashboard") in (401, 403, 404)
          and ev.get("dashboard_title_after") == DASHBOARD_TITLE)
    S.check(C14, ok, ev)


# ---------------------------------------------------------------- 15 Console + Spark UI
TILES_JS = r"""
(domain) => {
  // The Console's tiles: #tiles a.card (name in <strong>) or any [data-tile]; as a last
  // resort, visible links to other lab hosts. Each tile -> {name, host}.
  const vis = (e) => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length);
  const host = (a) => { try { return new URL(a.href, location.href).hostname.split('.')[0]; } catch (e) { return ''; } };
  let els = [...document.querySelectorAll('[data-tile]')].filter(vis);
  let via = 'data-tile';
  if (!els.length) { els = [...document.querySelectorAll('#tiles a')].filter(vis); via = '#tiles'; }
  if (!els.length) {
    els = [...document.querySelectorAll('a[href]')].filter(vis).filter(a => {
      try { const h = new URL(a.href, location.href).hostname; return h.endsWith('.' + domain) && !h.startsWith('console.'); }
      catch (e) { return false; } });
    via = 'links';
  }
  const tiles = els.map(e => {
    const a = e.tagName === 'A' ? e : (e.querySelector('a') || e);
    const s = e.querySelector('strong');
    return {name: (e.dataset.tile || (s && s.innerText) || a.innerText || '').trim().split('\n')[0],
            host: a.href ? host(a) : ''};
  });
  return {tiles, via};
}
"""
HEALTH_JS = r"""
() => {
  const box = document.querySelector('[data-health], #health');
  if (!box) return null;
  const rows = [...box.querySelectorAll('li')].map(li => (li.innerText || '').replace(/\s+/g, ' ').trim());
  const text = rows.length ? rows : [(box.innerText || '').trim()];
  if (!text.length || /checking|unavailable/i.test(text.join(' '))) return {ready: false, rows: text.slice(0, 12)};
  return {ready: true, rows: text.slice(0, 12)};
}
"""
HEALTH_READY_JS = r"""
() => { const b = document.querySelector('[data-health], #health');
        return !!b && !/checking/i.test(b.innerText || ''); }
"""


def console_view(S, session):
    final, status = session.open(S.url("console", "/"), f"console.{S.D}")
    try:
        session.page.wait_for_function(HEALTH_READY_JS, timeout=30000)
    except Exception:  # noqa: BLE001 - evaluated below either way
        pass
    tiles = session.page.evaluate(TILES_JS, S.D)
    health = session.page.evaluate(HEALTH_JS)
    session.shot("console")
    return {"final_url": final, "status": status,
            "tiles": sorted({t["name"] for t in tiles["tiles"]}),
            "tile_hosts": sorted({t["host"] for t in tiles["tiles"]}),
            "tiles_via": tiles["via"], "health": health}


def spark_ui_status(S, session, timeout=60):
    """Status of the Spark UI page for an already logged-in session (forward-auth answers
    200 or 403 on spark.<domain>; it may pass through oauth2-proxy and Keycloak first)."""
    page = session.page
    page.goto(S.url("spark", "/"), wait_until="domcontentloaded")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if session._kc_form():
            session.prompts += 1
            if session.prompts > 1:
                raise RuntimeError(f"Keycloak asked {session.user} for the password twice")
            page.fill("#username", session.user)
            page.fill("#password", session.password)
            page.click("#kc-login")
            page.wait_for_load_state("domcontentloaded")
            continue
        cur = urllib.parse.urlparse(page.url)
        status = session.nav_status.get(page.url)
        if cur.hostname == f"spark.{S.D}" and (status in (200, 401, 403) or not LOGINISH.search(cur.path)):
            break
        page.wait_for_timeout(500)
    session.shot("spark-ui")
    return {"final_url": page.url, "status": session.nav_status.get(page.url)}


APP_UI_JS = r"""
async () => {
  // The master's JSON (same origin, through the forward-auth): the running Spark Connect app.
  const r = await fetch('/json/', {credentials: 'same-origin'});
  if (!r.ok) return {status: r.status};
  const j = await r.json();
  const apps = (j.activeapps || []).map(a => ({id: a.id, name: a.name}));
  return {status: r.status, apps, workers: (j.workers || []).length};
}
"""
# From a viewer's workspace (on `lab`): the Spark UIs must not connect at all (CONTRACT Phase 3,
# Networks). Spark Connect's gRPC port is the control that must connect.
INTERNAL_SPARK_UIS = ("http://spark-master:8080/", "http://spark-worker:8081/",
                      "http://spark-connect:4040/")
SPARK_CONNECT_GRPC = "tcp://spark-connect:15002"


def spark_app_ui(S, session):
    """An engineer opens the Spark Connect application UI through the master's reverse proxy
    at spark.<domain>/proxy/<app-id>/ (the only way to it). 200 and Spark's Jobs page."""
    info = session.page.evaluate(APP_UI_JS)
    app = next((a for a in info.get("apps", []) if a.get("name") == "Spark Connect"), None)
    if not app:
        return {"ok": False, "master_json": info}
    final, status = session.open(S.url("spark", f"/proxy/{app['id']}/jobs/"), f"spark.{S.D}")
    title = session.page.title()
    session.shot("spark-app-ui")
    return {"ok": status == 200 and "Spark Connect" in title, "app": app, "status": status,
            "title": title, "final_url": final, "workers": info.get("workers")}


def victor_internal_probe(S, browser):
    """victor (viewer) in his own workspace kernel: the master, worker and application UIs do
    not connect; Spark Connect's gRPC does."""
    from workspace import Workspace
    ws = Workspace(browser, S.url, S.D, "victor", S.PW)
    try:
        login = ws.login_and_spawn()
        if not login["ok"]:
            return {"ok": False, "login_spawn": login}
        params = dict(S.probe_params("victor", ["internal_ports"]),
                      unreachable=list(INTERNAL_SPARK_UIS), reachable=[SPARK_CONNECT_GRPC])
        result, raw = ws.run_probe(params, timeout=180)
        if result is None:
            return {"ok": False, "probe": "no result from the kernel", "status": raw.get("status"),
                    "error": raw.get("error"), "stderr_tail": (raw.get("stderr") or "")[-600:]}
        step = result["steps"].get("internal_ports", {"ok": False, "error": "step did not run"})
        step["ok"] = bool(step.get("ok")) and result.get("user_env") == "victor"
        step["jupyterhub_user"] = result.get("user_env")
        return step
    finally:
        print(f"[info] victor's workspace stopped: {ws.stop_server()}", flush=True)
        ws.close()


def check_console(S):
    """Console tiles (alice vs victor) and, on Spark profiles, the Spark UI: eddie (engineer)
    gets the master UI and the Connect application UI through spark.<domain>, victor gets 403
    there and, from his own workspace, cannot connect to any Spark UI port directly."""
    from playwright.sync_api import sync_playwright
    spark = includes(S.PROFILE, "spark")
    ev = {}
    with sync_playwright() as pw:
        browser = launch(pw, S)
        try:
            for user in ("alice", "victor"):
                sess = UserSession(S, browser, user)
                try:
                    ev[user] = console_view(S, sess)
                    if spark:
                        ev[user]["spark_ui"] = spark_ui_status(S, sess)
                finally:
                    sess.close()
            if spark:
                sess = UserSession(S, browser, "eddie")
                try:
                    ev["eddie"] = {"spark_ui": spark_ui_status(S, sess)}
                    ev["eddie"]["app_ui"] = spark_app_ui(S, sess)
                finally:
                    sess.close()
                ev["victor_workspace_internal_ports"] = victor_internal_probe(S, browser)
        finally:
            browser.close()
    a, v = set(ev["alice"]["tiles"]), set(ev["victor"]["tiles"])
    builders = {h for h in ("airflow", "spark") if includes(S.PROFILE, h)}
    ok = (ev["alice"]["status"] in (200, None) and bool(v) and v < a
          and builders <= set(ev["alice"]["tile_hosts"])
          and not builders & set(ev["victor"]["tile_hosts"])
          and all((ev[u]["health"] or {}).get("ready") for u in ("alice", "victor")))
    if spark:
        ok = (ok and ev["alice"]["spark_ui"]["status"] == 200
              and ev["victor"]["spark_ui"]["status"] == 403
              and ev["eddie"]["spark_ui"]["status"] == 200
              and ev["eddie"]["app_ui"]["ok"]
              and ev["victor_workspace_internal_ports"]["ok"])
    else:
        ev["spark_ui"] = f"not checked: profile {S.PROFILE} has no Spark"
    ev["alice_only_tiles"] = sorted(a - v)
    S.check(C15, ok, ev)


# ---------------------------------------------------------------- 16 external IdP (mock)
class KcAdmin:
    """Keycloak admin REST API as the master admin, through the public URL (like the UI)."""

    def __init__(self, S):
        self.S = S
        self.root = S.url("auth", "/admin/realms")
        self._tok = None
        self._at = 0

    def h(self):
        if self._tok is None or time.time() - self._at > 40:
            self._tok, self._at = self.S.kc_admin_token(), time.time()
        return {"Authorization": f"Bearer {self._tok}"}

    def req(self, method, path, ok=(200, 201, 204), **kw):
        r = requests.request(method, f"{self.root}{path}", headers=self.h(), verify=self.S.CA,
                             timeout=30, **kw)
        if ok and r.status_code not in ok:
            raise RuntimeError(f"{method} {path}: HTTP {r.status_code} {r.text[:200]}")
        return r

    def get(self, path, **kw):
        r = self.req("GET", path, **kw)
        return r.json() if r.text.strip() else None

    def user(self, username):
        found = self.get("/lakehouse/users", params={"exact": "true", "username": username})
        return found[0] if found else None


def mock_realm(auth_url, client_secret, users):
    """The throwaway provider realm: one confidential client whose only redirect is the
    lakehouse broker endpoint of alias github-mock. `users`: (username, email, password)."""
    return {
        "realm": MOCK_REALM, "enabled": True, "sslRequired": "none",
        "registrationAllowed": False, "displayName": "Mock GitHub (smoke test)",
        "clients": [{
            "clientId": MOCK_CLIENT, "enabled": True, "protocol": "openid-connect",
            "publicClient": False, "clientAuthenticatorType": "client-secret",
            "secret": client_secret, "standardFlowEnabled": True,
            "directAccessGrantsEnabled": False, "implicitFlowEnabled": False,
            "redirectUris": [f"{auth_url}/realms/lakehouse/broker/{MOCK_ALIAS}/endpoint"],
        }],
        "users": [{
            "username": u, "enabled": True, "email": e, "emailVerified": True,
            "firstName": "Mock", "lastName": u.replace(MOCK_USER_PREFIX, "").capitalize() or "User",
            "credentials": [{"type": "password", "value": p, "temporary": False}],
        } for u, e, p in users],
    }


def mock_idp(auth_url, client_secret):
    """Identity provider `github-mock` in realm lakehouse. Browser-facing endpoints use the
    public origin; Keycloak's own back-channel calls go to http://keycloak:8080 (no CA
    needed). Same flow and trust settings as the real `github` provider."""
    internal = f"http://keycloak:8080/realms/{MOCK_REALM}/protocol/openid-connect"
    return {
        "alias": MOCK_ALIAS, "displayName": "GitHub (mock)", "providerId": "oidc",
        "enabled": True, "trustEmail": False, "storeToken": False, "linkOnly": False,
        "firstBrokerLoginFlowAlias": FIRST_BROKER_FLOW, "postBrokerLoginFlowAlias": "",
        "config": {
            "authorizationUrl": f"{auth_url}/realms/{MOCK_REALM}/protocol/openid-connect/auth",
            "tokenUrl": f"{internal}/token", "jwksUrl": f"{internal}/certs",
            "issuer": f"{auth_url}/realms/{MOCK_REALM}", "useJwksUrl": "true",
            "validateSignature": "true", "disableUserInfo": "true",
            "clientId": MOCK_CLIENT, "clientSecret": client_secret,
            "clientAuthMethod": "client_secret_post", "defaultScope": "openid profile email",
            "syncMode": "IMPORT", "pkceEnabled": "false",
        },
    }


def flow_report(executions):
    providers = [e.get("providerId") for e in executions if not e.get("authenticationFlow")]
    return {"providers": providers,
            "forbidden": [p for p in providers if p in FORBIDDEN_FLOW_PROVIDERS],
            "reauth_required": any(e.get("providerId") == "idp-username-password-form"
                                   and e.get("requirement") == "REQUIRED" for e in executions)}


def _mock_cleanup(kc):
    """Remove everything check 16 creates (also leftovers of an interrupted run). Users are
    deleted only if they carry the prefix AND a github-mock federated identity."""
    done = []
    for u in kc.get("/lakehouse/users", params={"search": MOCK_USER_PREFIX, "max": 100}) or []:
        if not u.get("username", "").startswith(MOCK_USER_PREFIX):
            continue
        fed = kc.get(f"/lakehouse/users/{u['id']}/federated-identity") or []
        if any(f.get("identityProvider") == MOCK_ALIAS for f in fed):
            kc.req("DELETE", f"/lakehouse/users/{u['id']}")
            done.append(f"user {u['username']}")
    if kc.req("GET", f"/lakehouse/identity-provider/instances/{MOCK_ALIAS}", ok=None).status_code == 200:
        kc.req("DELETE", f"/lakehouse/identity-provider/instances/{MOCK_ALIAS}")
        done.append(f"idp {MOCK_ALIAS}")
    if kc.req("GET", f"/{MOCK_REALM}", ok=None).status_code == 200:
        kc.req("DELETE", f"/{MOCK_REALM}")
        done.append(f"realm {MOCK_REALM}")
    return done


class BrokerLogin:
    """Drives an authorization-code login for the `trino` client through the mock provider in
    one browser context, capturing the code from the redirect to Trino's callback, and
    exchanging it for the user's token like any OIDC client would. The browser must come from
    launch(..., blackhole=[trino host]): Trino never receives (and so never redeems) the code.
    (page.route does not see that request: it is the target of a cross-site 302.)"""

    def __init__(self, S, browser, mock_user, mock_password):
        self.S = S
        self.user = mock_user
        self.password = mock_password
        self.ctx = browser.new_context()
        self.page = self.ctx.new_page()
        self.redirect = S.url("trino", "/oauth2/callback")
        self.code_url = None
        self.nav_status = {}
        self.page.on("response", self._on_response)
        self.page.on("request", self._capture)

    def _on_response(self, r):
        try:
            if r.request.is_navigation_request() and r.frame == self.page.main_frame:
                self.nav_status[r.url] = r.status
        except Exception:  # noqa: BLE001
            pass

    def _capture(self, request):
        if request.url.startswith(self.redirect + "?") and "code=" in request.url:
            self.code_url = request.url

    def close(self):
        try:
            self.ctx.close()
        except Exception:  # noqa: BLE001
            pass

    def _mock_form(self):
        cur = urllib.parse.urlparse(self.page.url)
        return f"/realms/{MOCK_REALM}/" in cur.path and self.page.locator("#username").count() > 0

    def login(self, stop_at_link_page=False, timeout=90):
        """-> ("token", access_token) | ("link_page", None). Raises on anything else."""
        S = self.S
        self.code_url = None
        q = urllib.parse.urlencode({
            "client_id": "trino", "response_type": "code", "scope": "openid",
            "redirect_uri": self.redirect, "kc_idp_hint": MOCK_ALIAS,
            "state": secrets.token_hex(8), "nonce": secrets.token_hex(8)})
        try:
            self.page.goto(S.url("auth", f"/realms/lakehouse/protocol/openid-connect/auth?{q}"),
                           wait_until="domcontentloaded")
        except Exception:  # noqa: BLE001 - with an SSO session Keycloak redirects straight
            if not self.code_url:  # to the (blackholed) callback: expected, code captured
                raise
        deadline = time.time() + timeout
        prompts = 0
        while time.time() < deadline:
            if self.code_url:
                break
            if self._mock_form():
                prompts += 1
                if prompts > 1:
                    raise RuntimeError("the mock provider asked for the password twice")
                self.page.fill("#username", self.user)
                self.page.fill("#password", self.password)
                self.page.click("#kc-login")
                self.page.wait_for_load_state("domcontentloaded")
                continue
            if self.page.locator("#linkAccount").count() > 0:
                if stop_at_link_page:
                    return "link_page", None
                raise RuntimeError("Keycloak offered to link to an existing account")
            if self.page.locator("#kc-idp-review-profile-form, #kc-update-profile-form").count() > 0:
                self.page.locator("input[type=submit], button[type=submit]").first.click()
                self.page.wait_for_load_state("domcontentloaded")
                continue
            if self.page.locator("#username").count() > 0 and "/realms/lakehouse/" in self.page.url:
                raise RuntimeError("realm lakehouse showed its own password form (SSO/IdP hint lost)")
            self.page.wait_for_timeout(300)
        if not self.code_url:
            raise TimeoutError(f"no authorization code; stuck at {self.page.url}")
        code = urllib.parse.parse_qs(urllib.parse.urlparse(self.code_url).query).get("code", [None])[0]
        r = requests.post(S.url("auth", "/realms/lakehouse/protocol/openid-connect/token"), data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": self.redirect,
            "client_id": "trino", "client_secret": S.TRINO_SECRET}, verify=S.CA, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"code exchange: HTTP {r.status_code} {r.text[:200]}")
        return "token", r.json()["access_token"]

    def jupyter(self):
        """Log into JupyterHub with the same SSO session (never spawns: next=/hub/home)."""
        self.page.goto(self.S.url("jupyter", "/hub/oauth_login?next=%2Fhub%2Fhome"),
                       wait_until="domcontentloaded")
        deadline = time.time() + 60
        while time.time() < deadline:
            cur = urllib.parse.urlparse(self.page.url)
            if cur.hostname == f"jupyter.{self.S.D}" and "oauth" not in cur.path:
                break
            if cur.hostname == f"jupyter.{self.S.D}" and self.nav_status.get(self.page.url, 200) >= 400:
                break
            if self.page.locator("#username").count() > 0:
                return {"error": f"password form at {self.page.url}"}
            self.page.wait_for_timeout(500)
        try:
            self.page.wait_for_load_state("domcontentloaded")
            text = " ".join(self.page.locator("body").inner_text(timeout=5000).split())[:200]
        except Exception:  # noqa: BLE001
            text = ""
        path = urllib.parse.urlparse(self.page.url).path
        return {"path": path, "status": self.nav_status.get(self.page.url), "text": text,
                "allowed": path.rstrip("/") in ("/hub/home", "/hub/spawn")
                or path.startswith("/user/")}


def token_username(token):
    """preferred_username claim of a JWT (read only for evidence; Trino verifies it)."""
    import base64
    try:
        part = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        return claims.get("preferred_username")
    except Exception:  # noqa: BLE001
        return None


def trino_probe(S, token):
    """-> (Trino's current_user or None, "allowed (...)" | "denied: ..." | "error ...").
    A user with no group may not even run a query (Trino: "Cannot execute query")."""
    import trino
    cur = S.trino_conn(token).cursor()
    try:
        me = S.run(cur, "SELECT current_user")[0][0]
        n = S.run(cur, "SELECT count(*) FROM lakehouse.samples.region")[0][0]
        return me, f"allowed ({n} rows)"
    except trino.exceptions.TrinoUserError as e:
        if "Access Denied" in e.message:
            return None, f"denied: {e.message[:80]}"
        return None, f"error {e.error_name}"


DELETE_HUB_USER_JS = r"""
async (user) => {
  const m = document.cookie.match(/(?:^|;\s*)_xsrf=([^;]*)/);
  const hdr = m ? {"X-XSRFToken": decodeURIComponent(m[1])} : {};
  const r = await fetch("/hub/api/users/" + encodeURIComponent(user),
                        {method: "DELETE", headers: hdr, credentials: "same-origin"});
  return r.status;
}
"""


def remove_hub_user(S, browser, username):
    """JupyterHub keeps a user record after a login, even a refused one. alice (a hub admin,
    group lab-admin) deletes the throwaway user through the hub API, as the admin UI would."""
    sess = UserSession(S, browser, "alice")
    try:
        sess.open(S.url("jupyter", "/hub/oauth_login?next=%2Fhub%2Fhome"), f"jupyter.{S.D}")
        return sess.page.evaluate(DELETE_HUB_USER_JS, username)  # 204, or 404 if never created
    except Exception as e:  # noqa: BLE001 - housekeeping only; reported in the evidence
        return f"{type(e).__name__}: {e}"[:200]
    finally:
        sess.close()


def check_external_idp(S):
    kc = KcAdmin(S)
    ev = {}
    ok = False
    try:
        ev["leftovers_removed"] = _mock_cleanup(kc)
        ok = _external_idp_flow(S, kc, ev)
    except Exception as e:  # noqa: BLE001 - recorded; cleanup still runs
        traceback.print_exc()
        ev["error"] = f"{type(e).__name__}: {e}"[:500]
    finally:
        try:
            ev["cleanup"] = _mock_cleanup(kc)
        except Exception as e:  # noqa: BLE001 - reported, and fails the check
            ev["cleanup_error"] = f"{type(e).__name__}: {e}"
            ok = False
    S.check(C16, ok, ev)


def _shot(page, name):
    try:
        page.screenshot(path=f"/out/{name}.png")
    except Exception:  # noqa: BLE001 - evidence only
        pass


def _external_idp_flow(S, kc, ev):
    from playwright.sync_api import sync_playwright
    auth = S.url("auth")
    newcomer = f"{MOCK_USER_PREFIX}{secrets.token_hex(3)}"
    collider = f"{MOCK_USER_PREFIX}alice"
    pw_new, pw_col = secrets.token_urlsafe(18), secrets.token_urlsafe(18)
    alice = kc.user("alice")
    if alice is None:
        raise RuntimeError("test user alice not found")
    alice_email = (kc.get(f"/lakehouse/users/{alice['id']}") or {}).get("email")
    budget = 3 * int(os.environ.get("LAB_SYNC_INTERVAL", "30")) + 45

    flows = {f["alias"] for f in kc.get("/lakehouse/authentication/flows") or []}
    if FIRST_BROKER_FLOW not in flows:
        raise RuntimeError(f"flow {FIRST_BROKER_FLOW} missing: bootstrap "
                           f"(github_idp.ensure_github_idp) did not run")
    ev["flow"] = flow_report(kc.get(f"/lakehouse/authentication/flows/{FIRST_BROKER_FLOW}/executions"))
    secret = secrets.token_urlsafe(24)
    kc.req("POST", "", json=mock_realm(auth, secret, [
        (newcomer, f"{newcomer}@mock-idp.invalid", pw_new),
        (collider, alice_email or "alice@lab.invalid", pw_col)]))
    kc.req("POST", "/lakehouse/identity-provider/instances", json=mock_idp(auth, secret))

    def links(uid):
        return [f.get("identityProvider") for f in
                kc.get(f"/lakehouse/users/{uid}/federated-identity") or []]

    c = ev["email_collision"] = {"provider_email": alice_email}
    n = ev["newcomer"] = {"username": newcomer}
    with sync_playwright() as pw:
        browser = launch(pw, S, blackhole=[f"trino.{S.D}"])
        try:
            # (a) A provider account that shows alice's e-mail is never linked silently:
            # Keycloak offers to link, and linking needs alice's own password.
            col = BrokerLogin(S, browser, collider, pw_col)
            try:
                c["page"], _ = col.login(stop_at_link_page=True)
                if c["page"] == "link_page":
                    col.page.click("#linkAccount")
                    col.page.wait_for_load_state("domcontentloaded")
                    col.page.wait_for_timeout(1000)
                    c["after_link_click"] = {
                        "password_prompt": col.page.locator("#password").count() > 0,
                        "url_path": urllib.parse.urlparse(col.page.url).path}
                _shot(col.page, "idp-email-collision")
            finally:
                col.close()
            c["alice_links"] = links(alice["id"])
            c["user_created"] = kc.user(collider) is not None

            # (b) A newcomer: created with no group and refused; an admin adds a group in
            # Keycloak and access follows (Trino via identity-sync, Jupyter at next login).
            new = BrokerLogin(S, browser, newcomer, pw_new)
            try:
                _, tok = new.login()
                u = kc.user(newcomer)
                n["created"] = u is not None
                if u is None:
                    return False
                n["groups"] = [g["name"] for g in kc.get(f"/lakehouse/users/{u['id']}/groups") or []]
                n["linked_to"] = links(u["id"])
                me, verdict = trino_probe(S, tok)
                n["trino_before"] = {"token_user": token_username(tok), "current_user": me,
                                     "result": verdict}
                n["jupyter_before"] = new.jupyter()
                gid = {g["name"]: g["id"] for g in kc.get("/lakehouse/groups") or []}["engineer"]
                kc.req("PUT", f"/lakehouse/users/{u['id']}/groups/{gid}")
                t0 = time.time()
                n["budget_s"] = budget
                n["seconds_until_trino_allowed"] = None
                while time.time() - t0 < budget:
                    _, tok = new.login()
                    me, verdict = trino_probe(S, tok)
                    if verdict.startswith("allowed"):
                        n["seconds_until_trino_allowed"] = round(time.time() - t0, 1)
                        n["trino_after"] = {"current_user": me, "result": verdict}
                        break
                    time.sleep(5)
                n["jupyter_after"] = new.jupyter()
                _shot(new.page, "idp-newcomer")
            finally:
                new.close()
            n["hub_user_removed"] = remove_hub_user(S, browser, newcomer)
        finally:
            browser.close()
    f, jb, ja = ev["flow"], n.get("jupyter_before", {}), n.get("jupyter_after", {})
    return bool(not f["forbidden"] and f["reauth_required"]
                and c.get("page") == "link_page"
                and (c.get("after_link_click") or {}).get("password_prompt") is True
                and c.get("alice_links") == [] and c.get("user_created") is False
                and n.get("created") and n.get("groups") == [] and n.get("linked_to") == [MOCK_ALIAS]
                and (n.get("trino_before") or {}).get("token_user") == newcomer
                and (n.get("trino_before") or {}).get("result", "").startswith("denied")
                and jb.get("allowed") is False
                and n.get("seconds_until_trino_allowed") is not None
                and (n.get("trino_after") or {}).get("current_user") == newcomer
                and ja.get("allowed") is True)


# ---------------------------------------------------------------- entry
FUNCS = {C12: check_airflow, C13: check_airflow_long_run, C14: check_superset,
         C15: check_console, C16: check_external_idp}
NUMBERS = {C12: 12, C13: 13, C14: 14, C15: 15, C16: 16}


def run_all(S, want):
    """Run checks 12-16 in order (12 before 14: the dashboard reads what lab_dbt_build wrote)."""
    long_on = os.environ.get("LAB_SMOKE_LONG", "") not in ("", "0", "false")
    for name, reason in plan(S.PROFILE, long_on).items():
        if not want(NUMBERS[name]):
            continue
        if reason:
            S.skip(name, reason)
            continue
        try:
            FUNCS[name](S)
        except Exception as e:  # noqa: BLE001 - one failing check must not hide the others
            traceback.print_exc()
            if name not in S.RESULTS:
                S.check(name, False, f"{type(e).__name__}: {e}"[:500])
