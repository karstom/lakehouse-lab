"""Unit tests for smoke check 17 (tracks.py): module discovery, selection per profile and
LAB_SMOKE_TRACKS, the pass rule, and the kernel code it generates. Also checks that it agrees
with the workspace's lab-tracks about modules. No lab needed (stdlib only).
Run: python3 -m unittest discover -s v3/tests/smoke -p 'test_*.py' -v
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(V3, "images", "workspace"))

import tracks  # noqa: E402
from lakehouse import tracks as lab_tracks  # noqa: E402


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "tracks")
        self.sol = os.path.join(self.tmp, "solutions")
        for track, d, meta in (
                ("engineer", "E1-files", {"id": "E1", "profile": "engineer", "groups": ["engineer"]}),
                ("engineer", "E2-maint", {"id": "E2", "profile": "engineer", "groups": ["engineer"]}),
                ("engineer", "E10-late", {"id": "E10", "profile": "engineer", "groups": ["engineer"]}),
                ("analyst", "A1-sql", {"id": "A1", "profile": "core", "groups": ["analyst"]}),
                ("analyst", "A4-dash", {"id": "A4", "profile": "full", "groups": ["analyst"],
                                        "solution": {"timeout_s": 1200, "browser_logins": ["superset"]}}),
                ("analyst", "A3-dbt", {"id": "A3", "profile": "core", "groups": ["analyst"],
                                       "test_user": "alice"})):
            meta = dict(meta, track=track, title=d)
            os.makedirs(os.path.join(self.root, track, d))
            with open(os.path.join(self.root, track, d, "module.json"), "w") as f:
                json.dump(meta, f)
            if d != "E2-maint":                      # E2 has no solution yet
                os.makedirs(os.path.join(self.sol, track, d))
                open(os.path.join(self.sol, track, d, "solve.py"), "w").close()
        os.makedirs(os.path.join(self.root, "engineer", "_shared"))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def ids(self, sel):
        return [(m["id"], why) for m, why in sel]


class SharedSolutionHelpers(Fixture):
    def test_underscore_dirs_only(self):
        os.makedirs(os.path.join(self.sol, "engineer", "_lib"))
        os.makedirs(os.path.join(self.sol, "engineer", "__pycache__"))
        open(os.path.join(self.sol, "engineer", "_notadir.py"), "w").close()
        self.assertEqual(tracks.shared_solution_dirs("engineer", self.sol), ["_lib"])
        self.assertEqual(tracks.shared_solution_dirs("analyst", self.sol), [])
        self.assertEqual(tracks.shared_solution_dirs("nope", self.sol), [])


class Discovery(Fixture):
    def test_order_and_defaults(self):
        mods = tracks.load_modules(self.root)
        self.assertEqual([m["id"] for m in mods], ["A1", "A3", "A4", "E1", "E2", "E10"])
        by = {m["id"]: m for m in mods}
        self.assertEqual(by["E1"]["test_user"], "eddie")
        self.assertEqual(by["A1"]["test_user"], "anna")
        self.assertEqual(by["A3"]["test_user"], "alice")
        self.assertEqual((by["A4"]["timeout_s"], by["A4"]["browser_logins"]), (1200, ["superset"]))
        self.assertEqual(by["E1"]["timeout_s"], 900)

    def test_agrees_with_lab_tracks(self):
        os.environ["LAB_TRACKS_SRC"] = self.root
        try:
            mods, problems = lab_tracks.discover()
        finally:
            os.environ.pop("LAB_TRACKS_SRC")
        self.assertEqual(problems, [])
        self.assertEqual([m.id for m in mods], [m["id"] for m in tracks.load_modules(self.root)])
        self.assertEqual([m.test_user for m in mods],
                         [m["test_user"] for m in tracks.load_modules(self.root)])


class Selection(Fixture):
    def sel(self, spec, profile):
        return self.ids(tracks.select(tracks.load_modules(self.root), spec, profile, self.sol))

    def test_first_on_core_runs_a1_and_skips_e1(self):
        s = dict(self.sel("first", "core"))
        self.assertEqual(sorted(s), ["A1", "E1"])
        self.assertIsNone(s["A1"])
        self.assertIn("needs profile engineer", s["E1"])

    def test_first_on_engineer_runs_both(self):
        self.assertEqual(self.sel("first", "engineer"), [("A1", None), ("E1", None)])

    def test_all_on_full(self):
        s = dict(self.sel("all", "full"))
        self.assertEqual([k for k, v in s.items() if v is None], ["A1", "A3", "A4", "E1", "E10"])
        self.assertIn("no reference solution", s["E2"])

    def test_all_on_engineer_skips_full_only(self):
        s = dict(self.sel("all", "engineer"))
        self.assertIn("needs profile full", s["A4"])

    def test_list_and_none(self):
        self.assertEqual([i for i, _ in self.sel("e10,A3", "full")], ["A3", "E10"])
        self.assertEqual(self.sel("none", "full"), [])


class PassRule(unittest.TestCase):
    GOOD = {"reset_before": {"rc": 0, "json": {"pristine": True}}, "check_start": {"rc": 1},
            "upload": {"rc": 0}, "solve": {"rc": 0},
            "check_solved": {"rc": 0, "json": {"passed": True}},
            "reset_after": {"rc": 0, "json": {"pristine": True}}, "check_after_reset": {"rc": 1}}

    def test_good(self):
        self.assertTrue(tracks.module_ok(self.GOOD))

    def test_each_failure(self):
        for step, bad in (("check_start", {"rc": 0}),              # passes before any work
                          ("check_start", {"rc": 2}),              # could not run
                          ("solve", {"rc": 1}),
                          ("check_solved", {"rc": 1}),
                          ("check_solved", {"rc": 0, "json": {"passed": False}}),
                          ("reset_after", {"rc": 0, "json": {"pristine": False}}),
                          ("reset_after", {"rc": 1, "json": {"pristine": True}}),
                          ("check_after_reset", {"rc": 0}),        # reset did not drop objects
                          ("check_after_reset", {"rc": "no-result"})):
            with self.subTest(step=step, bad=bad):
                self.assertFalse(tracks.module_ok(dict(self.GOOD, **{step: bad})))

    def test_dag_runs_step(self):
        self.assertTrue(tracks.module_ok(dict(self.GOOD, dag_runs={"rc": 0})))
        self.assertFalse(tracks.module_ok(dict(self.GOOD, dag_runs={"rc": 1})))


class DagRuns(unittest.TestCase):
    def test_dag_ids(self):
        m = {"trigger_dags": ["{dag}orders_summary", "{dag}revenue_spark"]}
        self.assertEqual(tracks.dag_ids(m, "eddie"),
                         ["u_eddie_orders_summary", "u_eddie_revenue_spark"])
        self.assertEqual(tracks.dag_ids({}, "eddie"), [])

    def test_run_since_ignores_earlier_runs(self):
        from datetime import datetime, timezone
        since = datetime(2026, 9, 26, 17, 0, tzinfo=timezone.utc).timestamp()
        runs = [{"dag_run_id": "old", "queued_at": "2026-09-26T09:00:00Z"},
                {"dag_run_id": "new", "queued_at": "2026-09-26T17:00:30.123456Z"},
                {"dag_run_id": "newer", "queued_at": "2026-09-26T17:01:00+00:00"},
                {"dag_run_id": "bad", "queued_at": None}]
        self.assertEqual(tracks.run_since(runs, since)["dag_run_id"], "newer")
        self.assertIsNone(tracks.run_since(runs[:1], since))

    def test_modules_load_trigger_dags(self):
        mods = {m["id"]: m for m in tracks.load_modules(
            os.path.join(os.path.dirname(__file__), "..", "..", "tracks"))}
        if "E3" in mods:
            self.assertTrue(mods["E3"]["trigger_dags"])
            self.assertEqual(mods["E1"]["trigger_dags"], [])


class KernelCode(unittest.TestCase):
    def test_command_code_compiles_and_quotes(self):
        code = tracks.command_code(["lab-tracks", "check", "E1'; rm -rf /", "--json"], "~/x",
                                   {"A": "~/y"}, 30)
        compile(code, "<kernel>", "exec")
        self.assertIn(repr("E1'; rm -rf /"), code)       # a value never becomes code

    def test_upload_code_compiles(self):
        compile(tracks.upload_code("AAAA", "~/.lab-solutions/E1"), "<kernel>", "exec")


if __name__ == "__main__":
    unittest.main()
