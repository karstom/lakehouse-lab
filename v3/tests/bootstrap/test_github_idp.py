"""Unit tests for bootstrap.github_idp (ADR-016): the first-broker-login flow and the optional
`github` identity provider, against an in-memory fake of the Keycloak admin API.

The fake behaves like Keycloak where it matters here: new executions start DISABLED, an
execution's requirement can only be changed through its PARENT flow's alias, deleting a
sub-flow's execution deletes the sub-flow, and GET never returns an IdP's client secret.
Run: python3 -m unittest discover -s v3/tests/bootstrap -v
"""
import contextlib
import copy
import io
import itertools
import os
import sys
import unittest
import urllib.parse

V3 = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, V3)

from bootstrap import github_idp  # noqa: E402

MASK = "**********"


class FakeKeycloak:
    def __init__(self):
        self.ids = itertools.count(1)
        self.flows = {}        # alias -> {"id", "alias", "topLevel", "execs": [exec ids]}
        self.execs = {}        # id -> exec dict (+ "_sub": sub-flow alias for flow executions)
        self.configs = {}      # id -> {"alias", "config"}
        self.idps = {}         # alias -> stored representation (with the real secret)
        self.default_groups = []
        self.mappers = {}
        self.writes = []

    def _id(self, prefix):
        return f"{prefix}-{next(self.ids)}"

    # ------------------------------------------------------------- flows helpers
    def _flatten(self, alias, level=0):
        out = []
        for i, eid in enumerate(self.flows[alias]["execs"]):
            ex = self.execs[eid]
            rep = {k: v for k, v in ex.items() if not k.startswith("_")}
            rep.update(level=level, index=i)
            out.append(rep)
            if ex.get("_sub"):
                out += self._flatten(ex["_sub"], level + 1)
        return out

    def _delete_exec(self, eid):
        ex = self.execs.pop(eid)
        for f in self.flows.values():
            if eid in f["execs"]:
                f["execs"].remove(eid)
        if ex.get("_sub"):
            sub = self.flows.pop(ex["_sub"])
            for child in list(sub["execs"]):
                self._delete_exec(child)

    def _new_exec(self, flow_alias, provider=None, sub=None):
        eid = self._id("exec")
        ex = {"id": eid, "requirement": "DISABLED", "authenticationFlow": bool(sub)}
        if sub:
            ex.update(displayName=sub, flowId=self.flows[sub]["id"], _sub=sub)
        else:
            ex.update(providerId=provider, displayName=provider)
        self.execs[eid] = ex
        self.flows[flow_alias]["execs"].append(eid)

    # ------------------------------------------------------------- admin API
    def get(self, path, **_):
        p = urllib.parse.unquote(path)
        if p == "/authentication/flows":
            return [{"id": f["id"], "alias": a, "topLevel": f["topLevel"]}
                    for a, f in self.flows.items() if f["topLevel"]]
        if p.startswith("/authentication/flows/") and p.endswith("/executions"):
            return self._flatten(p[len("/authentication/flows/"):-len("/executions")])
        if p.startswith("/authentication/config/"):
            return copy.deepcopy(self.configs[p.rsplit("/", 1)[1]])
        if p == "/default-groups":
            return [{"name": g} for g in self.default_groups]
        if p.startswith("/identity-provider/instances/") and p.endswith("/mappers"):
            return list(self.mappers.get(p.split("/")[3], []))
        raise AssertionError(f"unexpected GET {path}")

    def call(self, method, path, body=None, expect=(200, 201, 204), **_):
        p = urllib.parse.unquote(path)
        if method != "GET":
            self.writes.append((method, p))
        if p.startswith("/identity-provider/instances"):
            return self._idp(method, p, body)
        if method == "POST" and p == "/authentication/flows":
            assert body["alias"] not in self.flows
            self.flows[body["alias"]] = {"id": self._id("flow"), "alias": body["alias"],
                                         "topLevel": body["topLevel"], "execs": []}
            return 201, None, {}
        if method == "POST" and p.endswith("/executions/execution"):
            self._new_exec(p.split("/")[3], provider=body["provider"])
            return 201, None, {}
        if method == "POST" and p.endswith("/executions/flow"):
            parent = p.split("/")[3]
            self.flows[body["alias"]] = {"id": self._id("flow"), "alias": body["alias"],
                                         "topLevel": False, "execs": []}
            self._new_exec(parent, sub=body["alias"])
            return 201, None, {}
        if method == "PUT" and p.startswith("/authentication/flows/") and p.endswith("/executions"):
            alias = p.split("/")[3]
            assert body["id"] in self.flows[alias]["execs"], \
                f"execution {body['id']} updated through {alias}, which is not its parent flow"
            self.execs[body["id"]]["requirement"] = body["requirement"]
            return 204, None, {}
        if method == "POST" and p.startswith("/authentication/executions/") and p.endswith("/config"):
            eid = p.split("/")[3]
            cid = self._id("cfg")
            self.configs[cid] = {"id": cid, "alias": body["alias"], "config": dict(body["config"])}
            self.execs[eid]["authenticationConfig"] = cid
            return 201, None, {}
        if method == "DELETE" and p.startswith("/authentication/executions/"):
            self._delete_exec(p.rsplit("/", 1)[1])
            return 204, None, {}
        if method == "DELETE" and p.startswith("/authentication/flows/"):
            return 404, None, {}
        raise AssertionError(f"unexpected {method} {path}")

    def _idp(self, method, p, body):
        parts = p.split("/")
        alias = parts[3] if len(parts) > 3 else None
        if method == "GET":
            if alias not in self.idps:
                return 404, None, {}
            rep = copy.deepcopy(self.idps[alias])
            rep["config"]["clientSecret"] = MASK
            return 200, rep, {}
        if method == "POST":
            assert body["alias"] not in self.idps
            self.idps[body["alias"]] = copy.deepcopy(body)
            return 201, None, {}
        if method == "PUT":
            rep = copy.deepcopy(body)
            if rep["config"].get("clientSecret") == MASK:  # Keycloak keeps the stored one
                rep["config"]["clientSecret"] = self.idps[alias]["config"]["clientSecret"]
            self.idps[alias] = rep
            return 204, None, {}
        if method == "DELETE":
            del self.idps[alias]
            return 204, None, {}
        raise AssertionError(f"unexpected {method} {p}")


def ensure(kc, cid="", secret=""):
    with contextlib.redirect_stdout(io.StringIO()) as out:
        changed = github_idp.ensure_github_idp(kc, cid, secret)
    return changed, out.getvalue()


def shape(kc):
    return github_idp.flow_shape(kc.get(f"/authentication/flows/{github_idp.FLOW}/executions"))


class FirstBrokerLoginFlow(unittest.TestCase):
    def test_created_with_exact_shape_even_without_github(self):
        kc = FakeKeycloak()
        changed, out = ensure(kc)
        self.assertTrue(changed)
        self.assertEqual(shape(kc), github_idp.FLOW_SHAPE)
        self.assertEqual(kc.idps, {})
        cfg = next(c for c in kc.configs.values())
        self.assertEqual(cfg["config"], {"update.profile.on.first.login": "missing"})

    def test_no_auto_link_or_email_verification(self):
        providers = {k for _, k, _ in github_idp.FLOW_SHAPE}
        for bad in github_idp.FORBIDDEN_PROVIDERS:
            self.assertNotIn(bad, providers)
        # Re-authentication is REQUIRED after the confirm-link step, not an alternative.
        self.assertIn((2, "idp-username-password-form", "REQUIRED"), github_idp.FLOW_SHAPE)
        self.assertIn((2, "idp-confirm-link", "REQUIRED"), github_idp.FLOW_SHAPE)

    def test_second_run_writes_nothing(self):
        kc = FakeKeycloak()
        ensure(kc)
        n = len(kc.writes)
        changed, out = ensure(kc)
        self.assertFalse(changed, out)
        self.assertEqual(len(kc.writes), n)

    def test_drift_is_rebuilt(self):
        for tamper in ("auto_link", "loosen", "drop_reauth", "review_config"):
            with self.subTest(tamper=tamper):
                kc = FakeKeycloak()
                ensure(kc)
                if tamper == "auto_link":   # an admin adds "Automatically set existing user"
                    kc._new_exec(github_idp.FLOW_EXISTING, provider="idp-auto-link")
                elif tamper == "loosen":
                    ex = next(e for e in kc.execs.values()
                              if e.get("providerId") == "idp-username-password-form")
                    ex["requirement"] = "DISABLED"
                elif tamper == "drop_reauth":
                    kc._delete_exec(next(i for i, e in kc.execs.items()
                                         if e.get("providerId") == "idp-username-password-form"))
                else:
                    next(iter(kc.configs.values()))["config"]["update.profile.on.first.login"] = "on"
                changed, out = ensure(kc)
                self.assertTrue(changed)
                self.assertIn("rebuilding", out)
                self.assertEqual(shape(kc), github_idp.FLOW_SHAPE)
                self.assertFalse(ensure(kc)[0], "not idempotent after a rebuild")


class GithubIdentityProvider(unittest.TestCase):
    def test_created_only_when_configured(self):
        kc = FakeKeycloak()
        changed, out = ensure(kc, "Ov23liABCDEF", "s" * 40)
        self.assertTrue(changed)
        idp = kc.idps["github"]
        self.assertEqual(idp["providerId"], "github")
        self.assertIs(idp["trustEmail"], False)
        self.assertIs(idp["linkOnly"], False)
        self.assertEqual(idp["firstBrokerLoginFlowAlias"], github_idp.FLOW)
        self.assertEqual(idp["config"]["clientId"], "Ov23liABCDEF")
        self.assertEqual(idp["config"]["clientSecret"], "s" * 40)
        self.assertEqual(kc.mappers, {}, "no mappers: a first login gets no group")
        self.assertNotIn("s" * 40, out, "the client secret was printed")

    def test_second_run_writes_nothing(self):
        kc = FakeKeycloak()
        ensure(kc, "cid", "secret-one")
        n = len(kc.writes)
        changed, out = ensure(kc, "cid", "secret-one")
        self.assertFalse(changed, out)
        self.assertEqual(len(kc.writes), n)

    def test_secret_and_id_changes_are_applied(self):
        kc = FakeKeycloak()
        ensure(kc, "cid", "secret-one")
        changed, out = ensure(kc, "cid", "secret-two")
        self.assertTrue(changed)
        self.assertIn(github_idp.SECRET_HASH_KEY, out)
        self.assertNotIn("secret-two", out)
        self.assertEqual(kc.idps["github"]["config"]["clientSecret"], "secret-two")
        changed, _ = ensure(kc, "cid2", "secret-two")
        self.assertTrue(changed)
        self.assertEqual(kc.idps["github"]["config"]["clientId"], "cid2")
        self.assertFalse(ensure(kc, "cid2", "secret-two")[0])

    def test_admin_changes_that_allow_takeover_are_repaired(self):
        kc = FakeKeycloak()
        ensure(kc, "cid", "sec")
        kc.idps["github"]["trustEmail"] = True
        kc.idps["github"]["firstBrokerLoginFlowAlias"] = "first broker login"
        changed, out = ensure(kc, "cid", "sec")
        self.assertTrue(changed)
        self.assertIs(kc.idps["github"]["trustEmail"], False)
        self.assertEqual(kc.idps["github"]["firstBrokerLoginFlowAlias"], github_idp.FLOW)
        self.assertEqual(kc.idps["github"]["config"]["clientSecret"], "sec", "secret lost on repair")

    def test_removed_when_unconfigured(self):
        kc = FakeKeycloak()
        ensure(kc, "cid", "sec")
        changed, out = ensure(kc, "", "")
        self.assertTrue(changed)
        self.assertIn("removed identity provider github", out)
        self.assertNotIn("github", kc.idps)
        self.assertEqual(shape(kc), github_idp.FLOW_SHAPE, "the flow stays (the mock IdP uses it)")
        self.assertFalse(ensure(kc, "", "")[0])

    def test_half_configured_is_an_error_and_writes_nothing(self):
        for cid, sec in (("cid", ""), ("", "sec")):
            with self.subTest(cid=cid, sec=sec):
                kc = FakeKeycloak()
                with self.assertRaises(RuntimeError):
                    ensure(kc, cid, sec)
                self.assertEqual(kc.writes, [])

    def test_warns_about_default_groups(self):
        kc = FakeKeycloak()
        kc.default_groups = ["viewer"]
        _, out = ensure(kc, "cid", "sec")
        self.assertIn("WARNING: realm default groups ['viewer']", out)

    def test_callback_path(self):
        self.assertEqual(github_idp.callback_path(), "/realms/lakehouse/broker/github/endpoint")


if __name__ == "__main__":
    unittest.main()
