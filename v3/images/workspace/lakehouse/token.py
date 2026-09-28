"""lab_token(): the ONE place workspace clients get the logged-in user's Keycloak token.

Mechanism (CONTRACT Phase 2, "Identity in the workspace"):

* JupyterHub logs the user in through Keycloak (client `jupyterhub`) and keeps the access
  and refresh tokens in its encrypted auth state (`enable_auth_state`).
* This function asks the hub for them: `GET $JUPYTERHUB_API_URL/users/$JUPYTERHUB_USER` with
  the server's own `JUPYTERHUB_API_TOKEN`. The hub grants that token `admin:auth_state!user`,
  so it can read the auth state of its own user and of nobody else. (The shorter `/user`
  endpoint never includes auth_state.)
* Every hub API request passes through the hub's `refresh_user_hook` (at most once a minute
  per user). When the access token has less than LAB_TOKEN_MIN_TTL left, the hub uses the
  refresh token to get a new one. The singleuser server's activity reports reach the hub
  every few minutes, so the Keycloak session stays alive while the workspace runs.

No secret lives in the workspace: not the client secret, and no long-lived token file.
Tokens are cached in this process until they are within `min_ttl` of expiry.
"""
import base64
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


class LabTokenError(RuntimeError):
    """No usable token: not running under JupyterHub, or the login has expired."""


_lock = threading.Lock()
_cache = {"token": None, "exp": 0.0}

# Seconds a returned token must still be valid. Per-request callers (Trino, PyIceberg) are
# fine with little; `lab-token` for a long command asks for more.
DEFAULT_MIN_TTL = 120


def token_claims(token):
    """Decode a JWT's payload WITHOUT verifying it (for display and expiry only; the
    services verify signatures)."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError) as e:
        raise LabTokenError(f"not a JWT: {e}") from None


def _from_hub():
    api = os.environ.get("JUPYTERHUB_API_URL")
    api_token = os.environ.get("JUPYTERHUB_API_TOKEN")
    user = os.environ.get("JUPYTERHUB_USER")
    if not api or not api_token or not user:
        raise LabTokenError(
            "lab_token() needs JupyterHub (JUPYTERHUB_API_URL / JUPYTERHUB_API_TOKEN / "
            "JUPYTERHUB_USER are not set). Open the workspace from the jupyter. URL of the lab.")
    url = f"{api.rstrip('/')}/users/{urllib.parse.quote(user, safe='')}"
    req = urllib.request.Request(url, headers={"Authorization": f"token {api_token}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            model = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise LabTokenError(
                "JupyterHub refused the request: your login has expired. Log out of the "
                "hub and log in again, then retry.") from None
        raise LabTokenError(f"JupyterHub API error: HTTP {e.code}") from None
    except OSError as e:
        raise LabTokenError(f"JupyterHub API unreachable: {e}") from None
    state = model.get("auth_state") or {}
    token = state.get("access_token")
    if not token:
        raise LabTokenError(
            "JupyterHub returned no token for you (no auth state). Log out of the hub and "
            "log in again.")
    return token


def lab_token(min_ttl=DEFAULT_MIN_TTL):
    """A Keycloak access token for the logged-in user, valid for at least `min_ttl`
    seconds. Use it as a Bearer token for Trino, Lakekeeper and the other lab services."""
    with _lock:
        now = time.time()
        if _cache["token"] and _cache["exp"] - now > min_ttl:
            return _cache["token"]
        token = _from_hub()
        exp = float(token_claims(token).get("exp", 0))
        # The hub refreshes when fewer than LAB_TOKEN_MIN_TTL seconds are left (checked at
        # most once a minute), so a min_ttl above that guarantee can still get a token with
        # less time left. It is returned anyway while it is valid.
        if exp <= now:
            raise LabTokenError("the hub returned an expired token; log out and in again")
        _cache.update(token=token, exp=exp)
        return token
