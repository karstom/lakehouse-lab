"""Unit tests for the generated Trino rules (bootstrap/trino_groups.py, Phase 4): each analyst
may write in lakehouse.dbt_<user> only. Run:
  python3 -m unittest discover -s v3/tests/bootstrap -v
"""
import json
import os
import re
import sys
import tempfile
import unittest

V3 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, V3)

from bootstrap import trino_groups as tg  # noqa: E402

BASE = os.path.join(V3, "config", "trino", "rules.json")
MEMBERS = {"lab-admin": ["alice"], "engineer": ["eddie"], "analyst": ["anna", "a.b-c"],
           "viewer": ["victor"]}


def first_match(rules, user, schema):
    """First schema/table rule whose user and schema regexes (fullmatch, like Trino) match."""
    for r in rules:
        if "user" in r and not re.fullmatch(r["user"], user):
            continue
        if "group" in r:
            continue
        if "schema" in r and not re.fullmatch(r["schema"], schema):
            continue
        return r
    return None


class UserSchemaRules(unittest.TestCase):
    def setUp(self):
        with open(BASE, encoding="utf-8") as f:
            self.base = json.load(f)
        self.rules = json.loads(tg.render_rules(self.base, MEMBERS))

    def test_base_rules_are_kept_in_order(self):
        for sec in self.base:
            got = self.rules[sec]
            if sec in ("schemas", "tables"):
                got = got[len(MEMBERS["analyst"]):]
            self.assertEqual(got, self.base[sec], sec)

    def test_one_rule_pair_per_analyst_only(self):
        users = sorted(r["user"] for r in self.rules["schemas"][:2])
        self.assertEqual(users, sorted(tg.java_literal(u) for u in MEMBERS["analyst"]))
        for u in ("alice", "eddie", "victor"):
            self.assertIsNone(first_match(self.rules["schemas"][:2], u, f"dbt_{u}"))

    def test_rule_matches_own_schema_not_others(self):
        s = self.rules["schemas"][:2]
        self.assertTrue(first_match(s, "anna", "dbt_anna")["owner"])
        self.assertIsNone(first_match(s, "anna", "dbt_victor"))
        self.assertIsNone(first_match(s, "anna", "dbt_annaX"))
        self.assertIsNone(first_match(s, "annaX", "dbt_anna"))
        # regex metacharacters in a username are literal
        self.assertTrue(first_match(s, "a.b-c", "dbt_a.b-c")["owner"])
        self.assertIsNone(first_match(s, "aXb-c", "dbt_aXb-c"))

    def test_table_privileges(self):
        t = first_match(self.rules["tables"][:2], "anna", "dbt_anna")
        self.assertIn("OWNERSHIP", t["privileges"])
        self.assertEqual(t["catalog"], "lakehouse")

    def test_write_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "rules.json")
            self.assertTrue(tg.write_rules(MEMBERS, BASE, out))
            self.assertFalse(tg.write_rules(MEMBERS, BASE, out))
            self.assertTrue(tg.write_rules({"analyst": ["anna"]}, BASE, out))

    def test_no_analyst_means_base_only(self):
        rules = json.loads(tg.render_rules(self.base, {"analyst": []}))
        self.assertEqual(rules, self.base)


if __name__ == "__main__":
    unittest.main()
