"""Unit tests for bootstrap/ai_frontdoor.py (the only way workspaces reach the AI gateway):
the route/path matrix incl. encoding and traversal tricks, header and body rules, and the
proxy on real sockets against a fake gateway (streaming, header filtering, errors).
Stdlib only:
    python3 -m unittest discover -s v3/tests/ai
"""
import http.client
import json
import os
import socket
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

V3 = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, V3)
from bootstrap import ai_frontdoor as fd  # noqa: E402

fd.log.disabled = True      # deny/allow lines are the service's log, not test output

KEY = "sk-" + "a1B2_c3-D4" * 3


class Decide(unittest.TestCase):
    ALLOWED = [
        ("POST", "/v1/chat/completions", "/v1/chat/completions"),
        ("POST", "/chat/completions", "/chat/completions"),
        ("POST", "/v1/messages", "/v1/messages"),
        ("POST", "/v1/messages?beta=true", "/v1/messages?beta=true"),
        ("POST", "/v1/messages/count_tokens?beta=true", "/v1/messages/count_tokens?beta=true"),
        ("POST", "/v1/embeddings", "/v1/embeddings"),
        ("GET", "/v1/models", "/v1/models"),
        ("GET", "/v2/user/info", "/v2/user/info"),
        ("GET", "/v1/models?", "/v1/models"),
    ]
    DENIED = [
        # Routes users must never reach (the reason this proxy exists).
        ("GET", "/health"), ("GET", "/health/liveliness"), ("GET", "/health/readiness"),
        ("GET", "/health/services"), ("GET", "/v1/health"), ("GET", "/model/info"),
        ("GET", "/v1/model/info"), ("GET", "/v2/model/info"), ("GET", "/model_group/info"),
        ("GET", "/key/info"), ("POST", "/key/generate"), ("POST", "/key/delete"),
        ("GET", "/key/list"), ("GET", "/user/info"), ("GET", "/user/info?user_id=alice"),
        ("POST", "/user/update"), ("GET", "/user/list"), ("GET", "/spend/logs"),
        ("GET", "/global/spend/report"), ("GET", "/config/yaml"), ("POST", "/config/update"),
        ("GET", "/ui"), ("GET", "/ui/"), ("GET", "/sso/key/generate"), ("GET", "/"),
        ("GET", "/routes"), ("GET", "/openapi.json"), ("GET", "/docs"), ("POST", "/model/new"),
        ("POST", "/v1/completions"), ("POST", "/completions"), ("POST", "/v1/responses"),
        ("POST", "/v1/audio/speech"), ("POST", "/v1/images/generations"), ("GET", "/v1/files"),
        ("POST", "/team/new"), ("GET", "/v2/user/info?user_id=bob"), ("GET", "/mcp"),
        ("POST", "/anthropic/v1/messages"), ("POST", "/openai/v1/chat/completions"),
        ("POST", "/v1/models"), ("GET", "/v1/chat/completions"), ("DELETE", "/v1/models"),
        ("PUT", "/v1/chat/completions"), ("HEAD", "/v1/models"), ("OPTIONS", "/v1/models"),
        # Case, encoding and traversal tricks.
        ("GET", "/HEALTH"), ("GET", "/V1/models"), ("POST", "/v1/Chat/Completions"),
        ("GET", "/v1/models/"), ("GET", "//v1/models"), ("GET", "/v1//models"),
        ("GET", "/v1/./models"), ("GET", "/v1/models/.."), ("POST", "/v1/chat/completions/../../health"),
        ("POST", "/v1/../health"), ("GET", "/%68ealth"), ("GET", "/v1/model%2finfo"),
        ("POST", "/v1/chat%2Fcompletions"), ("POST", "/v1/chat/completions%00"),
        ("GET", "/v1/models;/../health"), ("GET", "/v1\\models"), ("GET", "http://ai-gateway:4000/health"),
        ("GET", "*"), ("GET", ""), ("GET", "/v1/models#frag"), ("GET", "/v1/models\t"),
        ("GET", "/v1/models "), ("GET", "/health?x=/v1/models"),
        # Query rules: only the listed keys and values.
        ("GET", "/v1/models?return_wildcard_routes=true"), ("POST", "/v1/messages?beta=false"),
        ("POST", "/v1/messages?beta=true&beta=true"), ("POST", "/v1/messages?Beta=true"),
        ("POST", "/v1/messages?beta"), ("POST", "/v1/chat/completions?user=bob"),
        ("POST", "/v1/messages?beta=true&x=1"), ("POST", "/v1/messages?beta=%74rue"),
        ("POST", "/v1/messages?&"), ("GET", "/v2/user/info?user_id=alice"),
    ]

    def test_allowed_routes_are_forwarded_canonically(self):
        for method, target, want in self.ALLOWED:
            with self.subTest(method=method, target=target):
                self.assertEqual(fd.decide(method, target), want)

    def test_everything_else_is_refused(self):
        for method, target in self.DENIED:
            with self.subTest(method=method, target=target):
                with self.assertRaises(fd.Reject) as cm:
                    fd.decide(method, target)
                self.assertEqual(cm.exception.status, 403)

    def test_allowlist_is_exactly_the_documented_one(self):
        # Single source of truth: a change here must be a deliberate, reviewed change.
        self.assertEqual(sorted(fd.ROUTES), sorted([
            ("POST", "/v1/chat/completions"), ("POST", "/chat/completions"),
            ("POST", "/v1/messages"), ("POST", "/v1/messages/count_tokens"),
            ("POST", "/v1/embeddings"), ("GET", "/v1/models"), ("GET", "/v2/user/info")]))
        for (_, path) in fd.ROUTES:
            self.assertFalse(path.startswith(("/health", "/model", "/v1/model/", "/key", "/user",
                                              "/spend", "/global", "/config", "/ui")), path)


class Headers(unittest.TestCase):
    def h(self, pairs):
        m = http.client.HTTPMessage()
        for k, v in pairs:
            m[k] = v
        return m

    def test_key_required(self):
        for pairs in ([], [("Authorization", "Bearer")], [("Authorization", f"Basic {KEY}")],
                      [("Authorization", "Bearer sk-short")], [("Authorization", "Bearer notsk-" + "x" * 20)],
                      [("Authorization", f"Bearer {KEY}"), ("Authorization", f"Bearer {KEY}")],
                      [("Authorization", f"Bearer {KEY}%0d")]):
            with self.subTest(pairs=pairs):
                with self.assertRaises(fd.Reject) as cm:
                    fd.check_headers("GET", self.h(pairs))
                self.assertEqual(cm.exception.status, 401)

    def test_post_body_rules(self):
        auth = ("Authorization", f"Bearer {KEY}")
        ok, n = fd.check_headers("POST", self.h([auth, ("Content-Type", "application/json"),
                                                 ("Content-Length", "12")]))
        self.assertEqual(n, 12)
        bad = [
            [auth, ("Content-Type", "application/json")],                       # no length
            [auth, ("Content-Type", "application/json"), ("Transfer-Encoding", "chunked")],
            [auth, ("Content-Type", "application/json"), ("Content-Length", "1"), ("Content-Length", "1")],
            [auth, ("Content-Type", "application/json"), ("Content-Length", "-1")],
            [auth, ("Content-Type", "application/json"), ("Content-Length", str(fd.MAX_BODY + 1))],
            [auth, ("Content-Type", "text/plain"), ("Content-Length", "2")],
            [auth, ("Content-Length", "2")],
        ]
        for pairs in bad:
            with self.subTest(pairs=pairs):
                with self.assertRaises(fd.Reject):
                    fd.check_headers("POST", self.h(pairs))
        with self.assertRaises(fd.Reject):
            fd.check_headers("GET", self.h([auth, ("Content-Length", "5")]))

    def test_only_listed_headers_are_forwarded(self):
        out, _ = fd.check_headers("POST", self.h([
            ("Authorization", f"Bearer {KEY}"), ("Content-Type", "application/json"),
            ("Content-Length", "2"), ("anthropic-version", "2023-06-01"), ("anthropic-beta", "x"),
            ("Connection", "keep-alive, x-litellm-api-key"), ("Keep-Alive", "timeout=5"),
            ("Upgrade", "h2c"), ("Proxy-Authorization", "Basic x"), ("Cookie", "c=1"),
            ("X-Forwarded-For", "10.0.0.1"), ("x-litellm-customer-id", "bob"),
            ("x-litellm-end-user-id", "bob"), ("x-litellm-api-key", "sk-other"),
            ("x-litellm-tags", "t"), ("TE", "trailers"), ("Host", "evil")]))
        self.assertEqual(sorted(out), ["Anthropic-Beta", "Anthropic-Version", "Authorization",
                                       "Content-Type"])


# ------------------------------------------------------------------ on real sockets
class FakeGateway(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    seen = []

    def log_message(self, *a):
        pass

    def _go(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        FakeGateway.seen.append({"method": self.command, "path": self.path,
                                 "headers": {k.lower(): v for k, v in self.headers.items()},
                                 "body": body})
        if self.path.startswith("/v1/chat/completions") and b'"stream": true' in body:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("x-litellm-model-api-base", "http://192.0.2.1:9999/v1")
            self.end_headers()
            for i in range(3):
                data = f"data: {{\"n\": {i}}}\n\n".encode()
                self.wfile.write(b"%x\r\n%s\r\n" % (len(data), data))
                self.wfile.flush()
                time.sleep(0.3)
            self.wfile.write(b"0\r\n\r\n")
            return
        out = json.dumps({"ok": True, "path": self.path}).encode()
        self.send_response(401 if b"bad" in body else 200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.send_header("x-litellm-model-api-base", "http://192.0.2.1:9999/v1")
        self.send_header("x-litellm-key-spend", "1.0")
        self.send_header("Set-Cookie", "s=1")
        self.end_headers()
        self.wfile.write(out)

    do_GET = do_POST = _go


def _serve(handler):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class Proxy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gw = _serve(FakeGateway)
        fd.Handler.upstream = ("127.0.0.1", cls.gw.server_address[1])
        cls.srv = _serve(fd.Handler)
        cls.port = cls.srv.server_address[1]

    @classmethod
    def tearDownClass(cls):
        for s in (cls.srv, cls.gw):
            s.shutdown()
            s.server_close()

    def setUp(self):
        FakeGateway.seen.clear()

    def req(self, method, target, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {"Authorization": f"Bearer {KEY}"}
        if body is not None:
            h["Content-Type"] = "application/json"
        h.update(headers or {})
        c.putrequest(method, target, skip_accept_encoding=True)
        data = json.dumps(body).encode() if body is not None else None
        for k, v in h.items():
            c.putheader(k, v)
        if data is not None:
            c.putheader("Content-Length", str(len(data)))
        c.endheaders(data)
        r = c.getresponse()
        data = r.read()
        c.close()
        return r, data

    def test_forwarded_with_filtered_headers(self):
        r, b = self.req("POST", "/v1/chat/completions", {"model": "m"},
                        {"x-litellm-customer-id": "bob", "Cookie": "c=1"})
        self.assertEqual(r.status, 200)
        self.assertEqual(json.loads(b)["path"], "/v1/chat/completions")
        self.assertIsNone(r.getheader("x-litellm-model-api-base"))
        self.assertIsNone(r.getheader("x-litellm-key-spend"))
        self.assertIsNone(r.getheader("Set-Cookie"))
        seen = FakeGateway.seen[-1]
        self.assertEqual(seen["headers"]["authorization"], f"Bearer {KEY}")
        self.assertNotIn("x-litellm-customer-id", seen["headers"])
        self.assertNotIn("cookie", seen["headers"])
        self.assertEqual(seen["body"], b'{"model": "m"}')

    def test_upstream_status_passes_through(self):
        r, _ = self.req("POST", "/v1/chat/completions", {"bad": 1})
        self.assertEqual(r.status, 401)

    def test_denied_routes_never_reach_the_gateway(self):
        for method, target in (("GET", "/health"), ("GET", "/model/info"), ("GET", "/v1/model/info"),
                               ("GET", "/key/info"), ("GET", "/user/info"), ("GET", "/%68ealth"),
                               ("GET", "/v1//models"), ("GET", "/v1/models/../../health")):
            with self.subTest(target=target):
                r, b = self.req(method, target)
                self.assertEqual(r.status, 403)
                self.assertIn("ai-frontdoor", json.loads(b)["error"]["message"])
        self.assertEqual(FakeGateway.seen, [])

    def test_no_key_is_401(self):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request("GET", "/v1/models")
        r = c.getresponse()
        r.read()
        self.assertEqual(r.status, 401)
        self.assertEqual(FakeGateway.seen, [])

    def test_streaming_arrives_incrementally(self):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        data = json.dumps({"model": "m", "stream": True}).encode()
        c.request("POST", "/v1/chat/completions", body=data,
                  headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
        r = c.getresponse()
        self.assertEqual(r.getheader("Content-Type"), "text/event-stream")
        self.assertIsNone(r.getheader("x-litellm-model-api-base"))
        t0 = time.time()
        first = r.read1(1024)
        t_first = time.time() - t0
        rest = r.read()
        self.assertIn(b'data: {"n": 0}', first)
        self.assertLess(t_first, 0.25, "first event was held back until the end")
        self.assertIn(b'data: {"n": 2}', first + rest)

    def test_keep_alive_after_a_streamed_reply(self):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
        c.request("POST", "/v1/chat/completions", body=b'{"stream": true}', headers=h)
        c.getresponse().read()
        c.request("GET", "/v1/models", headers={"Authorization": f"Bearer {KEY}"})
        r = c.getresponse()
        self.assertEqual(json.loads(r.read())["path"], "/v1/models")

    def test_body_too_large_is_refused_unread(self):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.putrequest("POST", "/v1/chat/completions")
        c.putheader("Authorization", f"Bearer {KEY}")
        c.putheader("Content-Type", "application/json")
        c.putheader("Content-Length", str(fd.MAX_BODY + 1))
        c.endheaders()
        r = c.getresponse()
        r.read()
        self.assertEqual(r.status, 403)
        self.assertEqual(FakeGateway.seen, [])

    def test_raw_tricks_on_the_wire(self):
        for line in (b"GET /v1/models/../../health HTTP/1.1", b"GET http://ai-gateway:4000/health HTTP/1.1",
                     b"GET /v1/models HTTP/1.0\r\nTransfer-Encoding: chunked", b"GET /%2e%2e/health HTTP/1.1",
                     b"GET /health HTTP/1.1\r\nX-Original-URL: /v1/models"):
            with self.subTest(line=line):
                s = socket.create_connection(("127.0.0.1", self.port), timeout=5)
                s.sendall(line + b"\r\nHost: x\r\nAuthorization: Bearer " + KEY.encode() + b"\r\n\r\n")
                resp = s.recv(4096)
                s.close()
                self.assertTrue(resp.startswith(b"HTTP/1.1 403") or resp.startswith(b"HTTP/1.0 403"), resp[:60])
        self.assertEqual(FakeGateway.seen, [])

    def test_gateway_down_is_502(self):
        old = fd.Handler.upstream
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        fd.Handler.upstream = ("127.0.0.1", s.getsockname()[1])
        s.close()
        try:
            r, b = self.req("GET", "/v1/models")
            self.assertEqual(r.status, 502)
        finally:
            fd.Handler.upstream = old


if __name__ == "__main__":
    unittest.main()
