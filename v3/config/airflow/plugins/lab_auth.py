"""Airflow API as the logged-in lab user, from their workspace (CONTRACT Phase 5, the
lab-context MCP tool `airflow_runs`).

Airflow 3's REST API accepts only Airflow's own JWT. With the Keycloak auth manager that JWT
carries the user's Keycloak access token, and every authorization decision is a Keycloak UMA
request made with that token (bootstrap/airflow_client.py builds the model: lab-admin Admin,
engineer User+Op, analyst/viewer read-only). The provider mints API JWTs only from a username
and password (POST /auth/token), which a workspace does not have: its only credential is the
user's own Keycloak access token (lakehouse.lab_token()).

This plugin adds ONE route, POST /lab-auth/token with `Authorization: Bearer <Keycloak access
token>`, that exchanges such a token for an Airflow API JWT. A token is accepted when:
  * its signature verifies against the realm's keys (fetched from Keycloak on the lab network,
    cached), and it is not expired;
  * its issuer is the lab realm's public issuer (LAB_AUTH_URL, the single source of the public
    origin), and it is an access token (`typ` Bearer);
  * it was issued to an allowed client (`azp`, default only `jupyterhub`: the workspace login;
    LAB_AIRFLOW_BEARER_CLIENTS), so tokens minted for other clients are not accepted;
  * it has `sub` and `preferred_username`.
The Airflow JWT it returns carries that same Keycloak token and no refresh token, and expires
no later than the Keycloak token (and at most [api_auth] jwt_expiration_time). It grants
nothing by itself: Keycloak still decides every request, for this user. Mirrors
config/superset/lab_bearer.py (Phase 4, DEC_V3_SUPERSET_API_BEARER_KEYCLOAK).
"""
import logging
import os
import threading
import time

import jwt
from fastapi import FastAPI, HTTPException, Request

from airflow.plugins_manager import AirflowPlugin

log = logging.getLogger(__name__)

REALM = "lakehouse"
JWKS_URL = os.environ.get("LAB_KEYCLOAK_JWKS_URL",
                          f"http://keycloak:8080/realms/{REALM}/protocol/openid-connect/certs")
DEFAULT_CLIENTS = "jupyterhub"
MIN_LEFT_S = 30          # refuse a token that is about to expire

_lock = threading.Lock()
_jwks = None


def _jwks_client():
    global _jwks
    with _lock:
        if _jwks is None:
            _jwks = jwt.PyJWKClient(JWKS_URL, cache_keys=True, lifespan=600, timeout=10)
        return _jwks


def issuer():
    return f"{os.environ['LAB_AUTH_URL'].rstrip('/')}/realms/{REALM}"


def allowed_clients():
    raw = os.environ.get("LAB_AIRFLOW_BEARER_CLIENTS", DEFAULT_CLIENTS)
    return {c.strip() for c in raw.split(",") if c.strip()}


def verify(token, key=None):
    """The token's claims if it is acceptable, else raises jwt.InvalidTokenError."""
    if key is None:
        key = _jwks_client().get_signing_key_from_jwt(token).key
    claims = jwt.decode(token, key, algorithms=["RS256", "ES256", "PS256"], issuer=issuer(),
                        options={"verify_aud": False, "require": ["exp", "iat", "iss", "sub"]})
    if claims.get("typ") != "Bearer":
        raise jwt.InvalidTokenError("not an access token")
    if claims.get("azp") not in allowed_clients():
        raise jwt.InvalidTokenError(f"client {claims.get('azp')!r} is not allowed")
    if not claims.get("preferred_username"):
        raise jwt.InvalidTokenError("no preferred_username")
    if float(claims["exp"]) - time.time() < MIN_LEFT_S:
        raise jwt.InvalidTokenError("token expires too soon")
    return claims


app = FastAPI(title="Lakehouse Lab: Airflow API token for a workspace user",
              description="POST /token with the user's Keycloak access token (Bearer).")


@app.post("/token", status_code=201)
def exchange(request: Request):
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    token = header[7:].strip()
    try:
        claims = verify(token)
    except Exception as e:  # noqa: BLE001 - any failure means "not authenticated"
        log.info("lab_auth: refused a token (%s)", type(e).__name__)
        raise HTTPException(status_code=403, detail="token not accepted") from None
    from airflow.api_fastapi.app import get_auth_manager
    from airflow.configuration import conf
    from airflow.providers.keycloak.auth_manager.user import KeycloakAuthManagerUser
    user = KeycloakAuthManagerUser(user_id=claims["sub"], name=claims["preferred_username"],
                                   access_token=token, refresh_token=None)
    left = int(float(claims["exp"]) - time.time())
    ttl = max(1, min(left, conf.getint("api_auth", "jwt_expiration_time")))
    log.info("lab_auth: API token for %s (%d s)", claims["preferred_username"], ttl)
    return {"access_token": get_auth_manager().generate_api_jwt(user, expiration_time_in_seconds=ttl),
            "expires_in": ttl}


class LabAuthPlugin(AirflowPlugin):
    name = "lab_auth"
    fastapi_apps = [{"app": app, "url_prefix": "/lab-auth", "name": "Lab workspace token"}]
