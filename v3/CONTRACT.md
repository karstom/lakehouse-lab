# V3 Phase 1: Build Contract

> Written by the lead before the Phase 1 fan-out. The workstreams build against it.
> Changing anything here requires the lead. Design: `docs/v3/`. Phase 0 evidence:
> `spikes/*/RESULTS.md` (reuse what works there, and productionize it).

## Scope: Phase 1 (`core` profile)

Caddy, Keycloak, Postgres, SeaweedFS (with STS), Lakekeeper, Trino, one-shot `bootstrap`, the
installer, the version and compatibility checks, and CI.

**Exit:**
- A fresh install on Linux (and WSL2) reaches a query run in Trino **as a Keycloak-logged-in
  user** in under 15 minutes.
- The Iceberg table created by that query is readable through the catalog with vended
  credentials.
- CI runs the same path.

Not in Phase 1: Spark, JupyterHub/workspace, Airflow, Superset, Console UI (the Console is a
static placeholder page), AI.

## Layout and ownership

```
v3/
  CONTRACT.md                 lead
  versions.env                lead — the ONLY place versions live
  compose.yaml                CORE — top level; `include:`s compose/*.yaml
  compose/*.yaml              CORE — one fragment per service group
  images/<name>/Dockerfile    CORE — custom images (ARG pins only)
  config/                     CORE — caddy, keycloak realm template, trino, seaweedfs, lakekeeper
  bootstrap/                  CORE — idempotent scripts run by the one-shot `bootstrap` service
  tests/smoke/                CORE — end-to-end smoke test (headless login → Trino → catalog)
  install.sh                  INSTALLER
  lab                         INSTALLER — CLI: up | down | status | urls | logs | reset | test
  installer/                  INSTALLER — helper scripts (secrets, CA, domain detection, checks)
  tests/installer/            INSTALLER — installer tests (bats or plain bash + shellcheck)
  tools/                      TOOLING — check_versions.py, check_compat.py, relock helpers
  tests/lint/                 TOOLING
../.github/workflows/v3-*.yml TOOLING — v3-ci.yml (lint + install + smoke), v3-images.yml
```

A workstream edits only its own paths. If it needs a change elsewhere, it reports it
instead of making it.

## Runtime contract (installer ⇄ compose ⇄ CI)

The installer writes two **untracked** files next to `compose.yaml`. The stack is always
started as:

```
docker compose --project-directory v3 --env-file v3/versions.env --env-file v3/.env \
  --profile core up -d --wait --remove-orphans
```

`./lab` and `./install.sh` also export **`LAB_AUTH_URL`**, the public Keycloak origin derived
from `LAB_DOMAIN`/`LAB_HTTPS_PORT` with the default `:443` omitted. It is the single source
of the OIDC issuer origin and is never stored in `.env`. A raw `docker compose` call must
export it; compose fails loudly without it.

`v3/.env` holds non-secret settings. The installer writes it; users may edit it.

| Var | Meaning | Default |
|---|---|---|
| `COMPOSE_PROJECT_NAME` | Compose project; prefix for volumes and containers | `lakehouse` |
| `LAB_DOMAIN` | Base domain; services are `<svc>.${LAB_DOMAIN}` | `lab.localhost` |
| `LAB_HTTPS_PORT` | Host port Caddy publishes (the only published port) | `443` |
| `LAB_HTTP_PORT` | Plain-HTTP port (redirects, and `*.localhost` HTTP) | `80` |
| `LAB_PROFILE` | Selected profile | `core` |
| `LAB_STATE_DIR` | Host dir for state that must survive `down -v` (CA root, etc.) | `./state` |
| `LAB_TZ` | Timezone | host TZ |

`v3/.secrets.env` (mode 600) holds secrets, generated with a CSPRNG (`openssl rand` or
`/dev/urandom`, **never `$RANDOM`**, per ISSUE_WEAK_CREDENTIAL_RNG). Database passwords are
URL-safe (INV_DB_PASSWORDS_URL_SAFE).

| Var | Used by |
|---|---|
| `POSTGRES_PASSWORD` | postgres superuser |
| `KEYCLOAK_DB_PASSWORD`, `LAKEKEEPER_DB_PASSWORD` | per-service DB users |
| `KC_ADMIN_USER`, `KC_ADMIN_PASSWORD` | Keycloak master-realm admin |
| `LAB_ADMIN_USER`, `LAB_ADMIN_PASSWORD` | first lab admin (realm `lakehouse`, group `lab-admin`) |
| `SEAWEEDFS_ADMIN_ACCESS_KEY`, `SEAWEEDFS_ADMIN_SECRET_KEY` | SeaweedFS admin identity (bootstrap + Lakekeeper storage credential only) |
| `SEAWEEDFS_STS_SIGNING_KEY` | SeaweedFS STS signing key |
| `LAKEKEEPER_PG_ENCRYPTION_KEY` | Lakekeeper secret encryption |
| `OIDC_CLIENT_SECRET_TRINO`, `OIDC_CLIENT_SECRET_LAKEKEEPER`, `OIDC_CLIENT_SECRET_CONSOLE` | confidential OIDC clients |
| `OIDC_CLIENT_SECRET_SYNC` | read-only `lab-sync` service account used by `identity-sync` (created by bootstrap) |
| `TRINO_INTERNAL_SECRET` | Trino shared secret |

Test users (`alice` lab-admin, `eddie` engineer, `anna` analyst, `victor` viewer) are created
**only** when `LAB_SEED_TEST_USERS=true` (CI and dev). Their password is
`LAB_TEST_USER_PASSWORD`, stored in `.secrets.env`.

**CA root:** the installer creates it once in `${LAB_STATE_DIR}/ca/` (`root.crt`, `root.key`,
10 years), and Caddy mounts it read-only as its PKI root. `down -v`, reinstall and upgrade
never regenerate it (anti-pattern: Caddy CA in a wipeable volume). Containers trust it
through a mounted `ca-bundle`.

## Stack conventions (CORE)

- **One network, `lab`.** Caddy carries every public hostname as a network alias, so the
  issuer URL is the same inside containers and in browsers (S-3 pattern).
- **Public hostnames:** `auth.` (Keycloak), `trino.`, `catalog.` (Lakekeeper UI/API),
  `console.` (placeholder), `storage.` (SeaweedFS admin, lab-admin only via forward-auth, or
  omitted in Phase 1).
- **Volumes** are declared once in compose, with names derived from `COMPOSE_PROJECT_NAME`,
  and nowhere else (INV_VOLUME_NAMES_SINGLE_SOURCE). No `external: true`. Nothing outside
  compose creates volumes.
- **Every container** has `mem_limit` and `cpus` from `${SVC_MEM:-default}`-style variables.
  The core total must fit a 16 GB machine (target ≤ 10 GB of limits).
- **No logic in `command:`/`entrypoint:`** beyond calling a script. No runtime package
  installs. No `:latest`. Images are built from `images/` with pins from `versions.env`.
- **Healthchecks on every long-running service,** so `up --wait` means ready. `bootstrap` is
  one-shot and idempotent (re-running changes nothing), and later services depend on
  `service_completed_successfully` where needed.
- **Storage access follows ADR-006 as amended:** Trino uses vended STS credentials limited
  to one table. There are no static S3 keys in Trino. SeaweedFS STS is configured, and the
  trust policy is narrowed to Lakekeeper's identity.
- **Authorization:**
  - Trino web UI: OAuth2. Clients: JWT from Keycloak.
  - Trino access control uses a file-based group provider generated from Keycloak groups by
    bootstrap (OQ-17).
  - Lakekeeper uses OIDC. Try OpenFGA (OQ-5), with this decision rule: adopt it only if the
    bootstrap stays click-free and the smoke test passes. Otherwise use `allow-all` behind a
    documented flag and report the evidence.
  - Also report whether a Trino user's identity can reach Lakekeeper (session or token
    exchange) or whether Lakekeeper trusts Trino's service identity.

## Test contract

- `v3/lab test` runs `tests/smoke/run.sh` against the running stack. It exits 0 only when all
  of the following hold:
  1. The stack is healthy.
  2. A headless browser logs in as `alice` through `auth.` and reaches the Trino UI
     authenticated.
  3. Using a Keycloak-issued token for `alice`, the Trino client creates a namespace and an
     Iceberg table, inserts rows, and reads them back.
  4. PyIceberg loads the same table through Lakekeeper with vended credentials, and the
     credentials are denied on a sibling prefix.
  5. `victor` (viewer) is denied a write in Trino.
  6. No static S3 key appears in the Trino config or environment.
  7. A group change made through the Keycloak admin API (what the Keycloak UI does) reaches
     Trino with no shell step, both granting and revoking (the `identity-sync` service, OQ-20).
- The smoke test runs from a container on the `lab` network (Playwright image, pinned) that
  trusts the lab CA. The same command runs in CI and on the dev server.

## Where things run

- **Dev/validation host:** `$LAB_SERVER` (passwordless `ssh`; the lead gives agents the
  address). It runs production workloads, so these hard rules apply:
  - project `v3-p1` only;
  - the only published port is `LAB_HTTPS_PORT=18443` (plus `LAB_HTTP_PORT=18080` if
    needed);
  - never touch other projects;
  - no `sudo`, no `prune`;
  - `down -v` only for `v3-p1`.
- **Never commit** host IPs, hostnames, `.env`, `.secrets.env` or `state/`. The repo is public.
- **WSL2 check:** the lead's local machine (7 GB RAM, Docker available) with
  `LAB_DOMAIN=lab.localhost`.
- **Agents do not `git commit` or `git push`.** The lead integrates and pushes.

---

# Phase 2: Workspace and engines

> Added by the lead after Phase 1 (all exit criteria met, CI green) and the OQ-20
> identity-sync follow-up. Everything above still applies. Design: ADR-007/008/003,
> OQ-2/OQ-15. Evidence: `spikes/s4-workspace-image/RESULTS.md`, `v3/PHASE1_RESULTS.md`.

## Scope and exit

**Adds to `core`:**
- JupyterHub (OIDC login via Keycloak) spawning one **workspace** container per user from a
  pre-built `lakehouse-workspace` image. The image contains JupyterLab, SQL cells,
  jupyterlab-git, a terminal, code-server through jupyter-server-proxy, the Trino client,
  DuckDB with its extensions built in, PyIceberg, dbt-core + dbt-trino, the Spark Connect
  client, and jupyter-ai (installed, not configured: Phase 5).
- **Sample data:** bootstrap creates `lakehouse.samples.*` Iceberg tables with Trino
  `CREATE TABLE AS` from Trino's built-in `tpch` connector (`tiny` scale). No downloads.
- A starter dbt project (Trino target) over the samples, copied into each new user's home.

**Adds profile `engineer`:** Spark 4.1 master, one worker, and a **shared Spark Connect
server**. Profile `engineer` also includes everything in core. (Airflow and Superset come in
Phase 3.)

**Exit:**
1. The smoke test is extended to cover the workspace and passes in CI for **both** `core`
   and `engineer` (a CI matrix):
   - Alice logs into `jupyter.` in a headless browser and her workspace starts.
   - Inside it, as alice with her own token: a Trino query over `samples`, DuckDB `ATTACH`
     of the catalog with vended credentials, and `dbt build` of the starter project.
   - `engineer` profile only: Spark Connect creates and reads an Iceberg table as alice.
2. `victor` (viewer) is still denied writes from inside his workspace.
3. Idempotency, upgrade-in-place from Phase 1 (re-run `install.sh` on an existing install)
   and the existing 7 smoke checks keep passing.

## Workstreams and ownership

| Workstream | Owns |
|---|---|
| **WORKSPACE** | `images/workspace/`, `compose/workspace.yaml`, `config/jupyterhub/`, `starter/` (dbt project + a README notebook), `bootstrap/jupyterhub_client.py` |
| **SPARK+DATA** | `images/spark/`, `compose/spark.yaml`, `config/spark/`, `bootstrap/samples.py`, `config/trino/catalog/tpch.properties`, edits to `config/trino/rules.json` |
| **TESTS+CI** | `tests/smoke/` (new checks), `.github/workflows/v3-ci.yml` (profile matrix), `lab`/`installer/` changes for the `engineer` profile and per-user volume cleanup, bootstrap removal of test users when `LAB_SEED_TEST_USERS=false` (`bootstrap/keycloak.py`) |

Only the **integrator** edits `bootstrap/__main__.py`, `compose.yaml`, `versions.env` and
this contract. New pins go in `v3/.pins/<workstream>.env`. Any new Keycloak client is created
idempotently by bootstrap (pattern: `ensure_sync_client`), **never** only in the realm
template: the realm is imported on first start only, so existing installs would never get it.

## Identity in the workspace (the hard part)

- JupyterHub uses GenericOAuthenticator against realm `lakehouse`, with a new confidential
  client `jupyterhub` (secret `OIDC_CLIENT_SECRET_JUPYTERHUB` from the installer) and
  `enable_auth_state` (key `JUPYTERHUB_CRYPT_KEY` from the installer).
- **Workspace clients act as the logged-in user.** Trino (JWT), Lakekeeper/PyIceberg/DuckDB
  (OAuth token, vended credentials) and dbt-trino (`method: jwt`) all use the user's own
  Keycloak token, which must stay valid for hours-long sessions. Access tokens last 5 min,
  so provide a single helper in the image, for example `lab_token()` in Python plus a
  `lab-token` CLI. It gets a fresh token (refresh-token grant or the hub's auth-state
  refresh) and is the ONE place clients get tokens. Document the mechanism chosen.
- **Spark Connect identity (OQ-15).** Preferred: a per-session catalog token. Spark
  Connect gives each client its own session, and the Iceberg REST catalog is configured per
  session with the user's token, so Lakekeeper authorizes the real user. Decision rule:
  - adopt it if alice can write through Spark and victor is denied;
  - otherwise use the Spark service identity, **enforce "engineer/lab-admin only" for Spark
    Connect**, and document the evidence.
- Groups keep coming only from Keycloak; `identity-sync` is unchanged.

## Docker access (the host runs production)

- DockerSpawner **never** gets `/var/run/docker.sock` directly. A pinned
  `docker-socket-proxy` sidecar exposes only what DockerSpawner needs (containers, images
  read, networks, volumes), on an internal network that only JupyterHub is attached to.
- Every spawned container and volume has label `com.docker.compose.project=${COMPOSE_PROJECT_NAME}`
  plus `lab.role=workspace`, and name prefix `${COMPOSE_PROJECT_NAME}-ws-`. Each has
  `mem_limit`/`cpus` (`WORKSPACE_MEM`/`WORKSPACE_CPUS`) and joins only the `lab` network.
- **Per-user home volumes** are the one exception to "volumes declared only in compose".
  JupyterHub creates them from a single name template
  (`${COMPOSE_PROJECT_NAME}-home-{username}`) with the labels above. `lab reset` must also
  delete them, selected by label for this project only. `lab down` stops workspace
  containers too.
- On the dev host: never list, stop or remove anything outside `v3-`-prefixed projects. The
  verifier audits this with `docker ps -a` and `docker volume ls` before and after.

## Hostnames and resources

- New public hostname: `jupyter.` (JupyterHub; workspaces are reached through the hub).
  Spark UI and forward-auth come later (Phase 3).
- Budgets:
  - `core` + one active workspace fits **≤ 10 GB** of limits;
  - `engineer` + one workspace fits a **16 GB** machine and the GitHub runner (16 GB). Use
    lower CI limits if needed, via env overrides in the workflow, not by editing defaults.
