"""Superset 6 for S-3: Keycloak OIDC through FAB AUTH_OAUTH, groups claim -> roles."""
import os

from flask_appbuilder.security.manager import AUTH_OAUTH

_domain = os.environ["LAB_DOMAIN"]
_port = os.environ["LAB_PORT"]
_issuer = f"https://auth.{_domain}:{_port}/realms/lakehouse"

SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = (
    f"postgresql+psycopg2://superset:{os.environ['SUPERSET_DB_PASSWORD']}@postgres:5432/superset"
)

# Behind Caddy: trust X-Forwarded-Proto/Host so redirect_uri is https://superset.<domain>:<port>
ENABLE_PROXY_FIX = True
PROXY_FIX_CONFIG = {"x_for": 1, "x_proto": 1, "x_host": 1, "x_port": 1, "x_prefix": 1}

AUTH_TYPE = AUTH_OAUTH
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Public"
AUTH_ROLES_SYNC_AT_LOGIN = True
AUTH_ROLES_MAPPING = {
    "lab-admin": ["Admin"],
    "engineer": ["Alpha", "sql_lab"],
    "analyst": ["Gamma", "sql_lab"],
    "viewer": ["Gamma"],
}
OAUTH_PROVIDERS = [
    {
        "name": "keycloak",
        "icon": "fa-key",
        "token_key": "access_token",
        "remote_app": {
            "client_id": "superset",
            "client_secret": os.environ["SUPERSET_CLIENT_SECRET"],
            "api_base_url": f"{_issuer}/protocol/",
            "server_metadata_url": f"{_issuer}/.well-known/openid-configuration",
            "client_kwargs": {"scope": "openid profile email"},
        },
    }
]
