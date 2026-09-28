"""The batch service identity `lab-batch` (CONTRACT Phase 3, ADR-017).

Keycloak client `lab-batch`: confidential, client credentials only (no browser login, no
password grant). Airflow DAGs, dbt, Spark and Trino clients authenticate as it and re-fetch
tokens themselves; nothing ever refreshes a token for them. Created or repaired idempotently
by bootstrap (never only in the realm template, which is imported on first start only).

Its tokens carry the audiences `trino` (Trino JWT auth; principal = preferred_username =
`service-account-lab-batch`) and `lakekeeper` (Lakekeeper OIDC). Their lifespan is
LAB_BATCH_TOKEN_LIFESPAN seconds (default 300, the realm default). The ADR-017 proof sets it
to 120 so that a >= 300 s Spark job must outlive two token lifetimes.

Catalog permissions (Lakekeeper + OpenFGA; ensure_lakekeeper):
  * namespace `analytics` exists (the shared, production-style output schema);
  * lab-batch may read the whole warehouse (`select`: samples and analytics) and create and
    modify tables in `analytics` (namespace `create` + `modify`). Nothing else.
  Engineers and lab admins already write everywhere through their groups; analysts and viewers
  read. Trino enforces the same for lab-batch in rules.json (Trino talks to Lakekeeper as its
  own service account). Grants are only added, never removed, like lakekeeper_authz.
"""
import os

from . import lakekeeper, web

CLIENT_ID = "lab-batch"
NAMESPACE = "analytics"
DEFAULT_TOKEN_LIFESPAN = 300
WAREHOUSE_GRANTS = ("select",)
NAMESPACE_GRANTS = ("create", "modify")


def _audience_mapper(aud):
    return {
        "name": f"aud-{aud}", "protocol": "openid-connect",
        "protocolMapper": "oidc-audience-mapper",
        "config": {"included.client.audience": aud, "id.token.claim": "false",
                   "access.token.claim": "true", "introspection.token.claim": "true"},
    }


MAPPERS = (_audience_mapper("trino"), _audience_mapper("lakekeeper"))


def token_lifespan():
    v = os.environ.get("LAB_BATCH_TOKEN_LIFESPAN") or str(DEFAULT_TOKEN_LIFESPAN)
    n = int(v)
    if not 60 <= n <= 86400:
        raise RuntimeError(f"LAB_BATCH_TOKEN_LIFESPAN={v} is outside 60..86400 seconds")
    return n


def desired(lifespan):
    return {
        "clientId": CLIENT_ID, "name": "Batch jobs (service identity)", "enabled": True,
        "protocol": "openid-connect", "publicClient": False,
        "clientAuthenticatorType": "client-secret",
        "serviceAccountsEnabled": True, "standardFlowEnabled": False,
        "directAccessGrantsEnabled": False, "implicitFlowEnabled": False,
        "description": "Airflow batch jobs (ADR-017): client credentials only",
        "attributes": {
            "access.token.lifespan": str(lifespan),
            # No refresh tokens for client credentials: clients re-fetch.
            "client_credentials.use_refresh_token": "false",
        },
    }


def ensure_batch_client(kc, secret):
    """Create or repair the `lab-batch` client. Returns True if anything changed.
    `kc` is a keycloak.Admin with realm-admin rights (the one-shot bootstrap)."""
    if not secret:
        raise RuntimeError("OIDC_CLIENT_SECRET_BATCH is empty")
    want = desired(token_lifespan())
    changed = False
    if not kc.get(f"/clients?clientId={CLIENT_ID}"):
        kc.call("POST", "/clients", {**want, "secret": secret,
                                      "protocolMappers": [dict(m) for m in MAPPERS]})
        print(f"[keycloak] created client {CLIENT_ID}")
        changed = True
    c = kc.client(CLIENT_ID)
    drift = [k for k, v in want.items() if k != "attributes" and c.get(k) != v]
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


def _catalog(lk, method, path, body=None, expect=(200, 201, 204)):
    return web.request(method, f"{lakekeeper.LK}/catalog/v1{path}", headers=lk.h,
                       json_body=body, expect=expect)


def ensure_namespace(lk, wid, name=NAMESPACE):
    """Create the namespace if missing (Iceberg REST, as the Lakekeeper operator).
    Returns (namespace_id, created)."""
    status, ns, _ = _catalog(lk, "GET", f"/{wid}/namespaces/{name}", expect=(200, 404))
    created = False
    if status == 404:
        _catalog(lk, "POST", f"/{wid}/namespaces", {"namespace": [name], "properties": {}})
        print(f"[lakekeeper] created namespace {name}")
        _, ns, _ = _catalog(lk, "GET", f"/{wid}/namespaces/{name}")
        created = True
    nid = (ns.get("properties") or {}).get("namespace_id")
    if not nid:
        raise RuntimeError(f"Lakekeeper returned no namespace_id for {name!r}")
    return nid, created


def ensure_lakekeeper(lk, kc, wh, authz="openfga", quiet=False):
    """Namespace `analytics` and (OpenFGA only) lab-batch's catalog grants. Returns the number
    of changes. `lk` is a lakekeeper.Client as the operator, `wh` the warehouse, `kc` any
    keycloak.Admin that may view clients (bootstrap's admin or identity-sync's lab-sync).
    quiet=True (the identity-sync loop) prints only when something changed."""
    from . import lakekeeper_authz

    wid = wh.get("warehouse-id") or wh["id"]
    nid, created = ensure_namespace(lk, wid)
    n = int(created)
    if authz != "openfga":
        return n
    sa = kc.service_account_user(CLIENT_ID)
    uid = f"oidc~{sa['id']}"
    n += int(lakekeeper_authz.ensure_user(lk, uid, sa.get("username", f"service-account-{CLIENT_ID}"),
                                          "application"))
    n += lakekeeper_authz.ensure_assignments(
        lk, f"/permissions/warehouse/{wid}/assignments",
        [{"type": t, "user": uid} for t in WAREHOUSE_GRANTS])
    n += lakekeeper_authz.ensure_assignments(
        lk, f"/permissions/namespace/{nid}/assignments",
        [{"type": t, "user": uid} for t in NAMESPACE_GRANTS])
    if n or not quiet:
        print(f"[lakekeeper] {CLIENT_ID}: {'updated' if n else 'unchanged'} "
              f"(warehouse {'+'.join(WAREHOUSE_GRANTS)}, {NAMESPACE} {'+'.join(NAMESPACE_GRANTS)})")
    return n
