"""`lab-tracks`: the learning tracks in your workspace (CONTRACT Phase 4, "Workspace tooling").

    lab-tracks list               modules, what they need, and your progress
    lab-tracks check <module>     run the module's checkpoint as you; clear pass/fail hints
    lab-tracks reset <module>     start the module again: pristine files, and the module's
                                  objects in YOUR OWN schema/namespace and DAG folder dropped
    lab-tracks status <module>    which of your module files differ from the original
    lab-tracks sync               copy lessons that are new in this image into ~/tracks

Where things are (the interface is documented in v3/tracks/README.md):

  /opt/lakehouse/tracks/<track>/<module>/   the pristine lessons in the image (read-only)
  ~/tracks/<track>/<module>/                your copy: edit freely
  ~/.lab-progress.json                      your progress
  ~/.lakehouse/tracks-manifest.json         what was copied into ~/tracks, and its hash
  ~/.lakehouse/tracks-backup/               your files, saved by `reset` before it restores

Copy-on-upgrade (`sync`, run at every workspace start): a file the image has and ~/tracks
never had is copied in; a file you deleted is not brought back; a file you edited is never
overwritten; a file you did not edit is updated when a newer image changes it.

A checkpoint is the module's `checkpoint.py`, always run from the pristine image copy (so an
accidental edit in your copy cannot break it), as you (your own token), with the current
directory set to your copy of the module. It checks outcomes (tables, rows, snapshots, DAG
runs, dbt models, Superset objects), never file contents.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

RESULT_PREFIX = "LAB_TRACKS_RESULT "
SKIP_NAMES = {"__pycache__", ".ipynb_checkpoints", ".DS_Store", ".git"}
PROFILES = ("core", "engineer", "full")          # each includes the ones before it
DEFAULT_TEST_USERS = {"engineer": "eddie", "analyst": "anna", "lab-admin": "alice",
                      "viewer": "victor"}
REQUIRED_KEYS = ("id", "track", "title", "profile", "groups")


# ---------------------------------------------------------------------------- paths
def src_root():
    return os.environ.get("LAB_TRACKS_SRC", "/opt/lakehouse/tracks")


def home():
    return os.path.expanduser("~")


def tracks_home():
    return os.environ.get("LAB_TRACKS_HOME") or os.path.join(home(), "tracks")


def state_dir():
    return os.path.join(home(), ".lakehouse")


def manifest_path():
    return os.path.join(state_dir(), "tracks-manifest.json")


def progress_path():
    return os.path.join(home(), ".lab-progress.json")


def backup_root():
    return os.path.join(state_dir(), "tracks-backup")


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pretty(path):
    h = home()
    return "~" + path[len(h):] if path == h or path.startswith(h + os.sep) else path


# ---------------------------------------------------------------------------- json files
def _load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, type(default)) else default
    except (OSError, ValueError):
        return default


def _save_json(path, data):
    """Atomic write (a crash never leaves half a file)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_files(root):
    """Relative paths of the regular files under root, sorted, skipping caches."""
    out = []
    if not os.path.isdir(root):
        return out
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_NAMES)
        for name in sorted(files):
            if name in SKIP_NAMES or name.endswith(".pyc"):
                continue
            p = os.path.join(d, name)
            if os.path.isfile(p) and not os.path.islink(p):
                out.append(os.path.relpath(p, root))
    return out


# ---------------------------------------------------------------------------- modules
class Module:
    def __init__(self, meta, src_dir, rel):
        self.meta = meta
        self.src_dir = src_dir          # pristine copy in the image
        self.rel = rel                  # <track>/<module dir>
        self.id = str(meta["id"])
        self.track = meta["track"]
        self.title = meta["title"]
        self.profile = meta["profile"]
        self.groups = list(meta["groups"])
        self.minutes = meta.get("minutes")
        self.order = meta.get("order")

    @property
    def dirname(self):
        return os.path.basename(self.rel)

    @property
    def home_dir(self):
        return os.path.join(tracks_home(), self.rel)

    @property
    def checkpoint(self):
        return os.path.join(self.src_dir, self.meta.get("checkpoint", "checkpoint.py"))

    @property
    def test_user(self):
        u = self.meta.get("test_user")
        if u:
            return u
        for g in self.groups:
            if g in DEFAULT_TEST_USERS:
                return DEFAULT_TEST_USERS[g]
        return None

    def sort_key(self):
        m = re.match(r"^([A-Za-z]*)(\d+)", self.id)
        n = int(m.group(2)) if m else 0
        return (self.track, self.order if isinstance(self.order, int) else n, self.id)


def validate_meta(meta, track_dir_name):
    """-> list of problems with a module.json (empty = fine). Shared with tools/check_tracks.py."""
    probs = []
    if not isinstance(meta, dict):
        return ["module.json is not a JSON object"]
    for k in REQUIRED_KEYS:
        if k not in meta:
            probs.append(f"missing key {k!r}")
    if meta.get("track") not in (None, track_dir_name):
        probs.append(f"track {meta.get('track')!r} does not match its folder {track_dir_name!r}")
    if "profile" in meta and meta["profile"] not in PROFILES:
        probs.append(f"profile {meta['profile']!r} is not one of {', '.join(PROFILES)}")
    if "groups" in meta and (not isinstance(meta["groups"], list) or not meta["groups"]):
        probs.append("groups must be a non-empty list of Keycloak groups")
    if "id" in meta and not re.match(r"^[A-Za-z][A-Za-z0-9_-]*$", str(meta["id"])):
        probs.append(f"id {meta['id']!r}: use letters, digits, - and _ only (e.g. E1)")
    return probs


def discover(root=None):
    """-> (modules sorted per track, problems). A module is a folder <track>/<dir>/ with a
    module.json; anything else (README.md, _shared/, ...) is content, not a module."""
    root = root or src_root()
    mods, problems = [], []
    if not os.path.isdir(root):
        return mods, [f"no tracks in this image ({root} is missing)"]
    for track in sorted(os.listdir(root)):
        tdir = os.path.join(root, track)
        if not os.path.isdir(tdir) or track.startswith((".", "_")):
            continue
        for d in sorted(os.listdir(tdir)):
            mdir = os.path.join(tdir, d)
            mj = os.path.join(mdir, "module.json")
            if not os.path.isfile(mj):
                continue
            try:
                with open(mj, encoding="utf-8") as f:
                    meta = json.load(f)
            except (OSError, ValueError) as e:
                problems.append(f"{track}/{d}/module.json: {e}")
                continue
            p = validate_meta(meta, track)
            if p:
                problems.append(f"{track}/{d}/module.json: " + "; ".join(p))
                continue
            mods.append(Module(meta, mdir, f"{track}/{d}"))
    seen = {}
    for m in mods:
        if m.id.lower() in seen:
            problems.append(f"module id {m.id} is used twice ({seen[m.id.lower()]}, {m.rel})")
        seen[m.id.lower()] = m.rel
    return sorted(mods, key=Module.sort_key), problems


def find(mods, name):
    """By id (E1, e1) or folder name (E1-files-to-iceberg)."""
    n = name.strip().rstrip("/").lower()
    for m in mods:
        if n in (m.id.lower(), m.dirname.lower(), m.rel.lower()):
            return m
    return None


def profile_includes(have, need):
    try:
        return PROFILES.index(have) >= PROFILES.index(need)
    except ValueError:
        return False


# ---------------------------------------------------------------------------- sync (copy-on-upgrade)
def sync(quiet=False, root=None):
    """Copy the image's tracks into ~/tracks without ever overwriting an edit (see module doc).
    -> counts. Safe to run at every start; a failure here must never stop the workspace."""
    root = root or src_root()
    dest_root = tracks_home()
    man = _load_json(manifest_path(), {})
    files = man.setdefault("files", {})
    counts = {"added": 0, "updated": 0, "kept_edited": 0, "kept_deleted": 0, "unchanged": 0}
    for rel in iter_files(root):
        src = os.path.join(root, rel)
        dest = os.path.join(dest_root, rel)
        h = sha256(src)
        entry = files.get(rel)
        if entry is None:
            if not os.path.lexists(dest):
                _copy(src, dest)
                counts["added"] += 1
            else:
                counts["kept_edited"] += 1       # already there (restored home?): keep it
            files[rel] = {"sha256": h}
            continue
        if not os.path.lexists(dest):
            counts["kept_deleted"] += 1          # the learner deleted it: do not bring it back
            continue
        if entry.get("sha256") == h:
            counts["unchanged"] += 1
            continue
        if os.path.isfile(dest) and sha256(dest) == entry.get("sha256"):
            _copy(src, dest)                      # unedited, and the image has a newer version
            files[rel] = {"sha256": h}
            counts["updated"] += 1
        else:
            entry["newer_in_image"] = True        # edited: keep; `reset` gets the new version
            counts["kept_edited"] += 1
    man["synced_at"] = now_iso()
    _save_json(manifest_path(), man)
    if not quiet:
        print("lab-tracks sync: " + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in counts.items()))
    return counts


def _copy(src, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copyfile(src, dest)
    if os.access(src, os.X_OK):
        os.chmod(dest, 0o755)


# ---------------------------------------------------------------------------- progress
def load_progress():
    p = _load_json(progress_path(), {})
    p.setdefault("version", 1)
    p.setdefault("modules", {})
    return p


def record(mod, **fields):
    p = load_progress()
    e = p["modules"].setdefault(mod.id, {"track": mod.track, "status": "not-started"})
    e.update(fields)
    _save_json(progress_path(), p)
    return e


# ---------------------------------------------------------------------------- file state
def file_state(mod):
    """Differences between your copy and the pristine module files."""
    pristine = set(iter_files(mod.src_dir))
    mine = set(iter_files(mod.home_dir))
    modified = sorted(r for r in pristine & mine
                      if sha256(os.path.join(mod.src_dir, r)) != sha256(os.path.join(mod.home_dir, r)))
    return {"module": mod.id, "dir": _pretty(mod.home_dir), "modified": modified,
            "missing": sorted(pristine - mine), "extra": sorted(mine - pristine),
            "pristine": not modified and not (pristine - mine) and not (mine - pristine)}


def restore_files(mod):
    """Make ~/tracks/<module> identical to the image's copy. Every file that differs, and
    every file the image does not have, is MOVED to a backup folder first (never deleted).
    -> (backup dir or None, number of files saved, number restored)."""
    pristine = iter_files(mod.src_dir)
    pset = set(pristine)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = os.path.join(backup_root(), f"{mod.id}-{stamp}")
    saved = 0
    if os.path.isdir(mod.home_dir):
        for d, dirs, files in os.walk(mod.home_dir):
            for name in files:
                p = os.path.join(d, name)
                rel = os.path.relpath(p, mod.home_dir)
                if rel in pset and os.path.isfile(p) and not os.path.islink(p) \
                        and sha256(p) == sha256(os.path.join(mod.src_dir, rel)):
                    continue
                target = os.path.join(backup, rel)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.move(p, target)
                saved += 1
        # Remove directories left empty (deepest first); keep the module folder itself.
        for d, dirs, files in os.walk(mod.home_dir, topdown=False):
            if d != mod.home_dir and not os.listdir(d):
                os.rmdir(d)
    elif os.path.lexists(mod.home_dir):          # a file or link where the folder should be
        os.makedirs(backup, exist_ok=True)
        shutil.move(mod.home_dir, os.path.join(backup, os.path.basename(mod.home_dir)))
        saved += 1
    restored = 0
    man = _load_json(manifest_path(), {})
    files = man.setdefault("files", {})
    for rel in pristine:
        src = os.path.join(mod.src_dir, rel)
        dest = os.path.join(mod.home_dir, rel)
        if not os.path.exists(dest):
            _copy(src, dest)
            restored += 1
        files[f"{mod.rel}/{rel}"] = {"sha256": sha256(src)}
    _save_json(manifest_path(), man)
    return (backup if saved else None), saved, restored


# ---------------------------------------------------------------------------- running a checkpoint
def _module_env(mod):
    env = dict(os.environ)
    env.update({"LAB_MODULE_ID": mod.id, "LAB_MODULE_DIR": mod.home_dir,
                "LAB_MODULE_SRC": mod.src_dir, "LAB_TRACKS_HOME": tracks_home(),
                "PYTHONUNBUFFERED": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    return env


def parse_result(stdout):
    """The checkpoint's JSON summary: the last line that starts with LAB_TRACKS_RESULT, or
    else the last line that is a JSON object with a boolean "passed"."""
    lines = (stdout or "").splitlines()
    for line in reversed(lines):
        if line.startswith(RESULT_PREFIX):
            try:
                return json.loads(line[len(RESULT_PREFIX):])
            except ValueError:
                return None
    for line in reversed(lines):
        s = line.strip()
        if s.startswith("{") and s.endswith("}"):
            try:
                d = json.loads(s)
            except ValueError:
                continue
            if isinstance(d, dict) and isinstance(d.get("passed"), bool):
                return d
    return None


def run_checkpoint(mod, args, echo, timeout):
    """Run checkpoint.py from the image copy, as you, in your module folder.
    -> (rc, stdout). rc: 0 passed, 1 not yet, 2 could not run, 124 timed out."""
    if not os.path.isfile(mod.checkpoint):
        return 2, f"this module has no checkpoint ({mod.checkpoint} is missing)\n"
    cwd = mod.home_dir if os.path.isdir(mod.home_dir) else home()
    proc = subprocess.Popen([sys.executable, mod.checkpoint] + args, cwd=cwd, env=_module_env(mod),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    out = []
    import threading
    timer = threading.Timer(timeout, proc.kill)
    timer.start()
    try:
        for line in proc.stdout:
            out.append(line)
            if echo and not line.startswith(RESULT_PREFIX) and not _is_result_json(line):
                sys.stdout.write(line)
                sys.stdout.flush()
        proc.wait()
    finally:
        timed_out = not timer.is_alive() and proc.returncode not in (0, 1, 2)
        timer.cancel()
    rc = 124 if timed_out else proc.returncode
    return rc, "".join(out)


def _is_result_json(line):
    s = line.strip()
    return s.startswith("{") and s.endswith("}") and '"passed"' in s


# ---------------------------------------------------------------------------- commands
def _need_module(mods, name):
    m = find(mods, name)
    if m is None:
        ids = ", ".join(x.id for x in mods) or "none"
        print(f"lab-tracks: no module {name!r}. Modules: {ids}. Try `lab-tracks list`.",
              file=sys.stderr)
        raise SystemExit(2)
    return m


def _my_groups():
    try:
        from .token import lab_token, token_claims
        c = token_claims(lab_token())
    except Exception:  # noqa: BLE001 - informational only
        return None
    g = c.get("groups")
    return {x.strip("/") for x in g} if isinstance(g, list) else None


def cmd_list(a):
    mods, problems = discover()
    prog = load_progress()["modules"]
    groups = None if a.json else _my_groups()
    rows = []
    for m in mods:
        e = prog.get(m.id, {})
        rows.append({"id": m.id, "track": m.track, "title": m.title, "minutes": m.minutes,
                     "profile": m.profile, "groups": m.groups, "test_user": m.test_user,
                     "dir": m.rel, "status": e.get("status", "not-started"),
                     "passed_at": e.get("passed_at")})
    if a.json:
        print(json.dumps({"modules": rows, "problems": problems}, indent=1))
        return 0
    if not rows:
        print("No learning tracks in this workspace image." + (f" ({problems[0]})" if problems else ""))
        return 1
    track = None
    for r, m in zip(rows, mods):
        if r["track"] != track:
            track = r["track"]
            print(f"\n{track.capitalize()} track   (lessons in {_pretty(os.path.join(tracks_home(), track))}/)")
        needs = [f"profile {m.profile}+"] if m.profile != "core" else []
        if groups is not None and not (groups & set(m.groups)):
            needs.append("group " + " or ".join(m.groups) + " (ask your lab admin)")
        status = {"passed": "PASSED", "in-progress": "in progress"}.get(r["status"], "not started")
        mins = f"{m.minutes} min" if m.minutes else ""
        print(f"  {m.id:<4} {m.title:<46} {mins:>7}  {status:<12} {'; '.join(needs)}")
    print("\nStart a module: open its README.md. When you think you are done: lab-tracks check <ID>")
    for p in problems:
        print(f"(skipped a broken module: {p})", file=sys.stderr)
    return 0


def cmd_check(a):
    mods, _ = discover()
    m = _need_module(mods, a.module)
    if not a.json:
        print(f"Checking {m.id} \"{m.title}\" (this looks at what you built, as you)...\n")
    rc, out = run_checkpoint(m, ["--json"], echo=not a.json, timeout=a.timeout)
    res = parse_result(out) or {}
    passed = rc == 0 and res.get("passed", True) is True
    e = load_progress()["modules"].get(m.id, {})
    fields = {"last_checked_at": now_iso(), "checks": int(e.get("checks", 0)) + 1,
              "last_result": "pass" if passed else ("fail" if rc == 1 else "error")}
    if passed:
        fields["status"] = "passed"
        if not e.get("passed_at"):
            fields["passed_at"] = now_iso()
    elif e.get("status") != "passed":
        fields["status"] = "in-progress"
    record(m, **fields)
    if a.json:
        print(json.dumps({"module": m.id, "rc": rc, "passed": passed, "result": res,
                          "output_tail": out[-3000:] if not res else None}, default=str))
        return 0 if passed else (1 if rc == 1 else 2)
    print()
    if passed:
        nxt = next((x for x in mods if x.track == m.track and x.sort_key() > m.sort_key()), None)
        print(f"{m.id} PASSED. Well done!" + (f" Next: {nxt.id} \"{nxt.title}\" in "
                                              f"{_pretty(nxt.home_dir)}/" if nxt else ""))
        return 0
    if rc == 1:
        print(f"{m.id}: not yet. Fix the first FAIL above (its hint says how), then run "
              f"`lab-tracks check {m.id}` again.\nStuck? The lesson's \"Common mistakes\" "
              f"section is in {_pretty(m.home_dir)}/README.md.")
        return 1
    if rc == 124:
        print(f"{m.id}: the checkpoint took longer than {a.timeout}s and was stopped. Is the lab "
              f"busy or a service down? Try again in a minute.")
        return 2
    if rc != 2:
        print(out[-2000:])
    print(f"{m.id}: the checkpoint could not run (exit {rc}). This is not about your work: "
          f"check that you are logged in (`lab-token` prints a token) and that the lab is up.")
    return 2


def cmd_status(a):
    mods, _ = discover()
    m = _need_module(mods, a.module)
    st = file_state(m)
    st["progress"] = load_progress()["modules"].get(m.id, {"status": "not-started"})
    if a.json:
        print(json.dumps(st, indent=1))
        return 0
    print(f"{m.id} \"{m.title}\" in {st['dir']}/  progress: {st['progress'].get('status')}")
    if st["pristine"]:
        print("  your files are exactly as delivered")
    for k, label in (("modified", "changed by you"), ("extra", "added by you"),
                     ("missing", "missing (deleted?)")):
        for r in st[k]:
            print(f"  {label:<20} {r}")
    return 0


def cmd_reset(a):
    mods, _ = discover()
    m = _need_module(mods, a.module)
    st = file_state(m)
    if not a.yes:
        print(f"Reset {m.id} \"{m.title}\":\n"
              f"  - drop what this module created in YOUR OWN schema/namespace and DAG folder\n"
              f"    (nothing shared, nothing of other people's)\n"
              f"  - restore the original files in {st['dir']}/")
        n = len(st["modified"]) + len(st["extra"])
        if n:
            print(f"    ({n} changed or added file(s) are moved to "
                  f"{_pretty(backup_root())}/, not deleted)")
        if not sys.stdin.isatty():
            print("Not a terminal: add --yes to confirm.", file=sys.stderr)
            return 2
        if input("Continue? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Nothing changed.")
            return 1
    report = {"module": m.id}
    rc_obj, out = run_checkpoint(m, ["--reset"], echo=not a.json, timeout=a.timeout)
    report["objects"] = {"rc": rc_obj, "output_tail": out[-2000:]}
    backup, saved, restored = restore_files(m)
    report["files"] = {"backup": _pretty(backup) if backup else None, "saved": saved,
                       "restored": restored}
    report["pristine"] = file_state(m)["pristine"]
    e = load_progress()["modules"].get(m.id, {})
    record(m, status="not-started", reset_at=now_iso(),
           passed_before=bool(e.get("passed_at") or e.get("passed_before")))
    ok = rc_obj == 0 and report["pristine"]
    report["ok"] = ok
    if a.json:
        print(json.dumps(report))
        return 0 if ok else 1
    if backup:
        print(f"Your {saved} changed/added file(s) are saved in {_pretty(backup)}/")
    if rc_obj != 0:
        print(f"{m.id}: the files are restored, but dropping the module's objects failed "
              f"(exit {rc_obj}; see above). Run `lab-tracks reset {m.id}` again in a minute.")
        return 1
    print(f"{m.id} is back at its start: open {_pretty(m.home_dir)}/README.md to begin again.")
    return 0


def cmd_sync(a):
    sync(quiet=False)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="lab-tracks", description="Learning tracks: list, check and reset modules.")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("list", help="modules and your progress")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_list)
    s = sub.add_parser("check", help="run a module's checkpoint")
    s.add_argument("module")
    s.add_argument("--json", action="store_true")
    s.add_argument("--timeout", type=int, default=900)
    s.set_defaults(fn=cmd_check)
    s = sub.add_parser("reset", help="start a module again (your changes are backed up)")
    s.add_argument("module")
    s.add_argument("--yes", "-y", action="store_true", help="do not ask")
    s.add_argument("--json", action="store_true")
    s.add_argument("--timeout", type=int, default=900)
    s.set_defaults(fn=cmd_reset)
    s = sub.add_parser("status", help="which of your module files differ from the original")
    s.add_argument("module")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_status)
    s = sub.add_parser("sync", help="copy new lessons from the image into ~/tracks")
    s.set_defaults(fn=cmd_sync)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
