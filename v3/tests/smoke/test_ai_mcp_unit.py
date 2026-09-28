"""Unit tests for Phase 5 MCP+TESTS: the lab MCP servers' pure parts (images/workspace/mcp/
lab_mcp) and check 18's agent policy and evaluation (ai_agent_probe.py, ai_check.py).
No lab, no network, no MCP SDK needed (sqlglot-dependent tests skip without it).

    python3 -m unittest discover -s v3/tests/smoke -p 'test_*.py'
"""
import datetime
import importlib.util
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(V3, "images", "workspace", "mcp"))
sys.path.insert(0, os.path.join(V3, "images", "workspace"))     # the `lakehouse` package
sys.path.insert(0, HERE)

from lab_mcp import common, context, dbt_launcher, sqlguard  # noqa: E402
import ai_agent_probe as probe  # noqa: E402

HAVE_SQLGLOT = importlib.util.find_spec("sqlglot") is not None
FAKE_JWT = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJhbGljZSIsImV4cCI6OTk5OTk5OTk5OX0.c2lnbmF0dXJlX2J5dGVz"


class Scrub(unittest.TestCase):
    def test_jwt_and_secrets_removed(self):
        text = (f"Authorization: Bearer {FAKE_JWT} and token={FAKE_JWT} "
                f'{{"access_token": "abc123456789xyz", "password": "hunter2hunter2"}} '
                f"client_secret=s3cr3tvalue")
        out = common.scrub(text)
        self.assertNotIn(FAKE_JWT, out)
        self.assertNotIn("abc123456789xyz", out)
        self.assertNotIn("hunter2hunter2", out)
        self.assertNotIn("s3cr3tvalue", out)
        self.assertIn(common.REDACTED, out)

    def test_literal_extra_secret(self):
        self.assertEqual(common.scrub("x opaque-key-1234 y", extra=["opaque-key-1234"]),
                         f"x {common.REDACTED} y")

    def test_ordinary_text_kept(self):
        s = "lakehouse.analytics.fct_orders committed_at 2026-09-27T03:00:00+00:00"
        self.assertEqual(common.scrub(s), s)

    def test_to_json_scrubs_and_limits(self):
        out = common.to_json({"a": FAKE_JWT, "b": "x" * (common.MAX_OUTPUT_CHARS + 10)})
        self.assertNotIn(FAKE_JWT, out)
        self.assertTrue(out.endswith("[output truncated]"))

    def test_tool_failure_message(self):
        with self.assertRaises(RuntimeError) as cm:
            common.run_tool(lambda: (_ for _ in ()).throw(
                common.ToolFailure("denied", f"no, token {FAKE_JWT}")))
        self.assertIn("denied:", str(cm.exception))
        self.assertNotIn(FAKE_JWT, str(cm.exception))

    def test_unexpected_exception_has_no_traceback_or_token(self):
        def boom():
            raise ValueError(f"bad request with Bearer {FAKE_JWT}")
        with self.assertRaises(RuntimeError) as cm:
            common.run_tool(boom)
        self.assertTrue(str(cm.exception).startswith("error: ValueError"))
        self.assertNotIn(FAKE_JWT, str(cm.exception))


class Identifiers(unittest.TestCase):
    def test_split_table(self):
        self.assertEqual(common.split_table("analytics.fct_orders"),
                         ("lakehouse", "analytics", "fct_orders"))
        self.assertEqual(common.split_table('lakehouse."samples".Orders'),
                         ("lakehouse", "samples", "orders"))

    def test_split_table_refuses_injection(self):
        for bad in ('a.b"; DROP TABLE x; --', "a.b.c.d", "x", "a.b$snapshots", None):
            with self.assertRaises(common.ToolFailure):
                common.split_table(bad)

    def test_limit_rows(self):
        self.assertEqual(common.limit_rows(5000), common.MAX_ROWS)
        self.assertEqual(common.limit_rows(0), 1)
        self.assertEqual(common.limit_rows(None), 50)
        with self.assertRaises(common.ToolFailure):
            common.limit_rows("many")

    def test_public_url_from_auth_url(self):
        env = {"LAB_DOMAIN": "lab.localhost", "LAB_AUTH_URL": "https://auth.lab.localhost:8443"}
        with _env(env):
            self.assertEqual(common.public_url("superset", "/api"), "https://superset.lab.localhost:8443/api")
        with _env({"LAB_DOMAIN": "lab.localhost", "LAB_AUTH_URL": "https://auth.lab.localhost"}):
            self.assertEqual(common.public_url("airflow"), "https://airflow.lab.localhost")
        with _env({"LAB_DOMAIN": "x.io", "LAB_AUTH_URL": "https://auth.other.io"}):
            with self.assertRaises(common.ToolFailure):
                common.public_url("airflow")

    def test_denied_mapping(self):
        self.assertEqual(common.denied_or_error(403, {"message": "no"}, "Superset", "x").kind, "denied")
        self.assertEqual(common.denied_or_error(401, "", "Airflow", "x").kind, "denied")
        self.assertEqual(common.denied_or_error(404, {}, "Superset", "x").kind, "invalid")
        self.assertEqual(common.denied_or_error(500, {}, "Superset", "x").kind, "error")


@unittest.skipUnless(HAVE_SQLGLOT, "sqlglot not installed (it is in the workspace MCP venv)")
class ReadOnlyRule(unittest.TestCase):
    ALLOWED = [
        "SELECT 1", "select * from lakehouse.samples.orders limit 5;",
        "WITH a AS (SELECT 1 AS x) SELECT x FROM a",
        "SELECT * FROM a UNION ALL SELECT * FROM b",
        'SELECT committed_at FROM lakehouse.analytics."fct_orders$snapshots"',
        "SHOW SCHEMAS FROM lakehouse", "SHOW CREATE TABLE lakehouse.samples.orders",
        "DESCRIBE lakehouse.samples.orders", "EXPLAIN SELECT 1",
        "EXPLAIN (TYPE DISTRIBUTED) SELECT 1", "VALUES (1), (2)",
    ]
    REFUSED = [
        "INSERT INTO t VALUES (1)", "CREATE TABLE t AS SELECT 1", "DROP TABLE t",
        "DELETE FROM t", "UPDATE t SET a = 1", "MERGE INTO t USING s ON t.a = s.a WHEN MATCHED THEN DELETE",
        "ALTER TABLE t ADD COLUMN c int", "GRANT SELECT ON t TO alice",
        "CALL system.sync_partition_metadata('a', 'b', 'FULL')", "SET SESSION x = 1",
        "SELECT 1; DROP TABLE t", "WITH x AS (SELECT 1) DELETE FROM t",
        "EXPLAIN ANALYZE SELECT 1", "EXPLAIN (TYPE IO) ANALYZE SELECT 1", "EXPLAIN INSERT INTO t VALUES (1)",
        "SHOW TABLES; DROP TABLE t", "START TRANSACTION", "COMMIT", "USE lakehouse.samples",
        "TRUNCATE TABLE t", "", "   ", "this is not sql",
    ]

    def test_allowed(self):
        for sql in self.ALLOWED:
            with self.subTest(sql=sql):
                self.assertIsNone(sqlguard.check(sql))

    def test_refused(self):
        for sql in self.REFUSED:
            with self.subTest(sql=sql):
                self.assertIsNotNone(sqlguard.check(sql))


class CurrentLesson(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.src = os.path.join(root, "tracks")
        self.home = os.path.join(root, "home")
        os.makedirs(self.home)
        for mid, track, d in (("A1", "analyst", "A1-sql"), ("A2", "analyst", "A2-duck"),
                              ("E1", "engineer", "E1-files")):
            p = os.path.join(self.src, track, d)
            os.makedirs(p)
            with open(os.path.join(p, "module.json"), "w") as f:
                json.dump({"id": mid, "track": track, "title": f"{mid} title", "profile": "core",
                           "groups": ["analyst"], "tutor": "tutor.md"}, f)
            with open(os.path.join(p, "tutor.md"), "w") as f:
                f.write(f"# {mid} tutor notes\nHints only.\n")

    def tearDown(self):
        self.tmp.cleanup()

    def _progress(self, modules):
        with open(os.path.join(self.home, ".lab-progress.json"), "w") as f:
            json.dump({"version": 1, "modules": modules}, f)

    def test_named_module_carries_pristine_tutor_md(self):
        r = context.current_lesson("a2", home=self.home, src=self.src)
        self.assertEqual(r["module"]["id"], "A2")
        self.assertEqual(r["tutor_md"], "# A2 tutor notes\nHints only.\n")
        self.assertIn("do not hand over the solution", r["tutor_rules"])

    def test_last_unpassed_module_wins(self):
        self._progress({"A1": {"status": "passed", "last_checked_at": "2026-09-27T03:00:00Z"},
                        "A2": {"status": "in-progress", "last_checked_at": "2026-09-27T02:00:00Z"},
                        "E1": {"status": "in-progress", "last_checked_at": "2026-09-27T01:00:00Z"}})
        with _env({"LAB_CURRENT_MODULE": None}):
            r = context.current_lesson(home=self.home, src=self.src)
        self.assertEqual(r["module"]["id"], "A2")
        self.assertEqual(r["progress"]["status"], "in-progress")

    def test_no_module_in_progress(self):
        with _env({"LAB_CURRENT_MODULE": None}):
            r = context.current_lesson(home=self.home, src=self.src)
        self.assertIsNone(r["module"])

    def test_env_module(self):
        with _env({"LAB_CURRENT_MODULE": "E1"}):
            r = context.current_lesson(home=self.home, src=self.src)
        self.assertEqual(r["module"]["id"], "E1")

    def test_unknown_module(self):
        with self.assertRaises(common.ToolFailure):
            context.current_lesson("Z9", home=self.home, src=self.src)


class DbtLauncher(unittest.TestCase):
    def test_user_project_env_is_read_only_and_offline(self):
        with tempfile.TemporaryDirectory() as home:
            proj = os.path.join(home, "starter", "dbt_lakehouse")
            os.makedirs(proj)
            open(os.path.join(proj, "dbt_project.yml"), "w").close()
            env, got = dbt_launcher.server_env("user", home, base_env={
                "DBT_HOST": "cloud.getdbt.com", "DBT_TOKEN": "x", "DBT_PROFILES_DIR": "/elsewhere"})
        self.assertEqual(got, proj)
        self.assertEqual(env["DBT_MCP_ENABLE_TOOLS"], "list,parse,get_lineage_dev,get_node_details_dev")
        for tool in ("build", "run", "test", "show", "compile", "docs", "clone"):
            self.assertNotIn(tool, env["DBT_MCP_ENABLE_TOOLS"].split(","))
        for k in dbt_launcher.OFF:
            self.assertEqual(env[k], "true")
        self.assertEqual(env["DO_NOT_TRACK"], "1")
        self.assertNotIn("DBT_HOST", env)
        self.assertNotIn("DBT_TOKEN", env)
        self.assertNotIn("DBT_PROFILES_DIR", env)
        self.assertEqual(env["DBT_PATH"], "/opt/lakehouse/bin/dbt")

    def test_missing_user_project(self):
        with tempfile.TemporaryDirectory() as home:
            with self.assertRaises(SystemExit):
                dbt_launcher.server_env("user", home, base_env={})

    def test_analytics_profile_targets_analytics(self):
        self.assertIn("schema: analytics", dbt_launcher.ANALYTICS_PROFILE)
        self.assertIn("target: analytics", dbt_launcher.ANALYTICS_PROFILE)
        self.assertNotIn("password", dbt_launcher.ANALYTICS_PROFILE)

    def test_sync_tree_keeps_target(self):
        with tempfile.TemporaryDirectory() as t:
            src, dest = os.path.join(t, "src"), os.path.join(t, "dest")
            os.makedirs(os.path.join(src, "models"))
            with open(os.path.join(src, "models", "a.sql"), "w") as f:
                f.write("select 1")
            os.makedirs(os.path.join(dest, "target"))
            os.makedirs(os.path.join(dest, "models"))
            with open(os.path.join(dest, "models", "stale.sql"), "w") as f:
                f.write("x")
            with open(os.path.join(dest, "target", "manifest.json"), "w") as f:
                f.write("{}")
            dbt_launcher._sync_tree(src, dest)
            self.assertTrue(os.path.isfile(os.path.join(dest, "models", "a.sql")))
            self.assertFalse(os.path.exists(os.path.join(dest, "models", "stale.sql")))
            self.assertTrue(os.path.isfile(os.path.join(dest, "target", "manifest.json")))


class ServersJson(unittest.TestCase):
    def test_every_server_uses_the_launcher(self):
        with open(os.path.join(V3, "images", "workspace", "mcp", "servers.json")) as f:
            servers = json.load(f)["mcpServers"]
        self.assertEqual(set(servers), {"lab-trino", "lab-context", "dbt", "dbt-analytics"})
        for name, spec in servers.items():
            self.assertEqual(spec["command"], "/opt/lakehouse/bin/lab-mcp")
            self.assertIn(name, probe.SERVER_PREFIX)


def _result(obj, error=False):
    return {"is_error": error, "text": obj if isinstance(obj, str) else json.dumps(obj)}


class AgentPolicy(unittest.TestCase):
    """The scripted brain walks Superset -> dbt -> lineage -> snapshots -> answer."""

    def _walk(self, extra=()):
        pol = probe.Policy("Revenue by region", extra)
        turns = []
        answers = {
            "ctx__superset_dashboard_datasets": lambda a: _result(
                {"dashboard": {"id": 7, "title": a["dashboard"]},
                 "datasets": [{"dataset": "fct_orders", "table": "lakehouse.analytics.fct_orders"}]})
            if a["dashboard"] == "Revenue by region" else _result("error: invalid: no dashboard", True),
            "dbta__get_node_details_dev": lambda a: _result({
                "fct_orders": {"unique_id": "model.p.fct_orders", "name": "fct_orders",
                               "resource_type": "model", "relation_name": '"lakehouse"."analytics"."fct_orders"',
                               "config": {"materialized": "table"}},
                "stg_orders": {"unique_id": "model.p.stg_orders", "name": "stg_orders",
                               "resource_type": "model", "relation_name": '"lakehouse"."analytics"."stg_orders"',
                               "config": {"materialized": "view"}},
                "source:samples.orders": {"unique_id": "source.p.samples.orders", "name": "orders",
                                          "resource_type": "source",
                                          "relation_name": '"lakehouse"."samples"."orders"',
                                          "config": {}}}[a["node_id"]]),
            "dbta__get_lineage_dev": lambda a: _result({
                "model_id": a["unique_id"],
                "parents": [{"model_id": "model.p.stg_orders",
                             "parents": [{"model_id": "source.p.samples.orders", "parents": []}]}],
                "children": []}),
            "ctx__table_last_snapshot": lambda a: _result({
                "table": a["table"], "last_snapshot": {"committed_at": f"2026-09-27T0{len(a['table']) % 9}:00:00+00:00",
                                                       "operation": "append"}}),
            "trino__trino_query": lambda a: _result("error: invalid: refused (read-only)", True),
        }
        for _ in range(12):
            turn = pol.next_turn()
            turns.append(turn)
            if "content" in turn:
                return pol, turns
            for c in turn["tool_calls"]:
                fn = c["function"]["name"]
                args = json.loads(c["function"]["arguments"])
                pol.observe(fn, args, answers[fn](args))
        self.fail("the policy never answered")

    def test_walk_and_answer(self):
        pol, turns = self._walk()
        names = [[c["function"]["name"] for c in t.get("tool_calls", [])] for t in turns]
        self.assertEqual(names[0], ["ctx__superset_dashboard_datasets"])
        self.assertEqual(names[1], ["dbta__get_node_details_dev"])
        self.assertEqual(names[2], ["dbta__get_lineage_dev"])
        self.assertEqual(sorted(names[3]), ["dbta__get_node_details_dev"] * 2)
        self.assertEqual(sorted(names[4]), ["ctx__table_last_snapshot"] * 2)   # views skipped
        ans = probe.parse_answer(turns[-1]["content"])
        rows = {r["table"]: r for r in ans["tables"]}
        self.assertEqual(rows["lakehouse.analytics.fct_orders"]["role"], "dashboard dataset")
        self.assertEqual(rows["lakehouse.samples.orders"]["role"], "upstream source")
        self.assertEqual(rows["lakehouse.analytics.stg_orders"]["kind"], "view")
        self.assertIsNone(rows["lakehouse.analytics.stg_orders"]["last_loaded"])
        self.assertTrue(rows["lakehouse.samples.orders"]["last_loaded"].startswith("2026-09-27"))
        self.assertNotIn("{{", turns[-1]["content"])      # the mock's placeholder syntax

    def test_extra_first_calls_and_refusals(self):
        extra = [("ctx__superset_dashboard_datasets", {"dashboard": "private"}),
                 ("trino__trino_query", {"sql": "INSERT INTO t VALUES (1)"})]
        pol, turns = self._walk(extra)
        self.assertEqual([c["function"]["name"] for c in turns[0]["tool_calls"]],
                         ["ctx__superset_dashboard_datasets", "trino__trino_query"])
        self.assertEqual(len(pol.state["denied"]), 1)     # the write: "refused"
        self.assertEqual(len(pol.state["errors"]), 1)     # the unknown dashboard
        # the private dashboard's failure did not replace the real dashboard's datasets
        self.assertEqual(pol.state["dataset_tables"], ["lakehouse.analytics.fct_orders"])

    def test_denied_dashboard_answer(self):
        pol = probe.Policy("Revenue by region")
        pol.next_turn()
        pol.observe("ctx__superset_dashboard_datasets", {"dashboard": "Revenue by region"},
                    _result("Error executing tool x: denied: Superset refused", True))
        turn = pol.next_turn()
        self.assertIn("content", turn)
        self.assertIn("could not read", turn["content"])
        self.assertEqual(probe.parse_answer(turn["content"])["denied"], 1)

    def test_selector(self):
        self.assertEqual(probe._selector("source.lakehouse_starter.samples.orders"), "source:samples.orders")
        self.assertEqual(probe._selector("model.lakehouse_starter.stg_orders"), "stg_orders")

    def test_only_the_mock_model(self):
        with self.assertRaises(ValueError):
            probe.chat("http://127.0.0.1:9/v1", "k", "local", [], [])


class CheckEvaluation(unittest.TestCase):
    def setUp(self):
        import ai_check
        self.c = ai_check

    def test_frontdoor_evaluation(self):
        good = {"LAB_AI_GATEWAY_URL": "http://ai-frontdoor:4000", "OPENAI_BASE_URL": "http://ai-frontdoor:4000/v1",
                "direct_gateway_by_name": "gaierror: [Errno -2] Name or service not known",
                "direct_gateway_by_ip": "TimeoutError: timed out", "gateway_ip": "172.30.0.5",
                "frontdoor_tcp": "connected",
                "status": {"/health": 403, "/model/info": 403, "/v1/model/info": 403, "/v1/models": 200},
                "chat": {"ok": True, "sender": self.c.PERSONA_ID, "reply": "mock reply 1",
                         "personas": [self.c.PERSONA_ID]}}
        ok, ev = self.c.evaluate_frontdoor(good)
        self.assertTrue(ok, ev["checks"])
        for bad in ({"direct_gateway_by_name": "connected"}, {"direct_gateway_by_ip": "connected"},
                    {"LAB_AI_GATEWAY_URL": "http://ai-gateway:4000"},
                    {"status": dict(good["status"], **{"/health": 200})},
                    {"chat": dict(good["chat"], personas=[self.c.PERSONA_ID,
                                                          "jupyter-ai-personas::jupyter_ai_acp_client::CodexAcpPersona"])},
                    {"chat": dict(good["chat"], reply="Error: ai-frontdoor: not an AI route")}):
            with self.subTest(bad=bad):
                self.assertFalse(self.c.evaluate_frontdoor(dict(good, **bad))[0])
        self.assertFalse(self.c.evaluate_frontdoor(None)[0])

    def test_dt_normalizes(self):
        a = self.c._dt("2026-09-27T03:00:00.123000+00:00")
        b = self.c._dt(datetime.datetime(2026, 9, 27, 3, 0, 0, 123000, tzinfo=datetime.timezone.utc))
        self.assertEqual(a, b)
        self.assertEqual(self.c._dt("2026-09-27 03:00:00.123 UTC"), a)

    def test_victor_leak_detection(self):
        loop = {"turns": [{"gateway_status": 200, "calls": [
            {"tool": "ctx__superset_dashboard_datasets", "args": {"dashboard": self.c.PRIVATE_DASHBOARD},
             "is_error": True, "result_head": "no dashboard", "result_full": "no dashboard"},
            {"tool": "trino__trino_query", "args": {"sql": "INSERT INTO x"}, "is_error": True,
             "result_head": "refused", "result_full": "refused"},
            {"tool": "trino__trino_query", "args": {"sql": "SELECT count(*) FROM system.runtime.queries"},
             "is_error": False, "result_head": "", "result_full": json.dumps({"rows": [[0]]})}]}],
            "answer": "x", "answer_json": {"tables": [
                {"table": "lakehouse.samples.orders", "kind": "table",
                 "last_loaded": "2026-09-27T03:00:00+00:00"}]},
            "jwt_in_outputs": False, "user_token_in_outputs": False, "key_in_outputs": False}
        truth = {"lakehouse.samples.orders": self.c._dt("2026-09-27T03:00:00+00:00")}
        ok, ev = self.c.evaluate_victor({"loop": loop}, truth, 42)
        self.assertTrue(ok, ev)
        loop["answer_json"]["tables"][0]["last_loaded"] = "2026-09-27T04:00:00+00:00"
        ok, ev = self.c.evaluate_victor({"loop": loop}, truth, 42)
        self.assertFalse(ev["checks"]["only_what_victor_can_read"])
        loop["jwt_in_outputs"] = True
        self.assertFalse(self.c.evaluate_victor({"loop": loop}, truth, 42)[1]["checks"]["no_token_in_outputs"])


class _env:
    """Temporarily set (value) or remove (None) environment variables."""

    def __init__(self, values):
        self.values = values
        self.old = {}

    def __enter__(self):
        for k, v in self.values.items():
            self.old[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def __exit__(self, *a):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
