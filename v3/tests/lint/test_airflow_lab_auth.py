"""Airflow plugin lab_auth (CONTRACT Phase 5, MCP tool airflow_runs): which Keycloak tokens
POST /lab-auth/token accepts. Runs without Airflow or FastAPI (small stand-ins), with real
RS256 tokens when PyJWT + cryptography are installed (skipped otherwise).
"""
import importlib.util
import os
import sys
import time
import types
import unittest

V3 = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(V3, "config", "airflow", "plugins", "lab_auth.py")
ISSUER_ORIGIN = "https://auth.lab.localhost"

try:
    import jwt  # noqa: F401
    from cryptography.hazmat.primitives.asymmetric import rsa
    HAVE_JWT = True
except ImportError:  # the CI lint runner may not have them
    HAVE_JWT = False


def load_plugin():
    fastapi = types.ModuleType("fastapi")

    class FastAPI:
        def __init__(self, **kw):
            pass

        def post(self, *a, **kw):
            return lambda f: f

    class HTTPException(Exception):
        def __init__(self, status_code, detail=None):
            super().__init__(detail)
            self.status_code = status_code

    fastapi.FastAPI, fastapi.HTTPException, fastapi.Request = FastAPI, HTTPException, object
    airflow = types.ModuleType("airflow")
    pm = types.ModuleType("airflow.plugins_manager")
    pm.AirflowPlugin = type("AirflowPlugin", (), {})
    saved = {k: sys.modules.get(k) for k in ("fastapi", "airflow", "airflow.plugins_manager")}
    sys.modules.update({"fastapi": fastapi, "airflow": airflow, "airflow.plugins_manager": pm})
    try:
        spec = importlib.util.spec_from_file_location("lab_auth_under_test", PLUGIN)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return mod


@unittest.skipUnless(HAVE_JWT, "PyJWT/cryptography not installed")
class Verify(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_plugin()
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.other = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        self._env = {k: os.environ.get(k) for k in ("LAB_AUTH_URL", "LAB_AIRFLOW_BEARER_CLIENTS")}
        os.environ["LAB_AUTH_URL"] = ISSUER_ORIGIN
        os.environ.pop("LAB_AIRFLOW_BEARER_CLIENTS", None)

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def token(self, key=None, **over):
        now = int(time.time())
        claims = {"iss": f"{ISSUER_ORIGIN}/realms/lakehouse", "sub": "u-1", "iat": now,
                  "exp": now + 300, "typ": "Bearer", "azp": "jupyterhub",
                  "preferred_username": "alice"}
        claims.update(over)
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode(claims, key or self.key, algorithm="RS256")

    def verify(self, tok):
        return self.mod.verify(tok, key=self.key.public_key())

    def refused(self, tok):
        with self.assertRaises(jwt.InvalidTokenError):
            self.verify(tok)

    def test_workspace_token_accepted(self):
        self.assertEqual(self.verify(self.token())["preferred_username"], "alice")

    def test_wrong_signature(self):
        self.refused(self.token(key=self.other))

    def test_wrong_issuer(self):
        self.refused(self.token(iss="https://evil.example/realms/lakehouse"))

    def test_other_client(self):
        self.refused(self.token(azp="superset"))

    def test_extra_allowed_client(self):
        os.environ["LAB_AIRFLOW_BEARER_CLIENTS"] = "jupyterhub, lab-cli"
        self.assertTrue(self.verify(self.token(azp="lab-cli")))

    def test_not_an_access_token(self):
        self.refused(self.token(typ="ID"))
        self.refused(self.token(typ="Refresh"))

    def test_expired_or_about_to(self):
        self.refused(self.token(exp=int(time.time()) - 5))
        self.refused(self.token(exp=int(time.time()) + 10))

    def test_missing_claims(self):
        self.refused(self.token(preferred_username=None))
        self.refused(self.token(sub=None))

    def test_alg_none_refused(self):
        tok = jwt.encode({"iss": f"{ISSUER_ORIGIN}/realms/lakehouse", "sub": "x",
                          "iat": int(time.time()), "exp": int(time.time()) + 300,
                          "typ": "Bearer", "azp": "jupyterhub", "preferred_username": "alice"},
                         key=None, algorithm="none")
        self.refused(tok)


if __name__ == "__main__":
    unittest.main()
