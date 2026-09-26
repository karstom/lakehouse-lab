"""Keycloak client `jupyterhub` (CONTRACT Phase 2): created or repaired idempotently by
bootstrap, never only in the realm template, because the realm is imported on first start
only and existing installs would never get it (pattern: keycloak.Admin.ensure_sync_client).

Tokens this client issues are what workspace clients use as the logged-in user (lab_token()
in the workspace image), so it carries the same claims the services check:
  * `groups` (JupyterHub admin/allowed groups; also userinfo),
  * audiences `trino` (Trino JWT auth) and `lakekeeper` (Lakekeeper OIDC).

Access tokens from this client live ACCESS_TOKEN_LIFESPAN seconds (realm default: 5 min), so
a token handed to a long command (dbt, a DuckDB ATTACH) stays valid. The hub refreshes when
less than LAB_TOKEN_MIN_TTL (default 2700 s) is left, i.e. every ~15 min while the workspace
runs, which also keeps the Keycloak SSO session from idling out. Trino and Lakekeeper
authorize every request server-side (group file / OpenFGA), so group changes still apply at
once; only disabling a user lags by up to one token lifetime.
"""

CLIENT_ID = "jupyterhub"
ACCESS_TOKEN_LIFESPAN = 3600

_GROUPS_MAPPER = {
    "name": "groups", "protocol": "openid-connect",
    "protocolMapper": "oidc-group-membership-mapper",
    "config": {"full.path": "false", "id.token.claim": "true", "access.token.claim": "true",
               "userinfo.token.claim": "true", "introspection.token.claim": "true",
               "claim.name": "groups"},
}


def _audience_mapper(aud):
    return {
        "name": f"aud-{aud}", "protocol": "openid-connect",
        "protocolMapper": "oidc-audience-mapper",
        "config": {"included.client.audience": aud, "id.token.claim": "false",
                   "access.token.claim": "true", "introspection.token.claim": "true"},
    }


MAPPERS = (_GROUPS_MAPPER, _audience_mapper("trino"), _audience_mapper("lakekeeper"))


def desired(domain, https_port):
    """The client settings bootstrap enforces. Redirect URIs are registered with and without
    the port, like the realm template does, since browsers drop a default :443."""
    bases = [f"https://jupyter.{domain}:{https_port}", f"https://jupyter.{domain}"]
    return {
        "clientId": CLIENT_ID, "name": "JupyterHub", "enabled": True,
        "protocol": "openid-connect", "publicClient": False,
        "clientAuthenticatorType": "client-secret",
        "standardFlowEnabled": True, "directAccessGrantsEnabled": False,
        "implicitFlowEnabled": False, "serviceAccountsEnabled": False,
        "redirectUris": [f"{b}/hub/oauth_callback" for b in bases],
        "webOrigins": bases,
        "attributes": {
            "post.logout.redirect.uris": "##".join(f"{b}/hub/" for b in bases),
            "access.token.lifespan": str(ACCESS_TOKEN_LIFESPAN),
        },
    }


def ensure_jupyterhub_client(kc, secret, domain, https_port):
    """Create or repair the `jupyterhub` client. Returns True if anything changed.
    `kc` is a keycloak.Admin with realm-admin rights (the one-shot bootstrap)."""
    if not secret:
        raise RuntimeError("OIDC_CLIENT_SECRET_JUPYTERHUB is empty")
    want = desired(domain, https_port)
    changed = False
    if not kc.get(f"/clients?clientId={CLIENT_ID}"):
        kc.call("POST", "/clients", {**want, "secret": secret,
                                      "protocolMappers": [dict(m) for m in MAPPERS]})
        print(f"[keycloak] created client {CLIENT_ID}")
        changed = True
    c = kc.client(CLIENT_ID)

    def same(have, v):
        # Keycloak stores redirectUris/webOrigins as sets and returns them in any order.
        if isinstance(v, list):
            return sorted(have or []) == sorted(v)
        return have == v

    drift = [k for k, v in want.items() if k != "attributes" and not same(c.get(k), v)]
    attrs = c.get("attributes") or {}
    drift += [f"attributes.{k}" for k, v in want["attributes"].items() if attrs.get(k) != v]
    if kc.get(f"/clients/{c['id']}/client-secret").get("value") != secret:
        drift.append("secret")
    if drift:
        c.update({k: v for k, v in want.items() if k != "attributes"})
        c["attributes"] = {**attrs, **want["attributes"]}
        c["secret"] = secret
        kc.call("PUT", f"/clients/{c['id']}", c)
        print(f"[keycloak] {CLIENT_ID}: updated {', '.join(sorted(drift))}")
        changed = True

    have = {m["name"] for m in kc.get(f"/clients/{c['id']}/protocol-mappers/models")}
    for m in MAPPERS:
        if m["name"] not in have:
            kc.call("POST", f"/clients/{c['id']}/protocol-mappers/models", dict(m))
            print(f"[keycloak] {CLIENT_ID}: added mapper {m['name']}")
            changed = True
    return changed
