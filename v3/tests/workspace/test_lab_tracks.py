"""Unit tests for `lab-tracks` (images/workspace/lakehouse/tracks.py): copy-on-upgrade,
reset with backups, progress, checkpoint protocol. No lab, no Jupyter: a temporary HOME and a
fake image track tree. Run: python3 -m unittest discover -s v3/tests/workspace -v
"""
import io
import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(V3, "images", "workspace"))

from lakehouse import tracks as T  # noqa: E402

CHECKPOINT = textwrap.dedent('''\
    import json, os, sys
    state = os.path.join(os.environ["HOME"], "built.txt")
    if "--reset" in sys.argv:
        if os.path.exists(state):
            os.remove(state)
        print("dropped", flush=True)
        sys.exit(0)
    ok = os.path.exists(state)
    print("  PASS  table exists" if ok else "  FAIL  no table\\n        hint: run step 3")
    if "--json" in sys.argv:
        print("LAB_TRACKS_RESULT " + json.dumps({"module": os.environ["LAB_MODULE_ID"],
              "passed": ok, "checks": [{"name": "table", "ok": ok}],
              "cwd": os.getcwd()}))
    sys.exit(0 if ok else 1)
''')


def module_json(mid, track, profile="core", groups=("analyst",), **extra):
    d = {"id": mid, "track": track, "title": f"Module {mid}", "minutes": 30,
         "profile": profile, "groups": list(groups)}
    d.update(extra)
    return json.dumps(d)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.src = os.path.join(self.tmp, "image-tracks")
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)
        self.env = {k: os.environ.get(k) for k in ("HOME", "LAB_TRACKS_SRC", "LAB_TRACKS_HOME")}
        os.environ["HOME"] = self.home
        os.environ["LAB_TRACKS_SRC"] = self.src
        os.environ.pop("LAB_TRACKS_HOME", None)
        self.write("README.md", "tracks\n")
        self.write("analyst/A1-sql/module.json", module_json("A1", "analyst"))
        self.write("analyst/A1-sql/README.md", "lesson v1\n")
        self.write("analyst/A1-sql/notebook.ipynb", "{}\n")
        self.write("analyst/A1-sql/checkpoint.py", CHECKPOINT)
        self.write("analyst/A2-explore/module.json", module_json("A2", "analyst"))
        self.write("analyst/A2-explore/checkpoint.py", CHECKPOINT)
        self.write("engineer/_shared/helpers.py", "X = 1\n")
        self.write("engineer/E1-files/module.json",
                   module_json("E1", "engineer", "engineer", ["engineer", "lab-admin"]))
        self.write("engineer/E1-files/checkpoint.py", CHECKPOINT)

    def tearDown(self):
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp)

    def write(self, rel, text, root=None):
        p = os.path.join(root or self.src, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)
        return p

    def read(self, rel):
        with open(os.path.join(self.home, "tracks", rel)) as f:
            return f.read()

    def quiet(self, fn, *a, **kw):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = fn(*a, **kw)
        return rc, buf.getvalue()


class Discover(Base):
    def test_modules_sorted_and_shared_is_not_a_module(self):
        mods, problems = T.discover()
        self.assertEqual([m.id for m in mods], ["A1", "A2", "E1"])
        self.assertEqual(problems, [])
        self.assertEqual(T.find(mods, "a1").rel, "analyst/A1-sql")
        self.assertEqual(T.find(mods, "E1-files").id, "E1")
        self.assertIsNone(T.find(mods, "Z9"))

    def test_test_user_defaults_from_groups(self):
        mods, _ = T.discover()
        self.assertEqual(T.find(mods, "A1").test_user, "anna")
        self.assertEqual(T.find(mods, "E1").test_user, "eddie")

    def test_broken_module_is_reported_not_fatal(self):
        self.write("analyst/A3-bad/module.json", json.dumps({"id": "A3", "track": "engineer"}))
        mods, problems = T.discover()
        self.assertNotIn("A3", [m.id for m in mods])
        self.assertTrue(any("A3-bad" in p and "does not match" in p for p in problems))

    def test_duplicate_ids_reported(self):
        self.write("engineer/E9-dup/module.json", module_json("A1", "engineer"))
        _, problems = T.discover()
        self.assertTrue(any("used twice" in p for p in problems))

    def test_profile_includes(self):
        self.assertTrue(T.profile_includes("full", "engineer"))
        self.assertTrue(T.profile_includes("engineer", "core"))
        self.assertFalse(T.profile_includes("core", "engineer"))
        self.assertFalse(T.profile_includes("engineer", "full"))


class Sync(Base):
    def test_first_sync_copies_everything(self):
        c = T.sync(quiet=True)
        self.assertEqual(c["added"], len(T.iter_files(self.src)))
        self.assertEqual(self.read("analyst/A1-sql/README.md"), "lesson v1\n")
        self.assertTrue(os.path.isfile(os.path.join(self.home, "tracks/engineer/_shared/helpers.py")))

    def test_upgrade_adds_new_updates_unedited_keeps_edits_and_deletions(self):
        T.sync(quiet=True)
        mine = os.path.join(self.home, "tracks", "analyst", "A1-sql")
        with open(os.path.join(mine, "notebook.ipynb"), "w") as f:
            f.write("{\"my\": \"work\"}\n")                    # learner edit
        os.remove(os.path.join(self.home, "tracks", "engineer", "_shared", "helpers.py"))
        # new image: README changed (unedited by learner), notebook changed (edited), new module
        self.write("analyst/A1-sql/README.md", "lesson v2\n")
        self.write("analyst/A1-sql/notebook.ipynb", "{\"v\": 2}\n")
        self.write("engineer/_shared/helpers.py", "X = 2\n")
        self.write("analyst/A3-dbt/module.json", module_json("A3", "analyst"))
        c = T.sync(quiet=True)
        self.assertEqual(self.read("analyst/A1-sql/README.md"), "lesson v2\n")      # updated
        self.assertEqual(self.read("analyst/A1-sql/notebook.ipynb"), "{\"my\": \"work\"}\n")  # kept
        self.assertFalse(os.path.exists(os.path.join(self.home, "tracks/engineer/_shared/helpers.py")))
        self.assertTrue(os.path.exists(os.path.join(self.home, "tracks/analyst/A3-dbt/module.json")))
        self.assertEqual((c["added"], c["updated"], c["kept_edited"], c["kept_deleted"]), (1, 1, 1, 1))
        man = T._load_json(os.path.join(self.home, ".lakehouse", "tracks-manifest.json"), {})
        self.assertTrue(man["files"]["analyst/A1-sql/notebook.ipynb"]["newer_in_image"])
        # idempotent
        c2 = T.sync(quiet=True)
        self.assertEqual((c2["added"], c2["updated"]), (0, 0))

    def test_existing_file_without_manifest_is_never_overwritten(self):
        self.write("tracks/analyst/A1-sql/README.md", "restored home copy\n", root=self.home)
        T.sync(quiet=True)
        self.assertEqual(self.read("analyst/A1-sql/README.md"), "restored home copy\n")

    def test_missing_image_dir_is_harmless(self):
        shutil.rmtree(self.src)
        self.assertEqual(T.sync(quiet=True)["added"], 0)


class ResetAndCheck(Base):
    def setUp(self):
        super().setUp()
        T.sync(quiet=True)
        self.mods, _ = T.discover()
        self.a1 = T.find(self.mods, "A1")

    def test_restore_moves_changes_to_backup_and_restores_pristine(self):
        mine = self.a1.home_dir
        with open(os.path.join(mine, "README.md"), "w") as f:
            f.write("scribbles\n")
        os.remove(os.path.join(mine, "notebook.ipynb"))
        os.makedirs(os.path.join(mine, "data"))
        with open(os.path.join(mine, "data", "out.csv"), "w") as f:
            f.write("a,b\n")
        st = T.file_state(self.a1)
        self.assertEqual((st["modified"], st["missing"], st["extra"]),
                         (["README.md"], ["notebook.ipynb"], ["data/out.csv"]))
        backup, saved, restored = T.restore_files(self.a1)
        self.assertEqual((saved, restored), (2, 2))
        self.assertTrue(T.file_state(self.a1)["pristine"])
        self.assertFalse(os.path.exists(os.path.join(mine, "data")))
        with open(os.path.join(backup, "README.md")) as f:
            self.assertEqual(f.read(), "scribbles\n")
        self.assertTrue(os.path.isfile(os.path.join(backup, "data", "out.csv")))

    def test_restore_of_pristine_module_makes_no_backup(self):
        backup, saved, restored = T.restore_files(self.a1)
        self.assertEqual((backup, saved, restored), (None, 0, 0))

    def test_restore_recreates_a_deleted_module(self):
        shutil.rmtree(self.a1.home_dir)
        T.restore_files(self.a1)
        self.assertTrue(T.file_state(self.a1)["pristine"])

    def test_check_protocol_and_progress(self):
        rc, out = self.quiet(T.main, ["check", "A1", "--json"])
        self.assertEqual(rc, 1)
        res = json.loads(out.strip().splitlines()[-1])
        self.assertFalse(res["passed"])
        self.assertEqual(res["result"]["cwd"], self.a1.home_dir)   # runs in the learner's copy
        with open(os.path.join(self.home, "built.txt"), "w") as f:
            f.write("x")
        rc, out = self.quiet(T.main, ["check", "A1"])
        self.assertEqual(rc, 0)
        self.assertIn("A1 PASSED", out)
        self.assertIn("Next: A2", out)
        self.assertNotIn("LAB_TRACKS_RESULT", out)                 # the machine line is hidden
        p = T._load_json(os.path.join(self.home, ".lab-progress.json"), {})["modules"]["A1"]
        self.assertEqual((p["status"], p["checks"], p["last_result"]), ("passed", 2, "pass"))
        self.assertIn("passed_at", p)

    def test_checkpoint_runs_from_image_copy_even_if_learner_broke_theirs(self):
        with open(os.path.join(self.a1.home_dir, "checkpoint.py"), "w") as f:
            f.write("raise SystemExit(5)\n")
        rc, _ = self.quiet(T.main, ["check", "A1", "--json"])
        self.assertEqual(rc, 1)                                      # the real check ran

    def test_reset_drops_objects_restores_files_and_progress(self):
        with open(os.path.join(self.home, "built.txt"), "w") as f:
            f.write("x")
        self.quiet(T.main, ["check", "A1"])
        with open(os.path.join(self.a1.home_dir, "README.md"), "w") as f:
            f.write("mine\n")
        rc, out = self.quiet(T.main, ["reset", "A1", "--yes", "--json"])
        self.assertEqual(rc, 0, out)
        rep = json.loads(out.strip().splitlines()[-1])
        self.assertTrue(rep["ok"] and rep["pristine"])
        self.assertEqual(rep["objects"]["rc"], 0)
        self.assertEqual(rep["files"]["saved"], 1)
        self.assertFalse(os.path.exists(os.path.join(self.home, "built.txt")))
        p = T._load_json(os.path.join(self.home, ".lab-progress.json"), {})["modules"]["A1"]
        self.assertEqual(p["status"], "not-started")
        self.assertTrue(p["passed_before"])
        rc, _ = self.quiet(T.main, ["check", "A1", "--json"])
        self.assertEqual(rc, 1)

    def test_reset_needs_yes_without_a_terminal(self):
        stdin = sys.stdin
        sys.stdin = io.StringIO("")
        try:
            rc, _ = self.quiet(T.main, ["reset", "A1"])
        finally:
            sys.stdin = stdin
        self.assertEqual(rc, 2)

    def test_could_not_run_is_rc_2(self):
        self.write("analyst/A1-sql/checkpoint.py", "import sys; print('no token'); sys.exit(2)\n")
        rc, out = self.quiet(T.main, ["check", "A1"])
        self.assertEqual(rc, 2)
        self.assertIn("could not run", out)
        p = T._load_json(os.path.join(self.home, ".lab-progress.json"), {})["modules"]["A1"]
        self.assertEqual(p["last_result"], "error")

    def test_unknown_module(self):
        with self.assertRaises(SystemExit) as cm:
            self.quiet(T.main, ["check", "Q7"])
        self.assertEqual(cm.exception.code, 2)

    def test_list_json(self):
        rc, out = self.quiet(T.main, ["list", "--json"])
        self.assertEqual(rc, 0)
        rows = json.loads(out)["modules"]
        self.assertEqual([r["id"] for r in rows], ["A1", "A2", "E1"])
        self.assertEqual(rows[2]["test_user"], "eddie")


class ParseResult(unittest.TestCase):
    def test_prefixed_line_wins(self):
        out = 'x\n{"passed": false}\nLAB_TRACKS_RESULT {"passed": true, "checks": []}\n'
        self.assertTrue(T.parse_result(out)["passed"])

    def test_plain_json_last_line(self):
        self.assertFalse(T.parse_result('hello\n{"module": "E1", "passed": false}\n')["passed"])

    def test_none(self):
        self.assertIsNone(T.parse_result("nothing here\n{not json}\n"))


if __name__ == "__main__":
    unittest.main()
