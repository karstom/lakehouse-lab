"""Unit tests for bootstrap.jupyterhub_client.ensure_jupyterhub_client (idempotency).

No Keycloak needed: a fake keycloak.Admin keeps the client in memory and, like Keycloak,
returns redirectUris/webOrigins in a different order than they were written (they are sets
in Keycloak). Run: python3 -m unittest discover -s v3/tests/bootstrap -v
"""
import contextlib
import copy
import io
import os
import sys
import unittest

V3 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, V3)

from bootstrap import jupyterhub_client  # noqa: E402


class FakeAdmin:
    def __init__(self):
        self.clients = {}
        self.secrets = {}
        self.mappers = {}
        self.writes = []

    def _stored(self, rep):
        rep = copy.deepcopy(rep)
        for k in ("redirectUris", "webOrigins"):  # Keycloak's set order
            rep[k] = list(reversed(rep.get(k) or []))
        return rep

    def get(self, path):
        if path.startswith("/clients?clientId="):
            cid = path.split("=", 1)[1]
            return [self.clients[cid]] if cid in self.clients else []
        if path.endswith("/client-secret"):
            return {"value": self.secrets.get(path.split("/")[2])}
        if path.endswith("/protocol-mappers/models"):
            return list(self.mappers.get(path.split("/")[2], []))
        raise AssertionError(f"unexpected GET {path}")

    def call(self, method, path, body=None):
        self.writes.append((method, path))
        if method == "POST" and path == "/clients":
            rep = self._stored({k: v for k, v in body.items() if k not in ("secret", "protocolMappers")})
            rep["id"] = f"uuid-{body['clientId']}"
            self.clients[body["clientId"]] = rep
            self.secrets[rep["id"]] = body["secret"]
            self.mappers[rep["id"]] = [dict(m) for m in body.get("protocolMappers", [])]
            return None
        if method == "PUT" and path.startswith("/clients/"):
            rep = self._stored({k: v for k, v in body.items() if k != "secret"})
            self.clients[rep["clientId"]] = rep
            self.secrets[rep["id"]] = body["secret"]
            return None
        if method == "POST" and path.endswith("/protocol-mappers/models"):
            self.mappers.setdefault(path.split("/")[2], []).append(dict(body))
            return None
        raise AssertionError(f"unexpected {method} {path}")

    def client(self, client_id):
        return copy.deepcopy(self.clients[client_id])


def ensure(kc, secret="s3cret", domain="lab.localhost", port="18443"):
    with contextlib.redirect_stdout(io.StringIO()) as out:
        changed = jupyterhub_client.ensure_jupyterhub_client(kc, secret, domain, port)
    return changed, out.getvalue()


class EnsureJupyterhubClient(unittest.TestCase):
    def test_create_then_unchanged(self):
        kc = FakeAdmin()
        changed, out = ensure(kc)
        self.assertTrue(changed)
        self.assertIn("created client jupyterhub", out)
        n = len(kc.writes)
        changed, out = ensure(kc)
        self.assertFalse(changed, f"second run changed something: {out}")
        self.assertEqual(len(kc.writes), n, "second run wrote to Keycloak")

    def test_repairs_secret_and_lifespan(self):
        kc = FakeAdmin()
        ensure(kc)
        c = kc.clients["jupyterhub"]
        c["attributes"]["access.token.lifespan"] = "300"
        kc.secrets[c["id"]] = "old"
        changed, out = ensure(kc)
        self.assertTrue(changed)
        self.assertIn("attributes.access.token.lifespan", out)
        self.assertIn("secret", out)
        self.assertFalse(ensure(kc)[0])

    def test_adds_missing_mapper(self):
        kc = FakeAdmin()
        ensure(kc)
        cid = kc.clients["jupyterhub"]["id"]
        kc.mappers[cid] = [m for m in kc.mappers[cid] if m["name"] != "aud-lakekeeper"]
        changed, out = ensure(kc)
        self.assertTrue(changed)
        self.assertIn("added mapper aud-lakekeeper", out)
        self.assertFalse(ensure(kc)[0])


if __name__ == "__main__":
    unittest.main()
