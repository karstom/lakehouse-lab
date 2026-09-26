"""Unit tests for the smoke test's workspace parts (checks 8-10) that need no running lab:
code generation for the kernel, result parsing, and kernel_probe's pure helpers.

Run: python3 -m unittest discover -s v3/tests/smoke -p 'test_*.py' -v   (stdlib only)
"""
import ast
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import kernel_probe  # noqa: E402
import workspace  # noqa: E402

def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


STDLIB_OK = {"glob", "json", "os", "re", "subprocess", "time", "traceback", "base64",
             "urllib", "urllib.parse"}


class CodeGeneration(unittest.TestCase):
    def test_markers_agree(self):
        self.assertEqual(workspace.MARKER, kernel_probe.MARKER)

    def test_probe_code_compiles_and_carries_params_safely(self):
        params = {"user": "alice", "steps": ["trino_samples"],
                  "evil": "'''\"\"\"\n); import os; os.system('x') #", "n": 3}
        code = workspace.probe_code(params)
        tree = ast.parse(code)  # must be valid Python
        last = tree.body[-1]
        # The last statement is print(MARKER + json.dumps(probe(json.loads(<str>), globals())))
        self.assertIsInstance(last, ast.Expr)
        literals = [n.value for n in ast.walk(last) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        self.assertIn(json.dumps(params), literals)
        self.assertEqual(json.loads(json.dumps(params)), params)

    def test_probe_code_runs_end_to_end_with_stub_steps(self):
        code = workspace.probe_code({"steps": ["a", "b"]})
        ns = {"__name__": "__kernel__"}
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            exec(compile(code.replace("\nSTEPS = {", "\nSTEPS_REAL = {"), "<probe>", "exec"),
                 dict(ns, STEPS={"a": lambda p, n: {"ok": True},
                                 "b": lambda p, n: 1 / 0}))
        out = workspace.parse_probe_output(buf.getvalue())
        self.assertIsNotNone(out)
        self.assertTrue(out["steps"]["a"]["ok"])
        self.assertFalse(out["steps"]["b"]["ok"])
        self.assertIn("ZeroDivisionError", out["steps"]["b"]["error"])

    def test_parse_probe_output(self):
        self.assertIsNone(workspace.parse_probe_output("noise\nmore"))
        self.assertIsNone(workspace.parse_probe_output(None))
        out = workspace.parse_probe_output("x\n" + workspace.MARKER + '{"a": 1}\ntrailing')
        self.assertEqual(out, {"a": 1})

    def test_kernel_probe_imports_only_stdlib_at_top_level(self):
        # Workspace clients are imported inside each step, so one missing client fails one
        # step, not the whole probe.
        tree = ast.parse(read(kernel_probe.__file__))
        mods = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                mods |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                mods.add(node.module)
        self.assertLessEqual(mods, STDLIB_OK)

    def test_no_spark_purge(self):
        # ADR-003: never DROP ... PURGE from Spark against Lakekeeper.
        src = read(kernel_probe.__file__)
        for line in src.splitlines():
            if "DROP TABLE" in line:
                self.assertNotIn("PURGE", line.upper())

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_js_snippets_parse(self):
        for js in (workspace.KERNEL_EXEC_JS, workspace.STOP_SERVER_JS):
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
                f.write("const fn = " + js.strip() + ";\n")
            try:
                r = subprocess.run(["node", "--check", f.name], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
            finally:
                os.unlink(f.name)


class ProbeHelpers(unittest.TestCase):
    def test_dbt_summary(self):
        text = ("12:00:01  Finished running 3 view models, 2 tests in 0 hours 0 minutes.\n"
                "12:00:01  Done. PASS=5 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=5\n")
        self.assertEqual(kernel_probe.dbt_summary(text),
                         {"pass": 5, "warn": 0, "error": 0, "skip": 0, "no_op": 0, "total": 5})
        self.assertEqual(kernel_probe.dbt_summary("Done. PASS=1 WARN=0 ERROR=2 SKIP=0 TOTAL=3"),
                         {"pass": 1, "warn": 0, "error": 2, "skip": 0, "total": 3})
        self.assertIsNone(kernel_probe.dbt_summary("Encountered an error"))
        # dbt 1.12 adds REUSED= (and NO-OP=) to the Done line.
        self.assertEqual(
            kernel_probe.dbt_summary("Done. PASS=27 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=27"),
            {"pass": 27, "warn": 0, "error": 0, "skip": 0, "no_op": 0, "reused": 0, "total": 27})

    def test_find_starter(self):
        home = tempfile.mkdtemp()
        try:
            self.assertIsNone(kernel_probe.find_starter({}, home))
            deep = os.path.join(home, "projects", "x", "shop")
            os.makedirs(deep)
            open(os.path.join(deep, "dbt_project.yml"), "w").close()
            pkg = os.path.join(home, "a", "dbt_packages", "p")
            os.makedirs(pkg)
            open(os.path.join(pkg, "dbt_project.yml"), "w").close()
            self.assertEqual(kernel_probe.find_starter({}, home), deep)
            st = os.path.join(home, "starter")
            os.makedirs(st)
            open(os.path.join(st, "dbt_project.yml"), "w").close()
            self.assertEqual(kernel_probe.find_starter({"starter_dirs": ["starter"]}, home), st)
        finally:
            shutil.rmtree(home)

    def test_get_token_order(self):
        self.assertEqual(kernel_probe.get_token({}, {"lab_token": lambda: "ns"}),
                         ("ns", "kernel-namespace:lab_token"))
        d = tempfile.mkdtemp()
        try:
            with open(os.path.join(d, "fake_lab_helper.py"), "w") as f:
                f.write("def lab_token():\n    return 'mod'\n")
            sys.path.insert(0, d)
            got = kernel_probe.get_token({"token_modules": ["no_such_mod_xyz", "fake_lab_helper"]})
            self.assertEqual(got, ("mod", "python:fake_lab_helper.lab_token"))
        finally:
            sys.path.remove(d)
            shutil.rmtree(d)
        with mock.patch.dict(os.environ, {"PATH": "/nonexistent"}):
            with self.assertRaises(RuntimeError):
                kernel_probe.get_token({"token_modules": []})

    def test_scrub_removes_jwts(self):
        jwt = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ4In0.c2lnbmF0dXJl"
        self.assertEqual(kernel_probe._scrub(f"Bearer {jwt} failed"), "Bearer <jwt> failed")

    def test_spark_helper_resolution(self):
        d = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(d, "fake_lakehouse_pkg"))
            with open(os.path.join(d, "fake_lakehouse_pkg", "__init__.py"), "w") as f:
                f.write("def spark():\n    return 'session'\n")
            sys.path.insert(0, d)
            got = kernel_probe.spark_session(
                {"spark_helpers": ["nope_mod.spark", "fake_lakehouse_pkg.spark"]}, {}, "tok")
            self.assertEqual(got, ("session", "helper:fake_lakehouse_pkg.spark"))
            got = kernel_probe.spark_session({}, {"lab_spark": lambda: "ns"}, "tok")
            self.assertEqual(got, ("ns", "kernel-namespace:lab_spark"))
        finally:
            sys.path.remove(d)
            shutil.rmtree(d)

    def test_starter_as_the_image_copies_it(self):
        home = tempfile.mkdtemp()
        try:
            p = os.path.join(home, "starter", "dbt_lakehouse")
            os.makedirs(p)
            open(os.path.join(p, "dbt_project.yml"), "w").close()
            self.assertEqual(kernel_probe.find_starter(
                {"starter_dirs": ["starter/dbt_lakehouse", "starter"]}, home), p)
            self.assertEqual(kernel_probe.find_starter({}, home), p)
        finally:
            shutil.rmtree(home)

    def test_jwt_claims_only_whitelisted(self):
        import base64
        body = base64.urlsafe_b64encode(json.dumps(
            {"preferred_username": "alice", "exp": 1, "email": "a@x", "groups": ["g"]}).encode()).decode().rstrip("=")
        c = kernel_probe.jwt_claims(f"h.{body}.s")
        self.assertEqual(c, {"preferred_username": "alice", "azp": None, "exp": 1})
        self.assertEqual(kernel_probe.jwt_claims("not-a-jwt"), {})


class InternalPortsProbe(unittest.TestCase):
    """Check 15's network probe: only connection failures count as "unreachable"."""

    def _closed_port(self):
        import socket
        with socket.socket() as sk:
            sk.bind(("127.0.0.1", 0))
            return sk.getsockname()[1]   # closed again when the block ends

    def test_reach_outcomes(self):
        import http.server
        import threading
        self.assertEqual(kernel_probe.reach("http://no-such-host.invalid:8080/")[0], "no-name")
        self.assertEqual(kernel_probe.reach(f"http://127.0.0.1:{self._closed_port()}/")[0], "refused")
        srv = http.server.HTTPServer(("127.0.0.1", 0), http.server.SimpleHTTPRequestHandler)
        srv.RequestHandlerClass.log_message = lambda *a: None
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            port = srv.server_address[1]
            self.assertEqual(kernel_probe.reach(f"http://127.0.0.1:{port}/")[0], "http 200")
            self.assertEqual(kernel_probe.reach(f"tcp://127.0.0.1:{port}")[0], "connected")
        finally:
            srv.shutdown()
            srv.server_close()

    def test_step_requires_failures_and_a_working_control(self):
        outcomes = {}
        with mock.patch.object(kernel_probe, "reach", lambda url, timeout=5.0: (outcomes[url], None)):
            params = {"unreachable": ["a", "b"], "reachable": ["c"]}
            outcomes.update(a="no-name", b="refused", c="connected")
            self.assertTrue(kernel_probe.step_internal_ports(params, None)["ok"])
            outcomes.update(b="http 200")          # a UI answered: fail
            self.assertFalse(kernel_probe.step_internal_ports(params, None)["ok"])
            outcomes.update(b="timeout", c="refused")   # control down: the probe proves nothing
            self.assertFalse(kernel_probe.step_internal_ports(params, None)["ok"])
            self.assertFalse(kernel_probe.step_internal_ports({"unreachable": []}, None)["ok"])


if __name__ == "__main__":
    unittest.main()
