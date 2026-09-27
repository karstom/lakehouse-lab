"""ai-frontdoor: the ONE way workspaces reach the AI gateway, and the single source of truth
for which gateway routes a user key may call (CONTRACT Phase 5, "AI front door";
INV_V3_AI_FRONTDOOR_ONLY_USER_PATH). Python stdlib only; runs on the bootstrap image.

    workspace --(lab)--> ai-frontdoor:4000 --(ai)--> ai-gateway:4000 (LiteLLM) --> providers

Why it exists: LiteLLM (the MIT build has no `admin_only_routes`) lets any virtual key call
routes the lab never meant users to have. `GET /health` sends a real request to every
configured model (no budget charge: a free way to load a local GPU server), and
`/model/info` / `/v1/model/info` reveal each deployment's `api_base` (e.g. the host:port of
the owner's model server). So the gateway sits on the `ai` network, which workspaces are
not on, and this proxy, on both `lab` and `ai`, forwards only the calls the lab's clients
make. The allowlist was derived from their real traffic (PHASE5_RESULTS "AI front door"):

  client                         calls
  Jupyter AI "Lab Assistant"     POST /v1/chat/completions (streaming)
  lab-ai status                  GET /v1/models, GET /v2/user/info (own user: spend, budget)
  MCP agent loop (check 18)      GET /v1/models, POST /v1/chat/completions
  Claude Code (lab-ai opt-in)    POST /v1/messages?beta=true, POST /v1/messages/count_tokens?beta=true
  OpenAI-compatible clients      POST /chat/completions (base URL without /v1), POST /v1/embeddings

For every request the proxy:
1. validates the request-target: only [A-Za-z0-9/_.-] in the path (so no %-encoding,
   backslash, `;`, absolute-form or `*`), no empty, `.` or `..` segment (no `//`, no trailing
   `/`), and an EXACT, case-sensitive (method, path) match in ROUTES; the query string may
   hold only the keys and values ROUTES lists for that route, and is rebuilt from them;
2. requires `Authorization: Bearer sk-...` (the user's own gateway key);
3. reads a POST body only with a single Content-Length (no chunked uploads), at most
   MAX_BODY bytes, Content-Type application/json; a GET must have no body;
4. forwards only REQUEST_HEADERS (so hop-by-hop headers and LiteLLM's own control headers,
   e.g. customer-id / tag headers, never reach the gateway) and returns only
   RESPONSE_HEADERS (LiteLLM's `x-litellm-*` headers, which include the model's api_base,
   never reach the user);
5. streams the response as it arrives (SSE for `stream: true`), re-chunked when the gateway
   sends no Content-Length.
Anything else gets 403 (401 without a key) and one log line with a short reason; the
gateway never sees it. Bodies and keys are never logged.

Run: python3 -m bootstrap.ai_frontdoor (compose service `ai-frontdoor`, compose/ai.yaml).
`decide()` and the handler are exercised by tests/ai/test_ai_frontdoor.py.
"""
from __future__ import annotations

import http.client
import json
import logging
import os
import re
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger("ai-frontdoor")

# (method, path) -> {query key: allowed values}. The ONLY routes a user key may use.
ROUTES = {
    ("POST", "/v1/chat/completions"): {},
    ("POST", "/chat/completions"): {},
    ("POST", "/v1/messages"): {"beta": ("true",)},
    ("POST", "/v1/messages/count_tokens"): {"beta": ("true",)},
    ("POST", "/v1/embeddings"): {},
    ("GET", "/v1/models"): {},
    # The caller's own user row (spend, max_budget, budget_reset_at): LiteLLM's lightweight
    # v2 endpoint without `user_id` looks up the key's own user and returns no keys or teams.
    ("GET", "/v2/user/info"): {},
}
# Request headers passed on (lower-case). Everything else is dropped: hop-by-hop headers,
# Cookie, X-Forwarded-*, and every LiteLLM control header (x-litellm-*, customer-id headers).
REQUEST_HEADERS = ("authorization", "content-type", "accept", "user-agent",
                   "anthropic-version", "anthropic-beta")
# Response headers passed back. Not LiteLLM's x-litellm-* (x-litellm-model-api-base names the
# provider's URL) nor anything that describes the upstream connection.
RESPONSE_HEADERS = ("content-type", "cache-control", "retry-after")

PATH_RE = re.compile(r"/[A-Za-z0-9/_.-]{0,255}")
QUERY_RE = re.compile(r"[A-Za-z0-9=&_.-]{0,256}")
KEY_RE = re.compile(r"Bearer sk-[A-Za-z0-9_-]{8,256}")
HEADER_VALUE_RE = re.compile(r"[\x20-\x7e]{0,4096}")
JSON_TYPE_RE = re.compile(r"application/json(\s*;.*)?", re.I)

MAX_BODY = int(os.environ.get("LAB_AI_FRONTDOOR_MAX_BODY", str(16 * 1024 * 1024)))
MAX_CONCURRENT = int(os.environ.get("LAB_AI_FRONTDOOR_MAX_CONCURRENT", "64"))
CLIENT_TIMEOUT = 60                     # s: reading the request / idle keep-alive
# s: one read from the gateway; a model may think for minutes (LAB_AI_REQUEST_TIMEOUT).
UPSTREAM_TIMEOUT = int(os.environ.get("LAB_AI_REQUEST_TIMEOUT") or 600) + 30
CHUNK = 64 * 1024


class Reject(Exception):
    """Refused request. `status` 403 (not an allowed call) or 401 (no key); the message is
    the short, secret-free reason that is logged and returned."""

    def __init__(self, reason, status=403):
        super().__init__(reason)
        self.status = status


def decide(method, target):
    """(method, request-target) -> the canonical target to forward. Raises Reject. Pure."""
    path, sep, qs = target.partition("?")
    if not PATH_RE.fullmatch(path):
        raise Reject("path has characters outside [A-Za-z0-9/_.-]")
    if any(seg in ("", ".", "..") for seg in path[1:].split("/")):
        raise Reject("empty, '.' or '..' path segment")
    allowed = ROUTES.get((method, path))
    if allowed is None:
        raise Reject("not an AI route the lab allows")
    if not sep:
        return path
    if not QUERY_RE.fullmatch(qs):
        raise Reject("query has characters outside [A-Za-z0-9=&_.-]")
    try:
        pairs = urllib.parse.parse_qsl(qs, keep_blank_values=True, strict_parsing=bool(qs))
    except ValueError:
        raise Reject("malformed query") from None
    seen = {}
    for k, v in pairs:
        if k in seen or v not in allowed.get(k, ()):
            raise Reject("query parameter not allowed")
        seen[k] = v
    return path + ("?" + urllib.parse.urlencode(seen) if seen else "")


def check_headers(method, headers):
    """-> (headers to forward {Name: value}, body length). Raises Reject. Pure."""
    auth = headers.get_all("Authorization") or []
    if len(auth) != 1 or not KEY_RE.fullmatch(auth[0].strip()):
        raise Reject("an AI key is required (Authorization: Bearer sk-...)", 401)
    if headers.get("Transfer-Encoding") is not None:
        raise Reject("chunked request bodies are not accepted")
    lengths = headers.get_all("Content-Length") or []
    if len(lengths) > 1:
        raise Reject("more than one Content-Length")
    n = 0
    if lengths:
        if not re.fullmatch(r"[0-9]{1,10}", lengths[0].strip()):
            raise Reject("bad Content-Length")
        n = int(lengths[0])
    if method == "GET" and n:
        raise Reject("unexpected request body")
    if method == "POST":
        if not lengths:
            raise Reject("Content-Length required")
        if n > MAX_BODY:
            raise Reject(f"request body larger than {MAX_BODY} bytes")
        if not JSON_TYPE_RE.fullmatch((headers.get("Content-Type") or "").strip()):
            raise Reject("Content-Type must be application/json")
    out = {}
    for name in REQUEST_HEADERS:
        vals = headers.get_all(name) or []
        if len(vals) > 1:
            raise Reject(f"more than one {name} header")
        if vals:
            if not HEADER_VALUE_RE.fullmatch(vals[0]):
                raise Reject(f"bad {name} header")
            out[name.title()] = vals[0].strip()
    return out, n


def _error(message, status):
    kind = {401: "authentication_error", 403: "forbidden", 413: "request_too_large",
            502: "gateway_unavailable", 503: "busy"}.get(status, "error")
    return json.dumps({"error": {"message": f"ai-frontdoor: {message}", "type": kind,
                                 "code": status}}).encode()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "lab-ai-frontdoor"
    sys_version = ""
    timeout = CLIENT_TIMEOUT
    upstream = ("ai-gateway", 4000)
    slots = threading.BoundedSemaphore(MAX_CONCURRENT)

    def log_message(self, fmt, *args):      # http.server's own access log: off (we log below)
        pass

    def _where(self):
        return repr(self.path[:120])

    def _reply(self, status, payload, close=False):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        if close:
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        self.wfile.write(payload)

    def _deny(self, reason, status=403, close=False):
        log.warning("deny %s %s -> %d: %s", self.command[:10], self._where(), status, reason)
        self._reply(status, _error(reason, status), close=close)

    def _handle(self):
        t0 = time.time()
        try:
            target = decide(self.command, self.path)
        except Reject as e:
            # The body (if any) is not read: close so it is never taken for a next request.
            return self._deny(str(e), e.status, close=True)
        try:
            headers, n = check_headers(self.command, self.headers)
        except Reject as e:
            return self._deny(str(e), e.status, close=True)
        body = self.rfile.read(n) if n else None
        if n and len(body) != n:
            self.close_connection = True
            return log.warning("short body for %s %s", self.command, target)
        if not self.slots.acquire(blocking=False):
            return self._deny("too many requests in flight; retry shortly", 503)
        try:
            self._forward(target, headers, body, t0)
        finally:
            self.slots.release()

    def _forward(self, target, headers, body, t0):
        headers["Host"] = f"{self.upstream[0]}:{self.upstream[1]}"
        headers["Accept-Encoding"] = "identity"
        if body is not None:
            headers["Content-Length"] = str(len(body))
        conn = http.client.HTTPConnection(*self.upstream, timeout=UPSTREAM_TIMEOUT)
        sent = 0
        try:
            try:
                conn.request(self.command, target, body=body, headers=headers)
                resp = conn.getresponse()
            except (OSError, http.client.HTTPException) as e:
                log.error("upstream error for %s %s: %s", self.command, target, type(e).__name__)
                return self._reply(502, _error("the AI gateway is not reachable", 502), close=True)
            length = resp.getheader("Content-Length")
            self.send_response(resp.status)
            for k, v in resp.getheaders():
                if k.lower() in RESPONSE_HEADERS:
                    self.send_header(k, v)
            chunked = length is None
            if chunked:
                self.send_header("Transfer-Encoding", "chunked")
            else:
                self.send_header("Content-Length", length)
            self.end_headers()
            while True:
                data = resp.read1(CHUNK)
                if not data:
                    break
                sent += len(data)
                if chunked:
                    self.wfile.write(b"%x\r\n%s\r\n" % (len(data), data))
                else:
                    self.wfile.write(data)
                self.wfile.flush()
            if chunked:
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            log.info("allow %s %s -> %d (%d bytes, %.1f s)", self.command, target, resp.status,
                     sent, time.time() - t0)
        except (OSError, http.client.HTTPException) as e:
            # Headers are out: the only honest signal left is to drop the connection.
            log.error("stream error for %s %s after %d bytes: %s", self.command, target, sent,
                      type(e).__name__)
            self.close_connection = True
        finally:
            conn.close()

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = _handle

    def send_error(self, code, message=None, explain=None):
        # http.server's own errors (bad request line, oversized headers, unknown method):
        # JSON like ours, never an HTML page.
        self._reply(code, _error(message or "bad request", code), close=True)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 128


def main(argv=None):
    logging.basicConfig(level=os.environ.get("LAB_AI_FRONTDOOR_LOG_LEVEL", "INFO").upper(),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout)
    host, _, port = os.environ.get("LAB_AI_FRONTDOOR_UPSTREAM", "ai-gateway:4000").rpartition(":")
    Handler.upstream = (host, int(port))
    listen = int(os.environ.get("LAB_AI_FRONTDOOR_PORT", "4000"))
    srv = Server(("0.0.0.0", listen), Handler)
    log.info("listening on :%d -> %s:%d; %d routes: %s; max body %d bytes", listen, host, int(port),
             len(ROUTES), ", ".join(f"{m} {p}" for m, p in ROUTES), MAX_BODY)
    srv.serve_forever()


if __name__ == "__main__":
    main()
