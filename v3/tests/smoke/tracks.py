"""Smoke check 17 (CONTRACT Phase 4, exit 1): every selected learning-track module's reference
solution passes its checkpoint AS A SEEDED USER, INSIDE THAT USER'S WORKSPACE, and
`lab-tracks reset` brings the module back to its start state.

Per module, as its `test_user`, through the user's own Jupyter kernel (workspace.Workspace:
headless login, spawn, REST API + kernel websocket; the same path as a learner):

  1. `lab-tracks reset <ID> --yes --json`   clean start; files pristine; check exits 1
  2. upload v3/tests/tracks/solutions/<track>/<module>/ to ~/.lab-solutions/<module>/ (and
     the track's shared helper folders solutions/<track>/_*/ to ~/.lab-solutions/_*/)
     and run solve.py there (cwd and argv[1]: ~/tracks/<track>/<module>)  -> exit 0
  3. `lab-tracks check <ID> --json`         -> exit 0 (passed)
  4. `lab-tracks reset <ID> --yes --json`   -> exit 0; files pristine; check exits 1 again
  5. ~/.lab-solutions/ removed

Modules whose solution has Airflow DAGs (module.json `solution.trigger_dags`, e.g. E3/E4):
solve.py runs with `--no-wait`, and the harness, logged into Airflow as the test user, waits
for a run of each DAG queued after the solve started. A new @daily DAG gets one on its own
(fresh install); on a re-run the same day it does not (today's interval already ran), so
after a grace period the harness presses Trigger as the user, like the lesson does. It then
waits for that run to succeed (step `dag_runs`).

The module interface is documented in v3/tracks/README.md. run.sh mounts v3/tracks at
/opt/tracks and v3/tests/tracks at /opt/tracks-tests (read-only).

Selection, LAB_SMOKE_TRACKS: `first` (default; module 1 of each track, the PR matrix), `all`
(nightly), `none`, or ids (`E1,A3`). A module whose profile the lab's profile does not include
is skipped with its reason; the check is [SKIP] when nothing is left to run.
"""
import base64
import io
import json
import os
import re
import tarfile
import time
import traceback

C17 = "17.tracks_solution_checkpoint_reset"
TRACKS_DIR = os.environ.get("LAB_TRACKS_DIR", "/opt/tracks")
SOLUTIONS_DIR = os.environ.get("LAB_TRACKS_SOLUTIONS", "/opt/tracks-tests/solutions")
PROFILES = ("core", "engineer", "full")
DEFAULT_TEST_USERS = {"engineer": "eddie", "analyst": "anna", "lab-admin": "alice",
                      "viewer": "victor"}
MARK = "SMOKE_TRACKS_RESULT "
REMOTE_SOLUTIONS = "~/.lab-solutions"


# ---------------------------------------------------------------- plan (pure; unit-tested)
def load_modules(root=TRACKS_DIR):
    """[{id, track, dir, rel, profile, groups, test_user, order, timeout_s, browser_logins}]
    sorted per track. Mirrors lakehouse/tracks.py discover() without the workspace image."""
    mods = []
    if not os.path.isdir(root):
        return mods
    for track in sorted(os.listdir(root)):
        tdir = os.path.join(root, track)
        if not os.path.isdir(tdir) or track.startswith((".", "_")):
            continue
        for d in sorted(os.listdir(tdir)):
            mj = os.path.join(tdir, d, "module.json")
            if not os.path.isfile(mj):
                continue
            with open(mj, encoding="utf-8") as f:
                meta = json.load(f)
            sol = meta.get("solution") or {}
            groups = meta.get("groups") or []
            user = meta.get("test_user") or next(
                (DEFAULT_TEST_USERS[g] for g in groups if g in DEFAULT_TEST_USERS), None)
            m = re.match(r"^[A-Za-z]*(\d+)", str(meta.get("id", "")))
            order = meta.get("order") if isinstance(meta.get("order"), int) else (int(m.group(1)) if m else 0)
            mods.append({"id": str(meta.get("id")), "track": track, "dir": d, "rel": f"{track}/{d}",
                         "profile": meta.get("profile", "core"), "groups": groups,
                         "test_user": user, "order": order,
                         "timeout_s": int(sol.get("timeout_s", 900)),
                         "browser_logins": list(sol.get("browser_logins", [])),
                         "trigger_dags": [str(x) for x in sol.get("trigger_dags", [])]})
    return sorted(mods, key=lambda x: (x["track"], x["order"], x["id"]))


def profile_includes(have, need):
    try:
        return PROFILES.index(have) >= PROFILES.index(need)
    except ValueError:
        return False


def select(mods, spec, profile, solutions_dir=SOLUTIONS_DIR):
    """-> [(module, None | reason to skip)] for LAB_SMOKE_TRACKS=spec."""
    spec = (spec or "first").strip()
    if spec.lower() == "none":
        return []
    if spec.lower() == "first":
        firsts, seen = [], set()
        for m in mods:
            if m["track"] not in seen:
                seen.add(m["track"])
                firsts.append(m)
        chosen = firsts
    elif spec.lower() == "all":
        chosen = list(mods)
    else:
        want = [x.strip().lower() for x in spec.split(",") if x.strip()]
        chosen = [m for m in mods if m["id"].lower() in want or m["dir"].lower() in want]
    out = []
    for m in chosen:
        reason = None
        if not profile_includes(profile, m["profile"]):
            reason = f"needs profile {m['profile']} (lab is {profile})"
        elif not m["test_user"]:
            reason = "no test_user and no known group in module.json"
        elif not os.path.isfile(os.path.join(solutions_dir, m["rel"], "solve.py")):
            reason = f"no reference solution {m['rel']}/solve.py"
        out.append((m, reason))
    return out


def module_ok(steps):
    """The pass rule for one module, from its step results."""
    def rc(name):
        return (steps.get(name) or {}).get("rc")

    def js(name):
        return (steps.get(name) or {}).get("json") or {}
    if "dag_runs" in steps and rc("dag_runs") != 0:
        return False
    return (rc("reset_before") == 0 and js("reset_before").get("pristine") is True
            and rc("check_start") == 1
            and rc("solve") == 0
            and rc("check_solved") == 0 and js("check_solved").get("passed") is True
            and rc("reset_after") == 0 and js("reset_after").get("pristine") is True
            and rc("check_after_reset") == 1)


def shared_solution_dirs(track, solutions_dir=None):
    """Folders of shared solution helpers of a track: solutions/<track>/_*/ (e.g. _lib)."""
    d = os.path.join(solutions_dir or SOLUTIONS_DIR, track)
    if not os.path.isdir(d):
        return []
    return sorted(x for x in os.listdir(d) if x.startswith("_") and x != "__pycache__"
                  and os.path.isdir(os.path.join(d, x)))


# ---------------------------------------------------------------- kernel code
def tar_b64(src):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        t.add(src, arcname=".", filter=lambda ti: None if any(
            p in ("__pycache__", ".ipynb_checkpoints") for p in ti.name.split("/")) else ti)
    return base64.b64encode(buf.getvalue()).decode()


def upload_code(b64, dest):
    return f"""
import base64, io, json, os, shutil, tarfile
d = os.path.expanduser({dest!r})
shutil.rmtree(d, ignore_errors=True)
os.makedirs(d)
with tarfile.open(fileobj=io.BytesIO(base64.b64decode({b64!r})), mode="r:gz") as t:
    t.extractall(d, filter="data")
print({MARK!r} + json.dumps({{"rc": 0, "files": sum(len(f) for _, _, f in os.walk(d))}}))
"""


def command_code(argv, cwd, env, timeout):
    """Kernel code: run argv (~ expanded) as a subprocess of the user's kernel, i.e. as the
    user with the workspace's environment, and report rc, output tails and the last JSON line."""
    return f"""
import json, os, subprocess, sys, time
argv = [os.path.expanduser(a) if a.startswith("~") else a for a in {argv!r}]
argv = [sys.executable if a == "@python" else a for a in argv]
cwd = os.path.expanduser({cwd!r})
env = dict(os.environ, **{{k: os.path.expanduser(v) for k, v in {env!r}.items()}})
t0 = time.time()
try:
    r = subprocess.run(argv, cwd=cwd if os.path.isdir(cwd) else os.path.expanduser("~"),
                       env=env, capture_output=True, text=True, timeout={timeout})
    out = {{"rc": r.returncode, "stdout": r.stdout[-5000:], "stderr": r.stderr[-2500:]}}
except subprocess.TimeoutExpired as e:
    out = {{"rc": "timeout", "stdout": str(e.stdout or "")[-3000:], "stderr": str(e.stderr or "")[-1500:]}}
out["seconds"] = round(time.time() - t0, 1)
js = None
for line in reversed(out["stdout"].splitlines()):
    s = line.strip()
    if s.startswith("{{") and s.endswith("}}"):
        try:
            js = json.loads(s); break
        except ValueError:
            pass
out["json"] = js
print({MARK!r} + json.dumps(out))
"""


def _scrub(text):
    return re.sub(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "<jwt>", text or "")


def kernel(ws, code, timeout):
    raw = ws.run(code, timeout + 60)
    for line in reversed((raw.get("stdout") or "").splitlines()):
        if line.startswith(MARK):
            return json.loads(line[len(MARK):])
    return {"rc": "no-result", "kernel": {k: _scrub(str(v))[-1500:] for k, v in raw.items()}}


# ---------------------------------------------------------------- Airflow runs (E3/E4)
def dag_ids(m, user):
    """module.json solution.trigger_dags with {dag} = the user's DAG id prefix u_<user>_."""
    return [d.format(dag=f"u_{user}_", user=user) for d in m.get("trigger_dags", [])]


def _iso_epoch(v):
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def run_since(runs, since):
    """The newest run queued at or after `since` (epoch seconds), or None."""
    fresh = [(_iso_epoch(r.get("queued_at") or r.get("run_after")), r) for r in runs]
    fresh = [(t, r) for t, r in fresh if t is not None and t >= since - 1]
    return max(fresh, key=lambda x: x[0])[1] if fresh else None


def ensure_dag_runs(af, dags, since, timeout, grace=90, every=10):
    """For each DAG: wait until Airflow has parsed it, take a run queued after `since`, or
    trigger one as the user after `grace` seconds without one, and wait for it to finish.
    -> {"rc": 0 | 1, "seconds", "dags": {dag: evidence}}."""
    t0 = time.time()
    deadline = t0 + timeout
    out = {}
    for dag in dags:
        ev = out.setdefault(dag, {})
        while True:                                     # 1. parsed (and not stale)
            r = af.api("GET", f"/dags/{dag}")
            info = (r.json() if r.status == 200 else None) or {}
            if r.status == 200 and not info.get("is_stale"):
                break
            if time.time() > deadline:
                ev["error"] = f"DAG not in Airflow after {timeout}s (HTTP {r.status}, is_stale={info.get('is_stale')})"
                break
            time.sleep(every)
        if "error" in ev:
            continue
        seen = time.time()
        run = None
        while time.time() < deadline:                   # 2. a run of its own, or Trigger
            r = af.api("GET", f"/dags/{dag}/dagRuns?limit=100")
            run = run_since(((r.json() if r.status == 200 else None) or {}).get("dag_runs", []), since)
            if run or time.time() - seen > grace:
                break
            time.sleep(every)
        if run is None:
            status, run = af.trigger(dag)
            ev["triggered"] = status
            if status not in (200, 201):
                ev["error"] = f"trigger HTTP {status}: {str(run)[:300]}"
                continue
        ev["run_id"], ev["run_type"] = run.get("dag_run_id"), run.get("run_type")
        ev.update(af.wait_run(dag, run["dag_run_id"], max(60, deadline - time.time())))
    ok = bool(dags) and all(e.get("state") == "success" for e in out.values())
    return {"rc": 0 if ok else 1, "seconds": round(time.time() - t0, 1), "dags": out}


# ---------------------------------------------------------------- one module
def run_module(ws, m, log, airflow=None):
    home = f"~/tracks/{m['rel']}"
    sol = f"{REMOTE_SOLUTIONS}/{m['dir']}"
    env = {"LAB_SOLUTION_DIR": sol, "LAB_MODULE_DIR": home, "LAB_MODULE_ID": m["id"],
           "LAB_MODULE_SRC": f"/opt/lakehouse/tracks/{m['rel']}", "LAB_TRACKS_HOME": "~/tracks"}
    t = m["timeout_s"]
    plan = [
        ("reset_before", ["lab-tracks", "reset", m["id"], "--yes", "--json"], 900),
        ("check_start", ["lab-tracks", "check", m["id"], "--json"], 900),
        ("upload", None, 300),
        ("solve", ["@python", f"{sol}/solve.py", home], t),
        ("check_solved", ["lab-tracks", "check", m["id"], "--json"], 900),
        ("reset_after", ["lab-tracks", "reset", m["id"], "--yes", "--json"], 900),
        ("check_after_reset", ["lab-tracks", "check", m["id"], "--json"], 900),
    ]
    steps = {}
    dags = dag_ids(m, m["test_user"]) if airflow is not None else []
    if dags:                                       # the harness waits for (or starts) the runs
        plan[3] = ("solve", plan[3][1] + ["--no-wait"], t)
    since = None
    for name, argv, timeout in plan:
        if name == "solve":
            since = time.time()
        if name == "upload":
            r = kernel(ws, upload_code(tar_b64(os.path.join(SOLUTIONS_DIR, m["rel"])), sol), timeout)
            # The track's shared solution helpers (solutions/<track>/_lib/ ...) go next to it,
            # so `../_lib` from solve.py resolves the same way as in the repository.
            for helper in shared_solution_dirs(m["track"]):
                h = kernel(ws, upload_code(tar_b64(os.path.join(SOLUTIONS_DIR, m["track"], helper)),
                                           f"{REMOTE_SOLUTIONS}/{helper}"), timeout)
                if h.get("rc") != 0:
                    r = dict(h, helper=helper)
        else:
            r = kernel(ws, command_code(argv, home, env, timeout), timeout)
        steps[name] = r
        log(f"[info] 17 {m['id']} {name:<17} rc={r.get('rc')} ({r.get('seconds', '-')}s)")
        if name == "solve" and r.get("rc") != 0:
            break                                  # nothing further can pass; reset below
        if name == "solve" and dags:
            r = steps["dag_runs"] = ensure_dag_runs(airflow, dags, since, t)
            log(f"[info] 17 {m['id']} {'dag_runs':<17} rc={r['rc']} ({r['seconds']}s) "
                f"{json.dumps(r['dags'], default=str)[:400]}")
            if r["rc"] != 0:
                break
    if "reset_after" not in steps:                 # leave the user's home clean anyway
        steps["reset_after"] = kernel(ws, command_code(
            ["lab-tracks", "reset", m["id"], "--yes", "--json"], home, env, 900), 900)
    kernel(ws, command_code(["rm", "-rf", REMOTE_SOLUTIONS], "~", {}, 60), 60)
    ok = module_ok(steps)
    ev = {"ok": ok, "user": m["test_user"]}
    for name, r in steps.items():
        e = {"rc": r.get("rc"), "s": r.get("seconds")}
        js = r.get("json") or {}
        if name.startswith("check"):
            e["passed"] = js.get("passed")
        if name.startswith("reset"):
            e["pristine"] = js.get("pristine")
        if name == "dag_runs":
            e["dags"] = r.get("dags")
        if not ok:
            e["stdout_tail"] = _scrub(r.get("stdout", ""))[-1500:]
            e["stderr_tail"] = _scrub(r.get("stderr", ""))[-800:]
            if "kernel" in r:
                e["kernel"] = r["kernel"]
        ev[name] = e
    return ok, ev


# ---------------------------------------------------------------- check 17
def browser_login(S, browser, user, app):
    import phase3
    sess = phase3.UserSession(S, browser, user)
    try:
        if app == "superset":
            return phase3.Superset(S, sess).login()[0]
        if app == "airflow":
            return phase3.Airflow(S, sess).login()[0]
        return f"unknown app {app}"
    finally:
        sess.close()


def check_tracks(S):
    spec = os.environ.get("LAB_SMOKE_TRACKS", "first")
    if not os.path.isdir(TRACKS_DIR):
        S.check(C17, False, f"{TRACKS_DIR} is not mounted (tests/smoke/run.sh mounts v3/tracks)")
        return
    mods = load_modules()
    if not mods:
        S.skip(C17, "no modules in v3/tracks yet")
        return
    chosen = select(mods, spec, S.PROFILE)
    runnable = [m for m, why in chosen if why is None]
    ev = {"selection": spec, "skipped": {m["id"]: why for m, why in chosen if why}}
    if not runnable:
        S.skip(C17, f"nothing to run for LAB_SMOKE_TRACKS={spec} on profile {S.PROFILE}: "
                    f"{ev['skipped'] or 'no module selected'}")
        return
    from playwright.sync_api import sync_playwright

    from workspace import Workspace
    by_user = {}
    for m in runnable:
        by_user.setdefault(m["test_user"], []).append(m)
    ok_all = True
    with sync_playwright() as pw:
        browser = S._workspace_browser(pw)
        try:
            for user, ms in by_user.items():
                for app in sorted({a for m in ms for a in m["browser_logins"]}):
                    try:
                        ev.setdefault("browser_logins", {})[f"{user}:{app}"] = \
                            browser_login(S, browser, user, app)
                    except Exception as e:  # noqa: BLE001 - recorded; the module will fail
                        ev.setdefault("browser_logins", {})[f"{user}:{app}"] = f"{type(e).__name__}: {e}"[:300]
                ws = Workspace(browser, S.url, S.D, user, S.PW)
                airflow = af_sess = None
                try:
                    login = ws.login_and_spawn()
                    ev[f"spawn_{user}"] = {k: login.get(k) for k in ("ok", "seconds", "hub_error")}
                    if not login["ok"]:
                        ok_all = False
                        for m in ms:
                            ev[m["id"]] = {"ok": False, "error": f"{user}'s workspace did not start"}
                        continue
                    if any(m["trigger_dags"] for m in ms):
                        import phase3
                        af_sess = phase3.UserSession(S, browser, user)
                        airflow = phase3.Airflow(S, af_sess)
                        try:
                            ev[f"airflow_login_{user}"] = airflow.login()[0]
                        except Exception as e:  # noqa: BLE001 - recorded; dag_runs then fails
                            ev[f"airflow_login_{user}"] = f"{type(e).__name__}: {e}"[:300]
                    for m in ms:
                        t0 = time.time()
                        try:
                            ok, mev = run_module(ws, m, lambda s: print(s, flush=True), airflow)
                        except Exception as e:  # noqa: BLE001 - one module never hides the next
                            traceback.print_exc()
                            ok, mev = False, {"ok": False, "error": f"{type(e).__name__}: {e}"[:500]}
                        mev["seconds"] = round(time.time() - t0, 1)
                        ev[m["id"]] = mev
                        ok_all &= ok
                finally:
                    if af_sess is not None:
                        af_sess.close()
                    print(f"[info] 17 {user}'s workspace stopped: {ws.stop_server()}", flush=True)
                    ws.close()
        finally:
            browser.close()
    S.check(C17, ok_all, ev)
