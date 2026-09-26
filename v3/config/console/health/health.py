"""console-health: the Console's health summary (CONTRACT Phase 3; ADR-010). Stdlib only.

GET /health.json -> {"profile", "checked", "services": [{"id", "name", "status", "ms", "detail"}]}
GET /ping        -> 200 (container healthcheck)

Each service of the running profile is probed over the `lab` network (its own health
endpoint, never through Caddy), at most once per LAB_HEALTH_TTL seconds however often the
page asks. Services the profile does not run are left out, so the page also learns from this
which tiles exist. Caddy serves it at console./health.json behind the forward-auth.
"""
import http.client
import json
import os
import socket
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROFILE = os.environ.get("LAB_PROFILE", "core")
TTL = float(os.environ.get("LAB_HEALTH_TTL", "10"))
TIMEOUT = 3.0
# Profiles in order; a service runs in its profile and every later one (core < engineer < full).
TIERS = {"core": 0, "engineer": 1, "full": 2}

# (id, name, minimum profile, probe). A probe is ("http", url) = any 2xx, or ("tcp", host, port).
SERVICES = (
    ("keycloak", "Keycloak (login)", "core", ("http", "http://keycloak:9000/health/ready")),
    ("trino", "Trino", "core", ("http", "http://trino:8080/v1/info")),
    ("catalog", "Catalog (Lakekeeper)", "core", ("http", "http://lakekeeper:8181/health")),
    ("storage", "Object storage (SeaweedFS)", "core", ("tcp", "seaweedfs", 8333)),
    ("jupyter", "JupyterHub", "core", ("http", "http://jupyterhub:8000/hub/health")),
    # The master and its UI are only on the internal `spark` network (CONTRACT Phase 3), so
    # this probes what users reach on `lab`: Spark Connect, which is healthy only on a cluster
    # with a registered worker (compose/spark.yaml).
    ("spark", "Spark", "engineer", ("tcp", "spark-connect", 15002)),
    ("airflow", "Airflow", "engineer", ("http", "http://airflow-api:8080/api/v2/monitor/health")),
    ("superset", "Superset", "full", ("http", "http://superset:8088/health")),
)


def in_profile(minimum):
    # An unknown (future) profile shows everything rather than hiding services.
    return TIERS.get(PROFILE, max(TIERS.values())) >= TIERS[minimum]


def _ipv4(host):
    # A-record lookup only. A default lookup sends A and AAAA queries in parallel, and when
    # several probes start together a lost reply costs the resolver's 5 s retry timeout.
    return socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_STREAM)[0][4][0]


def probe(spec):
    t0 = time.monotonic()
    try:
        if spec[0] == "tcp":
            with socket.create_connection((_ipv4(spec[1]), spec[2]), timeout=TIMEOUT):
                pass
        else:
            u = urllib.parse.urlsplit(spec[1])
            conn = http.client.HTTPConnection(_ipv4(u.hostname), u.port or 80, timeout=TIMEOUT)
            try:
                conn.request("GET", u.path or "/", headers={"Host": u.netloc})
                r = conn.getresponse()
                r.read(4096)
            finally:
                conn.close()
            if not 200 <= r.status < 300:
                return "down", f"HTTP {r.status}", time.monotonic() - t0
        return "up", None, time.monotonic() - t0
    except (OSError, ValueError, http.client.HTTPException) as e:  # refused, timeout, no name
        if isinstance(e, socket.gaierror):
            detail = "not running"          # no container answers to the service name
        elif isinstance(e, (TimeoutError, socket.timeout)):
            detail = "no answer (timeout)"
        else:
            detail = str(e)[:120] or type(e).__name__
        return "down", detail, time.monotonic() - t0


class Cache:
    def __init__(self):
        self.lock = threading.Lock()
        self.body = b""
        self.at = 0.0
        self.pool = ThreadPoolExecutor(max_workers=len(SERVICES))

    def get(self):
        with self.lock:
            if time.monotonic() - self.at >= TTL or not self.body:
                wanted = [s for s in SERVICES if in_profile(s[2])]
                results = list(self.pool.map(lambda s: probe(s[3]), wanted))
                self.body = json.dumps({
                    "profile": PROFILE,
                    "checked": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "services": [
                        {"id": sid, "name": name, "status": st, "ms": round(dt * 1000),
                         "detail": detail}
                        for (sid, name, _, _), (st, detail, dt) in zip(wanted, results)
                    ],
                }).encode()
                self.at = time.monotonic()
            return self.body


CACHE = Cache()


class Handler(BaseHTTPRequestHandler):
    server_version = "console-health"
    sys_version = ""

    def do_GET(self):
        if self.path == "/ping":
            body, ctype = b"ok\n", "text/plain"
        elif self.path.split("?", 1)[0] == "/health.json":
            body, ctype = CACHE.get(), "application/json"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # quiet: the page polls
        pass


if __name__ == "__main__":
    print(f"[console-health] profile {PROFILE}; serving :8080/health.json", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
