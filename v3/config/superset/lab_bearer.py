"""Superset REST API as the logged-in lab user, from their workspace (CONTRACT Phase 4, A4).

Superset's login is a browser OAuth flow (FAB AUTH_OAUTH), and FAB's API login only knows
database and LDAP users. The analyst track's A4 checkpoint must look at a learner's charts
and dashboards *as that learner*, from their workspace, where the only credential is their
own Keycloak access token (lakehouse.lab_token()). This module lets Superset accept that
token:

  Authorization: Bearer <Keycloak access token of the user>

It is a Flask-Login request loader, consulted only when a request has no session user. A
token is accepted when:
  * its signature verifies against the realm's keys (fetched from Keycloak on the lab
    network and cached), and it is not expired;
  * its issuer is the lab realm's public issuer (LAB_AUTH_URL, the single source of the
    public origin), and it is an access token (`typ` Bearer);
  * it was issued to an allowed client (`azp`, default only `jupyterhub`: the workspace's
    own login), so tokens minted for other clients are not accepted;
  * a Superset user with that `preferred_username` already exists and is active (users
    are created only by the browser login, as before).
The user's roles are recomputed from the token's `groups` with AUTH_ROLES_MAPPING, as a
login would; a token whose groups map to no role is refused. Nothing else changes: every
query still runs in Trino as that user (lab_trino.py).
"""
import logging
import os
import threading

import jwt

log = logging.getLogger(__name__)

REALM = "lakehouse"
JWKS_URL = f"http://keycloak:8080/realms/{REALM}/protocol/openid-connect/certs"
DEFAULT_CLIENTS = "jupyterhub"

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
    raw = os.environ.get("LAB_SUPERSET_BEARER_CLIENTS", DEFAULT_CLIENTS)
    return {c.strip() for c in raw.split(",") if c.strip()}


def verify(token, key=None):
    """The token's claims if it is acceptable, else raises jwt.InvalidTokenError."""
    if key is None:
        key = _jwks_client().get_signing_key_from_jwt(token).key
    claims = jwt.decode(token, key, algorithms=["RS256", "ES256", "PS256"], issuer=issuer(),
                        options={"verify_aud": False, "require": ["exp", "iat", "iss"]})
    if claims.get("typ") != "Bearer":
        raise jwt.InvalidTokenError("not an access token")
    if claims.get("azp") not in allowed_clients():
        raise jwt.InvalidTokenError(f"client {claims.get('azp')!r} is not allowed")
    if not claims.get("preferred_username"):
        raise jwt.InvalidTokenError("no preferred_username")
    return claims


def load_user(sm, request):
    """Flask-Login request loader: the Superset user named by a valid bearer token, or None."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    try:
        claims = verify(header[len("Bearer "):].strip())
    except Exception as e:  # noqa: BLE001 - any failure means "not authenticated"
        log.info("lab bearer: token refused: %s", e)
        return None
    user = sm.find_user(username=claims["preferred_username"])
    if user is None or not user.is_active:
        log.info("lab bearer: no active Superset user %r (log in to Superset once in the "
                 "browser)", claims["preferred_username"])
        return None
    roles = sm.get_roles_from_keys(claims.get("groups") or [])
    if not roles:
        return None
    if set(user.roles) != roles:
        user.roles = list(roles)
        sm.update_user(user)
    return user
