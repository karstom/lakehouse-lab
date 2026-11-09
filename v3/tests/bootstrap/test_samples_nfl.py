"""NFL sample loader (bootstrap/samples.py): files, literals, statements, idempotence."""
import os
import sys
import unittest

V3 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, V3)

from bootstrap import samples  # noqa: E402


class FakeTrino:
    def __init__(self, tables=()):
        self.tables, self.sql = set(tables), []

    def query(self, sql):
        self.sql.append(sql)
        if sql.startswith("SHOW TABLES"):
            return [[t] for t in sorted(self.tables)], None
        if sql.startswith("ALTER TABLE"):
            self.tables.add(sql.rsplit(".", 1)[1])
        return [], 1


class NflSample(unittest.TestCase):
    def test_files_match_declared_columns(self):
        for table in samples.NFL_TABLES:
            rows = samples.nfl_rows(table)
            self.assertGreater(len(rows), 1000, table)
            self.assertTrue(all(len(r) == len(samples.NFL_TABLES[table]) for r in rows), table)

    def test_literals(self):
        self.assertEqual(samples.sql_literal("", "integer"), "NULL")
        self.assertEqual(samples.sql_literal("O'Brien", "varchar"), "'O''Brien'")
        self.assertEqual(samples.sql_literal("2015-09-10", "date"), "DATE '2015-09-10'")
        self.assertEqual(samples.sql_literal("-3.5", "double"), "-3.5")
        self.assertEqual(samples.sql_literal("7.0", "integer"), "7")

    def test_statements_load_then_rename(self):
        rows = samples.nfl_rows("nfl_games")
        sql = samples.nfl_statements("nfl_games", rows)
        self.assertTrue(sql[0].startswith("DROP TABLE IF EXISTS lakehouse.samples.nfl_games__loading"))
        self.assertTrue(sql[-1].endswith("RENAME TO lakehouse.samples.nfl_games"))
        inserts = [s for s in sql if s.startswith("INSERT")]
        self.assertEqual(len(inserts), -(-len(rows) // samples.NFL_BATCH))

    def test_existing_tables_are_left_alone(self):
        t = FakeTrino(tables=samples.NFL_TABLES)
        self.assertEqual(samples.ensure_nfl(t), [])
        self.assertFalse(any(s.startswith(("CREATE", "INSERT", "DROP")) for s in t.sql))

    def test_missing_table_is_created(self):
        t = FakeTrino(tables={"nfl_games"})
        self.assertEqual(samples.ensure_nfl(t), ["nfl_q4_flags"])


if __name__ == "__main__":
    unittest.main()
