"""Unit tests for bootstrap.keycloak.remove_test_users (LAB_SEED_TEST_USERS=false).

No Keycloak needed: bootstrap.web.request is replaced by a fake admin API that keeps users
in memory. Run: python3 -m unittest discover -s v3/tests/bootstrap -v
"""
import contextlib
import io
import os
import sys
import unittest
import urllib.parse

V3 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, V3)

from bootstrap import keycloak, web  # noqa: E402


class FakeKeycloak:
    """Just enough of /admin/realms/lakehouse/users for the removal code."""

    def __init__(self, users):
        # users: list of (username, email or None)
        self.users = {f"id-{u}": {"id": f"id-{u}", "username": u, "email": e} for u, e in users}
        self.deleted = []
        self.calls = []

    def request(self, method, url, *, headers=None, json_body=None, expect=(200, 201, 204), **kw):
        assert headers and headers.get("Authorization", "").startswith("Bearer "), "no admin token"
        base = f"{keycloak.KC}/admin/realms/{keycloak.REALM}"
        assert url.startswith(base), url
        path = url[len(base):]
        self.calls.append((method, path))
        parsed = urllib.parse.urlparse(path)
        q = urllib.parse.parse_qs(parsed.query)
        if method == "GET" and parsed.path == "/users":
            name = q["username"][0]
            assert q.get("exact") == ["true"], "user lookup must be exact"
            hits = [{"id": u["id"], "username": u["username"]}  # brief: no email
                    for u in self.users.values() if u["username"] == name]
            return 200, hits, {}
        if parsed.path.startswith("/users/"):
            uid = parsed.path.split("/")[2]
            if uid not in self.users:
                raise web.HTTPError(method, url, 404, "not found")
            if method == "GET":
                return 200, dict(self.users[uid]), {}
            if method == "DELETE":
                self.deleted.append(self.users.pop(uid)["username"])
                return 204, None, {}
        raise AssertionError(f"unexpected call {method} {path}")


class RemoveTestUsers(unittest.TestCase):
    def run_removal(self, users, protected=("labadmin",)):
        fake = FakeKeycloak(users)
        orig = web.request
        web.request = fake.request
        try:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                changed = keycloak.remove_test_users(keycloak.Admin("tok"), protected=protected)
        finally:
            web.request = orig
        return fake, changed, out.getvalue()

    def test_deletes_all_seeded_test_users(self):
        seeded = [(u, f"{u}@lab.invalid") for u, *_ in keycloak.TEST_USERS]
        fake, changed, out = self.run_removal(seeded + [("labadmin", "labadmin@lab.invalid")])
        self.assertTrue(changed)
        self.assertEqual(sorted(fake.deleted), sorted(u for u, *_ in keycloak.TEST_USERS))
        self.assertIn("id-labadmin", fake.users)
        self.assertIn("deleted test user alice", out)

    def test_second_run_changes_nothing(self):
        fake, changed, _ = self.run_removal([("labadmin", "labadmin@lab.invalid")])
        self.assertFalse(changed)
        self.assertEqual(fake.deleted, [])
        self.assertFalse([c for c in fake.calls if c[0] != "GET"])

    def test_real_user_with_a_test_name_is_kept(self):
        fake, changed, out = self.run_removal([
            ("alice", "alice@example.com"),   # a real person called alice
            ("eddie", None),                  # created by hand, no e-mail
            ("anna", "anna@lab.invalid"),     # seeded
        ])
        self.assertTrue(changed)
        self.assertEqual(fake.deleted, ["anna"])
        self.assertIn("alice: kept", out)

    def test_protected_admin_is_never_deleted(self):
        # An install whose first admin was named 'alice' (--admin-user alice): ensure_user
        # gave it the same marker e-mail, so only `protected` saves it.
        fake, changed, _ = self.run_removal([("alice", "alice@lab.invalid")], protected=("alice",))
        self.assertFalse(changed)
        self.assertEqual(fake.deleted, [])
        self.assertFalse([c for c in fake.calls if c[0] == "DELETE"])

    def test_other_users_are_never_looked_up_or_deleted(self):
        fake, _, _ = self.run_removal([("bob", "bob@lab.invalid"), ("alice2", "alice2@lab.invalid")])
        self.assertEqual(fake.deleted, [])
        looked_up = {urllib.parse.parse_qs(urllib.parse.urlparse(p).query)["username"][0]
                     for m, p in fake.calls if m == "GET" and p.startswith("/users?")}
        self.assertEqual(looked_up, {u for u, *_ in keycloak.TEST_USERS})

    def test_marker_matches_what_ensure_user_writes(self):
        import inspect
        src = inspect.getsource(keycloak.Admin.ensure_user)
        self.assertIn("TEST_EMAIL_DOMAIN", src)


if __name__ == "__main__":
    unittest.main()
