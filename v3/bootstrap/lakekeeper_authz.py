"""Lakekeeper permissions under OpenFGA (OQ-5), derived from the four Keycloak groups.

Model:
  * One Lakekeeper role per Keycloak group (provider `oidc`, source id = group name).
    Lakekeeper's OpenFGA authorizer does not read roles from tokens (only Cedar does), so
    bootstrap copies Keycloak group membership into the roles: members are users
    `oidc~<keycloak user id>` (the token `sub`). The copy is exact (missing members added,
    stale ones removed) and refreshed on every bootstrap run, like the Trino group file.
  * Grants on the `lakehouse` warehouse:
        lab-admin  ownership   (+ project_admin on the default project)
        engineer   modify, create
        analyst    select
        viewer     select
  * Trino's service account (Keycloak client `trino`) gets modify + create: Trino talks to
    the catalog as itself and enforces per-user rules in its own access control (rules.json).

Only missing grants are written; nothing is removed, so an admin's extra grants survive.
"""
from . import keycloak

ROLE_PROVIDER = "oidc"

WAREHOUSE_GRANTS = {
    "lab-admin": ("ownership",),
    "engineer": ("modify", "create"),
    "analyst": ("select",),
    "viewer": ("select",),
}
PROJECT_GRANTS = {"lab-admin": ("project_admin",)}
TRINO_WAREHOUSE_GRANTS = ("modify", "create")


def _roles_by_source(lk):
    out, token = {}, None
    while True:
        q = "/role?pageSize=100" + (f"&pageToken={token}" if token else "")
        page = lk.get(q)
        for r in page.get("roles", []):
            out[(r.get("provider-id"), r.get("source-id"))] = r
        token = page.get("next-page-token")
        if not token:
            return out


def ensure_roles(lk):
    existing = _roles_by_source(lk)
    ids = {}
    for group in keycloak.LAB_GROUPS:
        role = existing.get((ROLE_PROVIDER, group))
        if role is None:
            _, role, _ = lk.call("POST", "/role", {
                "name": group,
                "description": f"Keycloak group '{group}' (from the token's groups claim)",
                "provider-id": ROLE_PROVIDER,
                "source-id": group,
            })
            print(f"[lakekeeper] created role {group} ({ROLE_PROVIDER}~{group})")
        ids[group] = role["id"]
    return ids


def _member_id(m):
    return m.get("id") or m.get("user-id") or m.get("user")


def sync_members(lk, role_id, group, wanted_user_ids):
    current, token = set(), None
    while True:
        q = f"/role/{role_id}/members?type=user&pageSize=100" + (f"&pageToken={token}" if token else "")
        page = lk.get(q)
        current |= {_member_id(m) for m in page.get("members", []) if m.get("type", "user") == "user"}
        token = page.get("next-page-token")
        if not token:
            break
    add = sorted(set(wanted_user_ids) - current)
    remove = sorted(current - set(wanted_user_ids))
    if add:
        lk.call("POST", f"/role/{role_id}/members",
                {"members": [{"type": "user", "id": u} for u in add]})
    for u in remove:
        lk.call("DELETE", f"/role/{role_id}/members/user/{u}")
    if add or remove:
        print(f"[lakekeeper] role {group}: +{len(add)} -{len(remove)} member(s)")
    return len(add) + len(remove)


def ensure_user(lk, user_id, name, user_type):
    status, _, _ = lk.call("GET", f"/user/{user_id}", expect=None)
    if status == 200:
        return False
    lk.call("POST", "/user", {"id": user_id, "name": name, "user-type": user_type,
                              "update-if-exists": False})
    print(f"[lakekeeper] provisioned user {name} ({user_id})")
    return True


def _key(a):
    return (a.get("type"), a.get("user"), a.get("role"))


def ensure_assignments(lk, path, wanted):
    current = {_key(a) for a in lk.get(path).get("assignments", [])}
    writes = [a for a in wanted if _key(a) not in current]
    if writes:
        lk.call("POST", path, {"writes": writes, "deletes": []})
        for a in writes:
            who = f"role {a['role']}" if "role" in a else f"user {a['user']}"
            print(f"[lakekeeper] grant {a['type']} on {path.split('/permissions/')[1]} to {who}")
    return len(writes)


def sync(lk, kc, wh, members):
    """members: Keycloak group -> [usernames] (already read for the Trino group file)."""
    wid = wh.get("warehouse-id") or wh["id"]
    role_ids = ensure_roles(lk)

    subs = kc.user_subs(sorted({u for us in members.values() for u in us}))
    changes = 0
    for group, users in members.items():
        changes += sync_members(lk, role_ids[group], group, [f"oidc~{subs[u]}" for u in users if u in subs])

    sa = kc.service_account_user("trino")
    trino_id = f"oidc~{sa['id']}"
    ensure_user(lk, trino_id, sa.get("username", "service-account-trino"), "application")

    wanted = [{"type": t, "role": role_ids[g]} for g, ts in WAREHOUSE_GRANTS.items() for t in ts]
    wanted += [{"type": t, "user": trino_id} for t in TRINO_WAREHOUSE_GRANTS]
    n = ensure_assignments(lk, f"/permissions/warehouse/{wid}/assignments", wanted)

    wanted = [{"type": t, "role": role_ids[g]} for g, ts in PROJECT_GRANTS.items() for t in ts]
    n += ensure_assignments(lk, "/permissions/project/assignments", wanted)
    print(f"[lakekeeper] permissions: {n} grant(s) written, {changes} membership change(s)"
          if n or changes else "[lakekeeper] permissions: unchanged")
