"""S-3 SSO test driver (headless Chromium, trusting Caddy's root CA via NSS).

Criteria checked here:
  C2  one Keycloak login reaches all five apps (SSO session reused)
  C3  group -> role mapping differs for admin vs viewer in Superset and Airflow
  C4  changing a user's group in Keycloak is reflected on next login
Prints evidence and writes /out/results.json; exit 0 only if every check passed.
"""
import json
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright

D = os.environ["LAB_DOMAIN"]
P = os.environ["LAB_PORT"]
PW = os.environ["LAB_USER_PASSWORD"]


def url(svc, path="/"):
    return f"https://{svc}.{D}:{P}{path}"


AUTH = url("auth", "")
RESULTS = {}
FAILED = []


def check(name, ok, evidence):
    RESULTS[name] = {"pass": bool(ok), "evidence": evidence}
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {evidence}", flush=True)
    if not ok:
        FAILED.append(name)


# ---------------------------------------------------------------- Keycloak admin API
_ctx = ssl.create_default_context(cafile="/trust/ca-bundle.crt")


def _http(method, u, data=None, headers=None, form=False):
    body = None
    headers = dict(headers or {})
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
    req = urllib.request.Request(u, data=body, method=method, headers=headers)
    with urllib.request.urlopen(req, context=_ctx, timeout=30) as r:
        raw = r.read()
        return json.loads(raw) if raw else None


def kc_admin_token():
    tok = _http("POST", f"{AUTH}/realms/master/protocol/openid-connect/token", form=True, data={
        "grant_type": "password", "client_id": "admin-cli",
        "username": os.environ["KC_ADMIN_USER"], "password": os.environ["KC_ADMIN_PASSWORD"]})
    return {"Authorization": f"Bearer {tok['access_token']}"}


def kc_set_group(username, group):
    """Make `group` the user's only group (admin REST API, as provision-user.sh would)."""
    h = kc_admin_token()
    base = f"{AUTH}/admin/realms/lakehouse"
    uid = _http("GET", f"{base}/users?exact=true&username={username}", headers=h)[0]["id"]
    for g in _http("GET", f"{base}/users/{uid}/groups", headers=h):
        _http("DELETE", f"{base}/users/{uid}/groups/{g['id']}", headers=h)
    gid = next(g["id"] for g in _http("GET", f"{base}/groups?exact=true&search={group}", headers=h)
               if g["name"] == group)
    _http("PUT", f"{base}/users/{uid}/groups/{gid}", headers=h)
    now = [g["name"] for g in _http("GET", f"{base}/users/{uid}/groups", headers=h)]
    return now


# ---------------------------------------------------------------- browser helpers
class Session:
    """One browser context == one user's browser. Counts Keycloak password prompts."""

    def __init__(self, browser, user):
        self.user = user
        self.ctx = browser.new_context()
        self.page = self.ctx.new_page()
        self.password_prompts = 0

    def goto(self, target, settle_on=None, timeout=60):
        """Navigate; log into Keycloak if its form appears; wait until back on `settle_on` host."""
        page = self.page
        page.goto(target, wait_until="domcontentloaded")
        host = settle_on or urllib.parse.urlparse(target).hostname
        deadline = time.time() + timeout
        while time.time() < deadline:
            cur = urllib.parse.urlparse(page.url)
            if cur.hostname == f"auth.{D}" and page.locator("#username").count() > 0:
                self.password_prompts += 1
                page.fill("#username", self.user)
                page.fill("#password", PW)
                page.click("#kc-login")
                page.wait_for_load_state("domcontentloaded")
                continue
            if cur.hostname == host and "oauth" not in cur.path and "callback" not in cur.path \
                    and "login" not in cur.path:
                page.wait_for_load_state("networkidle")
                return page.url
            page.wait_for_timeout(500)
        raise TimeoutError(f"stuck at {page.url} while opening {target}")

    def get(self, u, **kw):
        return self.page.request.get(u, **kw)

    def shot(self, name):
        try:
            self.page.screenshot(path=f"/out/{name}.png", full_page=False)
        except Exception as e:  # noqa: BLE001 - evidence only
            print(f"screenshot {name} failed: {e}")

    def close(self):
        self.ctx.close()


def jupyter_probe(s):
    final = s.goto(url("jupyter", "/hub/home"))
    body = s.page.content()
    admin = s.get(url("jupyter", "/hub/admin"), max_redirects=0).status
    s.shot(f"jupyterhub-{s.user}")
    return {"url": final, "shows_user": s.user in body, "hub_admin_page_status": admin}


def superset_probe(s):
    final = s.goto(url("superset", "/login/keycloak"))
    r = s.get(url("superset", "/api/v1/me/roles/"))
    roles = sorted(r.json()["result"]["roles"].keys()) if r.ok else None
    me = s.get(url("superset", "/api/v1/me/"))
    uname = me.json()["result"]["username"] if me.ok else None
    s.shot(f"superset-{s.user}")
    return {"url": final, "username": uname, "roles": roles, "me_status": me.status}


def airflow_probe(s):
    final = s.goto(url("airflow", "/"))
    dags = s.get(url("airflow", "/api/v2/dags?limit=1")).status
    pool = f"s3probe_{s.user}"
    created = s.page.request.post(url("airflow", "/api/v2/pools"),
                                  data=json.dumps({"name": pool, "slots": 1}),
                                  headers={"Content-Type": "application/json"})
    if created.status in (200, 201):
        s.page.request.delete(url("airflow", f"/api/v2/pools/{pool}"))
    s.page.wait_for_timeout(1500)
    s.shot(f"airflow-{s.user}")
    return {"url": final, "get_dags_status": dags, "create_pool_status": created.status,
            "can_write": created.status in (200, 201, 409)}


def trino_probe(s):
    final = s.goto(url("trino", "/ui/"))
    stats = s.get(url("trino", "/ui/api/stats"))
    s.shot(f"trino-{s.user}")
    return {"url": final, "ui_api_stats_status": stats.status}


def lakekeeper_probe(s):
    page = s.page
    seen = []

    def on_resp(resp):
        if "/management/v1/" in resp.url and resp.request.headers.get("authorization", "").startswith("Bearer"):
            seen.append((resp.url.split(f":{P}")[-1], resp.status))

    page.on("response", on_resp)
    s.goto(url("catalog", "/ui/"))
    page.wait_for_timeout(2000)
    # Lakekeeper's UI shows a "Sign In" button rather than redirecting on its own.
    btn = page.get_by_role("button", name="Sign In")
    if btn.count() > 0:
        btn.first.click()
    final = s._finish_on(f"catalog.{D}")
    page.wait_for_timeout(3000)
    whoami = page.evaluate(
        """async () => {
            for (const store of [sessionStorage, localStorage]) {
              for (let i = 0; i < store.length; i++) {
                const k = store.key(i);
                if (k.startsWith('oidc.user:')) {
                  const t = JSON.parse(store.getItem(k)).access_token;
                  const r = await fetch('/management/v1/whoami', {headers: {Authorization: 'Bearer ' + t}});
                  return {status: r.status, body: await r.json()};
                }
              }
            }
            return null;
        }"""
    )
    s.shot(f"lakekeeper-{s.user}")
    page.remove_listener("response", on_resp)
    return {"url": final, "ui_bearer_calls": seen[:5], "whoami": whoami}


def _finish_on(self, host, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        cur = urllib.parse.urlparse(self.page.url)
        if cur.hostname == f"auth.{D}" and self.page.locator("#username").count() > 0:
            self.password_prompts += 1
            self.page.fill("#username", self.user)
            self.page.fill("#password", PW)
            self.page.click("#kc-login")
            self.page.wait_for_load_state("domcontentloaded")
            continue
        if cur.hostname == host and "callback" not in cur.path and not cur.path.endswith("/login"):
            self.page.wait_for_load_state("networkidle")
            return self.page.url
        self.page.wait_for_timeout(500)
    raise TimeoutError(f"stuck at {self.page.url}")


Session._finish_on = _finish_on


def mapped(roles):
    return None if roles is None else [r for r in roles if r != "Public"]


def safe(fn, s):
    try:
        return fn(s)
    except Exception as e:  # noqa: BLE001 - report per app, keep going
        s.shot(f"error-{fn.__name__}-{s.user}")
        return {"error": f"{type(e).__name__}: {e}", "url": s.page.url}


def main():
    os.makedirs("/out", exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        # ---- C2: one login, five apps (alice = lab-admin)
        s = Session(browser, "alice")
        apps = {"jupyterhub": safe(jupyter_probe, s), "superset": safe(superset_probe, s),
                "airflow": safe(airflow_probe, s), "trino": safe(trino_probe, s),
                "lakekeeper": safe(lakekeeper_probe, s)}
        print(json.dumps(apps, indent=1))
        check("C2.jupyterhub", apps["jupyterhub"].get("shows_user"), apps["jupyterhub"])
        check("C2.superset", apps["superset"].get("username") == "alice", apps["superset"])
        check("C2.airflow", apps["airflow"].get("get_dags_status") == 200, apps["airflow"])
        check("C2.trino", apps["trino"].get("ui_api_stats_status") == 200, apps["trino"])
        lk = apps["lakekeeper"].get("whoami") or {}
        check("C2.lakekeeper", lk.get("status") == 200, apps["lakekeeper"])
        check("C2.single_password_prompt", s.password_prompts == 1,
              f"Keycloak password form shown {s.password_prompts} time(s) across 5 apps")
        admin_apps = apps
        s.close()

        # ---- C3: viewer vs admin differ in Superset and Airflow (and JupyterHub admin)
        v = Session(browser, "victor")
        vs, va, vj = safe(superset_probe, v), safe(airflow_probe, v), safe(jupyter_probe, v)
        v.close()
        a_ss, a_af = admin_apps["superset"], admin_apps["airflow"]
        # "Public" is FAB's registration default and carries no permissions; compare the mapped roles.
        check("C3.superset", mapped(a_ss.get("roles")) == ["Admin"] and mapped(vs.get("roles")) == ["Gamma"],
              {"alice": a_ss.get("roles"), "victor": vs.get("roles")})
        check("C3.airflow", a_af.get("can_write") is True and va.get("create_pool_status") == 403
              and va.get("get_dags_status") == 200,
              {"alice": a_af, "victor": va})
        check("C3.jupyterhub_admin", admin_apps["jupyterhub"].get("hub_admin_page_status") == 200
              and vj.get("hub_admin_page_status") in (403, 302),
              {"alice": admin_apps["jupyterhub"].get("hub_admin_page_status"),
               "victor": vj.get("hub_admin_page_status")})

        # ---- C4: group change in Keycloak shows up on next login (sam: viewer -> lab-admin -> viewer)
        phases = []
        for group in ("viewer", "lab-admin", "viewer"):
            now = kc_set_group("sam", group)
            x = Session(browser, "sam")
            ss, af, jh = safe(superset_probe, x), safe(airflow_probe, x), safe(jupyter_probe, x)
            x.close()
            phases.append({"keycloak_groups": now, "superset_roles": ss.get("roles"),
                           "airflow_create_pool": af.get("create_pool_status"),
                           "hub_admin_page": jh.get("hub_admin_page_status")})
        print(json.dumps(phases, indent=1))
        want = [(["Gamma"], 403), (["Admin"], None), (["Gamma"], 403)]
        ok_ss = [mapped(p["superset_roles"]) for p in phases] == [w[0] for w in want]
        ok_af = phases[0]["airflow_create_pool"] == 403 and phases[1]["airflow_create_pool"] in (200, 201, 409) \
            and phases[2]["airflow_create_pool"] == 403
        check("C4.superset", ok_ss, [p["superset_roles"] for p in phases])
        check("C4.airflow", ok_af, [p["airflow_create_pool"] for p in phases])
        check("C4.jupyterhub_admin", [p["hub_admin_page"] == 200 for p in phases] == [False, True, False],
              [p["hub_admin_page"] for p in phases])
        browser.close()

    with open("/out/results.json", "w") as f:
        json.dump({"results": RESULTS, "failed": FAILED}, f, indent=1)
    print("FAILED:" if FAILED else "ALL BROWSER CHECKS PASSED", FAILED or "")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
