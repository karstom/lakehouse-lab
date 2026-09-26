"""Unit tests for bootstrap.batch_client (the lab-batch service identity, ADR-017).

No Keycloak or Lakekeeper needed: small in-memory fakes. Run:
  python3 -m unittest discover -s v3/tests/bootstrap -v
"""
import contextlib
import copy
import io
import os
import sys
import unittest
from unittest import mock

V3 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, V3)

from bootstrap import batch_client as bc  # noqa: E402


class FakeKeycloak:
    def __init__(self):
        self.clients, self.secrets, self.mappers, self.writes = {}, {}, {}, []

    def get(self, path):
        if path.startswith("/clients?clientId="):
            c = self.clients.get(path.split("=", 1)[1])
            return [copy.deepcopy(c)] if c else []
        if path.endswith("/client-secret"):
            return {"value": self.secrets.get(path.split("/")[2])}
        if path.endswith("/protocol-mappers/models"):
            return copy.deepcopy(self.mappers.get(path.split("/")[2], []))
        raise AssertionError(f"unexpected GET {path}")

    def call(self, method, path, body=None):
        self.writes.append((method, path))
        body = copy.deepcopy(body)
        if method == "POST" and path == "/clients":
            uuid = f"uuid-{body['clientId']}"
            self.clients[body["clientId"]] = dict(
                {k: v for k, v in body.items() if k not in ("secret", "protocolMappers")}, id=uuid)
            self.secrets[uuid] = body["secret"]
            self.mappers[uuid] = body["protocolMappers"]
        elif method == "PUT":
            self.secrets[body["id"]] = body.pop("secret")
            self.clients[body["clientId"]] = body
        elif method == "POST" and path.endswith("/protocol-mappers/models"):
            self.mappers[path.split("/")[2]].append(body)
        else:
            raise AssertionError(f"unexpected {method} {path}")

    def client(self, client_id):
        return copy.deepcopy(self.clients[client_id])

    def service_account_user(self, client_id):
        return {"id": "sa-1", "username": f"service-account-{client_id}"}


def ensure(kc, secret="s3cret", lifespan=None):
    env = {} if lifespan is None else {"LAB_BATCH_TOKEN_LIFESPAN": str(lifespan)}
    with mock.patch.dict(os.environ, env, clear=False), \
            contextlib.redirect_stdout(io.StringIO()) as out:
        if lifespan is None:
            os.environ.pop("LAB_BATCH_TOKEN_LIFESPAN", None)
        changed = bc.ensure_batch_client(kc, secret)
    return changed, out.getvalue()


class BatchClient(unittest.TestCase):
    def test_create_then_unchanged(self):
        kc = FakeKeycloak()
        self.assertTrue(ensure(kc)[0])
        c = kc.clients["lab-batch"]
        self.assertTrue(c["serviceAccountsEnabled"])
        self.assertFalse(c["standardFlowEnabled"] or c["directAccessGrantsEnabled"])
        self.assertEqual(c["attributes"]["access.token.lifespan"], str(bc.DEFAULT_TOKEN_LIFESPAN))
        self.assertEqual(sorted(m["config"]["included.client.audience"] for m in kc.mappers["uuid-lab-batch"]),
                         ["lakekeeper", "trino"])
        n = len(kc.writes)
        changed, out = ensure(kc)
        self.assertFalse(changed, out)
        self.assertEqual(len(kc.writes), n)

    def test_lifespan_override_and_back(self):
        kc = FakeKeycloak()
        ensure(kc)
        changed, out = ensure(kc, lifespan=120)
        self.assertTrue(changed)
        self.assertIn("access.token.lifespan", out)
        self.assertEqual(kc.clients["lab-batch"]["attributes"]["access.token.lifespan"], "120")
        self.assertTrue(ensure(kc)[0])  # override removed -> back to the default
        self.assertEqual(kc.clients["lab-batch"]["attributes"]["access.token.lifespan"], "300")

    def test_secret_rotation_and_bad_values(self):
        kc = FakeKeycloak()
        ensure(kc)
        self.assertTrue(ensure(kc, secret="new")[0])
        self.assertEqual(kc.secrets["uuid-lab-batch"], "new")
        with self.assertRaises(RuntimeError):
            ensure(kc, secret="")
        with self.assertRaises(RuntimeError):
            ensure(kc, lifespan=10)


class FakeLakekeeper:
    h = {}

    def __init__(self):
        self.namespaces = {"samples": "ns-samples"}
        self.users, self.assignments, self.calls = set(), {}, []


def fake_request(lk):
    def request(method, url, headers=None, json_body=None, expect=None):
        lk.calls.append((method, url))
        name = url.rsplit("/", 1)[-1]
        if method == "GET" and "/namespaces/" in url:
            if name in lk.namespaces:
                return 200, {"namespace": [name], "properties": {"namespace_id": lk.namespaces[name]}}, {}
            return 404, None, {}
        if method == "POST" and url.endswith("/namespaces"):
            lk.namespaces[json_body["namespace"][0]] = f"ns-{json_body['namespace'][0]}"
            return 200, {}, {}
        raise AssertionError(f"unexpected {method} {url}")
    return request


class FakeAuthz:
    """Stands in for bootstrap.lakekeeper_authz (ensure_user / ensure_assignments)."""

    def __init__(self, lk):
        self.lk = lk

    def ensure_user(self, lk, uid, name, kind):
        if uid in lk.users:
            return False
        lk.users.add(uid)
        return True

    def ensure_assignments(self, lk, path, wanted):
        have = lk.assignments.setdefault(path, [])
        new = [a for a in wanted if a not in have]
        have.extend(new)
        return len(new)


class Lakekeeper(unittest.TestCase):
    def run_ensure(self, lk, authz="openfga", quiet=False, out=None):
        fake = FakeAuthz(lk)
        with mock.patch.object(bc.web, "request", fake_request(lk)), \
                mock.patch.dict(sys.modules, {"bootstrap.lakekeeper_authz": fake}), \
                mock.patch("bootstrap.lakekeeper_authz", fake, create=True), \
                contextlib.redirect_stdout(out or io.StringIO()):
            return bc.ensure_lakekeeper(lk, FakeKeycloak(), {"warehouse-id": "wh-1"}, authz,
                                        quiet=quiet)

    def test_quiet_sync_loop_prints_only_changes(self):
        # identity-sync re-ensures analytics every tick (quiet=True): silent when unchanged,
        # but a dropped namespace is recreated and re-granted, and that is logged.
        lk = FakeLakekeeper()
        self.run_ensure(lk)
        out = io.StringIO()
        self.assertEqual(self.run_ensure(lk, quiet=True, out=out), 0)
        self.assertEqual(out.getvalue(), "")
        del lk.namespaces["analytics"]
        lk.assignments.pop("/permissions/namespace/ns-analytics/assignments")
        out = io.StringIO()
        self.assertGreater(self.run_ensure(lk, quiet=True, out=out), 0)
        self.assertIn("created namespace analytics", out.getvalue())

    def test_namespace_and_grants_then_unchanged(self):
        lk = FakeLakekeeper()
        self.assertGreater(self.run_ensure(lk), 0)
        self.assertIn("analytics", lk.namespaces)
        self.assertEqual(lk.assignments["/permissions/warehouse/wh-1/assignments"],
                         [{"type": "select", "user": "oidc~sa-1"}])
        self.assertEqual(sorted(a["type"] for a in lk.assignments["/permissions/namespace/ns-analytics/assignments"]),
                         ["create", "modify"])
        self.assertEqual(self.run_ensure(lk), 0)

    def test_allowall_creates_namespace_only(self):
        lk = FakeLakekeeper()
        self.assertEqual(self.run_ensure(lk, authz="allowall"), 1)
        self.assertEqual(lk.assignments, {})


if __name__ == "__main__":
    unittest.main()
