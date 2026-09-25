"""JupyterHub for S-3: Keycloak OIDC via GenericOAuthenticator. No spawning (S-4's job)."""
import os

domain = os.environ["LAB_DOMAIN"]
port = os.environ["LAB_PORT"]
issuer = f"https://auth.{domain}:{port}/realms/lakehouse"
oidc = f"{issuer}/protocol/openid-connect"

c = get_config()  # noqa: F821
c.JupyterHub.authenticator_class = "generic-oauth"
c.JupyterHub.db_url = "sqlite:////srv/jupyterhub/data/jupyterhub.sqlite"
c.JupyterHub.cookie_secret_file = "/srv/jupyterhub/data/jupyterhub_cookie_secret"
c.JupyterHub.default_url = "/hub/home"

a = c.GenericOAuthenticator
a.client_id = "jupyterhub"
a.client_secret = os.environ["JUPYTERHUB_CLIENT_SECRET"]
a.oauth_callback_url = f"https://jupyter.{domain}:{port}/hub/oauth_callback"
a.authorize_url = f"{oidc}/auth"
a.token_url = f"{oidc}/token"
a.userdata_url = f"{oidc}/userinfo"
a.logout_redirect_url = f"{oidc}/logout"
# Tornado uses pycurl here, which ignores SSL_CERT_FILE: pass the CA bundle explicitly.
a.http_request_kwargs = {"ca_certs": "/trust/ca-bundle.crt"}
a.scope = ["openid", "profile", "email"]
a.username_claim = "preferred_username"
a.auto_login = True
a.manage_groups = True
a.auth_state_groups_key = "oauth_user.groups"
a.allowed_groups = {"lab-admin", "engineer", "analyst", "viewer"}
a.admin_groups = {"lab-admin"}
