"""Lakehouse Lab V3 smoke test, in-container part (CONTRACT.md "Test contract", checks 2-5
and 7; Phase 2 checks 8-10, the workspace, driven by workspace.py + kernel_probe.py; Phase 3
checks 12-16, Airflow, Superset, Console, Spark UI and the external IdP, in phase3.py).

Runs on the `lab` network and talks to the public URLs https://<svc>.<LAB_DOMAIN>:<port>
through Caddy, trusting only the lab CA. Checks 1 and 6 need the Docker host and live in
run.sh. Prints one [PASS]/[FAIL]/[SKIP] line per check, writes /out/results.json and
/out/summary.env (counts for run.sh), and exits 0 only if no check failed. Idempotent: it
recreates its own tables on every run and stops the workspaces it started.
"""
import json
import os
import socket
import sys
import time
import traceback
import urllib.parse

import requests

D = os.environ["LAB_DOMAIN"]
P = os.environ["LAB_HTTPS_PORT"]  # numeric port for the Trino client
# Port suffix of every public URL, taken from the single derived origin (installer/lib.sh):
# "" on 443, ":<port>" otherwise. Browsers drop a default :443, so never rebuild it here.
PORT_SUFFIX = os.environ["LAB_AUTH_URL"].removeprefix(f"https://auth.{D}")
PW = os.environ.get("LAB_TEST_USER_PASSWORD", "")
TRINO_SECRET = os.environ["OIDC_CLIENT_SECRET_TRINO"]
CA = "/trust/ca-bundle.crt"
PROFILE = os.environ.get("LAB_PROFILE", "core")
SPARK_PROFILES = ("engineer", "full", "server")   # profiles that include Spark (ARCHITECTURE §8)

SCHEMA = "smoke"
TABLE = "events"
ROWS = [(1, "click", 1.5), (2, "view", 2.5), (3, "buy", 30.0)]

RESULTS = {}


def url(svc, path=""):
    return f"https://{svc}.{D}{PORT_SUFFIX}{path}"


def check(name, ok, evidence):
    RESULTS[name] = {"pass": bool(ok), "evidence": evidence}
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {evidence}", flush=True)
    return bool(ok)


def skip(name, reason):
    RESULTS[name] = {"pass": None, "skipped": True, "evidence": reason}
    print(f"[SKIP] {name}: {reason}", flush=True)


def guarded(name, fn):
    try:
        fn()
    except Exception as e:  # noqa: BLE001 - one failing check must not hide the others
        traceback.print_exc()
        check(name, False, f"{type(e).__name__}: {e}")


def user_token(username):
    """A Keycloak-issued access token for a test user (password grant on the `trino` client;
    bootstrap enables that grant only when LAB_SEED_TEST_USERS=true)."""
    r = requests.post(url("auth", "/realms/lakehouse/protocol/openid-connect/token"), data={
        "grant_type": "password", "client_id": "trino", "client_secret": TRINO_SECRET,
        "username": username, "password": PW, "scope": "openid"}, verify=CA, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"token for {username}: HTTP {r.status_code} {r.text[:200]}")
    return r.json()["access_token"]


def trino_conn(token):
    import trino
    return trino.dbapi.connect(
        host=f"trino.{D}", port=int(P), http_scheme="https", verify=CA,
        auth=trino.auth.JWTAuthentication(token), catalog="lakehouse", schema=SCHEMA)


def run(cur, sql):
    cur.execute(sql)
    return cur.fetchall()


# ---------------------------------------------------------------- 2. browser login -> Trino UI
def check_browser_login():
    from playwright.sync_api import sync_playwright
    # Chromium hard-wires *.localhost to loopback (it never asks DNS), so on the default
    # WSL2/CI domain lab.localhost it would miss Caddy's network aliases. Resolve the alias
    # the way every other client here does (Docker DNS) and pin all lab hostnames to it.
    # Every <svc>.<LAB_DOMAIN> is a Caddy alias, so one IP covers them all.
    caddy_ip = socket.gethostbyname(f"trino.{D}")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=[f"--host-resolver-rules=MAP *.{D} {caddy_ip}"])
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(url("trino", "/ui/"), wait_until="domcontentloaded")
        prompts = 0
        deadline = time.time() + 90
        while time.time() < deadline:
            cur = urllib.parse.urlparse(page.url)
            if cur.hostname == f"auth.{D}" and page.locator("#username").count() > 0:
                prompts += 1
                if prompts > 1:
                    raise RuntimeError("Keycloak asked for the password twice (login rejected?)")
                page.fill("#username", "alice")
                page.fill("#password", PW)
                page.click("#kc-login")
                page.wait_for_load_state("domcontentloaded")
                continue
            if cur.hostname == f"trino.{D}" and cur.path.startswith("/ui") \
                    and "oauth2" not in cur.path and "login" not in cur.path:
                break
            page.wait_for_timeout(500)
        page.wait_for_load_state("networkidle")
        stats = page.request.get(url("trino", "/ui/api/stats"))
        who = page.request.get(url("trino", "/ui/api/cluster"))  # needs an authenticated UI session
        try:
            os.makedirs("/out", exist_ok=True)
            page.screenshot(path="/out/trino-ui-alice.png")
        except Exception:  # noqa: BLE001 - evidence only
            pass
        final = page.url
        browser.close()
    check("2.browser_login_trino_ui",
          prompts == 1 and final.startswith(url("trino", "/ui")) and stats.status == 200,
          {"final_url": final, "keycloak_password_prompts": prompts, "caddy_ip": caddy_ip,
           "ui_api_stats": stats.status, "ui_api_cluster": who.status})


# ---------------------------------------------------------------- 3. Trino with alice's JWT
STATE = {}


def check_trino_alice():
    tok = user_token("alice")
    STATE["alice_token"] = tok
    cur = trino_conn(tok).cursor()
    me = run(cur, "SELECT current_user")[0][0]
    run(cur, f"CREATE SCHEMA IF NOT EXISTS lakehouse.{SCHEMA}")
    run(cur, f"DROP TABLE IF EXISTS lakehouse.{SCHEMA}.{TABLE}")
    run(cur, f"CREATE TABLE lakehouse.{SCHEMA}.{TABLE} (id bigint, kind varchar, amount double)")
    values = ", ".join(f"({i}, '{k}', {a})" for i, k, a in ROWS)
    inserted = run(cur, f"INSERT INTO lakehouse.{SCHEMA}.{TABLE} VALUES {values}")[0][0]
    rows = run(cur, f"SELECT id, kind, amount FROM lakehouse.{SCHEMA}.{TABLE} ORDER BY id")
    got = [tuple(r) for r in rows]
    check("3.trino_alice_create_insert_read",
          me == "alice" and inserted == len(ROWS) and got == ROWS,
          {"current_user": me, "inserted": inserted, "rows": got})


# ---------------------------------------------------------------- 4. PyIceberg + vended creds
def check_pyiceberg_vended():
    from pyiceberg.catalog.rest import RestCatalog
    tok = STATE.get("alice_token") or user_token("alice")
    cat = RestCatalog("lakehouse", **{
        "uri": url("catalog", "/catalog"),
        "warehouse": "lakehouse",
        "token": tok,
        "header.X-Iceberg-Access-Delegation": "vended-credentials",
    })
    tbl = cat.load_table((SCHEMA, TABLE))
    arrow = tbl.scan().to_arrow()
    got = sorted(zip(arrow["id"].to_pylist(), arrow["kind"].to_pylist(), arrow["amount"].to_pylist()))
    props = tbl.io.properties
    ak = props.get("s3.access-key-id", "")
    vended = ak.startswith("ASIA") and bool(props.get("s3.session-token"))
    endpoint = props.get("s3.endpoint", "")

    # With the same vended credentials: own table prefix allowed, sibling prefix denied.
    from pyarrow import fs as pafs
    ep = urllib.parse.urlparse(endpoint)
    s3 = pafs.S3FileSystem(access_key=ak, secret_key=props.get("s3.secret-access-key"),
                           session_token=props.get("s3.session-token"),
                           endpoint_override=ep.netloc, scheme=ep.scheme or "http",
                           region=props.get("s3.region") or props.get("client.region") or "us-east-1",
                           force_virtual_addressing=False)
    loc = tbl.metadata.location.removeprefix("s3://")     # warehouse/lakehouse/<ns-id>/<table-id>
    parent = loc.rsplit("/", 1)[0]

    def try_write(path):
        try:
            with s3.open_output_stream(path) as f:
                f.write(b"smoke scope probe")
        except OSError as e:
            msg = " ".join(str(e).split())
            if "ACCESS_DENIED" in msg or "AccessDenied" in msg or "403" in msg:
                return "denied (AccessDenied)"
            return f"error ({msg[-160:]})"
        try:
            s3.delete_file(path)
        except OSError:
            pass
        return "allowed"

    own = try_write(f"{loc}/smoke-scope-probe.txt")
    sibling = try_write(f"{parent}/smoke-sibling-not-a-table/smoke-scope-probe.txt")
    check("4.pyiceberg_vended_credentials",
          got == ROWS and vended and own == "allowed" and sibling.startswith("denied"),
          {"rows": got, "vended_sts_credentials": vended, "key_id_prefix": ak[:4],
           "s3_endpoint": endpoint, "own_prefix_write": own, "sibling_prefix_write": sibling})


# ---------------------------------------------------------------- 5. viewer denied a write
def check_viewer_denied():
    import trino
    tok = user_token("victor")
    cur = trino_conn(tok).cursor()
    me = run(cur, "SELECT current_user")[0][0]
    can_read = run(cur, f"SELECT count(*) FROM lakehouse.{SCHEMA}.{TABLE}")[0][0]
    err = None
    try:
        run(cur, f"INSERT INTO lakehouse.{SCHEMA}.{TABLE} VALUES (99, 'victor', 9.0)")
    except trino.exceptions.TrinoUserError as e:
        err = f"{e.error_name}: {e.message[:160]}"
    after = run(cur, f"SELECT count(*) FROM lakehouse.{SCHEMA}.{TABLE}")[0][0]
    check("5.viewer_write_denied",
          me == "victor" and err is not None and "Access Denied" in err and after == len(ROWS),
          {"current_user": me, "select_count": can_read, "insert_error": err, "count_after": after})


# ---------------------------------------------------------------- 7. group change, no shell (OQ-20)
def kc_admin_token():
    r = requests.post(url("auth", "/realms/master/protocol/openid-connect/token"), data={
        "grant_type": "password", "client_id": "admin-cli",
        "username": os.environ["KC_ADMIN_USER"], "password": os.environ["KC_ADMIN_PASSWORD"]},
        verify=CA, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def victor_can_insert(table):
    import trino
    cur = trino_conn(user_token("victor")).cursor()
    try:
        run(cur, f"INSERT INTO {table} VALUES (1)")
        return True
    except trino.exceptions.TrinoUserError as e:
        if "Access Denied" in e.message:
            return False
        raise


def wait_until(pred, want, budget):
    t0 = time.time()
    while time.time() - t0 < budget:
        if pred() == want:
            return round(time.time() - t0, 1)
        time.sleep(5)
    return None


def check_group_change_propagates():
    """An admin moves victor viewer -> engineer through the Keycloak admin API (what the
    Keycloak UI does), and Trino's permission follows with no shell step; then back."""
    budget = 3 * int(os.environ.get("LAB_SYNC_INTERVAL", "30")) + 45  # sync + Trino's 15s refresh
    base = url("auth", "/admin/realms/lakehouse")
    h = {"Authorization": f"Bearer {kc_admin_token()}"}
    uid = requests.get(f"{base}/users?exact=true&username=victor", headers=h, verify=CA, timeout=30).json()[0]["id"]
    gid = {g["name"]: g["id"] for g in requests.get(f"{base}/groups", headers=h, verify=CA, timeout=30).json()}["engineer"]
    table = f"lakehouse.{SCHEMA}.sync_probe"
    alice = trino_conn(STATE.get("alice_token") or user_token("alice")).cursor()
    run(alice, f"DROP TABLE IF EXISTS {table}")
    run(alice, f"CREATE TABLE {table} (id bigint)")
    before = victor_can_insert(table)
    granted = revoked = None
    try:
        requests.put(f"{base}/users/{uid}/groups/{gid}", headers=h, verify=CA, timeout=30).raise_for_status()
        granted = wait_until(lambda: victor_can_insert(table), True, budget)
    finally:
        h = {"Authorization": f"Bearer {kc_admin_token()}"}
        requests.delete(f"{base}/users/{uid}/groups/{gid}", headers=h, verify=CA, timeout=30).raise_for_status()
    if granted is not None:
        revoked = wait_until(lambda: victor_can_insert(table), False, budget)
    run(alice, f"DROP TABLE IF EXISTS {table}")
    check("7.group_change_propagates_without_shell",
          before is False and granted is not None and revoked is not None,
          {"victor_insert_before": before, "seconds_until_granted": granted,
           "seconds_until_revoked": revoked, "budget_s": budget})


# ---------------------------------------------------------------- 8-10. inside the workspace
C8 = "8.workspace_alice_trino_duckdb_dbt"
C9 = "9.workspace_viewer_write_denied"
C10 = "10.workspace_spark_connect_iceberg"


def probe_params(user, steps):
    return {
        "user": user, "steps": steps,
        "trino_host": f"trino.{D}", "trino_port": int(P),
        # Fallbacks after the workspace's $LAB_CATALOG_URL / $LAB_TRINO_HOST: the internal
        # catalog on the lab network, then the public URL through Caddy.
        "catalog_urls": ["http://lakekeeper:8181/catalog", url("catalog", "/catalog")],
        "token_modules": ["lakehouse", "lab_token"],
        "starter_dirs": ["starter/dbt_lakehouse", "starter"],
        "write_probe_table": f"lakehouse.{SCHEMA}.{TABLE}",
        "spark_helpers": ["lakehouse.spark"],
        "spark_remote": "sc://spark-connect:15002", "spark_catalog": "lakehouse",
        "spark_schema": SCHEMA, "spark_table": "spark_probe",
        "dbt_timeout": 420,
    }


def _steps_evidence(result, raw, names):
    if result is None:
        return {"probe": "no result from the kernel", "status": raw.get("status"),
                "error": raw.get("error"), "timeout": raw.get("timeout"),
                "stderr_tail": (raw.get("stderr") or "")[-800:],
                "stdout_tail": (raw.get("stdout") or "")[-400:],
                "stack_dump": raw.get("stack_dump")}
    ev = {"jupyterhub_user": result.get("user_env"), "kernel_seconds": raw.get("kernel_seconds")}
    for n in names:
        ev[n] = result["steps"].get(n, {"ok": False, "error": "step did not run"})
    return ev


def _workspace_browser(pw):
    caddy_ip = socket.gethostbyname(f"jupyter.{D}")   # same *.localhost workaround as check 2
    return pw.chromium.launch(args=[f"--host-resolver-rules=MAP *.{D} {caddy_ip}"])


def _alice_session(ws, spark):
    alice_steps = ["trino_samples", "duckdb_attach", "dbt_build"]
    login = ws.login_and_spawn()
    if not login["ok"]:
        check(C8, False, {"login_spawn": login})
        if spark:
            check(C10, False, "alice's workspace did not start (see check 8)")
        return
    steps = alice_steps + (["spark_iceberg"] if spark else [])
    result, raw = ws.run_probe(probe_params("alice", steps))
    ev = _steps_evidence(result, raw, alice_steps)
    ev["login_spawn"] = login
    ok8 = result is not None and result.get("user_env") == "alice" and \
        all(result["steps"].get(n, {}).get("ok") for n in alice_steps)
    check(C8, ok8, ev)
    if spark:
        check(C10, result is not None and bool(result["steps"].get("spark_iceberg", {}).get("ok")),
              _steps_evidence(result, raw, ["spark_iceberg"]))


def _victor_session(ws, _spark):
    login = ws.login_and_spawn()
    if not login["ok"]:
        check(C9, False, {"login_spawn": login})
        return
    steps = ["trino_write_denied"] + (["spark_write_denied"] if _spark else [])
    result, raw = ws.run_probe(probe_params("victor", steps), timeout=300)
    ev = _steps_evidence(result, raw, steps)
    ev["login_spawn"] = {k: login[k] for k in ("final_url", "seconds")}
    ok = result is not None and result.get("user_env") == "victor" and \
        all(result["steps"].get(n, {}).get("ok") for n in steps)
    check(C9, ok, ev)


def check_workspaces():
    """8: alice logs into jupyter., her workspace spawns, and inside it (her kernel, her token)
    Trino reads samples, DuckDB ATTACHes the catalog with vended credentials, and the starter
    dbt project builds. 10 (Spark profiles only): Spark Connect creates and reads an Iceberg
    table as alice, in the same kernel. 9: victor's workspace is denied a Trino write.
    One user at a time: each workspace is stopped again before the next one starts."""
    from playwright.sync_api import sync_playwright

    from workspace import Workspace

    spark = PROFILE in SPARK_PROFILES
    if not spark:
        skip(C10, f"profile {PROFILE}: Spark Connect is only in profile engineer")
    sessions = (("alice", _alice_session, (C8, C10) if spark else (C8,)),
                ("victor", _victor_session, (C9,)))
    with sync_playwright() as pw:
        browser = _workspace_browser(pw)
        try:
            for user, fn, names in sessions:
                ws = Workspace(browser, url, D, user, PW)
                try:
                    fn(ws, spark)
                except Exception as e:  # noqa: BLE001 - record, then go on to the next user
                    traceback.print_exc()
                    for name in names:
                        if name not in RESULTS:
                            check(name, False, f"{type(e).__name__}: {e}"[:500])
                finally:
                    print(f"[info] {user}'s workspace stopped: {ws.stop_server()}", flush=True)
                    ws.close()
        finally:
            browser.close()


def main():
    if not PW:
        print("LAB_TEST_USER_PASSWORD is empty: the smoke test needs LAB_SEED_TEST_USERS=true")
        sys.exit(2)
    # LAB_SMOKE_ONLY=3,8 runs only those checks (debugging; the contract run runs all).
    only = {x.strip() for x in os.environ.get("LAB_SMOKE_ONLY", "").split(",") if x.strip()}

    def want(n):
        return not only or str(n) in only

    for n, name, fn in ((2, "2.browser_login_trino_ui", check_browser_login),
                        (3, "3.trino_alice_create_insert_read", check_trino_alice),
                        (4, "4.pyiceberg_vended_credentials", check_pyiceberg_vended),
                        (5, "5.viewer_write_denied", check_viewer_denied),
                        (7, "7.group_change_propagates_without_shell", check_group_change_propagates)):
        if want(n):
            guarded(name, fn)
    if want(8) or want(9) or want(10):
        try:
            check_workspaces()
        except Exception as e:  # noqa: BLE001 - e.g. the browser failed to start
            traceback.print_exc()
            for name in (C8, C9, C10):
                if name not in RESULTS:
                    check(name, False, f"not run: {type(e).__name__}: {e}"[:500])
    # Phase 3 (12-16), each gated by profile with a [SKIP] line; 13 also by LAB_SMOKE_LONG.
    import phase3
    phase3.run_all(sys.modules[__name__], want)
    failed = [k for k, v in RESULTS.items() if v["pass"] is False]
    skipped = [k for k, v in RESULTS.items() if v.get("skipped")]
    passed = [k for k, v in RESULTS.items() if v["pass"] is True]
    try:
        os.makedirs("/out", exist_ok=True)
        with open("/out/results.json", "w") as f:
            json.dump({"profile": PROFILE, "results": RESULTS, "failed": failed,
                       "skipped": skipped}, f, indent=1, default=str)
        with open("/out/summary.env", "w") as f:
            f.write(f"CONTAINER_PASSED={len(passed)}\nCONTAINER_FAILED={len(failed)}\n"
                    f"CONTAINER_SKIPPED={len(skipped)}\n"
                    f"CONTAINER_SKIPPED_NAMES={','.join(skipped)}\n")
    except OSError:
        pass
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
