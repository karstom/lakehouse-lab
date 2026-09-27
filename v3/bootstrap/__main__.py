"""Lakehouse Lab V3 bootstrap: `python3 -m bootstrap` (the one-shot `bootstrap` service).

Idempotent: every step checks current state first, and a second run reports "unchanged"
everywhere. Exits non-zero on the first failure, so `up --wait` fails loudly instead of
starting Trino against a half-configured catalog.
"""
import os
import sys
import time

from . import (airflow_client, batch_client, github_idp, jupyterhub_client, keycloak, lakekeeper,
               seaweedfs, superset_client, trino_groups, web)


def env(name, default=None, required=True):
    v = os.environ.get(name, default)
    if required and not v:
        raise SystemExit(f"[bootstrap] missing required environment variable {name}")
    return v


def step(name):
    print(f"[bootstrap] -- {name}", flush=True)


def sync_trino_groups(kc, gids, quiet=False):
    """Keycloak group membership -> Trino file group provider. Returns the membership map."""
    members = {g: kc.group_members(gids[g]) for g in keycloak.LAB_GROUPS}
    changed = trino_groups.write(members)
    if changed or not quiet:
        print(f"[trino] {trino_groups.PATH}: {'written' if changed else 'unchanged'} "
              f"({', '.join(f'{g}={len(u)}' for g, u in members.items())})", flush=True)
    # Phase 4: the rules Trino reads = static rules + each analyst's own dbt_<user> schema.
    changed = trino_groups.write_rules(members)
    if changed or not quiet:
        print(f"[trino] {trino_groups.RULES_PATH}: {'written' if changed else 'unchanged'}",
              flush=True)
    return members


def sync_once(quiet):
    """One identity sync: Keycloak groups -> Trino group file and Lakekeeper roles/grants.
    Uses only the read-only lab-sync account and the Lakekeeper operator client (OQ-20)."""
    kc = keycloak.Admin.with_client(keycloak.SYNC_CLIENT, env("OIDC_CLIENT_SECRET_SYNC"))
    members = sync_trino_groups(kc, kc.group_ids(), quiet)
    authz = env("LAB_CATALOG_AUTHZ", "openfga", required=False)
    lk = lakekeeper.Client(keycloak.client_credentials_token(
        "lakekeeper", env("OIDC_CLIENT_SECRET_LAKEKEEPER")))
    wh = lk.find_warehouse()
    if wh is None:
        raise RuntimeError("warehouse not found; has bootstrap completed?")
    if authz == "openfga":
        from . import lakekeeper_authz
        lakekeeper_authz.sync(lk, kc, wh, members, quiet=quiet)
    # Phase 3: the shared `analytics` namespace and lab-batch's grants on it (CONTRACT Phase 3,
    # ADR-017). Re-ensured on every tick, so a dropped namespace is back, with its grants,
    # within one interval instead of at the next install.
    batch_client.ensure_lakekeeper(lk, kc, wh, authz, quiet=quiet)


HEARTBEAT = "/tmp/identity-sync.ok"


def sync_loop():
    """identity-sync service: repeat sync_once every LAB_SYNC_INTERVAL seconds so group
    changes made in the Keycloak UI take effect without a shell. Errors are logged and
    retried on the next tick; the healthcheck watches the heartbeat file."""
    interval = int(env("LAB_SYNC_INTERVAL", "30", required=False))
    print(f"[identity-sync] every {interval}s: Keycloak groups -> Trino, Lakekeeper", flush=True)
    quiet = False
    while True:
        try:
            sync_once(quiet)
            with open(HEARTBEAT, "w") as f:
                f.write(str(time.time()))
            quiet = True
        except Exception as e:  # keep running; the next tick retries
            print(f"[identity-sync] sync failed, retrying in {interval}s: {e}", file=sys.stderr, flush=True)
            quiet = False
        time.sleep(interval)


def main():
    t0 = time.time()
    seed = env("LAB_SEED_TEST_USERS", "false", required=False).lower() == "true"
    authz = env("LAB_CATALOG_AUTHZ", "openfga", required=False)
    s3_ak = env("SEAWEEDFS_ADMIN_ACCESS_KEY")
    s3_sk = env("SEAWEEDFS_ADMIN_SECRET_KEY")

    # ---------------------------------------------------------------- Keycloak
    step("keycloak: users")
    web.wait_for(f"{keycloak.KC}/realms/{keycloak.REALM}/.well-known/openid-configuration")
    kc = keycloak.Admin.with_password(env("KC_ADMIN_USER"), env("KC_ADMIN_PASSWORD"))
    gids = kc.group_ids()
    changed = kc.ensure_user(env("LAB_ADMIN_USER"), env("LAB_ADMIN_PASSWORD"),
                             "Lab", "Admin", "lab-admin", gids)
    if seed:
        pw = env("LAB_TEST_USER_PASSWORD")
        for username, first, last, group in keycloak.TEST_USERS:
            changed |= kc.ensure_user(username, pw, first, last, group, gids)
    else:
        # Seeding turned off later: delete the seeded test users (only accounts carrying the
        # seeding marker; never the first admin). Before the Trino/Lakekeeper syncs below, so
        # both drop them on this same run.
        changed |= keycloak.remove_test_users(kc, protected=(env("LAB_ADMIN_USER"),))
    changed |= kc.set_direct_grants("trino", seed)
    changed |= kc.ensure_sync_client(env("OIDC_CLIENT_SECRET_SYNC"))
    # Phase 2: JupyterHub's confidential client (never only in the realm template).
    changed |= jupyterhub_client.ensure_jupyterhub_client(
        kc, env("OIDC_CLIENT_SECRET_JUPYTERHUB"), env("LAB_DOMAIN"), env("LAB_HTTPS_PORT"))
    # Phase 3. Every client is ensured in every profile (harmless while its service is not
    # running), so a profile switch never needs a special bootstrap run.
    #  * airflow + its UMA model (OQ-16); password grant only for seeded tests, like trino.
    changed |= airflow_client.ensure_airflow_client(
        kc, env("OIDC_CLIENT_SECRET_AIRFLOW"), env("LAB_DOMAIN"), env("LAB_HTTPS_PORT"), gids,
        direct_grants=seed)
    #  * lab-batch, the batch service identity (client credentials only, ADR-017).
    changed |= batch_client.ensure_batch_client(kc, env("OIDC_CLIENT_SECRET_BATCH"))
    #  * superset (FAB OAuth) and console (oauth2-proxy forward-auth).
    changed |= superset_client.ensure_superset_client(
        kc, env("OIDC_CLIENT_SECRET_SUPERSET"), env("LAB_DOMAIN"), env("LAB_HTTPS_PORT"))
    changed |= superset_client.ensure_console_client(
        kc, env("OIDC_CLIENT_SECRET_CONSOLE"), env("LAB_DOMAIN"), env("LAB_HTTPS_PORT"))
    #  * ADR-016: the first-broker-login flow always; the github IdP only when configured.
    changed |= github_idp.ensure_github_idp(
        kc, env("OIDC_CLIENT_ID_GITHUB", required=False),
        env("OIDC_CLIENT_SECRET_GITHUB", required=False))
    print(f"[keycloak] users: {'updated' if changed else 'unchanged'} "
          f"(test users {'on' if seed else 'off'})")

    step("trino: group provider file from Keycloak groups (OQ-17)")
    members = sync_trino_groups(kc, gids)

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

    step("lakekeeper: namespace analytics + lab-batch grants (ADR-017)")
    batch_client.ensure_lakekeeper(lk, kc, wh, authz)

    print(f"[bootstrap] done in {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    try:
        if sys.argv[1:2] == ["sync"]:
            if "--once" in sys.argv:
                sync_once(quiet=False)
            else:
                sync_loop()
        else:
            main()
    except web.HTTPError as e:
        print(f"[bootstrap] FAILED: {e}", file=sys.stderr)
        sys.exit(1)
