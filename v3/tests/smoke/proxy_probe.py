"""Smoke check 11: the Docker socket proxy refuses everything outside this lab's scope.

Runs INSIDE the jupyterhub container (the only client of the proxy) via
`docker compose exec -T jupyterhub python3 - < proxy_probe.py`. Every denied case is built
to be side-effect free even if a rule were wrong: container creates use a nonexistent image
(Docker answers 404 before creating anything), volume creates use a nonexistent driver.
Prints one JSON line; exit 0 only if every case got the expected status.
"""
import http.client
import json
import os
import sys

P = os.environ["COMPOSE_PROJECT_NAME"]
HOST = os.environ.get("DOCKER_HOST", "tcp://docker-proxy:2375").split("//")[-1]
NOIMG = "lakehouse-lab/proxy-probe-no-such-image:none"
WS = f"{P}-ws-proxyprobe"


def req(method, path, body=None):
    c = http.client.HTTPConnection(*HOST.split(":"), timeout=20)
    c.request(method, path, body=json.dumps(body) if body is not None else None,
              headers={"Content-Type": "application/json"})
    r = c.getresponse()
    r.read()
    return r.status


def create(binds=None, net=f"{P}_lab", extra=None, name=WS):
    hc = {"NetworkMode": net}
    if binds is not None:
        hc["Binds"] = binds
    body = {"Image": NOIMG, "HostConfig": hc}
    body.update(extra or {})
    return req("POST", f"/containers/create?name={name}", body)


home, trust = f"{P}-home-proxyprobe:/home/jovyan:rw", f"{P}_trust:/trust:ro"
cases = [
    # (name, status, expected)
    ("list containers", req("GET", "/containers/json"), 403),
    ("stop a non-workspace container", req("POST", f"/containers/{P}-postgres-1/stop"), 403),
    ("exec in a workspace container", req("POST", f"/containers/{WS}/exec", {"Cmd": ["id"]}), 403),
    ("bind a foreign volume", create([home, "someone-else_postgres_data:/x"]), 403),
    ("foreign volume first", create(["someone-else_data:/x", trust]), 403),
    ("bind a host path", create([home, "/etc:/host-etc:ro"]), 403),
    ("default bridge network", create([home, trust], net="bridge"), 403),
    ("host network", create([home, trust], net="host"), 403),
    ("Mounts of another volume", create([trust], extra={"HostConfig": {"NetworkMode": f"{P}_lab",
        "Mounts": [{"Type": "volume", "Source": "someone-else_data", "Target": "/x"}]}}), 403),
    ("VolumesFrom another container", create([trust], extra={"HostConfig": {"NetworkMode": f"{P}_lab",
        "VolumesFrom": [f"{P}-postgres-1"]}}), 403),
    ("attach an extra network", create([trust], extra={"NetworkingConfig": {"EndpointsConfig": {"bridge": {}}}}), 403),
    ("create a foreign-named volume", req("POST", "/volumes/create", {"Name": "someone-else_probe", "Driver": "no-such-driver"}), 403),
    ("create outside the ws- prefix", create([home, trust], name=f"{P}-notws-probe"), 403),
    # Allowed by the proxy: Docker itself answers 404 (no such image), nothing is created.
    ("in-scope create passes the proxy", create([home, trust]), 404),
]
bad = [{"case": n, "got": got, "want": want} for n, got, want in cases if got != want]
print(json.dumps({"cases": len(cases), "unexpected": bad}))
sys.exit(1 if bad else 0)
