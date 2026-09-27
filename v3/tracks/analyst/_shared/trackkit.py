"""Small helpers shared by the analyst track's checkpoints (not a lesson; you can ignore it).

A checkpoint checks OUTCOMES, never your files: the tables in your own schema, the rows in
them, your dbt model's tests, your Superset chart. Everything runs AS YOU, with your own
login token (lakehouse.lab_token()), so it can see exactly what you can see and nothing more.

Checkpoint interface (what `lab-tracks check` / `lab-tracks reset` call):

  python3 checkpoint.py            run the checks, print PASS/FAIL lines with hints
                                   exit 0 = passed, 1 = not yet, 2 = could not run
  python3 checkpoint.py --json     same, plus one last line: LAB_TRACKS_RESULT {json}
  python3 checkpoint.py --reset    drop what this module created, in YOUR schema only

Your schema is lakehouse.dbt_<your user name>: the one schema an analyst can write to (the
lab's Trino rules give each member of `analyst` that one schema; dbt's starter profile writes
there too). superset_api.py (next to this file) is the same idea for Superset (A4).
"""
import json
import os
import re
import sys
import traceback

RESULT_MARKER = "LAB_TRACKS_RESULT "


class CheckError(Exception):
    """A check could not run (the lab is unreachable, you are logged out, ...)."""


# ------------------------------------------------------------------ who and where
def whoami():
    import lakehouse
    return lakehouse.whoami()


def user_schema(user=None):
    """Your own schema. dbt (profiles.yml in the starter project) writes to the same one."""
    return f"dbt_{(user or whoami()).lower()}"


def groups():
    import lakehouse
    return lakehouse.token_claims(lakehouse.lab_token()).get("groups") or []


def public_url(svc):
    """https://<svc>.<LAB_DOMAIN>[:port]. The port suffix comes from LAB_AUTH_URL, the one
    derived public origin (never rebuilt from the port number)."""
    override = os.environ.get(f"LAB_{svc.upper()}_URL")
    if override:
        return override.rstrip("/")
    domain = os.environ.get("LAB_DOMAIN")
    auth = (os.environ.get("LAB_AUTH_URL") or "").rstrip("/")
    prefix = f"https://auth.{domain}"
    if not domain or not auth.startswith(prefix):
        raise CheckError("LAB_DOMAIN / LAB_AUTH_URL are not set: run this inside your lab workspace")
    return f"https://{svc}.{domain}{auth[len(prefix):]}"


# ------------------------------------------------------------------ Trino
_conn = None


def trino():
    global _conn
    if _conn is None:
        import lakehouse
        _conn = lakehouse.trino_connection()
    return _conn


def query(sql, params=None):
    cur = trino().cursor()
    cur.execute(sql, params) if params is not None else cur.execute(sql)
    rows = cur.fetchall()
    cols = [d[0] for d in (cur.description or [])]
    return cols, rows


def table_type(schema, table):
    """'BASE TABLE', 'VIEW' or None."""
    _, rows = query(
        "SELECT table_type FROM lakehouse.information_schema.tables "
        "WHERE table_schema = ? AND table_name = ?", [schema, table])
    return rows[0][0] if rows else None


def columns(schema, table):
    """[(name, type)] in table order."""
    _, rows = query(
        "SELECT column_name, data_type FROM lakehouse.information_schema.columns "
        "WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position", [schema, table])
    return [(r[0], r[1]) for r in rows]


def schema_exists(schema):
    _, rows = query("SELECT 1 FROM lakehouse.information_schema.schemata WHERE schema_name = ?",
                    [schema])
    return bool(rows)


_IDENT = re.compile(r"^[a-z0-9_][a-z0-9_.@-]*$")


def quote(ident):
    if not _IDENT.match(ident):
        raise CheckError(f"unexpected identifier {ident!r}")
    return '"' + ident.replace('"', '""') + '"'


def drop_own(table, schema=None):
    """Drop a table or view in YOUR schema (never anywhere else). Returns what was dropped."""
    mine = user_schema()
    schema = schema or mine
    if schema != mine:
        raise CheckError(f"refusing to drop outside your schema {mine}: {schema}.{table}")
    kind = table_type(schema, table)
    if kind is None:
        return None
    what = "VIEW" if kind == "VIEW" else "TABLE"
    query(f"DROP {what} lakehouse.{quote(schema)}.{quote(table)}")
    return f"{what.lower()} lakehouse.{schema}.{table}"


def module_dir():
    """The learner's copy of the module (lab-tracks sets LAB_MODULE_DIR); when a learner runs
    `python3 checkpoint.py` by hand, the folder the script is in."""
    d = os.environ.get("LAB_MODULE_DIR")
    if d and os.path.isdir(d):
        return d
    main = sys.modules.get("__main__")
    f = getattr(main, "__file__", None)
    return os.path.dirname(os.path.abspath(f)) if f else os.getcwd()


def close_enough(a, b, tol=0.01):
    try:
        return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(b)))
    except (TypeError, ValueError):
        return a == b


# ------------------------------------------------------------------ the runner
class Checkpoint:
    """Collects checks and prints them for a beginner:

        [PASS] what was checked
        [FAIL] what was checked
               why: what we found
               hint: what to try next
    """

    def __init__(self, module, title):
        self.module, self.title = module, title
        self.results = []

    def check(self, name, ok, found="", hint=""):
        self.results.append({"name": name, "ok": bool(ok), "detail": found,
                             "hint": "" if ok else hint})
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        if not ok:
            if found:
                print(f"         why:  {found}")
            if hint:
                print(f"         hint: {hint}")
        return bool(ok)

    def run(self, checks, reset=None, argv=None):
        """checks(ck): run every check through ck.check(...); may stop early by returning.
        reset(): drop the module's objects; returns a list of what it removed."""
        argv = sys.argv[1:] if argv is None else argv
        as_json = "--json" in argv
        if "--reset" in argv:
            return self._reset(reset, as_json)
        print(f"{self.module} {self.title}: checkpoint")
        rc = 0
        try:
            checks(self)
            passed = bool(self.results) and all(r["ok"] for r in self.results)
            rc = 0 if passed else 1
        except CheckError as e:
            print(f"  [ERROR] {e}")
            self.results.append({"name": "run", "ok": False, "detail": str(e), "hint": ""})
            rc = 2
        except Exception as e:  # noqa: BLE001 - explain, never a bare traceback
            msg = f"{type(e).__name__}: {e}"
            print(f"  [ERROR] the checkpoint could not finish: {msg[:400]}")
            if "LabTokenError" in msg or "401" in msg:
                print("         hint: your login may have expired: in JupyterLab use "
                      "File > Log Out, log in again, and re-run the check.")
            if os.environ.get("LAB_TRACKS_DEBUG"):
                traceback.print_exc()
            self.results.append({"name": "run", "ok": False, "detail": msg[:400], "hint": ""})
            rc = 2
        n_ok = sum(r["ok"] for r in self.results)
        verdict = {0: "PASS", 1: "NOT YET", 2: "ERROR"}[rc]
        print(f"RESULT: {verdict} ({n_ok}/{len(self.results)} checks passed)")
        if rc == 1:
            print("Fix the first [FAIL] above, then run the check again. The lesson's "
                  "'Common mistakes' section covers most of them.")
        if as_json:
            print(RESULT_MARKER + json.dumps({"module": self.module, "passed": rc == 0,
                                              "status": verdict.lower().replace(" ", "_"),
                                              "checks": self.results}))
        return rc

    def _reset(self, reset, as_json):
        removed, rc, err = [], 0, None
        try:
            removed = [r for r in (reset() if reset else []) if r]
        except Exception as e:  # noqa: BLE001
            rc, err = 2, f"{type(e).__name__}: {e}"[:400]
        if err:
            print(f"{self.module} reset FAILED: {err}")
        else:
            print(f"{self.module} reset: " + (", ".join(removed) if removed else "nothing to remove"))
        if as_json:
            print(RESULT_MARKER + json.dumps({"module": self.module, "reset": rc == 0,
                                              "removed": removed, "error": err}))
        return rc
