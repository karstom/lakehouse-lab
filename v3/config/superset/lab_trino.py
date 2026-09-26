"""Superset -> Trino as the logged-in user (CONTRACT Phase 3, "Superset -> Trino as the user").

Superset authenticates to Trino as its own service client `superset` (Keycloak client
credentials; Trino principal `service-account-superset`) and asks Trino to run each query
as the Superset user (X-Trino-User). Trino's `impersonation` rules (config/trino/rules.json)
allow exactly that principal to do so, and then authorize the query as the person: their
groups, their catalog/schema/table rules. Nobody's own token is involved.

`mutate_connection` is Superset's DB_CONNECTION_MUTATOR. It applies to every engine Superset
opens against the lab's Trino (SQL Lab, charts, dashboards, metadata), whatever an admin
typed into the database's URI or extras:
  * the session user is always the logged-in username; with no logged-in user (startup,
    CLI) it is the service account itself, which the Trino rules give no data access;
  * the credentials are always the service token (never a user password or a static JWT).
"""
import os
import threading
import time
import urllib.parse

import requests
from trino.auth import Authentication

REALM = "lakehouse"
CLIENT_ID = "superset"
# Trino's principal for this client's service account (principal-field=preferred_username).
SERVICE_USER = f"service-account-{CLIENT_ID}"
# Back channel: tokens still carry the public issuer (Keycloak KC_HOSTNAME), which Trino checks.
TOKEN_URL = f"http://keycloak:8080/realms/{REALM}/protocol/openid-connect/token"
# Refresh this many seconds before expiry (tokens live 5 min by the realm default).
EARLY = 60


def trino_endpoint():
    """(host, port) of the lab's Trino, the `trino.` sibling of LAB_AUTH_URL (the single
    source of the public origin, INV_V3_PUBLIC_ORIGIN_SINGLE_SOURCE). Containers reach it
    through Caddy's network alias. The port is explicit: the Trino client defaults to 8080."""
    u = urllib.parse.urlsplit(os.environ["LAB_AUTH_URL"])
    host = u.hostname
    if not host or not host.startswith("auth."):
        raise RuntimeError(f"LAB_AUTH_URL must be https://auth.<domain>[:port], got {u.geturl()!r}")
    return "trino." + host[len("auth."):], u.port or 443


class _ClientCredentials(requests.auth.AuthBase):
    """Bearer token from Keycloak client credentials, cached and renewed before expiry."""

    def __init__(self):
        self._lock = threading.Lock()
        self._token = None
        self._expires = 0.0

    def token(self):
        with self._lock:
            if self._token is None or time.time() > self._expires - EARLY:
                r = requests.post(TOKEN_URL, timeout=10, data={
                    "grant_type": "client_credentials", "client_id": CLIENT_ID,
                    "client_secret": os.environ["OIDC_CLIENT_SECRET_SUPERSET"],
                    # Trino reads the principal from Keycloak's userinfo, which needs `openid`.
                    "scope": "openid"})
                r.raise_for_status()
                body = r.json()
                self._token = body["access_token"]
                self._expires = time.time() + int(body.get("expires_in", 300))
            return self._token

    def __call__(self, req):
        req.headers["Authorization"] = f"Bearer {self.token()}"
        return req


_CREDENTIALS = _ClientCredentials()


class ServiceAuthentication(Authentication):
    """trino-python Authentication that signs every request with the service token."""

    def set_http_session(self, http_session):
        http_session.auth = _CREDENTIALS
        return http_session

    def get_exceptions(self):
        return ()

    def __eq__(self, other):
        return isinstance(other, ServiceAuthentication)

    def __hash__(self):
        return hash(ServiceAuthentication)


def mutate_connection(uri, params, username, security_manager, source):
    """Superset DB_CONNECTION_MUTATOR (see module docstring)."""
    host, port = trino_endpoint()
    if uri.drivername != "trino" or (uri.host or "").lower() != host:
        return uri, params
    user = username or SERVICE_USER
    uri = uri.set(username=user, password=None, port=port)
    connect_args = params.setdefault("connect_args", {})
    connect_args.update({
        "user": user,                       # wins over the URI user in the trino dialect
        "http_scheme": "https",
        "auth": ServiceAuthentication(),
        "verify": os.environ.get("REQUESTS_CA_BUNDLE", True),
        "source": "superset",
    })
    return uri, params
