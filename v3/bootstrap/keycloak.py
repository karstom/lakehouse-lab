"""Keycloak admin steps (realm `lakehouse`), through the internal URL http://keycloak:8080.

The realm itself (groups, clients, client secrets, mappers) is declarative: it comes from
config/keycloak/realm-lakehouse.json via `start --import-realm`. Bootstrap only does what a
static template cannot: users that depend on settings, and reading group membership.
"""
import urllib.parse

from . import web

KC = "http://keycloak:8080"
REALM = "lakehouse"
LAB_GROUPS = ("lab-admin", "engineer", "analyst", "viewer")

# Test users (LAB_SEED_TEST_USERS=true only; CI and dev). Password: LAB_TEST_USER_PASSWORD.
TEST_USERS = (
    ("alice", "Alice", "Admin", "lab-admin"),
    ("eddie", "Eddie", "Engineer", "engineer"),
    ("anna", "Anna", "Analyst", "analyst"),
    ("victor", "Victor", "Viewer", "viewer"),
)


def token_url(realm=REALM):
    return f"{KC}/realms/{realm}/protocol/openid-connect/token"


# Read-only identity for the long-running identity-sync service (OQ-20). It can only read
# users, groups and clients in the lakehouse realm; the master admin password never leaves
# the one-shot bootstrap.
SYNC_CLIENT = "lab-sync"
SYNC_ROLES = ("view-users", "query-users", "query-groups", "view-clients")


class Admin:
    def __init__(self, token):
        self.h = {"Authorization": f"Bearer {token}"}
        self.base = f"{KC}/admin/realms/{REALM}"

    @classmethod
    def with_password(cls, user, password):
        """Master-realm admin: one-shot bootstrap only."""
        _, tok, _ = web.request("POST", token_url("master"), form={
            "grant_type": "password", "client_id": "admin-cli",
            "username": user, "password": password})
        return cls(tok["access_token"])

    @classmethod
    def with_client(cls, client_id, secret):
        """A service account in the lakehouse realm (identity-sync)."""
        return cls(client_credentials_token(client_id, secret))

    def get(self, path, **kw):
        return web.request("GET", self.base + path, headers=self.h, **kw)[1]

    def call(self, method, path, body=None, **kw):
        return web.request(method, self.base + path, headers=self.h, json_body=body, **kw)

    # ------------------------------------------------------------------ groups
    def group_ids(self):
        out = {}
        for g in self.get("/groups?briefRepresentation=true&max=1000"):
            out[g["name"]] = g["id"]
        missing = [g for g in LAB_GROUPS if g not in out]
        if missing:
            raise RuntimeError(f"realm is missing groups {missing}; was the realm template imported?")
        return out

    def group_members(self, gid):
        return sorted(u["username"] for u in
                      self.get(f"/groups/{gid}/members?briefRepresentation=true&max=10000"))

    # ------------------------------------------------------------------ users
    def find_user(self, username):
        q = urllib.parse.quote(username)
        users = self.get(f"/users?exact=true&briefRepresentation=true&username={q}")
        return users[0] if users else None

    def ensure_user(self, username, password, first, last, group, gids):
        """Create the user if missing (password set only on creation, so a user's own
        password change is kept) and make sure it is in `group`. Returns True if changed."""
        changed = False
        user = self.find_user(username)
        if user is None:
            if not password:
                raise RuntimeError(f"no password available to create user {username!r}")
            self.call("POST", "/users", {
                "username": username, "enabled": True,
                "firstName": first, "lastName": last,
                "email": f"{username}@lab.invalid", "emailVerified": True,
                "requiredActions": [],
                "credentials": [{"type": "password", "value": password, "temporary": False}],
            })
            user = self.find_user(username)
            changed = True
            print(f"[keycloak] created user {username}")
        uid = user["id"]
        groups = {g["name"] for g in self.get(f"/users/{uid}/groups?briefRepresentation=true")}
        if group not in groups:
            self.call("PUT", f"/users/{uid}/groups/{gids[group]}")
            changed = True
            print(f"[keycloak] added {username} to group {group}")
        return changed

    # ------------------------------------------------------------------ clients
    def client(self, client_id):
        found = self.get(f"/clients?clientId={urllib.parse.quote(client_id)}")
        if not found:
            raise RuntimeError(f"client {client_id!r} missing from realm {REALM}")
        return found[0]

    def set_direct_grants(self, client_id, enabled):
        """The password grant exists only for automated tests (LAB_SEED_TEST_USERS=true)."""
        c = self.client(client_id)
        if bool(c.get("directAccessGrantsEnabled")) == enabled:
            return False
        c["directAccessGrantsEnabled"] = enabled
        self.call("PUT", f"/clients/{c['id']}", c)
        print(f"[keycloak] {client_id}: password grant {'enabled' if enabled else 'disabled'}")
        return True

    def ensure_sync_client(self, secret):
        """Create or repair the read-only lab-sync service account. Returns True if changed.
        Done here rather than in the realm template so existing installs get it too (the
        realm is imported only on first start)."""
        changed = False
        found = self.get(f"/clients?clientId={SYNC_CLIENT}")
        if not found:
            self.call("POST", "/clients", {
                "clientId": SYNC_CLIENT, "enabled": True, "publicClient": False,
                "clientAuthenticatorType": "client-secret", "secret": secret,
                "serviceAccountsEnabled": True, "standardFlowEnabled": False,
                "directAccessGrantsEnabled": False, "implicitFlowEnabled": False,
                "description": "identity-sync: reads Keycloak groups (read-only)"})
            print(f"[keycloak] created client {SYNC_CLIENT}")
            changed = True
        c = self.client(SYNC_CLIENT)
        if self.get(f"/clients/{c['id']}/client-secret").get("value") != secret:
            c["secret"] = secret
            self.call("PUT", f"/clients/{c['id']}", c)
            print(f"[keycloak] {SYNC_CLIENT}: secret updated from .secrets.env")
            changed = True
        sa = self.get(f"/clients/{c['id']}/service-account-user")
        rm = self.client("realm-management")
        have = {r["name"] for r in self.get(f"/users/{sa['id']}/role-mappings/clients/{rm['id']}")}
        add = [self.get(f"/clients/{rm['id']}/roles/{r}") for r in SYNC_ROLES if r not in have]
        if add:
            self.call("POST", f"/users/{sa['id']}/role-mappings/clients/{rm['id']}", add)
            print(f"[keycloak] {SYNC_CLIENT}: granted {[r['name'] for r in add]}")
            changed = True
        return changed

    def service_account_user(self, client_id):
        c = self.client(client_id)
        return self.get(f"/clients/{c['id']}/service-account-user")

    def user_subs(self, usernames):
        """username -> Keycloak user id (the `sub` claim)."""
        out = {}
        for name in usernames:
            u = self.find_user(name)
            if u:
                out[name] = u["id"]
        return out


def client_credentials_token(client_id, secret, scope="openid"):
    _, tok, _ = web.request("POST", token_url(), form={
        "grant_type": "client_credentials", "client_id": client_id,
        "client_secret": secret, "scope": scope})
    return tok["access_token"]
