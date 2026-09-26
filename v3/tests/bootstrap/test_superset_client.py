"""Unit tests for bootstrap.superset_client (Keycloak clients `superset` and `console`).

No Keycloak needed: a fake keycloak.Admin keeps clients in memory and, like Keycloak,
returns redirectUris/webOrigins in another order than written and gives mappers ids.
Run: python3 -m unittest discover -s v3/tests/bootstrap -v
"""
import contextlib
import copy
import io
import os
import sys
import unittest

V3 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, V3)

from bootstrap import superset_client  # noqa: E402


class FakeAdmin:
    def __init__(self):
        self.clients, self.secrets, self.mappers, self.writes = {}, {}, {}, []

    @staticmethod
    def _stored(rep):
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
            return copy.deepcopy(self.mappers.get(path.split("/")[2], []))
        raise AssertionError(f"unexpected GET {path}")

    def _add_mapper(self, cid, m):
        m = copy.deepcopy(m)
        m["id"] = f"m-{len(self.mappers.get(cid, []))}"
        self.mappers.setdefault(cid, []).append(m)

    def call(self, method, path, body=None):
        self.writes.append((method, path))
        parts = path.split("/")
        if method == "POST" and path == "/clients":
            rep = self._stored({k: v for k, v in body.items() if k not in ("secret", "protocolMappers")})
            rep["id"] = f"uuid-{body['clientId']}"
            self.clients[body["clientId"]] = rep
            self.secrets[rep["id"]] = body["secret"]
            for m in body.get("protocolMappers", []):
                self._add_mapper(rep["id"], m)
            return None
        if method == "PUT" and len(parts) == 3 and parts[1] == "clients":
            rep = self._stored({k: v for k, v in body.items() if k != "secret"})
            self.clients[rep["clientId"]] = rep
            self.secrets[rep["id"]] = body["secret"]
            return None
        if method == "POST" and path.endswith("/protocol-mappers/models"):
            self._add_mapper(parts[2], body)
            return None
        if method == "PUT" and "/protocol-mappers/models/" in path:
            ms = self.mappers[parts[2]]
            ms[[m["id"] for m in ms].index(parts[-1])] = copy.deepcopy(body)
            return None
        raise AssertionError(f"unexpected {method} {path}")

    def client(self, client_id):
        return copy.deepcopy(self.clients[client_id])


def run(fn, kc, secret="s3cret", domain="lab.localhost", port="18443"):
    with contextlib.redirect_stdout(io.StringIO()) as out:
        changed = fn(kc, secret, domain, port)
    return changed, out.getvalue()


class SupersetClient(unittest.TestCase):
    def test_create_then_unchanged(self):
        kc = FakeAdmin()
        changed, out = run(superset_client.ensure_superset_client, kc)
        self.assertTrue(changed)
        self.assertIn("created client superset", out)
        c = kc.clients["superset"]
        self.assertTrue(c["serviceAccountsEnabled"])      # Trino impersonation principal
        self.assertIn("https://superset.lab.localhost:18443/oauth-authorized/keycloak", c["redirectUris"])
        self.assertIn("https://superset.lab.localhost/oauth-authorized/keycloak", c["redirectUris"])
        names = {m["name"] for m in kc.mappers[c["id"]]}
        self.assertEqual(names, {"groups", "aud-trino"})
        n = len(kc.writes)
        changed, out = run(superset_client.ensure_superset_client, kc)
        self.assertFalse(changed, f"second run changed something: {out}")
        self.assertEqual(len(kc.writes), n)

    def test_secret_rotation_repaired(self):
        kc = FakeAdmin()
        run(superset_client.ensure_superset_client, kc)
        changed, out = run(superset_client.ensure_superset_client, kc, secret="rotated")
        self.assertTrue(changed)
        self.assertIn("secret", out)
        self.assertEqual(kc.secrets["uuid-superset"], "rotated")

    def test_empty_secret_refused(self):
        with self.assertRaises(RuntimeError):
            run(superset_client.ensure_superset_client, FakeAdmin(), secret="")


class ConsoleClient(unittest.TestCase):
    def template_console(self, kc):
        """The `console` client as the Phase 1 realm template imports it."""
        kc.call("POST", "/clients", {
            "clientId": "console", "name": "Lab Console", "enabled": True,
            "protocol": "openid-connect", "publicClient": False,
            "clientAuthenticatorType": "client-secret", "secret": "s3cret",
            "standardFlowEnabled": True, "directAccessGrantsEnabled": False,
            "redirectUris": ["https://console.lab.localhost:18443/oauth2/callback",
                             "https://console.lab.localhost/oauth2/callback"],
            "webOrigins": ["https://console.lab.localhost:18443", "https://console.lab.localhost"],
            "attributes": {"post.logout.redirect.uris":
                           "https://console.lab.localhost:18443/##https://console.lab.localhost/"},
            "protocolMappers": [
                {**superset_client.GROUPS_MAPPER,
                 "config": {**superset_client.GROUPS_MAPPER["config"], "userinfo.token.claim": "false"}},
                superset_client.audience_mapper("console")],
        })
        kc.writes.clear()

    def test_template_client_repaired_then_unchanged(self):
        kc = FakeAdmin()
        self.template_console(kc)
        changed, out = run(superset_client.ensure_console_client, kc)
        self.assertTrue(changed)
        self.assertIn("pkce.code.challenge.method", out)
        self.assertIn("repaired mapper groups", out)
        groups = [m for m in kc.mappers["uuid-console"] if m["name"] == "groups"][0]
        self.assertEqual(groups["config"]["userinfo.token.claim"], "true")
        n = len(kc.writes)
        changed, out = run(superset_client.ensure_console_client, kc)
        self.assertFalse(changed, f"second run changed something: {out}")
        self.assertEqual(len(kc.writes), n)

    def test_redirect_uri_drift_repaired(self):
        kc = FakeAdmin()
        run(superset_client.ensure_console_client, kc)
        kc.clients["console"]["redirectUris"] = ["https://evil.example/*"]
        changed, out = run(superset_client.ensure_console_client, kc)
        self.assertTrue(changed)
        self.assertIn("redirectUris", out)
        self.assertNotIn("https://evil.example/*", kc.clients["console"]["redirectUris"])


if __name__ == "__main__":
    unittest.main()
