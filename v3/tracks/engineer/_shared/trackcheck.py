"""Shared helpers for the engineer track's checkpoints and resets.

Everything here runs as YOU, inside your workspace, with your own Keycloak token
(`lakehouse.lab_token()`): a checkpoint can only see what you can see, and a reset can only
drop what you are allowed to drop.

Names used by the whole track (one place, so lessons, checkpoints and resets agree):

  your namespace            lakehouse.eng_<you>            E1, E2 (interactive work)
  your production tables    lakehouse.analytics.u_<you>_*  E3, E4 (written by Airflow as lab-batch)
  your DAG folder           ~/airflow-dags/<you>/          E3, E4 (Airflow reads it at dags/user/<you>/)
  your DAG ids              u_<you>_*                      E3, E4 (Airflow's policy enforces it)

<you> is your login name; in table names every character other than a-z, 0-9 and _ becomes _.

Command line:
  python checkpoint.py [--json]               check a module (what `lab-tracks check` runs)
  python checkpoint.py --reset                drop the module's objects, listed in its
                                              module.json "reset" (what `lab-tracks reset` runs)
  python trackcheck.py reset <module dir>     the same drop, for a module folder
"""
import json
import os
import re
import sys
import time

TRACK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------------------ names
def username():
    """Your login name, from your token (the same name Trino and Airflow see)."""
    from lakehouse import whoami
    return whoami()


def safe_name(user):
    return re.sub(r"[^a-z0-9_]", "_", user.lower())


def namespace(user=None):
    """Your own namespace for the engineer track: eng_<you>."""
    return f"eng_{safe_name(user or username())}"


def prod_prefix(user=None):
    """Prefix of your tables in the shared `analytics` namespace: u_<you>_."""
    return f"u_{safe_name(user or username())}_"


def dag_prefix(user=None):
    """Prefix Airflow requires for your DAG ids: u_<you>_ (your login name as-is)."""
    return f"u_{user or username()}_"


def dags_dir(user=None):
    """Your DAG folder in the workspace."""
    return os.path.join(os.path.expanduser("~/airflow-dags"), user or username())


def expand(text, user=None):
    """Fill {user}, {ns}, {prod} and {dag} in a module.json string."""
    user = user or username()
    return text.format(user=user, ns=namespace(user), prod=prod_prefix(user), dag=dag_prefix(user))


# ------------------------------------------------------------------------------ Trino
class Trino:
    """A small Trino client as you (lakehouse.trino_connection: your token on every call)."""

    def __init__(self):
        from lakehouse import trino_connection
        self.conn = trino_connection(catalog="lakehouse")

    def rows(self, sql, params=None):
        cur = self.conn.cursor()
        if params is None:
            cur.execute(sql)
        else:
            cur.execute(sql, params)
        return cur.fetchall()

    def one(self, sql, params=None):
        r = self.rows(sql, params)
        return r[0][0] if r else None

    def schema_exists(self, schema):
        return bool(self.rows(
            "SELECT 1 FROM lakehouse.information_schema.schemata WHERE schema_name = ?", [schema]))

    def table_exists(self, schema, table):
        return bool(self.rows(
            "SELECT 1 FROM lakehouse.information_schema.tables "
            "WHERE table_schema = ? AND table_name = ?", [schema, table]))

    def columns(self, schema, table):
        return {c: t for c, t in self.rows(
            "SELECT column_name, data_type FROM lakehouse.information_schema.columns "
            "WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position", [schema, table])}

    def snapshots(self, schema, table):
        """[(committed_at, snapshot_id, parent_id, operation, summary)], oldest first."""
        return self.rows(
            f'SELECT committed_at, snapshot_id, parent_id, operation, summary '
            f'FROM lakehouse."{schema}"."{table}$snapshots" ORDER BY committed_at')


# ------------------------------------------------------------------------------ checkpoint
class Fail(Exception):
    """A check did not pass. `hint` tells the learner what to do next."""

    def __init__(self, message, hint=""):
        super().__init__(message)
        self.message, self.hint = message, hint


class Checkpoint:
    """Runs a module's checks in order and prints clear PASS/FAIL lines with hints.

    A check is a function that returns a short "what I saw" string, or raises Fail. Checks
    run in order and stop at the first failure (later checks usually depend on it); the rest
    are listed as not checked yet.

    Exit status: 0 all passed, 1 a check failed, 2 the checkpoint could not run (no token,
    service down). With --json the last line of output is a JSON summary for lab-tracks.
    """

    def __init__(self, module, title):
        self.module, self.title = module, title
        self.checks = []

    def check(self, name):
        def deco(fn):
            self.checks.append((name, fn))
            return fn
        return deco

    def run(self, argv=None):
        argv = sys.argv[1:] if argv is None else argv
        if "--reset" in argv:
            return self.reset()
        as_json = "--json" in argv
        results, failed, t0 = [], False, time.time()
        print(f"Checkpoint {self.module}: {self.title}")
        try:
            for name, fn in self.checks:
                if failed:
                    results.append({"name": name, "ok": None, "detail": "not checked yet"})
                    print(f"  ....  {name} (not checked yet)")
                    continue
                try:
                    detail = fn() or ""
                    results.append({"name": name, "ok": True, "detail": detail})
                    print(f"  PASS  {name}" + (f": {detail}" if detail else ""))
                except Fail as f:
                    failed = True
                    results.append({"name": name, "ok": False, "detail": f.message, "hint": f.hint})
                    print(f"  FAIL  {name}: {f.message}")
                    for line in (f.hint or "").splitlines():
                        print(f"        hint: {line}" if line.strip() else "")
        except Exception as e:  # noqa: BLE001 - cannot check (token, network): say so plainly
            msg = f"{type(e).__name__}: {e}"
            print(f"\nThe checkpoint could not run: {msg}")
            print("Is your workspace logged in (try `lab-token`) and is the lab running (`lab status`)?")
            if as_json:
                print(json.dumps({"module": self.module, "passed": False, "error": msg[:500],
                                  "checks": results}))
            return 2
        passed = not failed
        n_ok = sum(1 for r in results if r["ok"])
        print(f"\n{self.module}: {'PASSED' if passed else 'NOT YET'} "
              f"({n_ok}/{len(results)} checks, {time.time() - t0:.0f}s)")
        if as_json:
            print(json.dumps({"module": self.module, "passed": passed, "checks": results},
                             default=str))
        return 0 if passed else 1

    def reset(self):
        """`checkpoint.py --reset` (what `lab-tracks reset` calls): drop the module's objects,
        your own only, as listed in the module.json next to the checkpoint. Files in your
        module folder are lab-tracks' job (it restores them)."""
        spec_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        print(f"Reset {self.module}: dropping what this module created (your own objects only)")
        try:
            reset(spec_dir, work_dir=os.environ.get("LAB_MODULE_DIR") or spec_dir)
        except Exception as e:  # noqa: BLE001 - say what failed; lab-tracks reports the exit
            print(f"  could not drop the module's objects: {type(e).__name__}: {e}")
            return 1
        return 0


# ------------------------------------------------------------------------------ reset
TABLE_RE = re.compile(r"^lakehouse\.([a-z0-9_]+)\.([a-z0-9_]+)$")


def _allowed_table(full, user):
    """Only your own objects: tables in eng_<you>, or u_<you>_* tables in analytics."""
    m = TABLE_RE.match(full)
    if not m:
        return False
    schema, table = m.groups()
    return schema == namespace(user) or (schema == "analytics" and table.startswith(prod_prefix(user)))


def _inside(path, root):
    path, root = os.path.realpath(path), os.path.realpath(root)
    return path != root and os.path.commonpath([path, root]) == root


def reset(module_dir, user=None, log=print, work_dir=None):
    """Drop what a module created, as described in its module.json "reset" section
    (module_dir: the folder with module.json; work_dir: your copy of the module, default
    module_dir):

      tables                 lakehouse.<schema>.<table> names ({ns}, {prod} placeholders);
                             only eng_<you>.* and analytics.u_<you>_* are ever dropped
      drop_namespace_if_empty  drop eng_<you> when nothing is left in it
      dag_files              paths relative to ~/airflow-dags/<you>/ (files or folders)
      generated              paths relative to your copy of the module (files or folders)

    Tables are dropped with a plain DROP TABLE through Trino (the catalog deletes the data;
    never Spark's DROP ... PURGE). Restoring the module's pristine files is lab-tracks' job.
    Returns a list of what was done."""
    import shutil
    user = user or username()
    with open(os.path.join(module_dir, "module.json"), encoding="utf-8") as f:
        spec = json.load(f).get("reset", {})
    done = []
    tables = [expand(t, user) for t in spec.get("tables", [])]
    trino = Trino() if tables or spec.get("drop_namespace_if_empty") else None
    for full in tables:
        if not _allowed_table(full, user):
            raise ValueError(f"refusing to drop {full}: not one of your own tables")
        _, schema, table = full.split(".")
        if trino.table_exists(schema, table):
            trino.rows(f'DROP TABLE IF EXISTS lakehouse."{schema}"."{table}"')
            done.append(f"dropped table {full}")
    if spec.get("drop_namespace_if_empty"):
        ns = namespace(user)
        if trino.schema_exists(ns) and not trino.rows(
                "SELECT 1 FROM lakehouse.information_schema.tables WHERE table_schema = ?", [ns]):
            trino.rows(f'DROP SCHEMA IF EXISTS lakehouse."{ns}"')
            done.append(f"dropped empty namespace lakehouse.{ns}")
    roots = [(dags_dir(user), spec.get("dag_files", [])),
             (work_dir or module_dir, spec.get("generated", []))]
    for root, rels in roots:
        for rel in rels:
            p = os.path.join(root, expand(rel, user))
            if not _inside(p, root):
                raise ValueError(f"refusing to delete {p}: outside {root}")
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p)
                done.append(f"deleted folder {p}")
            elif os.path.lexists(p):
                os.remove(p)
                done.append(f"deleted {p}")
    for line in done or ["nothing to drop"]:
        log(f"  {line}")
    return done


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "reset":
        reset(os.path.abspath(sys.argv[2]))
        sys.exit(0)
    else:
        print(__doc__)
        sys.exit(2)
