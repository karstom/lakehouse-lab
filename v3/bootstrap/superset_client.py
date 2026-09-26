"""Keycloak clients of the BI+CONSOLE workstream (CONTRACT Phase 3), created or repaired
idempotently by bootstrap, never only in the realm template (the realm is imported on first
start only, so existing installs would never get a change there). Pattern:
jupyterhub_client.ensure_jupyterhub_client.

* `superset` (new, confidential): Superset's FAB OAuth login, and its service account
  `service-account-superset`, the only principal Trino lets impersonate lab users
  (config/trino/rules.json). Its tokens carry audience `trino` for that reason, and `groups`
  (userinfo) for Superset's group -> role mapping.
* `console` (exists in the realm template since Phase 1): oauth2-proxy, the forward-auth in
  front of console. and spark. Repaired here: redirect URIs, `groups` in the ID token and
  userinfo (tiles, Spark UI group check), audience `console`, and the secret from .secrets.env.
"""

GROUPS_MAPPER = {
    "name": "groups", "protocol": "openid-connect",
    "protocolMapper": "oidc-group-membership-mapper",
    "config": {"full.path": "false", "id.token.claim": "true", "access.token.claim": "true",
               "userinfo.token.claim": "true", "introspection.token.claim": "true",
               "claim.name": "groups"},
}


def audience_mapper(aud):
    return {
        "name": f"aud-{aud}", "protocol": "openid-connect",
        "protocolMapper": "oidc-audience-mapper",
        "config": {"included.client.audience": aud, "id.token.claim": "false",
                   "access.token.claim": "true", "introspection.token.claim": "true"},
    }


def _bases(svc, domain, https_port):
    """Origins with and without the port, like the realm template: browsers drop a default :443."""
    return [f"https://{svc}.{domain}:{https_port}", f"https://{svc}.{domain}"]


def superset_desired(domain, https_port):
    bases = _bases("superset", domain, https_port)
    return {
        "clientId": "superset", "name": "Superset", "enabled": True,
        "protocol": "openid-connect", "publicClient": False,
        "clientAuthenticatorType": "client-secret",
        "standardFlowEnabled": True, "directAccessGrantsEnabled": False,
        "implicitFlowEnabled": False,
        # Client credentials: Superset -> Trino as service-account-superset (impersonation).
        "serviceAccountsEnabled": True,
        "redirectUris": [f"{b}/oauth-authorized/keycloak" for b in bases],
        "webOrigins": bases,
        "attributes": {"post.logout.redirect.uris": "##".join(f"{b}/" for b in bases)},
    }


SUPERSET_MAPPERS = (GROUPS_MAPPER, audience_mapper("trino"))


def console_desired(domain, https_port):
    bases = _bases("console", domain, https_port)
    return {
        "clientId": "console", "name": "Lab Console", "enabled": True,
        "protocol": "openid-connect", "publicClient": False,
        "clientAuthenticatorType": "client-secret",
        "standardFlowEnabled": True, "directAccessGrantsEnabled": False,
        "implicitFlowEnabled": False, "serviceAccountsEnabled": False,
        # oauth2-proxy always signs in through console. (Caddy sends spark.'s 401s there).
        "redirectUris": [f"{b}/oauth2/callback" for b in bases],
        "webOrigins": bases,
        "attributes": {
            "post.logout.redirect.uris": "##".join(f"{b}/" for b in bases),
            # oauth2-proxy sends a PKCE challenge (code_challenge_method S256).
            "pkce.code.challenge.method": "S256",
        },
    }


CONSOLE_MAPPERS = (GROUPS_MAPPER, audience_mapper("console"))


def _same(have, want):
    # Keycloak stores redirectUris/webOrigins as sets and returns them in any order.
    if isinstance(want, list):
        return sorted(have or []) == sorted(want)
    return have == want


def ensure_client(kc, want, secret, mappers):
    """Create or repair one confidential client. Returns True if anything changed.
    `kc` is a keycloak.Admin with realm-admin rights (the one-shot bootstrap)."""
    cid = want["clientId"]
    if not secret:
        raise RuntimeError(f"no client secret for Keycloak client {cid!r} (see .secrets.env)")
    changed = False
    if not kc.get(f"/clients?clientId={cid}"):
        kc.call("POST", "/clients", {**want, "secret": secret,
                                      "protocolMappers": [dict(m) for m in mappers]})
        print(f"[keycloak] created client {cid}")
        changed = True
    c = kc.client(cid)
    drift = [k for k, v in want.items() if k != "attributes" and not _same(c.get(k), v)]
    attrs = c.get("attributes") or {}
    drift += [f"attributes.{k}" for k, v in want["attributes"].items() if attrs.get(k) != v]
    if kc.get(f"/clients/{c['id']}/client-secret").get("value") != secret:
        drift.append("secret")
    if drift:
        c.update({k: v for k, v in want.items() if k != "attributes"})
        c["attributes"] = {**attrs, **want["attributes"]}
        c["secret"] = secret
        kc.call("PUT", f"/clients/{c['id']}", c)
        print(f"[keycloak] {cid}: updated {', '.join(sorted(drift))}")
        changed = True

    have = {m["name"]: m for m in kc.get(f"/clients/{c['id']}/protocol-mappers/models")}
    for m in mappers:
        cur = have.get(m["name"])
        if cur is None:
            kc.call("POST", f"/clients/{c['id']}/protocol-mappers/models", dict(m))
            print(f"[keycloak] {cid}: added mapper {m['name']}")
            changed = True
        elif cur.get("protocolMapper") != m["protocolMapper"] or any(
                (cur.get("config") or {}).get(k) != v for k, v in m["config"].items()):
            kc.call("PUT", f"/clients/{c['id']}/protocol-mappers/models/{cur['id']}",
                    {**cur, "protocolMapper": m["protocolMapper"],
                     "config": {**(cur.get("config") or {}), **m["config"]}})
            print(f"[keycloak] {cid}: repaired mapper {m['name']}")
            changed = True
    return changed


def ensure_superset_client(kc, secret, domain, https_port):
    return ensure_client(kc, superset_desired(domain, https_port), secret, SUPERSET_MAPPERS)


def ensure_console_client(kc, secret, domain, https_port):
    return ensure_client(kc, console_desired(domain, https_port), secret, CONSOLE_MAPPERS)
