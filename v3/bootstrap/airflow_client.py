"""Keycloak client `airflow` and Airflow's UMA authorization model (CONTRACT Phase 3, OQ-16).

Created or repaired idempotently by bootstrap, never only in the realm template: the realm is
imported on first start only, so existing installs would never get it (pattern:
keycloak.Admin.ensure_sync_client, jupyterhub_client).

Airflow's Keycloak auth manager (apache-airflow-providers-keycloak) does not read roles from
token claims. For every check it asks Keycloak for a UMA decision on
`<Resource>#<METHOD>` (audience `airflow`), so authorization lives in the client's
Authorization Services model. The provider ships a CLI (`create-all`) that builds that model,
but it cannot run twice and needs the master admin password inside an Airflow container.
Bootstrap builds the same model itself instead, declaratively (DESIRED below), with the admin
token it already holds, and repairs drift on every run.

The model mirrors the provider's non-team model (provider 0.10.0, `create-all` without
--teams): scopes GET/POST/PUT/DELETE/MENU/LIST, one resource per KeycloakResource with the
method scopes and one per Airflow menu item with MENU, role policies `Allow-<Role>` on the
client roles Viewer/User/Op/Admin/SuperAdmin, and the permissions ReadOnly, User, Op and Admin.
One deliberate difference: the provider's ReadOnly lets every role GET every resource,
including Connections, Variables and Configuration. Here those (and their menu entries) are
split into `ReadSensitive`, granted to User/Op/Admin only, so analysts and viewers cannot read
connection details or variable values (the S-3 spike's gotcha 4).

Lab group -> Airflow role (enforced exactly for the four lab groups):
    lab-admin  Admin              everything
    engineer   User + Op          trigger, clear, pause and edit DAGs and assets (User);
                                  connections, pools, variables, backfills (Op)
    analyst    Viewer             read-only
    viewer     Viewer             read-only
The resource server uses decisionStrategy AFFIRMATIVE: one granting permission is enough
(otherwise ReadOnly and Admin, which both cover GET, would both have to grant).
"""
import urllib.parse

CLIENT_ID = "airflow"

ROLES = ("Viewer", "User", "Op", "Admin", "SuperAdmin")
GROUP_ROLES = {
    "lab-admin": ("Admin",),
    "engineer": ("User", "Op"),
    "analyst": ("Viewer",),
    "viewer": ("Viewer",),
}

METHODS = ("GET", "POST", "PUT", "DELETE")
SCOPES = METHODS + ("MENU", "LIST")

# airflow.providers.keycloak.auth_manager.resources.KeycloakResource (provider 0.10.0)
RESOURCES = ("Asset", "AssetAlias", "Backfill", "Configuration", "Connection", "Custom", "Dag",
             "Menu", "Pool", "Team", "Variable", "View")
# airflow.api_fastapi.common.types.MenuItem (Airflow 3.3.2). A menu item missing here is
# simply hidden from every user (Keycloak answers "invalid_resource" -> not authorized).
MENU_ITEMS = ("Required Actions", "Assets", "Audit Log", "Config", "Connections", "Dags",
              "Deadlines", "Docs", "Jobs", "Plugins", "Pools", "Providers", "Variables", "XComs")

SENSITIVE_RESOURCES = ("Connection", "Variable", "Configuration")
SENSITIVE_MENU_ITEMS = ("Connections", "Variables", "Config", "Providers", "Plugins")

_READ = ("GET", "MENU", "LIST")
_ALL = [r for r in RESOURCES if r not in SENSITIVE_RESOURCES] + \
       [m for m in MENU_ITEMS if m not in SENSITIVE_MENU_ITEMS]

# name -> (type, scopes, resources, policies, decisionStrategy). Empty resources on a
# scope permission = those scopes on every resource.
PERMISSIONS = {
    "ReadOnly": ("scope", _READ, tuple(_ALL), ("Viewer", "User", "Op", "Admin", "SuperAdmin"),
                 "AFFIRMATIVE"),
    "ReadSensitive": ("scope", _READ, SENSITIVE_RESOURCES + SENSITIVE_MENU_ITEMS,
                      ("User", "Op", "Admin", "SuperAdmin"), "AFFIRMATIVE"),
    "User": ("resource", (), ("Dag", "Asset"), ("User",), "AFFIRMATIVE"),
    "Op": ("resource", (), ("Connection", "Pool", "Variable", "Backfill"), ("Op",), "AFFIRMATIVE"),
    "Admin": ("scope", SCOPES, (), ("Admin", "SuperAdmin"), "AFFIRMATIVE"),
}
RESOURCE_SERVER = {"policyEnforcementMode": "ENFORCING", "decisionStrategy": "AFFIRMATIVE",
                   "allowRemoteResourceManagement": False}
# Keycloak adds these when Authorization Services is switched on. The default policy is a
# grant-everything JS policy; they are removed so the model above is the whole model.
DEFAULTS = ("Default Permission", "Default Policy")
DEFAULT_RESOURCE = "Default Resource"


def policy_name(role):
    return f"Allow-{role}"


_GROUPS_MAPPER = {
    "name": "groups", "protocol": "openid-connect",
    "protocolMapper": "oidc-group-membership-mapper",
    "config": {"full.path": "false", "id.token.claim": "true", "access.token.claim": "true",
               "userinfo.token.claim": "true", "introspection.token.claim": "true",
               "claim.name": "groups"},
}
_AUD_MAPPER = {
    "name": "aud-airflow", "protocol": "openid-connect",
    "protocolMapper": "oidc-audience-mapper",
    "config": {"included.client.audience": CLIENT_ID, "id.token.claim": "false",
               "access.token.claim": "true", "introspection.token.claim": "true"},
}
MAPPERS = (_GROUPS_MAPPER, _AUD_MAPPER)


def desired(domain, https_port, direct_grants):
    """Client settings bootstrap enforces. Callback paths are the provider's
    (/auth/login_callback, /auth/logout_callback), registered with and without the port like
    the realm template, since browsers drop a default :443. The password grant exists only for
    automated tests (LAB_SEED_TEST_USERS=true), as for the `trino` client: Airflow's
    POST /auth/token uses it."""
    bases = [f"https://airflow.{domain}:{https_port}", f"https://airflow.{domain}"]
    return {
        "clientId": CLIENT_ID, "name": "Airflow", "enabled": True,
        "protocol": "openid-connect", "publicClient": False,
        "clientAuthenticatorType": "client-secret",
        "standardFlowEnabled": True, "directAccessGrantsEnabled": bool(direct_grants),
        "implicitFlowEnabled": False,
        # Authorization Services needs a service account; it has no roles.
        "serviceAccountsEnabled": True, "authorizationServicesEnabled": True,
        "redirectUris": [f"{b}/auth/login_callback" for b in bases],
        "webOrigins": bases,
        "attributes": {
            "post.logout.redirect.uris": "##".join(f"{b}/auth/logout_callback" for b in bases),
        },
    }


def _same(have, want):
    # Keycloak returns redirectUris/webOrigins as sets, in any order.
    if isinstance(want, list):
        return sorted(have or []) == sorted(want)
    return have == want


def ensure_client(kc, secret, domain, https_port, direct_grants):
    if not secret:
        raise RuntimeError("OIDC_CLIENT_SECRET_AIRFLOW is empty")
    want = desired(domain, https_port, direct_grants)
    changed = False
    if not kc.get(f"/clients?clientId={CLIENT_ID}"):
        kc.call("POST", "/clients", {**want, "secret": secret,
                                      "protocolMappers": [dict(m) for m in MAPPERS]})
        print(f"[keycloak] created client {CLIENT_ID}")
        changed = True
    c = kc.client(CLIENT_ID)
    drift = [k for k, v in want.items() if k != "attributes" and not _same(c.get(k), v)]
    attrs = c.get("attributes") or {}
    drift += [f"attributes.{k}" for k, v in want["attributes"].items() if attrs.get(k) != v]
    if kc.get(f"/clients/{c['id']}/client-secret").get("value") != secret:
        drift.append("secret")
    if drift:
        c.update({k: v for k, v in want.items() if k != "attributes"})
        c["attributes"] = {**attrs, **want["attributes"]}
        c["secret"] = secret
        c.pop("authorizationSettings", None)  # never overwrite the model from here
        kc.call("PUT", f"/clients/{c['id']}", c)
        print(f"[keycloak] {CLIENT_ID}: updated {', '.join(sorted(drift))}")
        changed = True
    have = {m["name"] for m in kc.get(f"/clients/{c['id']}/protocol-mappers/models")}
    for m in MAPPERS:
        if m["name"] not in have:
            kc.call("POST", f"/clients/{c['id']}/protocol-mappers/models", dict(m))
            print(f"[keycloak] {CLIENT_ID}: added mapper {m['name']}")
            changed = True
    return c["id"], changed


def ensure_roles(kc, cid, gids):
    """Client roles, and the exact lab-group -> role mapping (GROUP_ROLES)."""
    changed = False
    have = {r["name"]: r for r in kc.get(f"/clients/{cid}/roles")}
    for role in ROLES:
        if role not in have:
            kc.call("POST", f"/clients/{cid}/roles", {"name": role,
                    "description": f"Airflow {role} (Keycloak auth manager)"})
            print(f"[keycloak] {CLIENT_ID}: created role {role}")
            changed = True
    roles = {r["name"]: r for r in kc.get(f"/clients/{cid}/roles")}
    for group, want in GROUP_ROLES.items():
        path = f"/groups/{gids[group]}/role-mappings/clients/{cid}"
        current = {r["name"] for r in kc.get(path)}
        add = [roles[r] for r in want if r not in current]
        remove = [roles[r] for r in current if r in roles and r not in want]
        if add:
            kc.call("POST", path, [{"id": r["id"], "name": r["name"]} for r in add])
        if remove:
            kc.call("DELETE", path, [{"id": r["id"], "name": r["name"]} for r in remove])
        if add or remove:
            print(f"[keycloak] {CLIENT_ID}: group {group} roles -> {', '.join(want)}")
            changed = True
    return roles, changed


class _Authz:
    def __init__(self, kc, cid):
        self.kc = kc
        self.base = f"/clients/{cid}/authz/resource-server"

    def get(self, path):
        return self.kc.get(self.base + path)

    def call(self, method, path, body=None):
        return self.kc.call(method, self.base + path, body)


def _q(name):
    return urllib.parse.quote(name, safe="")


def ensure_authz(kc, cid, roles):
    """The UMA model (module docstring). Creates what is missing and repairs drift; objects
    it does not manage are left alone, except Keycloak's grant-everything defaults."""
    az = _Authz(kc, cid)
    changed = False

    rs = az.get("")
    if any(rs.get(k) != v for k, v in RESOURCE_SERVER.items()):
        rs.update(RESOURCE_SERVER)
        az.call("PUT", "", rs)
        print(f"[keycloak] {CLIENT_ID}: resource server settings -> {RESOURCE_SERVER}")
        changed = True

    # Keycloak's default permission/policy/resource.
    for p in az.get("/policy?max=-1"):
        if p.get("name") in DEFAULTS:
            az.call("DELETE", f"/policy/{p['id']}")
            print(f"[keycloak] {CLIENT_ID}: removed {p['name']}")
            changed = True
    for r in az.get("/resource?max=-1&deep=false"):
        if r.get("name") == DEFAULT_RESOURCE:
            az.call("DELETE", f"/resource/{r['_id']}")
            print(f"[keycloak] {CLIENT_ID}: removed {DEFAULT_RESOURCE}")
            changed = True

    # Scopes.
    scopes = {s["name"]: s["id"] for s in az.get("/scope?max=-1")}
    for s in SCOPES:
        if s not in scopes:
            az.call("POST", "/scope", {"name": s})
            changed = True
    if set(SCOPES) - set(scopes):
        print(f"[keycloak] {CLIENT_ID}: created scopes {sorted(set(SCOPES) - set(scopes))}")
        scopes = {s["name"]: s["id"] for s in az.get("/scope?max=-1")}

    # Resources: Airflow resource types with the method scopes + LIST; menu items with MENU.
    want_res = {r: METHODS + ("LIST",) for r in RESOURCES}
    want_res.update({m: ("MENU",) for m in MENU_ITEMS})
    have_res = {r["name"]: r for r in az.get("/resource?max=-1&deep=true")}
    made = []
    for name, sc in want_res.items():
        body = {"name": name, "scopes": [{"id": scopes[s], "name": s} for s in sc]}
        r = have_res.get(name)
        if r is None:
            az.call("POST", "/resource", body)
            made.append(name)
        elif sorted(s["name"] for s in r.get("scopes") or []) != sorted(sc):
            az.call("PUT", f"/resource/{r['_id']}", {**r, **body})
            made.append(name)
    if made:
        print(f"[keycloak] {CLIENT_ID}: created/updated {len(made)} resource(s)")
        changed = True
        have_res = {r["name"]: r for r in az.get("/resource?max=-1&deep=true")}
    res_ids = {n: r["_id"] for n, r in have_res.items()}

    # Role policies Allow-<Role> on the client roles.
    policies = {p["name"]: p for p in az.get("/policy?max=-1&permission=false")}
    for role in ROLES:
        name = policy_name(role)
        want_roles = [{"id": roles[role]["id"], "required": False}]
        p = policies.get(name)
        if p is None:
            az.call("POST", "/policy/role", {"name": name, "type": "role", "logic": "POSITIVE",
                                             "decisionStrategy": "UNANIMOUS", "roles": want_roles})
            print(f"[keycloak] {CLIENT_ID}: created policy {name}")
            changed = True
        else:
            full = az.get(f"/policy/role/{p['id']}")
            if [r["id"] for r in full.get("roles") or []] != [roles[role]["id"]] or \
                    full.get("logic") != "POSITIVE":
                full.update({"roles": want_roles, "logic": "POSITIVE"})
                az.call("PUT", f"/policy/role/{p['id']}", full)
                print(f"[keycloak] {CLIENT_ID}: repaired policy {name}")
                changed = True
    policy_ids = {p["name"]: p["id"] for p in az.get("/policy?max=-1&permission=false")}

    # Permissions.
    perms = {p["name"]: p for p in az.get("/permission?max=-1")}
    for name, (ptype, sc, res, pols, strategy) in PERMISSIONS.items():
        body = {"name": name, "type": ptype, "logic": "POSITIVE", "decisionStrategy": strategy,
                "scopes": [scopes[s] for s in sc],
                "resources": [res_ids[r] for r in res],
                "policies": [policy_ids[policy_name(r)] for r in pols]}
        p = perms.get(name)
        if p is not None and p.get("type") != ptype:
            az.call("DELETE", f"/permission/{p['id']}")
            p = None
        if p is None:
            az.call("POST", f"/permission/{ptype}", body)
            print(f"[keycloak] {CLIENT_ID}: created permission {name}")
            changed = True
            continue
        pid = p["id"]
        have = {
            "scopes": sorted(s["id"] for s in az.get(f"/permission/{ptype}/{pid}/scopes")),
            "resources": sorted(r["_id"] for r in az.get(f"/permission/{ptype}/{pid}/resources")),
            "policies": sorted(x["id"] for x in az.get(f"/permission/{ptype}/{pid}/associatedPolicies")),
        }
        drift = [k for k in ("scopes", "resources", "policies") if have[k] != sorted(body[k])]
        if p.get("decisionStrategy") != strategy:
            drift.append("decisionStrategy")
        if drift:
            az.call("PUT", f"/permission/{ptype}/{pid}", {**body, "id": pid})
            print(f"[keycloak] {CLIENT_ID}: repaired permission {name} ({', '.join(drift)})")
            changed = True
    return changed


def ensure_airflow_client(kc, secret, domain, https_port, gids, direct_grants=False):
    """Create or repair the `airflow` client, its roles, the group -> role mapping and the UMA
    model. `kc` is a keycloak.Admin with realm-admin rights (the one-shot bootstrap).
    Returns True if anything changed."""
    cid, changed = ensure_client(kc, secret, domain, https_port, direct_grants)
    roles, ch = ensure_roles(kc, cid, gids)
    changed |= ch
    changed |= ensure_authz(kc, cid, roles)
    return changed
