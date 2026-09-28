"""Unit tests for bootstrap.airflow_client (the `airflow` client and its UMA model, OQ-16).

No Keycloak needed: FakeKeycloak keeps clients, roles, group role mappings and the
Authorization Services objects (scopes, resources, policies, permissions) in memory, and
answers the admin REST paths airflow_client uses. Like Keycloak, it returns set-valued fields
in a different order than they were written.
Run: python3 -m unittest discover -s v3/tests/bootstrap -v
"""
import contextlib
import copy
import io
import itertools
import os
import sys
import unittest
import urllib.parse

V3 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, V3)

from bootstrap import airflow_client as ac  # noqa: E402

GIDS = {"lab-admin": "g-admin", "engineer": "g-eng", "analyst": "g-ana", "viewer": "g-view"}


class FakeKeycloak:
    def __init__(self):
        self.ids = (f"id-{n}" for n in itertools.count())
        self.clients = {}          # clientId -> rep
        self.secrets = {}
        self.mappers = {}          # uuid -> [mapper]
        self.roles = {}            # uuid -> {name: role}
        self.group_roles = {}      # (gid, uuid) -> set(role names)
        self.rs = {}               # uuid -> resource server settings
        self.scopes = {}           # uuid -> {id: rep}
        self.resources = {}        # uuid -> {id: rep}
        self.policies = {}         # uuid -> {id: rep}  (role policies and permissions)
        self.writes = []

    # -- helpers
    def _cid(self, path):
        return path.split("/")[2]

    def _authz_default(self, uuid):
        self.rs[uuid] = {"policyEnforcementMode": "ENFORCING", "decisionStrategy": "UNANIMOUS",
                         "allowRemoteResourceManagement": True}
        rid, pid, perm = next(self.ids), next(self.ids), next(self.ids)
        self.scopes[uuid] = {}
        self.resources[uuid] = {rid: {"_id": rid, "name": "Default Resource", "scopes": []}}
        self.policies[uuid] = {
            pid: {"id": pid, "name": "Default Policy", "type": "js"},
            perm: {"id": perm, "name": "Default Permission", "type": "resource",
                   "decisionStrategy": "UNANIMOUS", "scopes": [], "resources": [rid], "policies": [pid]},
        }

    def client(self, client_id):
        return copy.deepcopy(self.clients[client_id])

    def get(self, path):
        base, _, query = path.partition("?")
        q = urllib.parse.parse_qs(query)
        if base == "/clients" and "clientId" in q:
            c = self.clients.get(q["clientId"][0])
            return [copy.deepcopy(c)] if c else []
        uuid = self._cid(path) if base.startswith("/clients/") else None
        if base.endswith("/client-secret"):
            return {"value": self.secrets.get(uuid)}
        if base.endswith("/protocol-mappers/models"):
            return copy.deepcopy(self.mappers.get(uuid, []))
        if base.endswith("/roles") and base.startswith("/clients/"):
            return list(reversed(copy.deepcopy(list(self.roles.get(uuid, {}).values()))))
        if base.startswith("/groups/"):
            gid, uuid = base.split("/")[2], base.split("/")[-1]
            names = self.group_roles.get((gid, uuid), set())
            return [copy.deepcopy(self.roles[uuid][n]) for n in sorted(names)]
        a = base.split("/authz/resource-server", 1)
        if len(a) == 2:
            rest = a[1]
            if rest == "":
                return copy.deepcopy(self.rs[uuid])
            if rest == "/scope":
                return copy.deepcopy(list(self.scopes[uuid].values()))
            if rest == "/resource":
                out = []
                for r in self.resources[uuid].values():
                    r = copy.deepcopy(r)
                    r["scopes"] = [{"id": s, "name": self.scopes[uuid][s]["name"]}
                                   for s in reversed(r["scopes"])]
                    if q.get("deep") == ["false"]:
                        r.pop("scopes")
                    out.append(r)
                return out
            if rest == "/policy":
                pols = self.policies[uuid].values()
                if q.get("permission") == ["false"]:
                    pols = [p for p in pols if p["type"] not in ("scope", "resource")]
                return [{k: v for k, v in p.items() if k not in ("scopes", "resources", "policies", "roles")}
                        for p in copy.deepcopy(list(pols))]
            if rest == "/permission":
                return [{k: v for k, v in p.items() if k not in ("scopes", "resources", "policies")}
                        for p in copy.deepcopy(list(self.policies[uuid].values()))
                        if p["type"] in ("scope", "resource")]
            parts = rest.strip("/").split("/")
            if parts[0] == "policy" and parts[1] == "role":
                return copy.deepcopy(self.policies[uuid][parts[2]])
            if parts[0] == "permission":
                p = self.policies[uuid][parts[2]]
                if parts[3] == "scopes":
                    return [{"id": s, "name": self.scopes[uuid][s]["name"]} for s in reversed(p["scopes"])]
                if parts[3] == "resources":
                    return [{"_id": r, "name": self.resources[uuid][r]["name"]} for r in reversed(p["resources"])]
                if parts[3] == "associatedPolicies":
                    return [{"id": x, "name": self.policies[uuid][x]["name"]} for x in reversed(p["policies"])]
        raise AssertionError(f"unexpected GET {path}")

    def call(self, method, path, body=None):
        self.writes.append((method, path))
        body = copy.deepcopy(body)
        if method == "POST" and path == "/clients":
            uuid = next(self.ids)
            rep = {k: v for k, v in body.items() if k not in ("secret", "protocolMappers")}
            rep["id"] = uuid
            self.clients[body["clientId"]] = rep
            self.secrets[uuid] = body["secret"]
            self.mappers[uuid] = body.get("protocolMappers", [])
            self.roles[uuid] = {}
            if body.get("authorizationServicesEnabled"):
                self._authz_default(uuid)
            return None
        uuid = self._cid(path) if path.startswith("/clients/") else None
        if method == "PUT" and path == f"/clients/{uuid}":
            assert "authorizationSettings" not in body, "must never overwrite the UMA model"
            self.secrets[uuid] = body.pop("secret")
            self.clients[body["clientId"]] = body
            return None
        if method == "POST" and path.endswith("/protocol-mappers/models"):
            self.mappers[uuid].append(body)
            return None
        if method == "POST" and path.endswith("/roles"):
            self.roles[uuid][body["name"]] = {"id": next(self.ids), "name": body["name"]}
            return None
        if path.startswith("/groups/"):
            gid, uuid = path.split("/")[2], path.split("/")[-1]
            names = self.group_roles.setdefault((gid, uuid), set())
            for r in body:
                (names.add if method == "POST" else names.discard)(r["name"])
            return None
        rest = path.split("/authz/resource-server", 1)[1]
        store = None
        if method == "PUT" and rest == "":
            self.rs[uuid] = body
            return None
        parts = rest.strip("/").split("/")
        if parts[0] == "scope" and method == "POST":
            sid = next(self.ids)
            self.scopes[uuid][sid] = {"id": sid, "name": body["name"]}
            return None
        if parts[0] == "resource":
            store = self.resources[uuid]
            if method == "DELETE":
                del store[parts[1]]
                return None
            rid = parts[1] if method == "PUT" else next(self.ids)
            store[rid] = {"_id": rid, "name": body["name"], "scopes": [s["id"] for s in body["scopes"]]}
            return None
        if parts[0] in ("policy", "permission"):
            store = self.policies[uuid]
            if method == "DELETE":
                del store[parts[-1]]
                return None
            pid = parts[2] if method == "PUT" else next(self.ids)
            rep = dict(body, id=pid)
            if parts[0] == "policy":
                rep["type"] = parts[1]
            store[pid] = rep
            return None
        raise AssertionError(f"unexpected {method} {path}")


def ensure(kc, seed=False):
    with contextlib.redirect_stdout(io.StringIO()) as out:
        changed = ac.ensure_airflow_client(kc, "s3cret", "lab.localhost", "18443", GIDS, direct_grants=seed)
    return changed, out.getvalue()


def perm(kc, name):
    uuid = kc.clients["airflow"]["id"]
    p = next(p for p in kc.policies[uuid].values() if p["name"] == name)
    names = lambda store, ids, key="name": sorted(store[i][key] for i in ids)  # noqa: E731
    return {"scopes": names(kc.scopes[uuid], p["scopes"]),
            "resources": names(kc.resources[uuid], p["resources"]),
            "policies": names(kc.policies[uuid], p["policies"]),
            "strategy": p["decisionStrategy"]}


class Model(unittest.TestCase):
    """The declared model itself (no Keycloak)."""

    def test_permissions_reference_known_objects(self):
        for name, (ptype, scopes, res, pols, _) in ac.PERMISSIONS.items():
            self.assertTrue(set(scopes) <= set(ac.SCOPES), name)
            self.assertTrue(set(res) <= set(ac.RESOURCES) | set(ac.MENU_ITEMS), name)
            self.assertTrue(set(pols) <= set(ac.ROLES), name)
            self.assertEqual(ptype == "resource", not scopes, name)

    def test_group_roles_match_contract(self):
        self.assertEqual(ac.GROUP_ROLES["lab-admin"], ("Admin",))
        self.assertIn("User", ac.GROUP_ROLES["engineer"])       # trigger / edit DAGs
        for g in ("analyst", "viewer"):
            self.assertEqual(ac.GROUP_ROLES[g], ("Viewer",))      # read-only

    def test_viewers_cannot_read_sensitive_resources(self):
        _, _, res, pols, _ = ac.PERMISSIONS["ReadOnly"]
        self.assertIn("Viewer", pols)
        self.assertFalse(set(res) & (set(ac.SENSITIVE_RESOURCES) | set(ac.SENSITIVE_MENU_ITEMS)))
        self.assertNotIn("Viewer", ac.PERMISSIONS["ReadSensitive"][3])
        # Viewer appears in no permission with a write scope or a whole resource.
        for name, (ptype, scopes, _, pols, _) in ac.PERMISSIONS.items():
            if "Viewer" in pols:
                self.assertEqual(ptype, "scope", name)
                self.assertTrue(set(scopes) <= {"GET", "MENU", "LIST"}, name)

    def test_redirects_with_and_without_port(self):
        d = ac.desired("lab.localhost", "443", False)
        self.assertIn("https://airflow.lab.localhost/auth/login_callback", d["redirectUris"])
        self.assertIn("https://airflow.lab.localhost:443/auth/login_callback", d["redirectUris"])
        self.assertFalse(d["directAccessGrantsEnabled"])
        self.assertTrue(ac.desired("x", "1", True)["directAccessGrantsEnabled"])


class Ensure(unittest.TestCase):
    def test_create_then_unchanged(self):
        kc = FakeKeycloak()
        changed, out = ensure(kc)
        self.assertTrue(changed)
        self.assertIn("created client airflow", out)
        self.assertIn("removed Default Permission", out)
        n = len(kc.writes)
        changed, out = ensure(kc)
        self.assertFalse(changed, f"second run changed something:\n{out}")
        self.assertEqual(len(kc.writes), n, kc.writes[n:])

    def test_model_as_declared(self):
        kc = FakeKeycloak()
        ensure(kc)
        uuid = kc.clients["airflow"]["id"]
        self.assertEqual(kc.rs[uuid]["decisionStrategy"], "AFFIRMATIVE")
        self.assertFalse(any(r["name"].startswith("Default") for r in kc.resources[uuid].values()))
        self.assertFalse(any(p["name"].startswith("Default") for p in kc.policies[uuid].values()))
        self.assertEqual(perm(kc, "User")["resources"], ["Asset", "Dag"])
        self.assertEqual(perm(kc, "User")["policies"], ["Allow-User"])
        self.assertEqual(perm(kc, "Admin")["scopes"], sorted(ac.SCOPES))
        self.assertEqual(kc.group_roles[("g-eng", uuid)], {"User", "Op"})
        self.assertEqual(kc.group_roles[("g-view", uuid)], {"Viewer"})

    def test_drift_is_repaired(self):
        kc = FakeKeycloak()
        ensure(kc)
        uuid = kc.clients["airflow"]["id"]
        # Someone gives viewers Admin, removes a policy from a permission, adds a scope to
        # nothing, and turns the password grant on.
        kc.group_roles[("g-view", uuid)].add("Admin")
        p = next(p for p in kc.policies[uuid].values() if p["name"] == "ReadSensitive")
        p["policies"] = p["policies"][:1]
        kc.clients["airflow"]["directAccessGrantsEnabled"] = True
        changed, out = ensure(kc)
        self.assertTrue(changed)
        self.assertEqual(kc.group_roles[("g-view", uuid)], {"Viewer"})
        self.assertEqual(perm(kc, "ReadSensitive")["policies"],
                         sorted(ac.policy_name(r) for r in ac.PERMISSIONS["ReadSensitive"][3]))
        self.assertFalse(kc.clients["airflow"]["directAccessGrantsEnabled"])
        self.assertFalse(ensure(kc)[0])

    def test_seeded_tests_get_password_grant(self):
        kc = FakeKeycloak()
        ensure(kc, seed=True)
        self.assertTrue(kc.clients["airflow"]["directAccessGrantsEnabled"])


if __name__ == "__main__":
    unittest.main()
