"""Unit tests for the Phase 3 smoke checks (phase3.py) that need no running lab: profile
gating, the mock IdP fixture, agreement with bootstrap's GitHub IdP flow, and the JS
snippets. Run: python3 -m unittest discover -s v3/tests/smoke -p 'test_*.py' -v (stdlib only)
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, V3)
if "requests" not in sys.modules:
    try:
        import requests  # noqa: F401
    except ImportError:  # the lint job's bare Python: phase3 only calls it inside checks
        sys.modules["requests"] = types.ModuleType("requests")

import phase3  # noqa: E402
from bootstrap import github_idp  # noqa: E402

AUTH = "https://auth.lab.localhost:18443"


class Gating(unittest.TestCase):
    def test_core(self):
        p = phase3.plan("core", long_on=True)
        self.assertIn("Airflow is only in profiles engineer and full", p[phase3.C12])
        self.assertIsNotNone(p[phase3.C13])
        self.assertIn("Superset is only in profile full", p[phase3.C14])
        self.assertIsNone(p[phase3.C15])
        self.assertIsNone(p[phase3.C16])

    def test_engineer(self):
        p = phase3.plan("engineer", long_on=False)
        self.assertIsNone(p[phase3.C12])
        self.assertIn("LAB_SMOKE_LONG=1", p[phase3.C13])
        self.assertIsNotNone(p[phase3.C14])
        self.assertIsNone(phase3.plan("engineer", long_on=True)[phase3.C13])

    def test_full(self):
        p = phase3.plan("full", long_on=True)
        self.assertEqual([k for k, v in p.items() if v], [])

    def test_every_check_is_planned_once_in_order(self):
        self.assertEqual(list(phase3.plan("full", True)), list(phase3.ALL))
        self.assertEqual(sorted(phase3.NUMBERS.values()), [12, 13, 14, 15, 16])
        self.assertLess(list(phase3.ALL).index(phase3.C12), list(phase3.ALL).index(phase3.C14),
                        "12 (dbt into analytics) must run before 14 (dashboard over analytics)")

    def test_profile_table_matches_installer(self):
        with open(os.path.join(V3, "installer", "lib.sh"), encoding="utf-8") as f:
            src = f.read()
        body = re.search(r"profile_includes\(\) \{(.*?)\n\}", src, re.S).group(1)
        pairs = set(re.findall(r"(\w+):(\w+)", body))
        want = {(f, p) for f in ("spark", "airflow", "superset")
                for p in ("core", "engineer", "full") if phase3.includes(p, f)}
        self.assertEqual(pairs, want)

    def test_run_all_skips_with_lines(self):
        seen = []
        S = types.SimpleNamespace(PROFILE="core", RESULTS={},
                                  skip=lambda n, r: seen.append(("skip", n)),
                                  check=lambda n, ok, ev: seen.append(("check", n, ok)))
        ran = []
        orig = dict(phase3.FUNCS)
        try:
            for k in phase3.FUNCS:
                phase3.FUNCS[k] = lambda S, k=k: ran.append(k)
            os.environ.pop("LAB_SMOKE_LONG", None)
            phase3.run_all(S, lambda n: True)
        finally:
            phase3.FUNCS.update(orig)
        self.assertEqual(ran, [phase3.C15, phase3.C16])
        self.assertEqual([n for kind, n, *_ in seen if kind == "skip"], [phase3.C12, phase3.C13, phase3.C14])

    def test_run_all_respects_only(self):
        S = types.SimpleNamespace(PROFILE="full", RESULTS={}, skip=lambda *a: None, check=lambda *a: None)
        ran = []
        orig = dict(phase3.FUNCS)
        try:
            for k in phase3.FUNCS:
                phase3.FUNCS[k] = lambda S, k=k: ran.append(k)
            phase3.run_all(S, lambda n: n == 16)
        finally:
            phase3.FUNCS.update(orig)
        self.assertEqual(ran, [phase3.C16])


class MockIdp(unittest.TestCase):
    def test_uses_bootstraps_flow_and_forbidden_list(self):
        self.assertEqual(phase3.FIRST_BROKER_FLOW, github_idp.FLOW)
        self.assertEqual(set(phase3.FORBIDDEN_FLOW_PROVIDERS), set(github_idp.FORBIDDEN_PROVIDERS))

    def test_idp_like_the_real_one(self):
        idp = phase3.mock_idp(AUTH, "x")
        real = github_idp.desired_idp("id", "secret")
        for k in ("trustEmail", "storeToken", "linkOnly", "firstBrokerLoginFlowAlias", "enabled"):
            self.assertEqual(idp[k], real[k], k)
        self.assertEqual(idp["alias"], "github-mock")
        cfg = idp["config"]
        self.assertEqual(cfg["issuer"], f"{AUTH}/realms/mock-idp")
        self.assertTrue(cfg["authorizationUrl"].startswith(AUTH + "/"), "browser leg is public")
        self.assertTrue(cfg["tokenUrl"].startswith("http://keycloak:8080/"), "back channel is internal")
        self.assertEqual(cfg["syncMode"], "IMPORT")

    def test_realm_redirect_only_to_the_broker(self):
        r = phase3.mock_realm(AUTH, "x", [("ghmock-a", "a@mock-idp.invalid", "p")])
        self.assertEqual(r["realm"], "mock-idp")
        self.assertEqual(r["clients"][0]["redirectUris"],
                         [f"{AUTH}/realms/lakehouse/broker/github-mock/endpoint"])
        self.assertEqual(r["users"][0]["credentials"][0]["value"], "p")
        self.assertTrue(r["users"][0]["username"].startswith(phase3.MOCK_USER_PREFIX))

    def test_flow_report(self):
        execs = [{"providerId": "idp-review-profile", "requirement": "REQUIRED"},
                 {"authenticationFlow": True, "displayName": "x", "requirement": "REQUIRED"},
                 {"providerId": "idp-username-password-form", "requirement": "REQUIRED"}]
        rep = phase3.flow_report(execs)
        self.assertTrue(rep["reauth_required"])
        self.assertEqual(rep["forbidden"], [])
        rep = phase3.flow_report(execs + [{"providerId": "idp-auto-link", "requirement": "ALTERNATIVE"}])
        self.assertEqual(rep["forbidden"], ["idp-auto-link"])

    def test_no_credential_literals(self):
        with open(phase3.__file__, encoding="utf-8") as f:
            src = f.read()
        self.assertNotRegex(src, r'(password|secret)\s*=\s*"[^"{]')


class Helpers(unittest.TestCase):
    def test_loginish(self):
        for p in ("/login/keycloak", "/oauth2/callback", "/auth/login_callback", "/oauth-authorized/keycloak"):
            self.assertRegex(p, phase3.LOGINISH)
        for p in ("/", "/superset/welcome/", "/dags", "/home"):
            self.assertNotRegex(p, phase3.LOGINISH)

    def test_first_value(self):
        self.assertEqual(phase3._first_value({"data": [{"u": "alice"}]}), "alice")
        self.assertIsNone(phase3._first_value({}))

    def test_run_seconds(self):
        secs, start = phase3._run_seconds({"start_date": "2026-09-25T10:00:00Z",
                                           "end_date": "2026-09-25T10:05:30.5Z"})
        self.assertEqual(secs, 330.5)
        self.assertEqual(phase3._run_seconds({}), (None, None))

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_js_snippets_parse(self):
        for js in (phase3.TILES_JS, phase3.HEALTH_JS, phase3.HEALTH_READY_JS, phase3.DELETE_HUB_USER_JS):
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
                f.write("const fn = " + js.strip() + ";\n")
            try:
                r = subprocess.run(["node", "--check", f.name], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
            finally:
                os.unlink(f.name)


if __name__ == "__main__":
    unittest.main()
