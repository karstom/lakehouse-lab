"""docker-guard: the ONE place that decides which Docker API requests JupyterHub may make
(CONTRACT "Docker access"; INV_V3_DOCKER_PROXY_PROJECT_SCOPE). Python stdlib only.

    jupyterhub --(hub-docker)--> docker-guard --(docker-api)--> docker-socket-proxy --> socket

The Docker daemon decodes request bodies with Go's encoding/json: keys match struct fields
CASE-INSENSITIVELY, `\\u` escapes are decoded, and the LAST of duplicate keys wins. Regexes
over the raw bytes (the socket proxy's old body ACLs) see none of that, so `"binds"`,
`"\\u004dounts"` or a second `"Mounts"` key reached Docker unchecked. This guard therefore
never forwards what it received. For every request it:

1. matches the method and path against the exact calls DockerSpawner (docker-py) makes, with
   containers and volumes addressed by NAME in this project's scope (never by id);
2. parses a body with a strict decoder (UTF-8 only; no duplicate keys at any level; no
   NaN/Infinity; no lone surrogates or NUL characters);
3. validates it against an allowlist in which every key at every level must be EXACTLY one
   canonical spelling (anything unknown, or differently cased, is refused), and every value
   is checked (image, name, labels, binds, mounts, network, limits);
4. RE-SERIALIZES the validated object (json.dumps) and forwards only those bytes, with their
   own Content-Length, and a query string rebuilt from validated values.

Docker therefore only ever sees bytes the guard produced from values it checked. Anything
else gets 403 and one log line with a short reason (never a body: it holds the user's
server token). The socket proxy behind the guard keeps its method/path allowlist; it has no
body rules any more, so this module is the single source of the body policy.

Run: python3 -m bootstrap.docker_guard (compose service `docker-guard`). The pure function
`decide()` is what tests/bootstrap/test_docker_guard.py exercises.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import logging
import os
import re
import sys
import urllib.parse
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger("docker-guard")

MAX_BODY = 256 * 1024                  # a DockerSpawner create body is ~2-4 KiB
MAX_RESPONSE = 32 * 1024 * 1024        # inspect answers are a few KiB
CLIENT_TIMEOUT = 60                    # s: request read / idle keep-alive
UPSTREAM_TIMEOUT = 120                 # s: `stop` waits for the container (default t=10)

HOME = "/home/jovyan"
DAGS_MOUNT = "/home/jovyan/airflow-dags"
# The DAG folder is the raw username (jupyterhub_config.py DAGS_USER_NAME_RE, the Airflow
# policy's USERNAME_RE): one path segment, never "." or "..".
DAGS_USER_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,62}")
# DockerSpawner's escaped username (escapism, safe chars a-z0-9, escape char "-", lowered):
# every other character is "-" plus two hex digits. So "x-postgres-1" is never a valid tail.
ESCAPED_RE = re.compile(r"(?:[a-z0-9]|-[0-9a-f]{2}){1,190}")
VERSION_RE = r"(?P<ver>/v1\.[0-9]{1,3})?"
PATH_CHARS = re.compile(r"/[A-Za-z0-9/._:@-]*")
QUERY_CHARS = re.compile(r"[A-Za-z0-9=&._-]*")
FALSE_VALUES = {"0", "false", "False"}
BOOL_VALUES = FALSE_VALUES | {"1", "true", "True"}


class Reject(Exception):
    """Refused request; the message is the short, secret-free reason that is logged."""


@dataclass(frozen=True)
class Policy:
    project: str             # COMPOSE_PROJECT_NAME
    workspace_image: str     # the image reference DockerSpawner uses (LAB_WORKSPACE_IMAGE)
    mem_limit: int           # bytes (WORKSPACE_MEM)
    cpus: float              # WORKSPACE_CPUS

    @property
    def labels(self):
        return {"com.docker.compose.project": self.project, "lab.role": "workspace"}

    @property
    def lab_network(self):
        return f"{self.project}_lab"

    @property
    def trust_volume(self):
        return f"{self.project}_trust"

    @property
    def dags_volume(self):
        return f"{self.project}_dags-user"

    def container(self, esc):
        return f"{self.project}-ws-{esc}"

    def home_volume(self, esc):
        return f"{self.project}-home-{esc}"

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env

        def need(name):
            v = env.get(name, "").strip()
            if not v:
                raise SystemExit(f"docker-guard: missing required environment variable {name}")
            return v
        project = need("LAB_PROJECT")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", project):
            raise SystemExit(f"docker-guard: bad LAB_PROJECT {project!r}")
        return cls(project=project, workspace_image=need("LAB_WORKSPACE_IMAGE"),
                   mem_limit=parse_bytes(need("WORKSPACE_MEM")),
                   cpus=float(need("WORKSPACE_CPUS")))


def parse_bytes(text):
    """Compose/DockerSpawner-style size ("1536m", "2G", "1073741824") -> bytes (1024-based,
    as DockerSpawner's ByteSpecification)."""
    m = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*([kKmMgGtT]?)[bB]?\s*", text or "")
    if not m:
        raise SystemExit(f"docker-guard: bad size {text!r}")
    mult = 1024 ** " KMGT".index(m.group(2).upper() or " ")
    return int(float(m.group(1)) * mult)


def escape_username(name):
    """DockerSpawner's container/volume name escaping (escapism.escape with safe chars a-z0-9
    and escape char '-', then lower())."""
    out = []
    for ch in name:
        if ch in "abcdefghijklmnopqrstuvwxyz0123456789":
            out.append(ch)
        else:
            out.extend(f"-{b:02X}" for b in ch.encode("utf-8"))
    return "".join(out).lower()


# ---------------------------------------------------------------- strict JSON
def _no_duplicates(pairs):
    obj = {}
    for k, v in pairs:
        if k in obj:
            raise Reject(f"duplicate key {k!r}")
        obj[k] = v
    return obj


def _no_constant(name):
    raise Reject(f"non-JSON number {name}")


def _check_strings(v, depth=0):
    """Lone surrogates (\\ud800) decode differently in Go (U+FFFD) than in Python, and NUL
    has no business in any Docker field: refuse both, in keys and values."""
    if depth > 32:
        raise Reject("JSON nested too deep")
    if isinstance(v, str):
        if "\x00" in v or any("\ud800" <= c <= "\udfff" for c in v):
            raise Reject("invalid character in a string")
    elif isinstance(v, dict):
        for k, x in v.items():
            _check_strings(k, depth + 1)
            _check_strings(x, depth + 1)
    elif isinstance(v, list):
        for x in v:
            _check_strings(x, depth + 1)


def strict_loads(raw):
    """bytes -> JSON object, refusing everything Go and Python could read differently."""
    if len(raw) > MAX_BODY:
        raise Reject("body too large")
    try:
        text = raw.decode("utf-8")               # strict: invalid UTF-8 raises
    except UnicodeDecodeError:
        raise Reject("body is not UTF-8") from None
    try:
        obj = json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_no_constant)
    except Reject:
        raise
    except (ValueError, RecursionError):
        raise Reject("body is not valid JSON") from None
    if not isinstance(obj, dict):
        raise Reject("body is not a JSON object")
    _check_strings(obj)
    return obj


def canonical(obj):
    """The only bytes ever forwarded to Docker for a body."""
    return json.dumps(obj, ensure_ascii=True, separators=(",", ":"), sort_keys=True,
                      allow_nan=False).encode("ascii")


# ---------------------------------------------------------------- value validators
# Each takes (value, where) and returns the validated value (the same data), or raises.
def _obj(value, where, required, optional=None):
    if not isinstance(value, dict):
        raise Reject(f"{where} must be an object")
    optional = optional or {}
    for k in value:
        if k not in required and k not in optional:
            raise Reject(f"{where}: key {k!r} is not allowed")
    out = {}
    for k, check in required.items():
        if k not in value:
            raise Reject(f"{where}: {k} is required")
        out[k] = check(value[k], f"{where}.{k}")
    for k, check in optional.items():
        if k in value:
            out[k] = check(value[k], f"{where}.{k}")
    return out


def _eq(expected):
    def check(v, where):
        if type(v) is not type(expected) or v != expected:
            raise Reject(f"{where} is not the allowed value")
        return v
    return check


def _false(v, where):
    if v is not False:
        raise Reject(f"{where} must be false")
    return v


def _bool(v, where):
    if not isinstance(v, bool):
        raise Reject(f"{where} must be a boolean")
    return v


def _empty(v, where):
    """Absent-equivalent only: null, [], {} or ""."""
    if v not in (None, [], {}, ""):
        raise Reject(f"{where} must be empty")
    return v


def _empty_obj(v, where):
    if v is not None and v != {}:
        raise Reject(f"{where} must be empty")
    return v


def _int(lo, hi):
    def check(v, where):
        if type(v) is not int or not lo <= v <= hi:
            raise Reject(f"{where} must be an integer in [{lo}, {hi}]")
        return v
    return check


def _str_list(max_items, max_len=65536, item=None):
    def check(v, where):
        if not isinstance(v, list) or len(v) > max_items:
            raise Reject(f"{where} must be a list of at most {max_items} strings")
        for i, s in enumerate(v):
            if not isinstance(s, str) or len(s) > max_len:
                raise Reject(f"{where}[{i}] must be a string")
            if item:
                item(s, f"{where}[{i}]")
        return v
    return check


def _env_item(s, where):
    if not re.match(r"[A-Za-z_][A-Za-z0-9_]*=", s):
        raise Reject(f"{where} is not NAME=value")


# ---------------------------------------------------------------- request bodies
def validate_create(policy, esc, body):
    """A container-create body as DockerSpawner/docker-py sends it (captured from real
    traffic, PHASE4_RESULTS "docker-guard"), for the workspace of the user whose escaped
    name is `esc`. -> validated object (equal to the input), or Reject."""
    home_bind = f"{policy.home_volume(esc)}:{HOME}:rw"
    trust_bind = f"{policy.trust_volume}:/trust:ro"
    targets = {HOME: {}, "/trust": {}}

    def binds(v, where):
        _str_list(2)(v, where)
        if sorted(v) != sorted([home_bind, trust_bind]):
            raise Reject(f"{where} must be exactly the user's home and the trust volume")
        return v

    def volumes(v, where):
        if v != targets or any(type(x) is not dict for x in v.values()):
            raise Reject(f"{where} must list exactly the bind targets")
        return v

    def mount(v, where):
        m = _obj(v, where,
                 {"Target": _str, "Source": _eq(policy.dags_volume), "Type": _eq("volume"),
                  "VolumeOptions": lambda o, w: _obj(o, w, {"Subpath": _str})},
                 {"ReadOnly": _bool})
        user = m["VolumeOptions"]["Subpath"]
        if not DAGS_USER_RE.fullmatch(user) or escape_username(user) != esc:
            raise Reject(f"{where}: the DAG folder is not this workspace's user")
        if m["Target"] != f"{DAGS_MOUNT}/{user}":
            raise Reject(f"{where}.Target is not ~/airflow-dags/<user>")
        return m

    def mounts(v, where):
        if not isinstance(v, list) or len(v) > 1:
            raise Reject(f"{where} may hold at most the user's own DAG folder")
        return [mount(m, f"{where}[{i}]") for i, m in enumerate(v)]

    def exposed(v, where):
        if not isinstance(v, dict) or len(v) > 1 or any(
                not re.fullmatch(r"[0-9]{1,5}/tcp", k) or x not in (None, {}) for k, x in v.items()):
            raise Reject(f"{where} may expose one tcp port")
        return v

    def networking(v, where):
        return _obj(v, where, {}, {"EndpointsConfig": lambda o, w: _obj(
            o, w, {}, {policy.lab_network: _empty_obj})})

    def host_config(v, where):
        hc = _obj(v, where,
                  {"NetworkMode": _eq(policy.lab_network),
                   "Binds": binds,
                   "Memory": _int(1, policy.mem_limit),
                   "CpuPeriod": _int(1000, 1_000_000),
                   "CpuQuota": _int(1000, 1_000_000 * 1024)},
                  {"AutoRemove": _bool, "Links": _empty, "Mounts": mounts,
                   "Privileged": _false, "CapAdd": _empty, "Devices": _empty,
                   "PidMode": _empty, "IpcMode": _empty, "UTSMode": _empty,
                   "UsernsMode": _empty})
        if hc["CpuQuota"] > int(policy.cpus * hc["CpuPeriod"]):
            raise Reject(f"{where}.CpuQuota is above the workspace CPU limit")
        return hc

    return _obj(body, "body",
                {"Image": _eq(policy.workspace_image),
                 "Cmd": _str_list(64),
                 "Env": _str_list(512, item=_env_item),
                 "HostConfig": host_config,
                 "Labels": _eq(policy.labels)},
                {"ExposedPorts": exposed, "Volumes": volumes,
                 "Tty": _false, "OpenStdin": _false, "StdinOnce": _false, "AttachStdin": _false,
                 "AttachStdout": _bool, "AttachStderr": _bool, "NetworkDisabled": _false,
                 "NetworkingConfig": networking})


def _str(v, where):
    if not isinstance(v, str):
        raise Reject(f"{where} must be a string")
    return v


def validate_volume_create(policy, body):
    """Only a user's home volume, with the lab labels (docker-py create_volume)."""
    def name(v, where):
        prefix = policy.home_volume("")
        if not isinstance(v, str) or not v.startswith(prefix) \
                or not ESCAPED_RE.fullmatch(v[len(prefix):]):
            raise Reject(f"{where} is not <project>-home-<user>")
        return v
    return _obj(body, "body", {"Name": name, "Labels": _eq(policy.labels)})


# ---------------------------------------------------------------- routing
def _query(qs, allowed):
    """Strict query parsing: each allowed key at most once, nothing else."""
    if not QUERY_CHARS.fullmatch(qs):
        raise Reject("query has characters outside [A-Za-z0-9=&._-]")
    try:
        pairs = urllib.parse.parse_qsl(qs, keep_blank_values=True, strict_parsing=True) if qs else []
    except ValueError:
        raise Reject("malformed query") from None
    out = {}
    for k, v in pairs:
        if k not in allowed:
            raise Reject(f"query parameter {k!r} is not allowed")
        if k in out:
            raise Reject(f"query parameter {k!r} given twice")
        out[k] = v
    return out


def decide(policy, method, target, body):
    """(method, request-target, raw body bytes) -> (path to forward, body bytes or None).
    Raises Reject for anything that is not one of DockerSpawner's calls in this project's
    scope. Pure: no I/O."""
    path, sep, qs = target.partition("?")
    if "#" in target or not PATH_CHARS.fullmatch(path):
        raise Reject("path has characters outside [A-Za-z0-9/._:@-]")
    P = re.escape(policy.project)
    esc = r"(?P<esc>(?:[a-z0-9]|-[0-9a-f]{2}){1,190})"

    def route(pattern):
        return re.fullmatch(VERSION_RE + pattern, path)

    def no_body():
        if body:
            raise Reject("unexpected request body")

    def json_body():
        if not body:
            raise Reject("missing request body")
        return strict_loads(body)

    if method == "GET":
        no_body()
        if route(r"/(?:_ping|version)") or route(rf"/containers/{P}-ws-{esc}/json") \
                or route(rf"/volumes/{P}-home-{esc}"):
            _query(qs, ())
            return path, None
        m = route(r"/images/(?P<img>.+)/json")
        if m and m.group("img") == policy.workspace_image:
            _query(qs, ())
            return path, None
    elif method == "POST":
        m = route(r"/containers/create")
        if m:
            q = _query(qs, ("name",))
            prefix = policy.container("")
            name = q.get("name", "")
            if not name.startswith(prefix) or not ESCAPED_RE.fullmatch(name[len(prefix):]):
                raise Reject("container name is not <project>-ws-<user>")
            out = canonical(validate_create(policy, name[len(prefix):], json_body()))
            return f"{path}?{urllib.parse.urlencode({'name': name})}", out
        if route(r"/volumes/create"):
            _query(qs, ())
            return path, canonical(validate_volume_create(policy, json_body()))
        if route(rf"/containers/{P}-ws-{esc}/start"):
            no_body()
            _query(qs, ())
            return path, None
        if route(rf"/containers/{P}-ws-{esc}/stop"):
            no_body()
            q = _query(qs, ("t",))
            if "t" in q:
                if not re.fullmatch(r"[0-9]{1,3}", q["t"]) or int(q["t"]) > 600:
                    raise Reject("stop timeout must be 0-600")
                return f"{path}?t={int(q['t'])}", None
            return path, None
    elif method == "DELETE":
        if route(rf"/containers/{P}-ws-{esc}"):
            no_body()
            q = _query(qs, ("v", "link", "force"))
            if any(v not in BOOL_VALUES for v in q.values()):
                raise Reject("boolean query value expected")
            if q.get("link", "0") not in FALSE_VALUES or q.get("force", "0") not in FALSE_VALUES:
                raise Reject("link/force removal is not allowed")
            v = "1" if q.get("v", "0") not in FALSE_VALUES else "0"
            return f"{path}?v={v}", None
    raise Reject("not a DockerSpawner call in this lab's scope")


# ---------------------------------------------------------------- HTTP server
RESPONSE_HEADERS = ("Content-Type", "Api-Version", "Docker-Experimental", "Ostype", "Server")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "docker-guard"
    sys_version = ""
    timeout = CLIENT_TIMEOUT
    policy: Policy = None
    upstream = ("docker-proxy", 2375)

    def log_message(self, fmt, *args):      # http.server's own access log: off (we log below)
        pass

    def _where(self):
        return repr(self.path[:200])

    def _reply(self, status, payload, headers=()):
        self.send_response(status)
        for k, v in headers:
            self.send_header(k, v)
        if not any(k.lower() == "content-type" for k, _ in headers):
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _deny(self, reason, close=False):
        log.warning("deny %s %s: %s", self.command, self._where(), reason)
        if close:
            self.close_connection = True
        self._reply(403, json.dumps({"message": f"docker-guard: {reason}"}).encode())

    def _read_body(self):
        if self.headers.get("Transfer-Encoding") is not None:
            raise Reject("chunked request bodies are not accepted")
        lengths = self.headers.get_all("Content-Length") or []
        if len(lengths) > 1:
            raise Reject("more than one Content-Length")
        if not lengths:
            return b""
        if not re.fullmatch(r"[0-9]{1,9}", lengths[0].strip()):
            raise Reject("bad Content-Length")
        n = int(lengths[0])
        if n > MAX_BODY:
            raise Reject("body too large")
        data = self.rfile.read(n)
        if len(data) != n:
            raise Reject("short body")
        return data

    def _handle(self):
        try:
            body = self._read_body()
        except Reject as e:
            return self._deny(str(e), close=True)
        try:
            path, out = decide(self.policy, self.command, self.path, body)
        except Reject as e:
            return self._deny(str(e))
        headers = {"Host": "docker"}
        if out is not None:
            headers["Content-Type"] = "application/json"
        conn = http.client.HTTPConnection(*self.upstream, timeout=UPSTREAM_TIMEOUT)
        try:
            conn.request(self.command, path, body=out, headers=headers)
            resp = conn.getresponse()
            data = resp.read(MAX_RESPONSE + 1)
            if len(data) > MAX_RESPONSE:
                raise OSError("upstream response too large")
            status = resp.status
            fwd = [(k, v) for k, v in resp.getheaders() if k.title() in RESPONSE_HEADERS
                   or k in RESPONSE_HEADERS]
        except (OSError, http.client.HTTPException) as e:
            log.error("upstream error for %s %s: %s", self.command, self._where(), e)
            self.close_connection = True
            return self._reply(502, json.dumps({"message": "docker-guard: upstream error"}).encode())
        finally:
            conn.close()
        if out is not None:
            log.info("allow %s %s -> %d; forwarded canonical body sha256=%s bytes=%d",
                     self.command, repr(path[:200]), status, hashlib.sha256(out).hexdigest(), len(out))
        else:                                   # the healthcheck pings every 5 s: debug
            log.log(logging.DEBUG if path.endswith("/_ping") else logging.INFO,
                    "allow %s %s -> %d", self.command, repr(path[:200]), status)
        self._reply(status, data, fwd)

    do_GET = do_POST = do_DELETE = do_PUT = do_HEAD = do_PATCH = do_OPTIONS = _handle


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 64


def main(argv=None):
    logging.basicConfig(level=os.environ.get("LAB_DOCKER_GUARD_LOG_LEVEL", "INFO").upper(),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout)
    Handler.policy = Policy.from_env()
    host, _, port = os.environ.get("LAB_DOCKER_GUARD_UPSTREAM", "docker-proxy:2375").rpartition(":")
    Handler.upstream = (host, int(port))
    listen = int(os.environ.get("LAB_DOCKER_GUARD_PORT", "2375"))
    srv = Server(("0.0.0.0", listen), Handler)
    p = Handler.policy
    log.info("listening on :%d -> %s:%d; project %s, image %s, memory <= %d, cpus <= %s",
             listen, host, int(port), p.project, p.workspace_image, p.mem_limit, p.cpus)
    srv.serve_forever()


if __name__ == "__main__":
    main()
