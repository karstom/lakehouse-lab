"""JupyterHub for Lakehouse Lab V3 (CONTRACT Phase 2; ADR-007).

* Login: GenericOAuthenticator against Keycloak realm `lakehouse`, confidential client
  `jupyterhub` (created by bootstrap/jupyterhub_client.py). Tokens are kept in the encrypted
  auth state (JUPYTERHUB_CRYPT_KEY) and refreshed by `_refresh_user_hook` below, so that the
  workspace's lab_token() always gets a token of the logged-in user with time left on it.
* Admin: Keycloak group `lab-admin`. Allowed: the four lab groups.
* Spawner: DockerSpawner through the docker-socket-proxy (never the Docker socket itself).
  Every workspace container and home volume carries the compose project label plus
  `lab.role=workspace` and the `${COMPOSE_PROJECT_NAME}-ws-` / `-home-` name prefixes, joins
  only the `lab` network, and has WORKSPACE_MEM / WORKSPACE_CPUS limits.

Public URLs are never rebuilt from LAB_DOMAIN/LAB_HTTPS_PORT here: the port suffix is taken
from LAB_AUTH_URL, the single derived origin (installer/lib.sh, INV_V3_PUBLIC_ORIGIN_SINGLE_SOURCE).
"""
import base64
import inspect
import json
import os
import time
import urllib.parse

import docker
from dockerspawner import DockerSpawner

c = get_config()  # noqa: F821


def need(name):
    v = os.environ.get(name)
    if not v:
        raise SystemExit(f"jupyterhub_config: missing required environment variable {name}")
    return v


PROJECT = need("COMPOSE_PROJECT_NAME")
DOMAIN = need("LAB_DOMAIN")
AUTH_URL = need("LAB_AUTH_URL").rstrip("/")
_AUTH_PREFIX = f"https://auth.{DOMAIN}"
if not AUTH_URL.startswith(_AUTH_PREFIX):
    raise SystemExit(f"jupyterhub_config: LAB_AUTH_URL {AUTH_URL!r} does not match LAB_DOMAIN {DOMAIN!r}")
PORT_SUFFIX = AUTH_URL[len(_AUTH_PREFIX):]          # "" on 443, ":<port>" otherwise


def public_url(svc):
    return f"https://{svc}.{DOMAIN}{PORT_SUFFIX}"


JUPYTER_URL = public_url("jupyter")
TRINO_HOST = f"trino.{DOMAIN}"
TRINO_PORT = PORT_SUFFIX.lstrip(":") or "443"
ISSUER = f"{AUTH_URL}/realms/lakehouse"
KC_INTERNAL = "http://keycloak:8080/realms/lakehouse/protocol/openid-connect"
CA_BUNDLE = "/trust/ca-bundle.crt"
CATALOG_URI = "http://lakekeeper:8181/catalog"
LAB_GROUPS = {"lab-admin", "engineer", "analyst", "viewer"}

# ------------------------------------------------------------------------------ hub
c.JupyterHub.bind_url = "http://0.0.0.0:8000"
c.JupyterHub.hub_bind_url = "http://0.0.0.0:8081"
c.JupyterHub.hub_connect_url = "http://jupyterhub:8081"      # compose service name on `lab`
c.JupyterHub.db_url = "sqlite:////srv/jupyterhub/data/jupyterhub.sqlite"
c.JupyterHub.cookie_secret_file = "/srv/jupyterhub/data/jupyterhub_cookie_secret"
c.ConfigurableHTTPProxy.pid_file = "/srv/jupyterhub/data/jupyterhub-proxy.pid"
c.JupyterHub.default_url = "/hub/home"
# On a graceful stop (lab down) the hub stops every workspace it started.
c.JupyterHub.cleanup_servers = True

# The server's own API token may read its user's auth state, and only that (lab_token()).
# A token never gets more than its owner, so every user also needs `admin:auth_state` on
# themselves (their own Keycloak tokens); without it only lab-admins (hub admins) got one.
c.JupyterHub.load_roles = [
    {"name": "user", "scopes": ["self", "admin:auth_state!user"]},
    {"name": "server", "scopes": ["users:activity!user", "access:servers!server",
                                  "read:users!user", "admin:auth_state!user"]},
]

# ------------------------------------------------------------------------------ login
# Access tokens handed to workspaces keep at least this many seconds of validity; the hub
# checks at most every auth_refresh_age seconds. Together with the `jupyterhub` client's
# access-token lifespan (bootstrap/jupyterhub_client.py) this also keeps the Keycloak session
# alive while the workspace reports activity.
TOKEN_MIN_TTL = int(os.environ.get("LAB_TOKEN_MIN_TTL", "2700"))


def _jwt_exp(token):
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return float(json.loads(base64.urlsafe_b64decode(payload))["exp"])


async def _refresh_user_hook(authenticator, user, auth_state):
    """Refresh the user's tokens BEFORE they expire (the default refresh_user only acts
    after the access token was rejected). Returns True (no change), False (log in again)
    or a new auth model. Uses only public OAuthenticator methods."""
    if not auth_state or not auth_state.get("access_token"):
        return False
    try:
        left = _jwt_exp(auth_state["access_token"]) - time.time()
    except (IndexError, KeyError, ValueError):
        return None                                   # not a JWT: default behaviour
    if left > TOKEN_MIN_TTL:
        return True
    refresh_token = auth_state.get("refresh_token")
    if not refresh_token:
        return False
    try:
        token_info = await authenticator.get_token_info(
            None, authenticator.build_refresh_token_request_params(refresh_token))
    except Exception as e:  # noqa: BLE001 - any failure means "log in again"
        authenticator.log.info("token refresh for %s failed (%s); login required", user.name, e)
        return False
    token_info.setdefault("refresh_token", refresh_token)
    user_info = await authenticator.token_to_user(token_info)
    name = authenticator.normalize_username(authenticator.user_info_to_username(user_info))
    if name != user.name:
        authenticator.log.warning("refreshed token belongs to %s, not %s", name, user.name)
        return False
    state = authenticator.build_auth_state_dict(token_info, user_info)
    # manage_groups needs `groups` in every auth model; login gets it from a private
    # OAuthenticator step, so do the same here with the public get_user_groups().
    groups = authenticator.get_user_groups(state)
    if inspect.isawaitable(groups):
        groups = await groups
    groups = set(groups or ())
    if authenticator.allowed_groups and not groups & authenticator.allowed_groups:
        authenticator.log.info("%s is no longer in an allowed group; login required", user.name)
        return False
    model = await authenticator.update_auth_model({
        "name": user.name, "auth_state": state, "groups": sorted(groups),
        "admin": bool(groups & authenticator.admin_groups)})
    authenticator.log.info("refreshed tokens for %s (had %ds left)", user.name, int(left))
    return model


c.JupyterHub.authenticator_class = "generic-oauth"
c.Authenticator.enable_auth_state = True             # key: JUPYTERHUB_CRYPT_KEY
c.Authenticator.auth_refresh_age = 60
c.Authenticator.refresh_pre_spawn = True
c.Authenticator.manage_groups = True
c.Authenticator.allowed_groups = LAB_GROUPS
c.Authenticator.admin_groups = {"lab-admin"}
c.Authenticator.auto_login = True

a = c.GenericOAuthenticator
a.client_id = "jupyterhub"
a.client_secret = need("OIDC_CLIENT_SECRET_JUPYTERHUB")
a.oauth_callback_url = f"{JUPYTER_URL}/hub/oauth_callback"
a.authorize_url = f"{ISSUER}/protocol/openid-connect/auth"     # the browser goes here
# Back channel on the lab network. Tokens still carry the public issuer (KC_HOSTNAME).
a.token_url = f"{KC_INTERNAL}/token"
a.userdata_url = f"{KC_INTERNAL}/userinfo"
a.scope = ["openid", "profile", "email"]
a.username_claim = "preferred_username"
a.auth_state_groups_key = "oauth_user.groups"
a.refresh_user_hook = _refresh_user_hook
# Tornado's pycurl client ignores SSL_CERT_FILE: pass the lab CA explicitly (anti-pattern list).
a.http_request_kwargs = {"ca_certs": CA_BUNDLE}
a.logout_redirect_url = (
    f"{ISSUER}/protocol/openid-connect/logout?client_id=jupyterhub&post_logout_redirect_uri="
    + urllib.parse.quote(f"{JUPYTER_URL}/hub/", safe=""))

# ------------------------------------------------------------------------------ spawner
# Names and labels (CONTRACT Phase 2 "Docker access"). `lab reset` selects home volumes by
# these labels; the name templates are the single source of the names.
LABELS = {"com.docker.compose.project": PROJECT, "lab.role": "workspace"}
HOME_VOLUME_TEMPLATE = f"{PROJECT}-home-{{username}}"
CONTAINER_NAME_TEMPLATE = f"{PROJECT}-ws-{{username}}"
# Compose names project resources <project>_<name>.
LAB_NETWORK = f"{PROJECT}_lab"
TRUST_VOLUME = f"{PROJECT}_trust"


class LabSpawner(DockerSpawner):
    """DockerSpawner that
    * addresses its container by NAME, never by id, so the socket proxy can confine every
      container call to the `<project>-ws-` prefix (ids and id prefixes could reach any
      container on the host's daemon), and
    * creates the user's home volume itself, with the lab labels (Docker would create it
      implicitly, unlabelled, on first mount)."""

    async def get_object(self):
        obj = await super().get_object()
        if obj is not None:
            self.object_id = self.object_name
        return obj

    async def create_object(self):
        obj = await super().create_object()
        return {**obj, self.object_id_key: self.object_name}

    async def start(self):
        name = self.format_volume_name(HOME_VOLUME_TEMPLATE, self)
        try:
            vol = await self.docker("inspect_volume", name)
            if (vol.get("Labels") or {}).get("lab.role") != "workspace":
                self.log.warning("home volume %s exists without lab labels", name)
        except docker.errors.NotFound:
            await self.docker("create_volume", name, labels=dict(LABELS))
            self.log.info("created home volume %s", name)
        return await super().start()


c.JupyterHub.spawner_class = LabSpawner
s = c.DockerSpawner
s.image = need("LAB_WORKSPACE_IMAGE")
s.pull_policy = "never"              # built by compose; the socket proxy refuses pulls anyway
# The image's ENTRYPOINT (start-workspace.sh: per-home wiring, then exec) stays in place;
# only the command is set. It must be explicit: the image's CMD is empty, and DockerSpawner
# fails on an image without Config.Cmd. Never override the entrypoint (ADR-007 rule).
s.cmd = ["jupyterhub-singleuser"]
s.name_template = CONTAINER_NAME_TEMPLATE
s.network_name = LAB_NETWORK
s.use_internal_ip = True
s.remove = True                      # containers are disposable; the home volume persists
s.extra_create_kwargs = {"labels": dict(LABELS)}
s.volumes = {
    HOME_VOLUME_TEMPLATE: "/home/jovyan",
    TRUST_VOLUME: {"bind": "/trust", "mode": "ro"},
}
s.notebook_dir = "/home/jovyan"
# Compose-style sizes ("2g", "1536m"); DockerSpawner's byte parser wants upper-case suffixes.
s.mem_limit = need("WORKSPACE_MEM").upper()
s.cpu_limit = float(need("WORKSPACE_CPUS"))
s.start_timeout = 180
s.http_timeout = 120
c.Spawner.default_url = "/lab"
c.Spawner.environment = {
    "LAB_DOMAIN": DOMAIN,
    "LAB_AUTH_URL": AUTH_URL,
    "LAB_JUPYTER_URL": JUPYTER_URL,
    "LAB_TRINO_URL": public_url("trino"),
    "LAB_TRINO_HOST": TRINO_HOST,
    "LAB_TRINO_PORT": TRINO_PORT,
    "LAB_CATALOG_URL": CATALOG_URI,
    "PYICEBERG_CATALOG__LAKEHOUSE__URI": CATALOG_URI,
    "LAB_WAREHOUSE": "lakehouse",
    "SPARK_REMOTE": os.environ.get("LAB_SPARK_REMOTE", "sc://spark-connect:15002"),
    "SSL_CERT_FILE": CA_BUNDLE,
    "REQUESTS_CA_BUNDLE": CA_BUNDLE,
    "TZ": os.environ.get("TZ", "UTC"),
}
