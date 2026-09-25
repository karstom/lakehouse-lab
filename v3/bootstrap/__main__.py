"""Lakehouse Lab V3 bootstrap: `python3 -m bootstrap` (the one-shot `bootstrap` service).

Idempotent: every step checks current state first, and a second run reports "unchanged"
everywhere. Exits non-zero on the first failure, so `up --wait` fails loudly instead of
starting Trino against a half-configured catalog.
"""
import os
import sys
import time

from . import keycloak, lakekeeper, seaweedfs, trino_groups, web


def env(name, default=None, required=True):
    v = os.environ.get(name, default)
    if required and not v:
        raise SystemExit(f"[bootstrap] missing required environment variable {name}")
    return v


def step(name):
    print(f"[bootstrap] -- {name}", flush=True)


def main():
    t0 = time.time()
    seed = env("LAB_SEED_TEST_USERS", "false", required=False).lower() == "true"
    authz = env("LAB_CATALOG_AUTHZ", "openfga", required=False)
    s3_ak = env("SEAWEEDFS_ADMIN_ACCESS_KEY")
    s3_sk = env("SEAWEEDFS_ADMIN_SECRET_KEY")

    # ---------------------------------------------------------------- Keycloak
    step("keycloak: users")
    web.wait_for(f"{keycloak.KC}/realms/{keycloak.REALM}/.well-known/openid-configuration")
    kc = keycloak.Admin(env("KC_ADMIN_USER"), env("KC_ADMIN_PASSWORD"))
    gids = kc.group_ids()
    changed = kc.ensure_user(env("LAB_ADMIN_USER"), env("LAB_ADMIN_PASSWORD"),
                             "Lab", "Admin", "lab-admin", gids)
    if seed:
        pw = env("LAB_TEST_USER_PASSWORD")
        for username, first, last, group in keycloak.TEST_USERS:
            changed |= kc.ensure_user(username, pw, first, last, group, gids)
    changed |= kc.set_direct_grants("trino", seed)
    print(f"[keycloak] users: {'updated' if changed else 'unchanged'} "
          f"(test users {'on' if seed else 'off'})")

    step("trino: group provider file from Keycloak groups (OQ-17)")
    members = {g: kc.group_members(gids[g]) for g in keycloak.LAB_GROUPS}
    changed = trino_groups.write(members)
    print(f"[trino] {trino_groups.PATH}: {'written' if changed else 'unchanged'} "
          f"({', '.join(f'{g}={len(u)}' for g, u in members.items())})")

    # ---------------------------------------------------------------- SeaweedFS
    step("seaweedfs: bucket")
    if not seaweedfs.anonymous_denied(lakekeeper.BUCKET):
        raise SystemExit("[seaweedfs] anonymous S3 access is not denied; refusing to continue")
    created = seaweedfs.ensure_bucket(lakekeeper.BUCKET, s3_ak, s3_sk, lakekeeper.REGION)
    print(f"[seaweedfs] bucket {lakekeeper.BUCKET}: {'created' if created else 'unchanged'}")

    # ---------------------------------------------------------------- Lakekeeper
    step("lakekeeper: server + warehouse")
    token = keycloak.client_credentials_token("lakekeeper", env("OIDC_CLIENT_SECRET_LAKEKEEPER"))
    lk = lakekeeper.Client(token)
    did, info = lk.ensure_bootstrapped()
    print(f"[lakekeeper] bootstrapped: {'now' if did else 'already'}; authz-backend "
          f"{info.get('authz-backend')} (requested {authz})")
    state, wh = lk.ensure_warehouse(s3_ak, s3_sk)
    print(f"[lakekeeper] warehouse {lakekeeper.WAREHOUSE}: {state} "
          f"({wh.get('warehouse-id') or wh.get('id')})")

    if authz == "openfga":
        from . import lakekeeper_authz
        step("lakekeeper: permissions from Keycloak groups (OpenFGA, OQ-5)")
        lakekeeper_authz.sync(lk, kc, wh, members)

    print(f"[bootstrap] done in {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    try:
        main()
    except web.HTTPError as e:
        print(f"[bootstrap] FAILED: {e}", file=sys.stderr)
        sys.exit(1)
