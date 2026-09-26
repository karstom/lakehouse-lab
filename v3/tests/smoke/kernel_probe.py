"""Smoke checks 8-10, the part that runs INSIDE a user's workspace (in a Jupyter kernel).

smoke.py sends this file's source to a kernel in the user's own JupyterLab server (Jupyter
REST API + kernel websocket, with the user's browser session), followed by one call:

    print(MARKER + json.dumps(probe(<params>)))

so everything here runs as that user, with the workspace image's clients and the user's own
Keycloak token. Stdlib at import time; the clients are imported inside each step, so a
missing one fails that step only. It never prints tokens or credentials.

Interface (CONTRACT.md Phase 2; as built in images/workspace and config/jupyterhub):
  * token: `lab_token()` is the ONE way to get the user's fresh Keycloak access token.
    Looked up as: a `lab_token` in the kernel namespace, then params["token_modules"]
    (the image ships `from lakehouse import lab_token`), then the `lab-token` CLI.
  * endpoints from the spawner's environment: LAB_TRINO_HOST/LAB_TRINO_PORT,
    LAB_CATALOG_URL, LAB_WAREHOUSE, SPARK_REMOTE; CA: SSL_CERT_FILE/REQUESTS_CA_BUNDLE.
    params carry fallbacks for each.
  * starter dbt project: a directory with dbt_project.yml in the home (params["starter_dirs"]
    first, then a shallow search). `dbt build` runs there as the user types it: the image's
    `dbt` wrapper supplies the token itself (DBT_ENV_SECRET_LAB_TOKEN from lab-token).
  * Spark Connect: the image's helper (params["spark_helpers"], e.g. lakehouse.spark) if it
    exists, else SparkSession.builder.remote(SPARK_REMOTE) with the user's token as
    spark.sql.catalog.<catalog>.token (OQ-15 per-session catalog token).
"""
import glob
import json
import os
import re
import subprocess
import time
import traceback

MARKER = "SMOKE_PROBE_RESULT "


def _short(e, n=400):
    return " ".join(f"{type(e).__name__}: {e}".split())[:n]


def _ca():
    return os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE") or True


# ---------------------------------------------------------------- token
def get_token(params, ns=None):
    """(token, source). The contract's single token helper, whichever form the image ships."""
    fn = (ns or {}).get("lab_token")
    if callable(fn):
        return fn(), "kernel-namespace:lab_token"
    for mod in params.get("token_modules", []):
        try:
            m = __import__(mod, fromlist=["lab_token"])
        except ImportError:
            continue
        fn = getattr(m, "lab_token", None)
        if callable(fn):
            return fn(), f"python:{mod}.lab_token"
    try:
        r = subprocess.run(["lab-token"], capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        raise RuntimeError("no token helper: neither lab_token() nor the lab-token CLI exists")
    tok = r.stdout.strip()
    if r.returncode != 0 or not tok:
        raise RuntimeError(f"lab-token exited {r.returncode}: {r.stderr.strip()[-300:]}")
    return tok, "cli:lab-token"


def jwt_claims(tok):
    """Unverified payload of a JWT (evidence only: preferred_username, exp)."""
    import base64
    try:
        part = tok.split(".")[1]
        part += "=" * (-len(part) % 4)
        c = json.loads(base64.urlsafe_b64decode(part))
        return {k: c.get(k) for k in ("preferred_username", "azp", "exp")}
    except Exception:  # noqa: BLE001
        return {}


# ---------------------------------------------------------------- Trino
def trino_cursor(params, tok, schema="samples"):
    import trino
    conn = trino.dbapi.connect(
        host=os.environ.get("LAB_TRINO_HOST") or params["trino_host"],
        port=int(os.environ.get("LAB_TRINO_PORT") or params["trino_port"]), http_scheme="https",
        auth=trino.auth.JWTAuthentication(tok), verify=_ca(),
        catalog="lakehouse", schema=schema)
    return conn.cursor()


def step_trino_samples(params, ns):
    tok, src = get_token(params, ns)
    cur = trino_cursor(params, tok)
    cur.execute("SELECT current_user")
    me = cur.fetchall()[0][0]
    cur.execute("SELECT count(*) FROM lakehouse.samples.orders")
    n = cur.fetchall()[0][0]
    return {"ok": me == params["user"] and n > 0, "current_user": me, "orders": n,
            "token_source": src, "token_claims": jwt_claims(tok)}


def step_trino_write_denied(params, ns):
    """Viewer: reading works, a write is refused by Trino's access control."""
    import trino
    tok, src = get_token(params, ns)
    cur = trino_cursor(params, tok)
    cur.execute("SELECT current_user")
    me = cur.fetchall()[0][0]
    cur.execute("SELECT count(*) FROM lakehouse.samples.orders")
    n = cur.fetchall()[0][0]
    table = params["write_probe_table"]
    err = None
    try:
        cur.execute(f"INSERT INTO {table} VALUES (99, 'from-workspace', 9.0)")
        cur.fetchall()
    except trino.exceptions.TrinoUserError as e:
        err = f"{e.error_name}: {e.message[:200]}"
    return {"ok": me == params["user"] and n > 0 and err is not None and "Access Denied" in err,
            "current_user": me, "orders_readable": n, "insert_error": err, "token_source": src}


# ---------------------------------------------------------------- DuckDB
def _duck_secret_summary(con):
    rows = con.execute("SELECT type, provider, secret_string FROM duckdb_secrets(redact=true)").fetchall()
    out = []
    for typ, prov, s in rows:
        kid = next((p.split("=", 1)[1][:4] for p in s.split(";") if p.startswith("key_id=")), "")
        out.append({"type": typ, "provider": prov, "key_id_prefix": kid})
    return out


def _duck_attach(con, tok, ep, mode):
    for ext in ("httpfs", "avro", "iceberg"):
        con.execute(f"LOAD {ext}")
    if "'" in tok:
        raise ValueError("unexpected quote in token")
    con.execute(f"CREATE OR REPLACE SECRET lab_catalog (TYPE iceberg, TOKEN '{tok}')")
    wh = os.environ.get("LAB_WAREHOUSE") or "lakehouse"
    con.execute(f"ATTACH '{wh}' AS lk (TYPE iceberg, ENDPOINT '{ep}', "
                f"SECRET lab_catalog, ACCESS_DELEGATION_MODE '{mode}')")
    return con.execute("SELECT count(*) FROM lk.samples.orders").fetchone()[0]


def _no_static_s3_credentials():
    """The workspace has no storage key of its own: no AWS_* variables and no ~/.aws."""
    env = sorted(k for k in os.environ if k.startswith("AWS_"))
    aws_dir = os.path.exists(os.path.expanduser("~/.aws"))
    return not env and not aws_dir, {"aws_env": env, "home_aws_dir": aws_dir}


def step_duckdb_attach(params, ns, expected=None):
    """DuckDB ATTACH of the catalog with vended credentials. Proof that the data came through
    Lakekeeper-vended credentials (duckdb_secrets() does not list the vended S3 secret
    reliably): the read works with ACCESS_DELEGATION_MODE 'vended_credentials', the same
    ATTACH with 'none' cannot read the data, and the workspace holds no S3 key itself."""
    import duckdb
    tok, src = get_token(params, ns)
    urls = [u for u in [os.environ.get("LAB_CATALOG_URL")] + params["catalog_urls"] if u]
    tried = []
    for ep in dict.fromkeys(urls):
        con = duckdb.connect()
        try:
            n = _duck_attach(con, tok, ep, "vended_credentials")
            secrets = _duck_secret_summary(con)
        except Exception as e:  # noqa: BLE001 - try the next endpoint, report all
            tried.append({"endpoint": ep, "error": _short(e)})
            continue
        finally:
            con.close()
        con = duckdb.connect()
        try:
            n_none = _duck_attach(con, tok, ep, "none")
            without = {"read": True, "orders": n_none}
        except Exception as e:  # noqa: BLE001 - expected: no credentials without vending
            without = {"read": False, "error": _short(e, 200)}
        finally:
            con.close()
        no_keys, key_ev = _no_static_s3_credentials()
        ok = n > 0 and (expected is None or n == expected) and not without["read"] and no_keys
        return {"ok": ok, "endpoint": ep, "orders": n, "trino_orders": expected,
                "without_vending": without, "static_s3_credentials": key_ev,
                "secrets": [s for s in secrets if s["provider"] != "config"] or secrets,
                "token_source": src, "tried": tried}
    return {"ok": False, "tried": tried}


# ---------------------------------------------------------------- dbt
def find_starter(params, home=None):
    home = home or os.path.expanduser("~")
    for d in params.get("starter_dirs", []):
        p = os.path.join(home, d)
        if os.path.isfile(os.path.join(p, "dbt_project.yml")):
            return p
    hits = sorted(glob.glob(os.path.join(home, "*", "dbt_project.yml"))
                  + glob.glob(os.path.join(home, "*", "*", "dbt_project.yml"))
                  + glob.glob(os.path.join(home, "*", "*", "*", "dbt_project.yml")),
                  key=lambda p: (p.count(os.sep), p))
    hits = [h for h in hits if "/dbt_packages/" not in h and "/.ipynb_checkpoints/" not in h]
    return os.path.dirname(hits[0]) if hits else None


DBT_DONE = re.compile(r"Done\. ((?:[A-Z][A-Z-]*=\d+ ?)+)")


def dbt_summary(text):
    """The last 'Done. PASS=.. WARN=.. ERROR=.. SKIP=.. [NO-OP=..] [REUSED=..] TOTAL=..' line
    as a dict (keys lower-case, '-' -> '_'). dbt adds fields between versions, so every
    KEY=N pair is taken; PASS, ERROR and TOTAL must be present."""
    m = None
    for m in DBT_DONE.finditer(text):
        pass
    if not m:
        return None
    out = {k.lower().replace("-", "_"): int(v)
           for k, v in re.findall(r"([A-Z][A-Z-]*)=(\d+)", m.group(1))}
    return out if {"pass", "error", "total"} <= out.keys() else None


def step_dbt_build(params, ns):
    proj = find_starter(params)
    if not proj:
        return {"ok": False, "error": "no starter dbt project (dbt_project.yml) in the home directory"}
    # As the user would run it: the workspace's `dbt` supplies the user's token itself.
    env = dict(os.environ, DBT_SEND_ANONYMOUS_USAGE_STATS="false", DO_NOT_TRACK="1")
    t0 = time.time()
    r = subprocess.run(["dbt", "build", "--no-use-colors"], cwd=proj, env=env,
                       capture_output=True, text=True, timeout=params.get("dbt_timeout", 420))
    out = (r.stdout or "") + (r.stderr or "")
    summ = dbt_summary(out)
    ok = r.returncode == 0 and bool(summ) and summ.get("error", 1) == 0 and summ.get("pass", 0) > 0
    res = {"ok": ok, "project": proj, "rc": r.returncode, "summary": summ,
           "seconds": round(time.time() - t0, 1)}
    if ok:
        # dbt's own PASS count is not enough: the mart tables must exist and hold data,
        # readable through Trino as the same user (verifier follow-up #3).
        schema = f"dbt_{params['user']}"
        tok, _ = get_token(params, ns)
        cur = trino_cursor(params, tok, schema=schema)
        cur.execute(f"SHOW TABLES FROM lakehouse.{schema}")
        tables = sorted(r[0] for r in cur.fetchall())
        cur.execute(f"SELECT count(*) FROM lakehouse.{schema}.revenue_by_region")
        rows = cur.fetchall()[0][0]
        marts = {"fct_orders", "dim_customers", "revenue_by_region"}
        res.update({"schema": schema, "tables": tables, "revenue_by_region_rows": rows})
        res["ok"] = marts <= set(tables) and rows > 0
    if not ok:
        res["tail"] = _scrub(out)[-1500:]
    return res


def _scrub(text):
    """Never let a JWT reach the smoke output."""
    return re.sub(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "<jwt>", text)


# ---------------------------------------------------------------- Spark Connect
def spark_session(params, ns, tok):
    helper, how = (ns or {}).get("lab_spark"), "kernel-namespace:lab_spark"
    if not callable(helper):
        helper = None
        for ref in params.get("spark_helpers", []):
            mod, _, attr = ref.rpartition(".")
            try:
                helper = getattr(__import__(mod, fromlist=[attr]), attr, None)
            except ImportError:
                helper = None
            if callable(helper):
                how = f"helper:{ref}"
                break
            helper = None
    if helper is not None:
        return helper(), how
    from pyspark.sql import SparkSession
    remote = os.environ.get("SPARK_REMOTE") or params["spark_remote"]
    cat = params["spark_catalog"]
    spark = (SparkSession.builder.remote(remote)
             .config(f"spark.sql.catalog.{cat}.token", tok)
             .create())
    return spark, f"remote:{remote}"


def step_spark_iceberg(params, ns):
    tok, src = get_token(params, ns)
    spark, how = spark_session(params, ns, tok)
    cat = params["spark_catalog"]
    t = f"{cat}.{params['spark_schema']}.{params['spark_table']}"
    try:
        spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {cat}.{params['spark_schema']}")
        # Plain DROP: never PURGE from Spark against Lakekeeper (ADR-003).
        spark.sql(f"DROP TABLE IF EXISTS {t}")
        spark.sql(f"CREATE TABLE {t} (id BIGINT, who STRING) USING iceberg")
        spark.sql(f"INSERT INTO {t} VALUES (1, '{params['user']}'), (2, '{params['user']}')")
        rows = [tuple(r) for r in spark.sql(f"SELECT id, who FROM {t} ORDER BY id").collect()]
        snaps = spark.sql(f"SELECT count(*) FROM {t}.snapshots").collect()[0][0]
        spark.sql(f"DROP TABLE IF EXISTS {t}")
    finally:
        try:
            spark.stop()
        except Exception:  # noqa: BLE001
            pass
    want = [(1, params["user"]), (2, params["user"])]
    return {"ok": rows == want and snaps >= 1, "table": t, "rows": rows, "snapshots": snaps,
            "session": how, "token_source": src}


def step_spark_write_denied(params, ns):
    """victor through Spark Connect: a table create must be refused by Lakekeeper. This is
    what proves the per-session user token reaches the catalog (OQ-15); with a shared
    service identity it would succeed."""
    tok, src = get_token(params, ns)
    spark, how = spark_session(params, ns, tok)
    t = f"{params['spark_catalog']}.samples.victor_spark_probe"
    created, err = False, None
    try:
        spark.sql(f"CREATE TABLE {t} (id BIGINT) USING iceberg")
        created = True
        spark.sql(f"DROP TABLE IF EXISTS {t}")  # plain DROP only (ADR-003)
    except Exception as e:  # noqa: BLE001 - the refusal is the expected outcome
        err = _short(e, 300)
    finally:
        try:
            spark.stop()
        except Exception:  # noqa: BLE001
            pass
    refused = err is not None and any(k in err for k in (
        "Forbidden", "NotAuthorized", "not allowed", "permission", "Permission", "403"))
    return {"ok": (not created) and refused, "table": t, "created": created, "error": err,
            "session": how, "token_source": src}


STEPS = {
    "trino_samples": step_trino_samples,
    "trino_write_denied": step_trino_write_denied,
    "duckdb_attach": step_duckdb_attach,
    "dbt_build": step_dbt_build,
    "spark_iceberg": step_spark_iceberg,
    "spark_write_denied": step_spark_write_denied,
}


STACK_DUMP = "~/.smoke-stack.txt"   # read back by workspace.py if the probe times out


def probe(params, ns=None):
    """Run params["steps"] in order; one failing step never hides the others. If the kernel
    is still busy after dump_after_s, every thread's stack is written to STACK_DUMP so a hang
    is diagnosable (an intermittent Spark Connect hang was seen once, not reproducible)."""
    import faulthandler
    dump = open(os.path.expanduser(STACK_DUMP), "w")  # noqa: SIM115 - must stay open
    faulthandler.dump_traceback_later(params.get("dump_after_s", 240), file=dump)
    try:
        return _probe(params, ns)
    finally:
        faulthandler.cancel_dump_traceback_later()
        dump.close()


def _probe(params, ns):
    out = {"user_env": os.environ.get("JUPYTERHUB_USER"), "steps": {}}
    for name in params["steps"]:
        t0 = time.time()
        try:
            if name == "duckdb_attach":
                prev = out["steps"].get("trino_samples", {})
                res = STEPS[name](params, ns, expected=prev.get("orders"))
            else:
                res = STEPS[name](params, ns)
        except Exception as e:  # noqa: BLE001
            res = {"ok": False, "error": _short(e), "trace": traceback.format_exc()[-1200:]}
        res.setdefault("seconds", round(time.time() - t0, 1))
        out["steps"][name] = res
    return out
