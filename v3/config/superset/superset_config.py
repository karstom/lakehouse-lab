"""Superset for Lakehouse Lab (CONTRACT Phase 3, profile `full`; ADR-009). Baked into the image.

* Login: FAB AUTH_OAUTH against Keycloak client `superset` (ensured by bootstrap). There is
  no local admin user: Keycloak owns users, and group membership decides the roles at every
  login (S-3 recipe).
* Data: the lab's Trino, always as the logged-in user (lab_trino.py, Trino impersonation).
* Metadata: database `superset` in the shared Postgres (created by the superset-db one-shot).
"""
import os

from flask_appbuilder.security.manager import AUTH_OAUTH
from superset.security import SupersetSecurityManager

import lab_trino

_issuer = f"{os.environ['LAB_AUTH_URL'].rstrip('/')}/realms/{lab_trino.REALM}"

SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = (
    f"postgresql+psycopg2://superset:{os.environ['SUPERSET_DB_PASSWORD']}@postgres:5432/superset"
)

# Behind Caddy: trust X-Forwarded-* so OAuth redirect URIs are https://superset.<domain>[:port].
ENABLE_PROXY_FIX = True
PROXY_FIX_CONFIG = {"x_for": 1, "x_proto": 1, "x_host": 1, "x_port": 1, "x_prefix": 1}
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"

# ------------------------------------------------------------------ login and roles
# Group -> roles (CONTRACT Phase 3): lab-admin is Admin; analyst and engineer get Gamma plus
# SQL Lab; viewer gets Gamma. LAB_DATA_ROLE (created by lab_init.py) lets the non-admin roles
# open datasets at all; what they can actually read is decided by Trino, per user.
LAB_DATA_ROLE = "lab_data"
AUTH_TYPE = AUTH_OAUTH
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Public"      # no permissions: a user with no lab group sees nothing
AUTH_ROLES_SYNC_AT_LOGIN = True             # demotions apply at the next login too
AUTH_ROLES_MAPPING = {
    "lab-admin": ["Admin"],
    "engineer": ["Gamma", "sql_lab", LAB_DATA_ROLE],
    "analyst": ["Gamma", "sql_lab", LAB_DATA_ROLE],
    "viewer": ["Gamma", LAB_DATA_ROLE],
}
OAUTH_PROVIDERS = [{
    "name": "keycloak",
    "icon": "fa-key",
    "token_key": "access_token",
    "remote_app": {
        "client_id": lab_trino.CLIENT_ID,
        "client_secret": os.environ["OIDC_CLIENT_SECRET_SUPERSET"],
        "api_base_url": f"{_issuer}/protocol/",
        "server_metadata_url": f"{_issuer}/.well-known/openid-configuration",
        "client_kwargs": {"scope": "openid profile email"},
    },
}]


class LabSecurityManager(SupersetSecurityManager):
    """FAB's keycloak provider maps preferred_username -> username and groups -> role keys.
    Superset's user table needs a unique e-mail, and external (GitHub) accounts may have none,
    so fall back to a per-user placeholder in the reserved .invalid domain."""

    def get_oauth_user_info(self, provider, resp):
        info = super().get_oauth_user_info(provider, resp)
        if info.get("username") and not info.get("email"):
            info["email"] = f"{info['username']}@users.lab.invalid"
        return info


CUSTOM_SECURITY_MANAGER = LabSecurityManager

# ------------------------------------------------------------------ Trino as the user
DB_CONNECTION_MUTATOR = lab_trino.mutate_connection
# Not needed by the bundled connection (the mutator sets the auth); listed so an admin who
# edits the database can pick it in "Secure extra" without a code change.
ALLOWED_EXTRA_AUTHENTICATIONS = {"trino": {"lab_service": lab_trino.ServiceAuthentication}}

# One container, no Redis: say so explicitly (silences Flask-Limiter's startup warning).
RATELIMIT_STORAGE_URI = "memory://"

# Nothing public, no example data, no telemetry.
PUBLIC_ROLE_LIKE = None
SUPERSET_LOAD_EXAMPLES = False
SCARF_ANALYTICS = False
