"""Unit tests for bootstrap/ai_gateway.py (the ai-keys broker) against an in-memory fake of
the LiteLLM admin API, plus the broker's HTTP surface on a real socket. Stdlib only:
    python3 -m unittest discover -s v3/tests/ai
"""
import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

V3 = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, V3)
from bootstrap import ai_gateway, web  # noqa: E402

HUB = "h" * 40


class FakeLiteLLM:
    """Just enough of LiteLLM's management API, keyed like the real one."""

    def __init__(self, models=("lab-default", "mock")):
        self.users, self.keys, self.models_ = {}, {}, list(models)
        self.calls = []
        self.n = 0
        self.down = False

    def request(self, method, url, json_body=None, headers=None, expect=(200,), timeout=30):
        if self.down:
            raise OSError("connection refused")
        assert headers["Authorization"] == "Bearer sk-master"
        u = urllib.parse.urlparse(url)
        q = dict(urllib.parse.parse_qsl(u.query))
        self.calls.append((method, u.path))
        path = u.path
        if path == "/health":
            raise AssertionError("the broker must never call /health (it calls every model)")
        if path in ("/v1/chat/completions", "/v1/messages", "/chat/completions"):
            raise AssertionError("the broker must never make a model call")
        if path == "/health/liveliness":
            return 200, "I'm alive!", {}
        if path == "/v1/models":
            return 200, {"data": [{"id": m} for m in self.models_]}, {}
        if path == "/user/info":
            if q["user_id"] not in self.users:
                raise web.HTTPError(method, url, 404, "not found")
            return 200, {"user_info": dict(self.users[q["user_id"]])}, {}
        if path == "/user/new":
            self.users[json_body["user_id"]] = {k: v for k, v in json_body.items()
                                                if k not in ("auto_create_key", "send_invite_email")}
            return 200, {}, {}
        if path == "/user/update":
            self.users[json_body["user_id"]].update(json_body)
            return 200, {}, {}
        if path == "/user/list":
            return 200, {"users": [dict(u) for u in self.users.values()]}, {}
        if path == "/key/generate":
            self.n += 1
            token = f"hash{self.n}"
            self.keys[token] = dict(json_body, token=token)
            return 200, {"key": f"sk-key{self.n}", "token": token}, {}
        if path == "/key/list":
            return 200, {"keys": [dict(k) for k in self.keys.values() if k["user_id"] == q["user_id"]]}, {}
        if path == "/key/delete":
            for t in json_body["keys"]:
                self.keys.pop(t)
            return 200, {}, {}
        raise AssertionError(f"unexpected call {method} {path}")


CFG = ai_gateway.settings({})


class Settings(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(CFG, {"max_budget": 5.0, "budget_duration": "30d", "rpm_limit": 30, "key_duration": "30d"})

    def test_overrides_and_validation(self):
        cfg = ai_gateway.settings({"LAB_AI_USER_BUDGET_USD": "0.5", "LAB_AI_BUDGET_DURATION": "7d",
                                   "LAB_AI_USER_RPM": "10", "LAB_AI_KEY_DURATION": "24h"})
        self.assertEqual(cfg, {"max_budget": 0.5, "budget_duration": "7d", "rpm_limit": 10, "key_duration": "24h"})
        for bad in ({"LAB_AI_USER_BUDGET_USD": "lots"}, {"LAB_AI_USER_BUDGET_USD": "-1"},
                    {"LAB_AI_BUDGET_DURATION": "forever"}):
            with self.assertRaises(SystemExit):
                ai_gateway.settings(bad)

    def test_valid_user(self):
        for ok in ("alice", "a.b", "eddie_x", "u-1", "x@y"):
            self.assertTrue(ai_gateway.valid_user(ok), ok)
        for bad in ("", "Alice", "../x", "a b", "a/b", "-x", "x" * 65, None, 5, "a\nb"):
            self.assertFalse(ai_gateway.valid_user(bad), bad)


class Operations(unittest.TestCase):
    def setUp(self):
        self.fake = FakeLiteLLM()
        self.gw = ai_gateway.Gateway("sk-master", url="http://gw:4000", request=self.fake.request)

    def test_mint_creates_viewer_user_with_budget(self):
        out = ai_gateway.mint(self.gw, "alice", CFG)
        u = self.fake.users["alice"]
        self.assertEqual(u["user_role"], "internal_user_viewer")
        self.assertEqual((u["max_budget"], u["budget_duration"], u["rpm_limit"]), (5.0, "30d", 30))
        self.assertTrue(u["metadata"]["lab_managed"])
        self.assertTrue(out["key"].startswith("sk-"))
        self.assertTrue(out["configured"])
        self.assertIsNone(out["message"])
        self.assertEqual(out["model"], "lab-default")

    def test_mint_rotates_one_live_key_and_keeps_spend(self):
        a = ai_gateway.mint(self.gw, "alice", CFG)
        self.fake.users["alice"]["spend"] = 1.25
        b = ai_gateway.mint(self.gw, "alice", CFG)
        self.assertNotEqual(a["key"], b["key"])
        live = [k for k in self.fake.keys.values() if k["user_id"] == "alice"]
        self.assertEqual(len(live), 1)
        self.assertEqual(self.fake.users["alice"]["spend"], 1.25)  # budget is per user

    def test_rotation_never_touches_other_users_or_foreign_keys(self):
        ai_gateway.mint(self.gw, "alice", CFG)
        ai_gateway.mint(self.gw, "bob", CFG)
        self.fake.keys["manual"] = {"user_id": "alice", "key_alias": "admin-made", "token": "manual"}
        ai_gateway.mint(self.gw, "alice", CFG)
        self.assertIn("manual", self.fake.keys)
        self.assertEqual(len([k for k in self.fake.keys.values() if k["user_id"] == "bob"]), 1)

    def test_not_configured_still_mints(self):
        self.fake.models_ = []
        out = ai_gateway.mint(self.gw, "alice", CFG)
        self.assertFalse(out["configured"])
        self.assertEqual(out["message"], "AI isn't configured; ask your lab admin.")

    def test_budget_change_reconciled(self):
        ai_gateway.mint(self.gw, "alice", CFG)
        self.assertEqual(ai_gateway.reconcile(self.gw, CFG), {"updated": 0, "unchanged": 1})
        cfg = dict(CFG, max_budget=10.0)
        self.assertEqual(ai_gateway.reconcile(self.gw, cfg), {"updated": 1, "unchanged": 0})
        self.assertEqual(self.fake.users["alice"]["max_budget"], 10.0)

    def test_revoke(self):
        ai_gateway.mint(self.gw, "alice", CFG)
        self.assertEqual(ai_gateway.revoke(self.gw, "alice"), {"user": "alice", "revoked": 1})
        self.assertEqual(ai_gateway.revoke(self.gw, "alice"), {"user": "alice", "revoked": 0})

    def test_invalid_user_refused(self):
        with self.assertRaises(ValueError):
            ai_gateway.mint(self.gw, "../admin", CFG)

    def test_status_when_down(self):
        self.fake.down = True
        st = ai_gateway.status(self.gw, CFG)
        self.assertFalse(st["configured"])
        self.assertTrue(st["gateway"].startswith("unavailable"))

    def test_only_management_calls(self):
        ai_gateway.mint(self.gw, "alice", CFG)
        ai_gateway.status(self.gw, CFG)
        paths = {p for _, p in self.fake.calls}
        self.assertLessEqual(paths, {"/user/info", "/user/new", "/key/list", "/key/generate",
                                     "/key/delete", "/v1/models"})


class HTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeLiteLLM()
        gw = ai_gateway.Gateway("sk-master", url="http://gw:4000", request=cls.fake.request)
        handler = ai_gateway.make_handler(gw, CFG, HUB)
        handler.log_message = lambda *a: None
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def call(self, method, path, body=None, token=HUB, raw=None):
        h = {"Content-Type": "application/json"}
        if token:
            h["Authorization"] = f"Bearer {token}"
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(self.url + path, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_healthz_open(self):
        self.assertEqual(self.call("GET", "/healthz", token=None), (200, {"ok": True}))

    def test_auth_required(self):
        self.assertEqual(self.call("POST", "/v1/keys/mint", {"user": "alice"}, token=None)[0], 401)
        self.assertEqual(self.call("POST", "/v1/keys/mint", {"user": "alice"}, token="x" * 40)[0], 401)
        self.assertEqual(self.call("GET", "/v1/status", token="nope")[0], 401)

    def test_mint_rotate_revoke(self):
        s, a = self.call("POST", "/v1/keys/mint", {"user": "carol"})
        self.assertEqual(s, 200)
        s, b = self.call("POST", "/v1/keys/rotate", {"user": "carol"})
        self.assertEqual(s, 200)
        self.assertNotEqual(a["key"], b["key"])
        self.assertEqual(self.call("POST", "/v1/keys/revoke", {"user": "carol"}), (200, {"user": "carol", "revoked": 1}))

    def test_bad_requests(self):
        self.assertEqual(self.call("POST", "/v1/keys/mint", {"user": "../x"})[0], 400)
        self.assertEqual(self.call("POST", "/v1/keys/mint", raw=b"{not json")[0], 400)
        self.assertEqual(self.call("POST", "/v1/keys/mint", raw=b"x" * 5000)[0], 400)
        self.assertEqual(self.call("POST", "/v1/keys/other", {"user": "a"})[0], 404)

    def test_status(self):
        s, st = self.call("GET", "/v1/status")
        self.assertEqual(s, 200)
        self.assertEqual(st["models"], ["lab-default", "mock"])
        self.assertNotIn("key", json.dumps(st).replace("key_duration", ""))

    def test_gateway_down_is_503(self):
        self.fake.down = True
        try:
            self.assertEqual(self.call("POST", "/v1/keys/mint", {"user": "dave"}),
                             (503, {"error": "AI gateway unavailable"}))
        finally:
            self.fake.down = False

    def test_short_hub_token_refused(self):
        with self.assertRaises(SystemExit):
            ai_gateway.make_handler(None, CFG, "short")


if __name__ == "__main__":
    unittest.main()
