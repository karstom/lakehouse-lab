"""Smoke check 11: JupyterHub's Docker access refuses everything outside this lab's scope.

Runs INSIDE the jupyterhub container (the only client of docker-guard) via
`docker compose exec -T jupyterhub python3 - < proxy_probe.py`, against $DOCKER_HOST
(tcp://docker-guard:2375; the guard forwards to the socket proxy).

Side-effect free even if a rule were wrong: every container create uses the real workspace
image but `Memory: 4` bytes, below Docker's 6 MB minimum, so Docker answers
400 "Minimum memory limit allowed is 6MB" before it creates anything (the guard allows any
Memory up to WORKSPACE_MEM). Volume creates use a nonexistent driver. So:
  - a refused case must get 403 from the guard (or from the socket proxy);
  - an allowed case must get Docker's 400 with that message: it passed the guard and the
    proxy and reached the daemon.
The last allowed case is sent with \\u-escaped keys, shuffled keys and odd whitespace; the
probe prints the sha256 of the canonical JSON the guard should forward for it
(`canonical_sha256`), and tests/smoke/run.sh requires that exact hash in the guard's log
("forwarded canonical body sha256=..."): Docker received the guard's bytes, not ours.
Prints one JSON line; exit 0 only if every case got the expected answer.
"""
import hashlib
import http.client
import json
import os
import socket
import sys

P = os.environ["COMPOSE_PROJECT_NAME"]
IMG = os.environ["LAB_WORKSPACE_IMAGE"]
HOST = os.environ.get("DOCKER_HOST", "tcp://docker-guard:2375").split("//")[-1]
NOIMG = "lakehouse-lab/proxy-probe-no-such-image:none"
USER = "proxyprobe"
WS = f"{P}-ws-{USER}"
TINY = 4                      # bytes: Docker refuses (400) before creating anything
CPU_QUOTA = int(float(os.environ.get("WORKSPACE_CPUS", "1")) * 100000)   # as DockerSpawner
MIN_MEM = "Minimum memory limit"
POSTGRES = f"{P}_postgres-data"   # a real volume of this project that no workspace may mount
DAGS = f"{P}_dags-user"
home, trust = f"{P}-home-{USER}:/home/jovyan:rw", f"{P}_trust:/trust:ro"


def raw_req(method, path, text=None):
    c = http.client.HTTPConnection(*HOST.split(":"), timeout=30)
    body = text.encode("utf-8") if isinstance(text, str) else text
    c.request(method, path, body=body, headers={"Content-Type": "application/json"})
    r = c.getresponse()
    data = r.read()
    c.close()
    try:
        msg = json.loads(data).get("message", "")
    except (ValueError, AttributeError):
        msg = data[:200].decode("utf-8", "replace")
    return r.status, msg


def req(method, path, body=None):
    return raw_req(method, path, json.dumps(body) if body is not None else None)


def dag_mount(user=USER, source=DAGS, subpath=None, target=None):
    """One Mounts entry as docker-py writes it (docker.types.Mount)."""
    m = {"Target": target or f"/home/jovyan/airflow-dags/{user}", "Source": source,
         "Type": "volume", "ReadOnly": False}
    sp = user if subpath is None else subpath
    if sp:
        m["VolumeOptions"] = {"Subpath": sp}
    return m


def body(binds=(home, trust), net=f"{P}_lab", mounts=None, image=IMG, host=None, extra=None):
    """A create body shaped like DockerSpawner's (docker-py 7.2), Memory TINY."""
    hc = {"Memory": TINY, "NetworkMode": net, "Binds": list(binds), "Links": [],
          "CpuQuota": CPU_QUOTA, "CpuPeriod": 100000, "AutoRemove": True}
    if mounts is not None:
        hc["Mounts"] = mounts
    hc.update(host or {})
    b = {"ExposedPorts": {"8888/tcp": None}, "Tty": False, "OpenStdin": False,
         "StdinOnce": False, "AttachStdin": False, "AttachStdout": True, "AttachStderr": True,
         "Env": ["LAB_PROBE=1"], "Cmd": ["jupyterhub-singleuser"], "Image": image,
         "Volumes": {"/home/jovyan": {}, "/trust": {}}, "NetworkDisabled": False,
         "HostConfig": hc, "Labels": {"com.docker.compose.project": P, "lab.role": "workspace"}}
    b.update(extra or {})
    return b


def create(b, name=WS):
    return req("POST", f"/containers/create?name={name}", b)


def create_raw(text, name=WS):
    return raw_req("POST", f"/containers/create?name={name}", text)


def with_key(key_json, value_json, where="HostConfig"):
    """The in-scope body with one more raw `"key": value` pair spliced in (JSON a dict cannot
    express: case variants next to the canonical key, escapes, duplicates)."""
    text = json.dumps(body(mounts=[dag_mount()]))
    anchor = '"HostConfig": {' if where == "HostConfig" else "{"
    i = text.index(anchor) + len(anchor)
    return text[:i] + f"{key_json}: {value_json}, " + text[i:]


foreign_mount = json.dumps([{"Type": "volume", "Source": POSTGRES, "Target": "/x"}])
foreign_bind = json.dumps([home, trust, f"{POSTGRES}:/x"])
# The Phase 4 verifier's proven bypasses of the old regexes, and the rest of the class.
bypasses = [
    ("lowercase binds", with_key('"binds"', foreign_bind)),
    ("escaped Binds (\\u0042inds)", with_key('"\\u0042inds"', foreign_bind)),
    ("escaped Mounts (\\u004dounts)", with_key('"\\u004dounts"', foreign_mount)),
    ("a second escaped Mounts after the allowed DAG mount",
     json.dumps(body(mounts=[dag_mount()])).replace(
         f'"Subpath": "{USER}"}}}}]', f'"Subpath": "{USER}"}}}}], "\\u004dounts": {foreign_mount}', 1)),
    ("a second HostConfig", json.dumps(body())[:-1]
     + f', "HostConfig": {json.dumps(body(binds=[home, trust, POSTGRES + ":/x"])["HostConfig"])}}}'),
    ("duplicate Binds key", with_key('"Binds"', foreign_bind)),
    ("MOUNTS in upper case", with_key('"MOUNTS"', foreign_mount)),
    ("hostconfig in lower case", with_key('"hostconfig"', json.dumps({"Binds": ["/:/host"]}), where="top")),
    ("privileged in lower case", with_key('"privileged"', "true")),
    ("networkmode host (case variant)", with_key('"networkmode"', '"host"')),
    ("capAdd (case variant)", with_key('"capAdd"', '["SYS_ADMIN"]')),
    ("pidmode host (case variant)", with_key('"pidmode"', '"host"')),
    ("an unknown key", with_key('"VolumesFrom"', json.dumps([f"{P}-postgres-1"]))),
    ("escaped value of a foreign volume", json.dumps(body(binds=[home, trust]))
     .replace(f'"{trust}"', f'"{trust}", "{POSTGRES.replace("p", chr(92) + "u0070", 1)}:/x"')),
    ("not UTF-8", json.dumps(body()).encode("utf-8").replace(b"LAB_PROBE=1", b"LAB_PROBE=\xff")),
    ("trailing data", json.dumps(body()) + json.dumps(body(binds=[home, trust, POSTGRES + ":/x"]))),
]

# The allowed body again, but written the way no regex expected: escaped keys, reversed key
# order, extra whitespace. The guard must forward exactly canonical(parsed) for it.
allowed = body(mounts=[dag_mount()])
weird = json.dumps(dict(reversed(list(allowed.items()))), indent=3) \
    .replace('"Image"', '"\\u0049mage"').replace('"Binds"', '"\\u0042inds"')
canon = json.dumps(json.loads(weird), ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()
canonical_sha256 = hashlib.sha256(canon).hexdigest()

cases = [
    # (name, (status, message), expected status)
    ("list containers", req("GET", "/containers/json"), 403),
    ("stop a non-workspace container", req("POST", f"/containers/{P}-postgres-1/stop"), 403),
    ("exec in a workspace container", req("POST", f"/containers/{WS}/exec", {"Cmd": ["id"]}), 403),
    ("inspect a non-workspace container", req("GET", f"/containers/{P}-postgres-1/json"), 403),
    ("pull an image", req("POST", "/images/create?fromImage=busybox&tag=latest"), 403),
    ("inspect a network", req("GET", f"/networks/{P}_lab"), 403),
    ("a nonexistent image", create(body(image=NOIMG)), 403),
    ("bind a foreign volume", create(body(binds=[home, "someone-else_postgres_data:/x"])), 403),
    ("foreign volume first", create(body(binds=["someone-else_data:/x", trust])), 403),
    ("bind a host path", create(body(binds=[home, "/etc:/host-etc:ro"])), 403),
    ("default bridge network", create(body(net="bridge")), 403),
    ("host network", create(body(net="host")), 403),
    ("Mounts of another volume", create(body(mounts=json.loads(foreign_mount))), 403),
    ("VolumesFrom another container", create(body(host={"VolumesFrom": [f"{P}-postgres-1"]})), 403),
    ("attach an extra network", create(body(extra={"NetworkingConfig": {"EndpointsConfig": {"bridge": {}}}})), 403),
    ("create a foreign-named volume", req("POST", "/volumes/create", {"Name": "someone-else_probe", "Driver": "no-such-driver"}), 403),
    ("create outside the ws- prefix", create(body(), name=f"{P}-notws-probe"), 403),
    ("container name of another user than the home", create(body(), name=f"{P}-ws-alice"), 403),
    ("another volume of this project", create(body(binds=[home, trust, f"{POSTGRES}:/x"])), 403),
    ("Memory above WORKSPACE_MEM", create(body(host={"Memory": 1 << 40})), 403),
    ("CPU quota above WORKSPACE_CPUS", create(body(host={"CpuQuota": CPU_QUOTA + 1})), 403),
    ("Privileged true", create(body(host={"Privileged": True})), 403),
    # User DAGs: only the user's own folder, only as a subpath mount.
    ("the whole user-DAG volume as a bind", create(body(binds=[home, trust, f"{DAGS}:/home/jovyan/airflow-dags:rw"])), 403),
    ("another project's user-DAG volume", create(body(binds=[home, trust, "someone-else_dags-user:/x"])), 403),
    ("DAG mount of another volume", create(body(mounts=[dag_mount(source=f"{P}_trust")])), 403),
    ("DAG mount of another project's volume", create(body(mounts=[dag_mount(source="someone-else_dags-user")])), 403),
    ("DAG mount without a subpath (whole volume)", create(body(mounts=[dag_mount(subpath="")])), 403),
    ("DAG mount with subpath ..", create(body(mounts=[dag_mount(subpath="..", target="/home/jovyan/airflow-dags/..")])), 403),
    ("DAG mount with a nested subpath", create(body(mounts=[dag_mount(subpath=f"{USER}/x", target=f"/home/jovyan/airflow-dags/{USER}/x")])), 403),
    ("DAG folder of another user", create(body(mounts=[dag_mount(user="alice")])), 403),
    ("DAG mount of a folder other than its target", create(body(mounts=[dag_mount(subpath="alice")])), 403),
    ("DAG mount elsewhere in the container", create(body(mounts=[dag_mount(target=f"/etc/{USER}")])), 403),
    ("a second Mounts entry", create(body(mounts=[dag_mount(), dag_mount()])), 403),
] + [(name, create_raw(text), 403) for name, text in bypasses]

allowed_cases = [
    ("in-scope create reaches Docker", create(body())),
    ("in-scope create with the user's DAG folder", create(body(mounts=[dag_mount()]))),
    ("DAG folder of a dotted username", create(
        body(binds=[f"{P}-home-a-2eb-2dc-5fd:/home/jovyan:rw", trust],
             mounts=[dag_mount(user="a.b-c_d")]), name=f"{P}-ws-a-2eb-2dc-5fd")),
    ("escaped/shuffled keys reach Docker as canonical JSON", create_raw(weird)),
]

# Topology: the socket proxy is on `docker-api` (only the guard and the proxy), so the hub
# cannot reach it directly, whatever it sends.
try:
    socket.create_connection(("docker-proxy", 2375), timeout=5).close()
    direct = "reachable"
except OSError:
    direct = "unreachable"
cases.append(("the socket proxy directly, bypassing the guard", (direct, ""), "unreachable"))

bad = [{"case": n, "got": got[0], "want": want, "msg": got[1][:160]}
       for n, got, want in cases if got[0] != want]
bad += [{"case": n, "got": got[0], "want": f"400 {MIN_MEM}", "msg": got[1][:160]}
        for n, got in allowed_cases if got[0] != 400 or MIN_MEM not in got[1]]
print(json.dumps({"cases": len(cases) + len(allowed_cases), "unexpected": bad,
                  "canonical_sha256": canonical_sha256}))
sys.exit(1 if bad else 0)
