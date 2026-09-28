"""The bodies of the lab-context tools (context_server.py registers them). Each one acts as
the logged-in user with their own token and only reads. Kept free of the MCP SDK so the unit
tests can call them directly.
"""
import datetime
import json
import os
import urllib.parse

from . import trino_client
from .common import (MAX_ROWS, ToolFailure, clip, denied_or_error, http_json,
                     ident, public_url, split_table, user_token)

TRACKS_SRC = "/opt/lakehouse/tracks"
AIRFLOW_TOKEN_PATH = "/lab-auth/token"    # config/airflow lab_auth plugin (Phase 5)


def _iso(v):
    if isinstance(v, datetime.datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=datetime.timezone.utc)
        return v.astimezone(datetime.timezone.utc).isoformat()
    return v


# ---------------------------------------------------------------------------- Superset
def _rison_str(s):
    # Rison string: '...' with ! and ' escaped by !
    return "'" + s.replace("!", "!!").replace("'", "!'") + "'"


def superset_dashboard_datasets(dashboard):
    """Datasets (and so the tables) behind one Superset dashboard, as the user."""
    if not isinstance(dashboard, str) or not dashboard.strip() or len(dashboard) > 200:
        raise ToolFailure("invalid", "dashboard: give its title, slug or numeric id")
    base = public_url("superset")
    token = user_token()
    name = dashboard.strip()
    dash = None
    if name.isdigit():
        st, body = http_json("GET", f"{base}/api/v1/dashboard/{name}", token, service="Superset")
        if st != 200:
            raise denied_or_error(st, body, "Superset", f"dashboard {name}")
        dash = body.get("result") or {}
    else:
        q = ("(columns:!(id,dashboard_title,slug,published,changed_on_utc),"
             "filters:!((col:dashboard_title,opr:eq,value:" + _rison_str(name) + ")),page_size:5)")
        st, body = http_json("GET", f"{base}/api/v1/dashboard/?q={urllib.parse.quote(q)}",
                             token, service="Superset")
        if st != 200:
            raise denied_or_error(st, body, "Superset", "the dashboard list")
        found = body.get("result") or []
        if not found:
            # a slug?
            st2, body2 = http_json("GET", f"{base}/api/v1/dashboard/{urllib.parse.quote(name, safe='')}",
                                   token, service="Superset")
            if st2 == 200:
                found = [body2.get("result") or {}]
            elif st2 in (401, 403):
                raise denied_or_error(st2, body2, "Superset", f"dashboard {name!r}")
        if not found:
            raise ToolFailure("invalid", f"no dashboard titled {name!r} that you can see "
                              f"(it does not exist, or your account may not view it)")
        dash = found[0]
    did = dash.get("id")
    st, body = http_json("GET", f"{base}/api/v1/dashboard/{did}/datasets", token,
                         service="Superset")
    if st != 200:
        raise denied_or_error(st, body, "Superset", f"the datasets of dashboard {did}")
    out = []
    for d in body.get("result") or []:
        db = d.get("database") or {}
        catalog = d.get("catalog") or "lakehouse"
        schema = d.get("schema")
        table = d.get("table_name")
        virtual = bool(d.get("sql"))
        out.append({
            "dataset_id": d.get("id"), "dataset": d.get("datasource_name") or table,
            "kind": "virtual (SQL)" if virtual else "physical",
            "database": db.get("database_name"),
            "table": None if virtual else f"{catalog}.{schema}.{table}",
            "sql": clip(d.get("sql"), 1000) if virtual else None,
        })
    return {"dashboard": {"id": did, "title": dash.get("dashboard_title"),
                          "slug": dash.get("slug"), "published": dash.get("published")},
            "datasets": sorted(out, key=lambda x: str(x["dataset"])),
            "source": "Superset API, as you"}


# ---------------------------------------------------------------------------- Iceberg snapshots
def table_last_snapshot(table):
    """The newest Iceberg snapshot of a table (when it last changed), through Trino as the
    user. 'schema.table' or 'lakehouse.schema.table'."""
    c, s, t = split_table(table)
    sql = (f'SELECT snapshot_id, committed_at, operation, summary[\'added-records\'], '
           f'summary[\'total-records\'] FROM {c}.{s}."{t}$snapshots" '
           f'ORDER BY committed_at DESC LIMIT 1')
    try:
        r = trino_client.run(sql, max_rows=1, guarded=False)
    except ToolFailure as e:
        if e.kind == "invalid" and ("does not exist" in e.message or "NOT_FOUND" in e.message):
            raise ToolFailure("invalid", f"{c}.{s}.{t} has no Iceberg snapshots: it does not "
                              f"exist, is a view, or you may not see it") from None
        raise
    if not r["rows"]:
        return {"table": f"{c}.{s}.{t}", "as_user": r["as_user"], "last_snapshot": None,
                "note": "the table has no snapshot yet (never written)"}
    sid, committed, op, added, total = r["rows"][0]
    return {"table": f"{c}.{s}.{t}", "as_user": r["as_user"],
            "last_snapshot": {"snapshot_id": sid, "committed_at": _iso(committed),
                              "operation": op, "added_records": added, "total_records": total},
            "source": f'Trino {c}.{s}."{t}$snapshots", as you'}


# ---------------------------------------------------------------------------- Airflow
def _airflow_token(base):
    """Airflow's API wants its own JWT. The lab_auth plugin (config/airflow) exchanges the
    user's Keycloak token for one that carries it, so every authorization decision is
    Keycloak's, for this user."""
    st, body = http_json("POST", f"{base}{AIRFLOW_TOKEN_PATH}", user_token(), body={},
                         service="Airflow")
    if st in (200, 201) and isinstance(body, dict) and body.get("access_token"):
        return body["access_token"]
    raise denied_or_error(st, body, "Airflow", "a session")


def airflow_runs(dag_id=None, limit=10, state=None):
    """Recent DAG runs the user may see (all DAGs, or one), newest first."""
    base = public_url("airflow")
    limit = max(1, min(int(limit or 10), 50))
    if dag_id is not None:
        if not isinstance(dag_id, str) or not dag_id or len(dag_id) > 250 or \
                any(ch in dag_id for ch in "/?#&%\\ "):
            raise ToolFailure("invalid", f"dag_id {dag_id!r} is not a DAG id")
    if state is not None and state not in ("queued", "running", "success", "failed"):
        raise ToolFailure("invalid", "state must be queued, running, success or failed")
    tok = _airflow_token(base)
    q = {"order_by": "-start_date", "limit": str(limit)}
    if state:
        q["state"] = state
    path = f"/api/v2/dags/{urllib.parse.quote(dag_id or '~', safe='~')}/dagRuns?" + \
        urllib.parse.urlencode(q)
    st, body = http_json("GET", base + path, tok, service="Airflow")
    if st != 200:
        raise denied_or_error(st, body, "Airflow", f"the runs of {dag_id or 'all DAGs'}")
    runs = []
    for r in (body or {}).get("dag_runs") or []:
        runs.append({k: r.get(k) for k in ("dag_id", "dag_run_id", "state", "run_type",
                                           "logical_date", "start_date", "end_date",
                                           "triggered_by")})
    return {"dag_id": dag_id, "runs": runs, "total_entries": (body or {}).get("total_entries"),
            "source": "Airflow API, as you"}


# ---------------------------------------------------------------------------- catalog
def _catalog_base():
    return (os.environ.get("LAB_CATALOG_URL") or "http://lakekeeper:8181/catalog").rstrip("/")


def catalog_list(namespace=None):
    """Namespaces of the lab catalog (Lakekeeper, as the user), or the tables and views of
    one namespace. Lakekeeper shows only what the user may see."""
    base = _catalog_base()
    token = user_token()
    wh = os.environ.get("LAB_WAREHOUSE", "lakehouse")
    st, cfg = http_json("GET", f"{base}/v1/config?warehouse={urllib.parse.quote(wh)}", token,
                        service="the catalog (Lakekeeper)")
    if st != 200:
        raise denied_or_error(st, cfg, "Lakekeeper", "the catalog config")
    prefix = ((cfg or {}).get("overrides") or {}).get("prefix") or \
        ((cfg or {}).get("defaults") or {}).get("prefix") or ""
    root = f"{base}/v1/{urllib.parse.quote(prefix, safe='')}" if prefix else f"{base}/v1"

    def pages(url, key):
        items, token_ = [], None
        for _ in range(20):
            u = url + (("&" if "?" in url else "?") + "pageToken=" + urllib.parse.quote(token_)
                       if token_ else "")
            s2, body = http_json("GET", u, token, service="Lakekeeper")
            if s2 != 200:
                raise denied_or_error(s2, body, "Lakekeeper", key)
            items += (body or {}).get(key) or []
            token_ = (body or {}).get("next-page-token")
            if not token_ or len(items) >= MAX_ROWS:
                break
        return items[:MAX_ROWS]

    if namespace is None:
        ns = pages(f"{root}/namespaces", "namespaces")
        return {"warehouse": wh, "namespaces": sorted(".".join(n) for n in ns),
                "source": "Lakekeeper (Iceberg REST), as you"}
    parts = [ident(p, "namespace") for p in str(namespace).split(".")]
    enc = urllib.parse.quote("\x1f".join(parts), safe="")
    tables = pages(f"{root}/namespaces/{enc}/tables", "identifiers")
    try:
        views = pages(f"{root}/namespaces/{enc}/views", "identifiers")
    except ToolFailure:
        views = []
    return {"warehouse": wh, "namespace": ".".join(parts),
            "tables": sorted(t["name"] for t in tables),
            "views": sorted(v["name"] for v in views),
            "source": "Lakekeeper (Iceberg REST), as you"}


# ---------------------------------------------------------------------------- current lesson
def _load_progress(home):
    try:
        with open(os.path.join(home, ".lab-progress.json"), encoding="utf-8") as f:
            p = json.load(f)
        return p if isinstance(p, dict) else {}
    except (OSError, ValueError):
        return {}


def _modules(src):
    try:
        from lakehouse import tracks
    except ImportError:
        return []
    mods, _ = tracks.discover(src)
    return mods


def current_lesson(module=None, home=None, src=None):
    """The learner's current track module (or `module`), its progress, and its tutor notes
    (tutor.md from the image's pristine copy), for tutor mode."""
    home = home or os.path.expanduser("~")
    src = src or os.environ.get("LAB_TRACKS_SRC", TRACKS_SRC)
    mods = _modules(src)
    if not mods:
        raise ToolFailure("unavailable", "no learning tracks in this workspace")
    progress = (_load_progress(home).get("modules") or {})
    chosen, why = None, None
    if module:
        want = str(module).strip().lower()
        chosen = next((m for m in mods if want in (m.id.lower(), m.dirname.lower(),
                                                   m.rel.lower())), None)
        if chosen is None:
            raise ToolFailure("invalid", f"no module {module!r}; modules: "
                              + ", ".join(m.id for m in mods))
        why = "asked for"
    else:
        env_mod = os.environ.get("LAB_CURRENT_MODULE")
        if env_mod:
            chosen = next((m for m in mods if m.id.lower() == env_mod.lower()), None)
            why = "LAB_CURRENT_MODULE"
        if chosen is None:
            touched = [(e.get("last_checked_at") or e.get("reset_at") or "", mid)
                       for mid, e in progress.items()
                       if isinstance(e, dict) and e.get("status") != "passed"]
            touched.sort(reverse=True)
            for _, mid in touched:
                chosen = next((m for m in mods if m.id == mid), None)
                if chosen:
                    why = "the module you worked on last and have not passed yet"
                    break
    if chosen is None:
        return {"module": None, "progress": {mid: e.get("status") for mid, e in progress.items()
                                             if isinstance(e, dict)},
                "note": "no module in progress: the learner has not started a track module "
                        "(or has passed every one they touched). `lab-tracks list` shows them."}
    tutor_file = os.path.join(chosen.src_dir, chosen.meta.get("tutor", "tutor.md"))
    try:
        with open(tutor_file, encoding="utf-8") as f:
            tutor = f.read()
    except OSError:
        tutor = None
    return {"module": {"id": chosen.id, "track": chosen.track, "title": chosen.title,
                       "profile": chosen.profile, "minutes": chosen.minutes,
                       "folder": f"~/tracks/{chosen.rel}"},
            "selected_because": why,
            "progress": progress.get(chosen.id, {"status": "not-started"}),
            "tutor_md_path": tutor_file, "tutor_md": clip(tutor, 20000),
            "tutor_rules": "Explain and give the smallest hint that unblocks the learner; "
                           "do not hand over the solution."}
