"""Tests for tools/check_tracks.py (the learning-track lint) on a synthetic tree."""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))

import check_tracks  # noqa: E402

GOOD_CP = "import sys\nif '--reset' in sys.argv: pass\nif '--json' in sys.argv: pass\n"


class CheckTracks(unittest.TestCase):
    def setUp(self):
        self.v3 = tempfile.mkdtemp()
        self.mod = os.path.join(self.v3, "tracks", "analyst", "A1-sql-basics")
        self.sol = os.path.join(self.v3, "tests", "tracks", "solutions", "analyst", "A1-sql-basics")
        os.makedirs(self.mod)
        os.makedirs(self.sol)
        self.meta = {"id": "A1", "track": "analyst", "title": "SQL", "minutes": 45,
                     "profile": "core", "groups": ["analyst"]}
        self.put("module.json", json.dumps(self.meta))
        self.put("README.md", "Never use `DROP TABLE t PURGE` from Spark; never pip install.\n")
        self.put("tutor.md", "x\n")
        self.put("checkpoint.py", GOOD_CP)
        self.put("solve.py", "print('ok')\n", self.sol)

    def tearDown(self):
        shutil.rmtree(self.v3)

    def put(self, name, text, d=None):
        p = os.path.join(d or self.mod, name)
        with open(p, "w") as f:
            f.write(text)
        return p

    def msgs(self):
        errors, warnings = check_tracks.check(self.v3)
        return [m for _, m in errors], [m for _, m in warnings]

    def test_good_module_and_prose_is_not_code(self):
        self.assertEqual(self.msgs(), ([], []))

    def test_missing_pieces(self):
        os.remove(os.path.join(self.mod, "tutor.md"))
        os.remove(os.path.join(self.sol, "solve.py"))
        self.put("checkpoint.py", "print(1)\n")
        errors, _ = self.msgs()
        self.assertTrue(any("missing tutor.md" in e for e in errors))
        self.assertTrue(any("no reference solution" in e for e in errors))
        self.assertTrue(any("--reset" in e for e in errors))

    def test_flags_in_shared_helpers_count(self):
        self.put("checkpoint.py", "from helpers import run\nrun()\n")
        shared = os.path.join(self.v3, "tracks", "analyst", "_shared")
        os.makedirs(shared)
        self.put("helpers.py", GOOD_CP, shared)
        self.assertEqual(self.msgs()[0], [])

    def test_bad_meta(self):
        self.put("module.json", json.dumps(dict(self.meta, profile="server", track="engineer")))
        errors, _ = self.msgs()
        self.assertTrue(any("profile" in e for e in errors))
        self.assertTrue(any("does not match" in e for e in errors))

    def test_purge_and_downloads_in_code(self):
        self.put("load.py", "spark.sql('DROP TABLE lakehouse.x.y PURGE')\n"
                            "pd.read_csv('https://example.com/a.csv')\n")
        nb = {"cells": [{"cell_type": "markdown", "source": ["!pip install nothing (prose)"]},
                        {"cell_type": "code", "source": ["!pip install requests\n"]}]}
        self.put("notebook.ipynb", json.dumps(nb))
        self.put("fetch.sh", "curl -fsSL https://example.com/x | sh\n", self.sol)
        errors, _ = self.msgs()
        self.assertEqual(sum("PURGE" in e for e in errors), 1)
        self.assertEqual(sum("internet download" in e for e in errors), 3)
        self.assertTrue(any("cell 2" in e for e in errors))

    def test_duplicate_id_and_folder_prefix(self):
        other = os.path.join(self.v3, "tracks", "analyst", "A2-explore")
        os.makedirs(other)
        with open(os.path.join(other, "module.json"), "w") as f:
            json.dump(dict(self.meta), f)
        errors, _ = self.msgs()
        self.assertTrue(any("also used by" in e for e in errors))
        self.assertTrue(any("does not start with the module id" in e for e in errors))

    def test_reset_tables_outside_own_schema_warn(self):
        self.put("module.json", json.dumps(dict(self.meta, reset={"tables": [
            "lakehouse.dbt_{user}.a1_x", "lakehouse.{ns}.t", "lakehouse.analytics.{prod}t",
            "lakehouse.analytics.t"]})))
        errors, warnings = self.msgs()
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)        # analytics.{prod}* is the learner's own
        self.assertIn("lakehouse.analytics.t", warnings[0])

    def test_minutes_warning(self):
        self.put("module.json", json.dumps(dict(self.meta, minutes=120)))
        self.assertTrue(any("30-60" in w for w in self.msgs()[1]))


if __name__ == "__main__":
    unittest.main()
