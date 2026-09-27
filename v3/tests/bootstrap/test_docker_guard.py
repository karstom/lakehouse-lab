"""Unit tests for the docker-guard validator (bootstrap/docker_guard.py; CONTRACT "Docker
access", INV_V3_DOCKER_PROXY_PROJECT_SCOPE). Run:
  python3 -m unittest discover -s v3/tests/bootstrap -v

The fixtures are the exact bytes docker-py 7.2.0 sends for DockerSpawner 14's calls with the
lab's LabSpawner settings (captured against a recording server; secrets replaced). Every
bypass the Phase 4 verifier proved against the old HAProxy body regexes is here and must be
refused, together with the rest of the class (case variants of every sensitive key, \\u
escapes, duplicate keys, unknown keys, nested tricks).
"""
import json
import os
import sys
import unittest

V3 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, V3)

from bootstrap import docker_guard as g  # noqa: E402

P = "v3-t"
IMAGE = "lakehouse-lab/v3-workspace:guard-test"
POL = g.Policy(project=P, workspace_image=IMAGE, mem_limit=g.parse_bytes("1536m"), cpus=2.0)
V = "/v1.52"
NAME = f"{P}-ws-alice"
CREATE = f"{V}/containers/create?name={NAME}"

# docker-py 7.2.0 / DockerSpawner 14, byte for byte (engineer: with the DAG folder mount).
DOCKERPY_CREATE = (
    '{"ExposedPorts": {"8888/tcp": null}, "Tty": false, "OpenStdin": false, "StdinOnce": false, '
    '"AttachStdin": false, "AttachStdout": true, "AttachStderr": true, '
    '"Env": ["JUPYTERHUB_API_TOKEN=secret", "LAB_DOMAIN=d"], "Cmd": ["jupyterhub-singleuser"], '
    '"Image": "lakehouse-lab/v3-workspace:guard-test", "Volumes": {"/home/jovyan": {}, "/trust": {}}, '
    '"NetworkDisabled": false, "HostConfig": {"Memory": 1610612736, "NetworkMode": "v3-t_lab", '
    '"Binds": ["v3-t-home-alice:/home/jovyan:rw", "v3-t_trust:/trust:ro"], "Links": [], '
    '"CpuQuota": 200000, "CpuPeriod": 100000, "AutoRemove": true, "Mounts": [{"Target": '
    '"/home/jovyan/airflow-dags/alice", "Source": "v3-t_dags-user", "Type": "volume", '
    '"ReadOnly": false, "VolumeOptions": {"Subpath": "alice"}}]}, "Labels": '
    '{"com.docker.compose.project": "v3-t", "lab.role": "workspace"}}')
DOCKERPY_VOLUME = ('{"Name": "v3-t-home-alice", "Labels": {"com.docker.compose.project": "v3-t", '
                   '"lab.role": "workspace"}}')
POSTGRES = "v3-p4v_postgres-data"      # the volume the verifier mounted through the old proxy


def body():
    return json.loads(DOCKERPY_CREATE)


def create(raw, target=CREATE):
    if not isinstance(raw, (bytes, str)):
        raw = json.dumps(raw)
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    return g.decide(POL, "POST", target, raw)


class Allowed(unittest.TestCase):
    def test_dockerspawner_create_passes_and_is_reserialized(self):
        path, out = create(DOCKERPY_CREATE)
        self.assertEqual(path, CREATE)
        self.assertEqual(json.loads(out), json.loads(DOCKERPY_CREATE))
        self.assertEqual(out, g.canonical(json.loads(DOCKERPY_CREATE)))
        self.assertNotEqual(out, DOCKERPY_CREATE.encode())   # Docker never sees the client's bytes

    def test_analyst_create_without_mounts(self):
        b = body()
        b["HostConfig"]["Mounts"] = []
        self.assertEqual(json.loads(create(b)[1]), b)
        del b["HostConfig"]["Mounts"]
        self.assertEqual(json.loads(create(b)[1]), b)

    def test_escaped_key_is_decoded_then_validated_then_canonical(self):
        # "Image" IS "Image" to Go and to Python; the forwarded bytes carry the plain key.
        raw = DOCKERPY_CREATE.replace('"Image"', '"\\u0049mage"')
        path, out = create(raw)
        self.assertIn(b'"Image":"lakehouse-lab/v3-workspace:guard-test"', out)
        self.assertNotIn(b"\\u0049", out)

    def test_dotted_username(self):
        user, esc = "a.b-c_d", g.escape_username("a.b-c_d")
        self.assertEqual(esc, "a-2eb-2dc-5fd")
        b = body()
        b["HostConfig"]["Binds"][0] = f"{P}-home-{esc}:/home/jovyan:rw"
        b["HostConfig"]["Mounts"][0].update(Target=f"/home/jovyan/airflow-dags/{user}",
                                            VolumeOptions={"Subpath": user})
        create(b, f"{V}/containers/create?name={P}-ws-{esc}")

    def test_volume_create(self):
        path, out = g.decide(POL, "POST", f"{V}/volumes/create", DOCKERPY_VOLUME.encode())
        self.assertEqual(json.loads(out), json.loads(DOCKERPY_VOLUME))

    def test_read_and_lifecycle_calls(self):
        for method, target, fwd in [
                ("GET", "/version", "/version"),
                ("GET", f"{V}/_ping", f"{V}/_ping"),
                ("GET", f"{V}/volumes/{P}-home-alice", None),
                ("GET", f"{V}/images/{IMAGE}/json", None),
                ("GET", f"{V}/containers/{NAME}/json", None),
                ("POST", f"{V}/containers/{NAME}/start", None),
                ("POST", f"{V}/containers/{NAME}/stop", None),
                ("POST", f"{V}/containers/{NAME}/stop?t=10", None),
                ("DELETE", f"{V}/containers/{NAME}?v=True&link=False&force=False",
                 f"{V}/containers/{NAME}?v=1")]:
            path, out = g.decide(POL, method, target, b"")
            self.assertEqual(path, fwd or target, target)
            self.assertIsNone(out)


class Refused(unittest.TestCase):
    def refused(self, raw, target=CREATE, method="POST"):
        if not isinstance(raw, (bytes, str)):
            raw = json.dumps(raw)
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        with self.assertRaises(g.Reject):
            g.decide(POL, method, target, raw)

    # -- the verifier's proven bypasses (201 creates mounting another project's database)
    def test_lowercase_binds(self):
        self.refused(DOCKERPY_CREATE.replace('"Links": []',
                                             f'"Links": [], "binds": ["{POSTGRES}:/x"]'))

    def test_escaped_mounts_key(self):
        self.refused(DOCKERPY_CREATE.replace(
            '"Links": []', f'"Links": [], "\\u004dounts": [{{"Type": "volume", "Source": '
                           f'"{POSTGRES}", "Target": "/x"}}]'))

    def test_second_escaped_mounts_after_the_allowed_dag_mount(self):
        raw = DOCKERPY_CREATE.replace(
            '"Subpath": "alice"}}]', '"Subpath": "alice"}}], "\\u004dounts": [{"Type": "volume", '
                                     f'"Source": "{POSTGRES}", "Target": "/x"}}]')
        self.refused(raw)

    # -- the class: every sensitive key in other cases, escaped, duplicated
    def test_case_variants_of_every_sensitive_key(self):
        keys = ["Binds", "Mounts", "Privileged", "CapAdd", "Devices", "NetworkMode", "PidMode",
                "IpcMode", "UsernsMode", "VolumesFrom", "Image", "Labels", "HostConfig",
                "Memory", "NetworkingConfig", "Volumes"]
        for k in keys:
            for variant in {k.lower(), k.upper(), k[0].lower() + k[1:], k.swapcase()} - {k}:
                with self.subTest(key=variant):
                    b = body()
                    target = b if k in ("Image", "Labels", "HostConfig", "NetworkingConfig",
                                        "Volumes") else b["HostConfig"]
                    target[variant] = target.get(k, True)
                    self.refused(b)

    def test_duplicate_keys_at_every_level(self):
        for raw in [
                DOCKERPY_CREATE[:-1] + ', "Image": "' + IMAGE + '"}',                 # top level
                DOCKERPY_CREATE.replace('"AutoRemove": true', '"AutoRemove": true, "AutoRemove": true'),
                DOCKERPY_CREATE.replace('"Type": "volume"', '"Type": "volume", "Type": "bind"'),
                DOCKERPY_CREATE.replace('{"Subpath": "alice"}', '{"Subpath": "alice", "Subpath": "bob"}'),
                DOCKERPY_CREATE.replace('"lab.role": "workspace"}', '"lab.role": "workspace", "lab.role": "x"}'),
                DOCKERPY_CREATE.replace('"Mounts": [', '"Mounts": [], "Mounts": ['),
                DOCKERPY_CREATE.replace('"Mounts": [', '"M\\u006funts": [], "Mounts": ['),
                '{"Image": "a", "HostConfig": {}, "HostConfig": {}}']:
            with self.subTest(raw=raw[-80:]):
                self.refused(raw)

    def test_unknown_keys(self):
        for where, key, val in [(None, "Entrypoint", ["sh"]), (None, "User", "0"),
                                (None, "Hostname", "x"), ("HostConfig", "VolumesFrom", ["c"]),
                                ("HostConfig", "PortBindings", {"8888/tcp": [{}]}),
                                ("HostConfig", "SecurityOpt", ["seccomp=unconfined"]),
                                ("HostConfig", "Tmpfs", {"/x": ""}), ("HostConfig", "Sysctls", {}),
                                ("HostConfig", "MemorySwap", -1), ("HostConfig", "NanoCpus", 1)]:
            with self.subTest(key=key):
                b = body()
                (b if where is None else b[where])[key] = val
                self.refused(b)

    def test_nested_tricks(self):
        cases = []
        b = body(); b["HostConfig"]["Mounts"][0]["BindOptions"] = {"Propagation": "rshared"}; cases.append(b)
        b = body(); b["HostConfig"]["Mounts"][0]["type"] = "bind"; cases.append(b)
        b = body(); b["HostConfig"]["Mounts"][0]["VolumeOptions"]["DriverConfig"] = {"Name": "local"}; cases.append(b)
        b = body(); b["HostConfig"]["Mounts"][0]["VolumeOptions"]["subpath"] = "bob"; cases.append(b)
        b = body(); b["HostConfig"]["Mounts"].append(dict(b["HostConfig"]["Mounts"][0])); cases.append(b)
        b = body(); b["HostConfig"]["Mounts"][0]["Source"] = POSTGRES; cases.append(b)
        b = body(); b["HostConfig"]["Mounts"][0]["Type"] = "bind"; cases.append(b)
        b = body(); b["HostConfig"]["Mounts"][0]["VolumeOptions"] = {"Subpath": "bob"}; cases.append(b)
        b = body(); b["HostConfig"]["Mounts"][0].update(Target="/home/jovyan/airflow-dags/bob",
                                                       VolumeOptions={"Subpath": "bob"}); cases.append(b)
        b = body(); b["HostConfig"]["Mounts"][0].update(Target="/home/jovyan/airflow-dags/..",
                                                       VolumeOptions={"Subpath": ".."}); cases.append(b)
        b = body(); b["HostConfig"]["Mounts"][0].update(Target="/home/jovyan/airflow-dags/alice/x",
                                                       VolumeOptions={"Subpath": "alice/x"}); cases.append(b)
        b = body(); b["HostConfig"]["Mounts"][0]["VolumeOptions"] = {}; cases.append(b)
        b = body(); b["HostConfig"]["Mounts"][0]["Target"] = "/etc/alice"; cases.append(b)
        b = body(); b["HostConfig"]["Mounts"] = {"0": b["HostConfig"]["Mounts"][0]}; cases.append(b)
        b = body(); b["NetworkingConfig"] = {"EndpointsConfig": {"bridge": {}}}; cases.append(b)
        b = body(); b["NetworkingConfig"] = {"EndpointsConfig": {f"{P}_lab": {"Aliases": ["x"]}}}; cases.append(b)
        b = body(); b["Volumes"]["/var/lib/postgresql"] = {}; cases.append(b)
        b = body(); b["Volumes"]["/home/jovyan"] = {"x": 1}; cases.append(b)
        b = body(); b["Labels"]["com.docker.compose.service"] = "postgres"; cases.append(b)
        b = body(); b["Env"].append("no-equals-sign"); cases.append(b)
        b = body(); b["Cmd"] = "sh -c id"; cases.append(b)
        for i, b in enumerate(cases):
            with self.subTest(case=i):
                self.refused(b)

    def test_binds_values(self):
        for binds in [["v3-t-home-alice:/home/jovyan:rw", f"{POSTGRES}:/x"],
                      ["v3-t-home-alice:/home/jovyan:rw", "v3-t_trust:/trust:rw"],
                      ["v3-t-home-bob:/home/jovyan:rw", "v3-t_trust:/trust:ro"],
                      ["v3-t-home-alice:/home/jovyan:rw", "v3-t_trust:/trust:ro", "/etc:/x:ro"],
                      ["v3-t-home-alice:/home/jovyan:rw", "v3-t_dags-user:/home/jovyan/airflow-dags:rw"],
                      ["v3-t-home-alice:/home/jovyan:rw", "v3-t-home-alice:/home/jovyan:rw"],
                      ["v3-t-home-alice:/:rw", "v3-t_trust:/trust:ro"], ["/:/home/jovyan:rw"]]:
            with self.subTest(binds=binds):
                b = body()
                b["HostConfig"]["Binds"] = binds
                self.refused(b)

    def test_host_config_values(self):
        for k, v in [("Privileged", True), ("CapAdd", ["SYS_ADMIN"]),
                     ("Devices", [{"PathOnHost": "/dev/sda"}]), ("PidMode", "host"),
                     ("IpcMode", "host"), ("UsernsMode", "host"), ("UTSMode", "host"),
                     ("NetworkMode", "host"), ("NetworkMode", "bridge"),
                     ("NetworkMode", "container:v3-t-postgres-1"), ("NetworkMode", "other_lab"),
                     ("Memory", 0), ("Memory", 1610612737), ("Memory", 1.5e9), ("Memory", True),
                     ("Memory", "1536m"), ("CpuQuota", 200001), ("CpuQuota", -1),
                     ("CpuPeriod", 99), ("Links", ["v3-t-postgres-1:db"]), ("AutoRemove", "yes")]:
            with self.subTest(key=k, value=v):
                b = body()
                b["HostConfig"][k] = v
                self.refused(b)

    def test_top_level_values(self):
        for k, v in [("Image", "postgres:16"), ("Image", IMAGE + " "), ("Tty", True),
                     ("OpenStdin", True), ("NetworkDisabled", True),
                     ("Labels", {"com.docker.compose.project": "other", "lab.role": "workspace"})]:
            with self.subTest(key=k):
                b = body()
                b[k] = v
                self.refused(b)
        for k in ("Image", "HostConfig", "Labels", "Cmd", "Env"):
            with self.subTest(missing=k):
                b = body()
                del b[k]
                self.refused(b)
        for k in ("NetworkMode", "Binds", "Memory", "CpuQuota", "CpuPeriod"):
            with self.subTest(missing=k):
                b = body()
                del b["HostConfig"][k]
                self.refused(b)

    def test_not_json(self):
        for raw in [b"", b"[]", b"null", b'"x"', b"{", DOCKERPY_CREATE.encode() + b"{}",
                    DOCKERPY_CREATE.replace('1610612736', 'NaN').encode(),
                    DOCKERPY_CREATE.replace('1610612736', 'Infinity').encode(),
                    DOCKERPY_CREATE.replace('=d"', '=d\xff"').encode("latin-1"),     # not UTF-8
                    DOCKERPY_CREATE.replace('=d"', '=\\ud800"').encode(),            # lone surrogate
                    DOCKERPY_CREATE.replace('=d"', '=\\u0000"').encode(),            # NUL
                    b"\xef\xbb\xbf" + DOCKERPY_CREATE.encode(),                     # BOM
                    b"{" * 5000 + b"}" * 5000,
                    b" " * (g.MAX_BODY + 1)]:
            with self.subTest(raw=raw[-40:]):
                self.refused(raw)

    def test_names_and_queries(self):
        b = DOCKERPY_CREATE
        for target in [f"{V}/containers/create", f"{V}/containers/create?name=v3-t-postgres-1",
                       f"{V}/containers/create?name={P}-ws-bob",            # not the binds' user
                       f"{V}/containers/create?name={P}-ws-x-postgres-1",   # not an escaped name
                       f"{V}/containers/create?name={NAME}&name={P}-ws-bob",
                       f"{V}/containers/create?name={NAME}&platform=linux",
                       f"{V}/containers/create?name={P}-ws-%61lice",
                       f"{V}/containers/create;name={NAME}",
                       f"/v2/containers/create?name={NAME}",
                       f"{V}//containers/create?name={NAME}",
                       f"http://docker{V}/containers/create?name={NAME}",
                       f"{V}/containers/create?name={NAME}#x"]:
            with self.subTest(target=target):
                self.refused(b, target)

    def test_other_calls(self):
        for method, target, raw in [
                ("GET", f"{V}/containers/json", b""),
                ("GET", f"{V}/containers/{P}-postgres-1/json", b""),
                ("GET", f"{V}/containers/0123456789ab/json", b""),
                ("POST", f"{V}/containers/{P}-postgres-1/stop", b""),
                ("POST", f"{V}/containers/{NAME}/exec", b'{"Cmd": ["id"]}'),
                ("POST", f"{V}/containers/{NAME}/start", b'{"Binds": ["/:/x"]}'),
                ("POST", f"{V}/containers/{NAME}/stop?t=10&signal=KILL", b""),
                ("POST", f"{V}/containers/{NAME}/stop?t=9999", b""),
                ("POST", f"{V}/containers/{NAME}/kill", b""),
                ("POST", f"{V}/containers/{NAME}/update", b'{"Memory": 1}'),
                ("PUT", f"{V}/containers/{NAME}/archive?path=/", b"x"),
                ("DELETE", f"{V}/containers/{NAME}?force=True", b""),
                ("DELETE", f"{V}/containers/{NAME}?link=1", b""),
                ("DELETE", f"{V}/containers/{P}-postgres-1", b""),
                ("DELETE", f"{V}/volumes/{P}-home-alice", b""),
                ("GET", f"{V}/images/postgres:16/json", b""),
                ("POST", f"{V}/images/create?fromImage=busybox", b""),
                ("GET", f"{V}/volumes", b""),
                ("GET", f"{V}/volumes/{POSTGRES}", b""),
                ("GET", f"{V}/networks/{P}_lab", b""),
                ("POST", f"{V}/networks/{P}_lab/connect", b"{}"),
                ("GET", f"{V}/version?x=1", b""),
                ("HEAD", f"{V}/_ping", b""),
                ("POST", f"{V}/volumes/create", b'{"Name": "someone-else_probe"}'),
                ("POST", f"{V}/volumes/create", json.dumps({"Name": f"{P}-home-alice", "Labels": POL.labels,
                                                             "Driver": "local"}).encode()),
                ("POST", f"{V}/volumes/create", json.dumps({"Name": f"{P}-home-alice", "Labels": POL.labels,
                                                             "DriverOpts": {"type": "none", "o": "bind",
                                                                            "device": "/"}}).encode()),
                ("POST", f"{V}/volumes/create", json.dumps({"name": f"{P}-home-alice", "Labels": POL.labels}).encode()),
                ("POST", f"{V}/volumes/create", json.dumps({"Name": f"{P}_dags-user", "Labels": POL.labels}).encode()),
                ("POST", f"{V}/volumes/create", json.dumps({"Name": f"{P}-home-alice"}).encode())]:
            with self.subTest(method=method, target=target):
                self.refused(raw, target, method)


class Helpers(unittest.TestCase):
    def test_parse_bytes(self):
        self.assertEqual(g.parse_bytes("1536m"), 1536 * 1024 ** 2)
        self.assertEqual(g.parse_bytes("2G"), 2 * 1024 ** 3)
        self.assertEqual(g.parse_bytes("1000"), 1000)

    def test_escape_matches_dockerspawner(self):
        # escapism.escape(name, set(a-z0-9), escape_char='-').lower()
        self.assertEqual(g.escape_username("alice"), "alice")
        self.assertEqual(g.escape_username("eddie_x"), "eddie-5fx")
        self.assertEqual(g.escape_username("a-b"), "a-2db")

    def test_canonical_is_stable(self):
        a = g.canonical(json.loads(DOCKERPY_CREATE))
        self.assertEqual(a, g.canonical(json.loads(a)))
        self.assertTrue(a.isascii())


if __name__ == "__main__":
    unittest.main()
