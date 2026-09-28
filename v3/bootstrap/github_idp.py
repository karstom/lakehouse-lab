"""Optional GitHub login through Keycloak (ADR-016, CONTRACT Phase 3 exit 4).

Ensured idempotently by the one-shot bootstrap, never only in the realm template (the realm is
imported on first start only, so existing installs would never get it):

* The first-broker-login flow `lab-first-broker-login` is ALWAYS ensured (it is harmless while
  unused, and the CI mock provider `github-mock` uses the very same flow). It:
    - reviews the profile only when an attribute is missing;
    - creates the user only if no account has the same username or e-mail, with NO group
      (groups come only from an admin in Keycloak; identity-sync does the rest);
    - otherwise asks "link to the existing account?" and then requires that account's own
      password (re-authentication). There is no e-mail verification branch and no
      `idp-auto-link`, so an external account that merely shows someone's e-mail address can
      never take over their account.
* The identity provider `github` exists ONLY while both OIDC_CLIENT_ID_GITHUB and
  OIDC_CLIENT_SECRET_GITHUB are set (installer flags --github-client-id/--github-client-secret).
  With both unset it is removed; users created through it are kept (with their groups), they
  just cannot log in through GitHub any more. `trustEmail` is off and no mappers are added.

Keycloak never returns an IdP's client secret (GET shows "**********"), so drift of the secret
is detected through a SHA-256 of it stored in the IdP config (`labClientSecretSha256`); the
secret itself is only ever sent, never compared or printed.
"""
import hashlib
import urllib.parse

ALIAS = "github"
FLOW = "lab-first-broker-login"
FLOW_LINK = f"{FLOW}-user-creation-or-linking"
FLOW_EXISTING = f"{FLOW}-handle-existing-account"
SECRET_HASH_KEY = "labClientSecretSha256"
REVIEW_PROFILE_CONFIG = {"update.profile.on.first.login": "missing"}

# The flow, flattened the way GET /authentication/flows/<alias>/executions returns it:
# (level, provider id or "flow:<sub-flow alias>", requirement). Parents are implied by order.
FLOW_SHAPE = (
    (0, "idp-review-profile", "REQUIRED"),
    (0, f"flow:{FLOW_LINK}", "REQUIRED"),
    (1, "idp-create-user-if-unique", "ALTERNATIVE"),
    (1, f"flow:{FLOW_EXISTING}", "ALTERNATIVE"),
    (2, "idp-confirm-link", "REQUIRED"),
    (2, "idp-username-password-form", "REQUIRED"),
)
# Never allowed anywhere in the flow (ADR-016: no automatic linking by e-mail).
FORBIDDEN_PROVIDERS = ("idp-auto-link", "idp-email-verification")


def callback_path(alias=ALIAS):
    """Path of the redirect URI to register at the provider (the GitHub OAuth App):
    <LAB_AUTH_URL>/realms/lakehouse/broker/github/endpoint."""
    return f"/realms/lakehouse/broker/{alias}/endpoint"


def secret_sha256(secret):
    return hashlib.sha256(secret.encode()).hexdigest()


def desired_idp(client_id, client_secret):
    return {
        "alias": ALIAS, "displayName": "GitHub", "providerId": "github", "enabled": True,
        "trustEmail": False, "storeToken": False, "addReadTokenRoleOnCreate": False,
        "linkOnly": False, "hideOnLogin": False,
        "firstBrokerLoginFlowAlias": FLOW, "postBrokerLoginFlowAlias": "",
        "config": {"clientId": client_id, "clientSecret": client_secret, "syncMode": "IMPORT",
                   SECRET_HASH_KEY: secret_sha256(client_secret)},
    }


# ---------------------------------------------------------------- flow
def _q(alias):
    return urllib.parse.quote(alias, safe="")


def _executions(kc, alias=FLOW):
    return kc.get(f"/authentication/flows/{_q(alias)}/executions") or []


def _key(ex):
    return f"flow:{ex.get('displayName')}" if ex.get("authenticationFlow") else ex.get("providerId")


def flow_shape(executions):
    """(level, key, requirement) tuples of a flattened execution list."""
    return tuple((ex.get("level", 0), _key(ex), ex.get("requirement")) for ex in executions)


def _parents(executions, top=FLOW):
    """Parent flow alias of every execution in a flattened list (by level and order)."""
    stack = [top]
    out = []
    for ex in executions:
        level = ex.get("level", 0)
        del stack[level + 1:]
        out.append(stack[level] if level < len(stack) else stack[-1])
        if ex.get("authenticationFlow"):
            stack.append(ex.get("displayName"))
    return out


def _review_config_ok(kc, executions):
    for ex in executions:
        if ex.get("providerId") == "idp-review-profile":
            cid = ex.get("authenticationConfig")
            if not cid:
                return False
            cfg = (kc.get(f"/authentication/config/{cid}") or {}).get("config") or {}
            return all(cfg.get(k) == v for k, v in REVIEW_PROFILE_CONFIG.items())
    return False


def _build_flow(kc):
    kc.call("POST", f"/authentication/flows/{_q(FLOW)}/executions/execution",
            {"provider": "idp-review-profile"})
    kc.call("POST", f"/authentication/flows/{_q(FLOW)}/executions/flow",
            {"alias": FLOW_LINK, "type": "basic-flow", "provider": "registration-page-form",
             "description": "Create the user if unique, else link after re-authentication"})
    kc.call("POST", f"/authentication/flows/{_q(FLOW_LINK)}/executions/execution",
            {"provider": "idp-create-user-if-unique"})
    kc.call("POST", f"/authentication/flows/{_q(FLOW_LINK)}/executions/flow",
            {"alias": FLOW_EXISTING, "type": "basic-flow", "provider": "registration-page-form",
             "description": "Existing account: confirm, then that account's password"})
    kc.call("POST", f"/authentication/flows/{_q(FLOW_EXISTING)}/executions/execution",
            {"provider": "idp-confirm-link"})
    kc.call("POST", f"/authentication/flows/{_q(FLOW_EXISTING)}/executions/execution",
            {"provider": "idp-username-password-form"})
    execs = _executions(kc)
    want = {key: req for _, key, req in FLOW_SHAPE}
    for ex, parent in zip(execs, _parents(execs)):
        req = want.get(_key(ex))
        if req and ex.get("requirement") != req:
            kc.call("PUT", f"/authentication/flows/{_q(parent)}/executions",
                    {**ex, "requirement": req})
    for ex in execs:
        if ex.get("providerId") == "idp-review-profile" and not ex.get("authenticationConfig"):
            kc.call("POST", f"/authentication/executions/{ex['id']}/config",
                    {"alias": f"{FLOW}-review-profile", "config": dict(REVIEW_PROFILE_CONFIG)})


def ensure_first_broker_login_flow(kc):
    """Create or repair `lab-first-broker-login`. Returns True if anything changed.
    A drifted flow (a step added, removed or loosened in the admin console) is rebuilt in
    place, so identity providers that point at it keep pointing at it."""
    flows = {f["alias"]: f for f in kc.get("/authentication/flows") or []}
    changed = False
    if FLOW not in flows:
        kc.call("POST", "/authentication/flows", {
            "alias": FLOW, "providerId": "basic-flow", "topLevel": True, "builtIn": False,
            "description": "Lakehouse Lab (ADR-016): external login creates a user with no "
                           "group; linking to an existing account needs its password"})
        print(f"[keycloak] created authentication flow {FLOW}")
        changed = True
    execs = _executions(kc)
    if flow_shape(execs) == FLOW_SHAPE and _review_config_ok(kc, execs):
        return changed
    if execs:
        print(f"[keycloak] {FLOW}: steps differ from ADR-016, rebuilding "
              f"(found {[k for _, k, _ in flow_shape(execs)]})")
        for ex in execs:
            if ex.get("level", 0) == 0:
                # Deleting a sub-flow's execution deletes the sub-flow and its steps too.
                kc.call("DELETE", f"/authentication/executions/{ex['id']}")
        # A sub-flow alias can survive as an orphan flow in some Keycloak versions.
        for alias in (FLOW_EXISTING, FLOW_LINK):
            for f in kc.get("/authentication/flows") or []:
                if f["alias"] == alias and not f.get("topLevel"):
                    kc.call("DELETE", f"/authentication/flows/{f['id']}", expect=None)
    _build_flow(kc)
    got = flow_shape(_executions(kc))
    if got != FLOW_SHAPE:
        raise RuntimeError(f"{FLOW}: flow is {got} after rebuilding, expected {FLOW_SHAPE}")
    print(f"[keycloak] {FLOW}: steps set (create if unique with no group; "
          f"link only after re-authentication)")
    return True


# ---------------------------------------------------------------- identity provider
def _get_idp(kc, alias=ALIAS):
    status, body, _ = kc.call("GET", f"/identity-provider/instances/{_q(alias)}", expect=None)
    if status == 404:
        return None
    if status != 200:
        raise RuntimeError(f"GET identity provider {alias}: HTTP {status}")
    return body


def _drift(have, want):
    out = [k for k in ("providerId", "enabled", "trustEmail", "storeToken", "linkOnly",
                       "firstBrokerLoginFlowAlias")
           if have.get(k) != want[k]]
    if have.get("postBrokerLoginFlowAlias"):
        out.append("postBrokerLoginFlowAlias")
    hc, wc = have.get("config") or {}, want["config"]
    out += [f"config.{k}" for k in ("clientId", "syncMode", SECRET_HASH_KEY) if hc.get(k) != wc[k]]
    return out


def _warn_grants(kc):
    """ADR-016: a first external login must not grant anything. Report (do not undo) admin
    changes that would: realm default groups, or group/role mappers on the provider."""
    try:
        defaults = [g.get("name") for g in kc.get("/default-groups") or []]
        if defaults:
            print(f"[keycloak] WARNING: realm default groups {defaults} are given to every new "
                  f"user, GitHub logins included (ADR-016 expects none)")
        mappers = kc.get(f"/identity-provider/instances/{ALIAS}/mappers") or []
        risky = [m.get("name") for m in mappers
                 if any(w in (m.get("identityProviderMapper") or "") for w in ("group", "role"))]
        if risky:
            print(f"[keycloak] WARNING: identity provider {ALIAS} has group/role mappers {risky}; "
                  f"new GitHub users will not start with no group")
    except Exception as e:  # noqa: BLE001 - advisory only
        print(f"[keycloak] could not check default groups/mappers: {e}")


def ensure_github_idp(kc, client_id, client_secret):
    """Ensure the flow, then the `github` identity provider exactly when it is configured.
    Returns True if anything changed. `kc` is a keycloak.Admin with realm-admin rights."""
    client_id = (client_id or "").strip()
    client_secret = (client_secret or "").strip()
    if bool(client_id) != bool(client_secret):
        raise RuntimeError("GitHub login needs both OIDC_CLIENT_ID_GITHUB and "
                           "OIDC_CLIENT_SECRET_GITHUB (install.sh --github-client-id/--github-client-secret)")
    changed = ensure_first_broker_login_flow(kc)
    have = _get_idp(kc)

    if not client_id:
        if have is not None:
            kc.call("DELETE", f"/identity-provider/instances/{ALIAS}")
            print(f"[keycloak] removed identity provider {ALIAS} (GitHub login not configured); "
                  f"users it created are kept")
            changed = True
        return changed

    want = desired_idp(client_id, client_secret)
    if have is None:
        kc.call("POST", "/identity-provider/instances", want)
        print(f"[keycloak] created identity provider {ALIAS} (first login: no group; "
              f"no linking by e-mail)")
        changed = True
    else:
        drift = _drift(have, want)
        if drift:
            rep = {**have, **{k: v for k, v in want.items() if k != "config"}}
            rep["config"] = {**(have.get("config") or {}), **want["config"]}
            kc.call("PUT", f"/identity-provider/instances/{ALIAS}", rep)
            print(f"[keycloak] identity provider {ALIAS}: updated {', '.join(sorted(drift))}")
            changed = True
    _warn_grants(kc)
    return changed
