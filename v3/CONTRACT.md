# V3 Phase 1: Build Contract

> Written by the lead before the Phase 1 fan-out. The workstreams build against it.
> Changing anything here requires the lead. Design: `docs/`. Phase 0 evidence:
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
  --profile "$LAB_PROFILE" up -d --wait --remove-orphans      # core (Phase 1) or engineer (Phase 2)
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
| `LAB_AI_QUIET_HOURS`, `LAB_AI_QUIET_TZ` | Local-model quiet hours `HH:MM-HH:MM` and their IANA zone (Phase 6; `./lab ai quiet-hours`); empty = off | empty (off) |

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
| `OIDC_CLIENT_SECRET_JUPYTERHUB` | confidential `jupyterhub` OIDC client (Phase 2; created and repaired by bootstrap) |
| `JUPYTERHUB_CRYPT_KEY` | JupyterHub auth-state encryption key (Phase 2; 32 bytes as 64 hex chars) |
| `OIDC_CLIENT_SECRET_AIRFLOW` | confidential `airflow` OIDC client (Phase 3; created, repaired and given its UMA model by bootstrap) |
| `OIDC_CLIENT_SECRET_BATCH` | `lab-batch` batch service identity, client credentials only (Phase 3, ADR-017); only `airflow-scheduler` and bootstrap hold it |
| `AIRFLOW_DB_PASSWORD` | Airflow metadata DB role `airflow` (Phase 3; re-synced by the `airflow-db` one-shot) |
| `AIRFLOW_FERNET_KEY` | Airflow connection/variable encryption (Phase 3; Fernet format = URL-safe base64 of 32 bytes) |
| `AIRFLOW_JWT_SECRET` | Airflow API/execution-API JWT signing (Phase 3) |
| `OIDC_CLIENT_SECRET_SUPERSET` | confidential `superset` OIDC client; also Superset's Trino service identity (Phase 3) |
| `SUPERSET_SECRET_KEY` | Superset session/metadata encryption key (Phase 3) |
| `SUPERSET_DB_PASSWORD` | Superset metadata DB role `superset` (Phase 3; re-synced by the `superset-db` one-shot) |
| `CONSOLE_COOKIE_SECRET` | oauth2-proxy session cookie key, exactly 32 chars (Phase 3) |
| `OIDC_CLIENT_ID_GITHUB`, `OIDC_CLIENT_SECRET_GITHUB` | **optional**, user-supplied, never generated: GitHub OAuth App (installer `--github-client-id/--github-client-secret`, both or neither; `--no-github` removes them). Absent = GitHub login off, and bootstrap removes the IdP (ADR-016, Phase 3) |
| `AI_GATEWAY_MASTER_KEY`, `AI_GATEWAY_SALT_KEY`, `AI_GATEWAY_DB_PASSWORD` | ai-gateway (LiteLLM admin key, credential encryption, DB role `ai_gateway`); the master key also goes to ai-keys (Phase 5) |
| `AI_GATEWAY_HUB_TOKEN` | JupyterHub credential for the ai-keys broker (Phase 5) |
| `LAB_AI_ANTHROPIC_API_KEY`, `LAB_AI_OPENAI_API_KEY`, `LAB_AI_LOCAL_API_KEY` | **optional**, user-supplied, never generated; `./lab ai enable-hosted` / `set-local` (Phase 5) |

Test users (`alice` lab-admin, `eddie` engineer, `anna` analyst, `victor` viewer) are created
**only** when `LAB_SEED_TEST_USERS=true` (CI and dev). Their password is
`LAB_TEST_USER_PASSWORD`, stored in `.secrets.env`.

**CA root:** the installer creates it once in `${LAB_STATE_DIR}/ca/` (`root.crt`, `root.key`,
10 years), and Caddy mounts it read-only as its PKI root. `down -v`, reinstall and upgrade
never regenerate it (anti-pattern: Caddy CA in a wipeable volume). Containers trust it
through a mounted `ca-bundle`.

## Stack conventions (CORE)

- **One network, `lab`** (Phase 3 adds the internal `spark` network, see "Networks" below). Caddy carries every public hostname as a network alias, so the
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

### Docker access design: the guard (amended after Phase 4)

> Added by the Phase 4 follow-up. The socket proxy's HAProxy regexes over raw request bodies
> were bypassable (a lowercase `"binds"`, an escaped `"Mounts"`, a second escaped
> `Mounts` key after the allowed DAG mount): Docker decodes JSON with Go's `encoding/json`,
> which matches keys case-insensitively, decodes `\u` escapes and keeps the last duplicate.
> The source of truth is the JSON **as Docker decodes it**, so the body policy now decodes it
> too (REG_V3_DOCKER_PROXY_BODY_REGEX_BYPASS).

```
jupyterhub --hub-docker--> docker-guard --docker-api--> docker-proxy --> /var/run/docker.sock
```

- **Topology.** `hub-docker` (internal) has only `jupyterhub` and `docker-guard`;
  `docker-api` (internal) has only `docker-guard` and `docker-proxy`. Only `docker-proxy`
  mounts the socket. JupyterHub's `DOCKER_HOST` is `tcp://docker-guard:2375`; it cannot reach
  the proxy directly (smoke check 11 tests this).
- **`docker-proxy`** (pinned `tecnativa/docker-socket-proxy`, `config/jupyterhub/docker-proxy.cfg`)
  keeps a METHOD + PATH allowlist only (paths are not JSON): no body rules.
- **`docker-guard`** (`bootstrap/docker_guard.py`, Python stdlib, runs on the bootstrap image,
  which is pinned by tag and digest) is the **single source of the request-body policy**:
  - forwards only the calls DockerSpawner makes (captured from real traffic): `GET /version`,
    `/_ping`; `GET` of the workspace image, of a `<project>-home-<user>` volume and of a
    `<project>-ws-<user>` container; `POST /containers/create?name=<project>-ws-<user>`;
    `start`, `stop` (`t` ≤ 600) and `DELETE` (`v` only; no `force`, no `link`) of that
    container; `POST /volumes/create`. `<user>` is DockerSpawner's escaped name
    (`[a-z0-9]` or `-` + two hex digits).
  - parses each body **strictly**: UTF-8 only, duplicate keys at any level refused, no
    NaN/Infinity, no lone surrogates or NUL, ≤ 256 KiB, no chunked bodies;
  - requires every key at every level to be **exactly** one allowlisted canonical spelling for
    that object (unknown or differently-cased keys are refused), then checks the values:
    `Image` = the workspace image; `Labels` = exactly the project labels;
    `HostConfig.Binds` = exactly `<project>-home-<user>:/home/jovyan:rw` and
    `<project>_trust:/trust:ro`; `HostConfig.Mounts` = nothing or exactly the user's own
    folder of `<project>_dags-user` (type volume, `VolumeOptions.Subpath` = the raw username
    whose escaped form is `<user>`, target `~/airflow-dags/<username>`; which users get it is
    still the hub's group decision); `NetworkMode` = `<project>_lab`; `NetworkingConfig`
    endpoints only `<project>_lab`; `Privileged`/`CapAdd`/`Devices`/host namespaces absent or
    false/empty; `Memory` ≤ `WORKSPACE_MEM`, `CpuQuota`/`CpuPeriod` ≤ `WORKSPACE_CPUS`;
    `Volumes` = exactly the bind targets. A volume create must be
    `{Name: <project>-home-<user>, Labels: <project labels>}`;
  - **re-serializes** the validated object (`json.dumps`, sorted keys, ASCII) and forwards
    only those bytes with their own `Content-Length`, and a query string rebuilt from
    validated values. Docker only ever sees bytes the guard produced;
  - fails closed: anything else is answered 403 and logged with a short reason (never the
    body, which holds the server's API token); a forwarded body is logged by sha256 and size.
- **Changing what the spawner sends** (a new DockerSpawner option, a new mount) means changing
  `validate_create` and its unit tests (`tests/bootstrap/test_docker_guard.py`) in the same
  change. Never add body rules to the proxy again.
- **Smoke check 11** (`tests/smoke/proxy_probe.py`, 54 cases) runs in `jupyterhub`: every
  refused case (including the bypasses above, case variants, escapes, duplicates, unknown
  keys) gets 403; allowed cases reach Docker, which refuses them itself (`Memory: 4` is below
  Docker's 6 MB minimum, so nothing is ever created); one allowed body with escaped and
  shuffled keys must appear in the guard's log as the canonical body the probe computed.

## Hostnames and resources

- New public hostname: `jupyter.` (JupyterHub; workspaces are reached through the hub).
  Spark UI and forward-auth come later (Phase 3).
- Budgets:
  - `core` + one active workspace fits **≤ 10 GB** of limits;
  - `engineer` + one workspace fits a **16 GB** machine and the GitHub runner (16 GB). Use
    lower CI limits if needed, via env overrides in the workflow, not by editing defaults.
  - **Amended in Phase 3 (proposed by the repair round; confirmed by the lead 2026-09-26):** Airflow adds 3.5 GiB of ceilings, so the sum of
    *default limits* for `engineer` + one workspace is 17.19 GiB, above 16 GB. The 16 GB
    budget for `engineer` is now measured on **use**, not on the sum of limits: measured peak
    use (whole lab, one instant) must stay ≤ 8 GiB, leaving half a 16 GB machine free; the
    Phase 3 dev-host peak on `full` with two workspaces and the 5 min Spark job was 5.5–6.25 GiB (the independent verifier's sampling measured 6.25 GiB, the higher figure counts).
    Limits are per-container ceilings that are never all reached at once. The CI runner
    still gets overrides that keep `engineer` + one workspace ≤ 16 GB of limits (15.44 GiB).
    `core` keeps its ≤ 10 GB-of-limits budget unchanged.

---

# Phase 3: Orchestration, BI, Console, external login

> Added by the lead after Phase 2 (verified, CI matrix green). Everything above still
> applies. Design: ADR-009/010/016/017, OQ-16/18. Evidence: `spikes/s3-sso-bootstrap/RESULTS.md`
> (Airflow 3 + Keycloak and Superset 6 OIDC already worked there), `v3/PHASE2_RESULTS.md`.

## Scope, profiles and exit

- **Profile `engineer`** adds **Airflow ≥ 3.1** (`AIRFLOW_VERSION`), with the Keycloak
  auth manager, and the **Spark UI** behind forward-auth.
- **Profile `full`** = engineer + **Superset 6** (`SUPERSET_VERSION`).
- **Every profile** gets the **Lab Console** v1 and optional **GitHub login** (ADR-016).

**Exit:**
1. **Airflow (engineer):**
   - One Keycloak login works. `lab-admin` is Admin, `engineer` can trigger and edit
     DAGs, `analyst`/`viewer` are read-only.
   - DAGs `lab_ingest`, `lab_dbt_build`, `lab_notebook` and `lab_spark_batch` succeed when
     triggered.
   - **ADR-017 proof:** `lab_spark_batch` survives past its token lifetime. With the batch
     service account's access-token lifespan cut to 120 s for the test, a Spark job running
     at least 300 s completes and commits.
2. **Superset (full):**
   - One Keycloak login works; `lab-admin` is Admin; others get Gamma plus SQL Lab
     (`analyst`, `engineer`) or Gamma only (`viewer`).
   - Queries run in Trino **as the logged-in user** (`current_user` = the person).
   - The bundled **"Revenue by region"** dashboard over `lakehouse.analytics.*` renders:
     the chart-data API returns rows.
3. **Console:** after login, `console.` shows only the tiles the user's groups can reach,
   plus a health summary. **Spark UI** (`spark.`) is reachable by
   `engineer`/`lab-admin` and refused (403) for `viewer`.
4. **GitHub login (optional, ADR-016):**
   - Off unless the installer is given `--github-client-id/--github-client-secret`.
   - A first external login creates a user with **no group**, who can reach nothing.
   - Once an admin adds a group in Keycloak, access follows within the `identity-sync`
     interval.
   - No automatic linking by email.
   - CI proves the flow against a **mock provider**: a second realm acting as an OIDC IdP,
     with alias `github-mock` in tests.
5. **Everything together:**
   - Upgrade in place from the running Phase 2 install passes; smoke passes on `core`,
     `engineer` and `full`.
   - The PR CI matrix (`core`, `engineer`) is green.
   - A **nightly/dispatch `full`** job runs the end-to-end chain ingest → dbt → dashboard. If
     `full` cannot fit a 16 GB runner even with overrides, say so with numbers and keep it
     dev-host-only.
6. The Docker-safety invariants and smoke check 11 still pass, and non-v3 objects on the
   dev host are unchanged.

## Shared interfaces (decided here so workstreams don't guess)

- **The `analytics` schema** is shared, production-style output. `lab_dbt_build` runs the
  starter dbt project with target `analytics` into `lakehouse.analytics`, as the batch
  service identity. Required tables: `fct_orders`, `dim_customers`, `revenue_by_region`.
  Superset's bundled dashboard reads only these. Everyone can read `analytics`; only the
  batch identity, `engineer` and `lab-admin` can write it (Trino rules plus Lakekeeper roles
  via bootstrap/identity-sync).
- **The batch service identity** is Keycloak client `lab-batch` (secret
  `OIDC_CLIENT_SECRET_BATCH`), created by bootstrap. Spark, dbt and Trino authenticate as it
  with **client credentials**, and clients re-fetch tokens themselves. The Iceberg REST
  `credential` flow (not the user token-exchange path) is expected to renew; prove it
  (exit 1).
- **Superset → Trino as the user:** Superset connects as service client `superset` and
  uses Trino **impersonation** of the logged-in username, with Trino
  `impersonation` rules allowing only that principal to impersonate users in the lab
  groups. Superset's per-user database OAuth2 is an acceptable alternative if it passes the
  same test.
- **Forward-auth** (Console and Spark UI) is **oauth2-proxy** (pinned) behind Caddy
  `forward_auth`, as Keycloak client `console` (the existing confidential client, which
  bootstrap repairs). Group headers from oauth2-proxy decide which Console tiles show and
  whether the Spark UI is allowed.
- **Keycloak clients** `airflow`, `superset`, `lab-batch` and the GitHub IdP are all
  ensured idempotently by bootstrap (never only in the realm template). Airflow's UMA
  authorization is a scripted, idempotent bootstrap step (OQ-16).

## Workstreams and ownership

| Workstream | Owns |
|---|---|
| **AIRFLOW** | `images/airflow/`, `compose/airflow.yaml`, `config/airflow/`, `dags/`, `bootstrap/airflow_client.py`, `bootstrap/batch_client.py` |
| **BI+CONSOLE** | `images/superset/`, `compose/superset.yaml`, `config/superset/` (incl. dashboard export), `bootstrap/superset_client.py`, `compose/console.yaml` (oauth2-proxy), `config/console/`, Caddy site changes for `console.`/`spark.`/`superset.`/`airflow.` (edits to `config/caddy/Caddyfile`), Trino impersonation rules (edits to `config/trino/rules.json`) |
| **IDP+TESTS+CI** | `bootstrap/github_idp.py`, installer/lab flags (`--profile full`, `--github-client-id/secret`), `tests/smoke/` new checks (Airflow, Superset, Console, Spark UI, IdP mock, batch long-run), `.github/workflows/v3-ci.yml` (+ `v3-nightly.yml`), mock-IdP test fixture |

As before: only the integrator edits `bootstrap/__main__.py`, `compose.yaml`,
`versions.env` and this contract. New pins go in `v3/.pins/<workstream>.env`. Public
hostnames added in Phase 3: `airflow.`, `superset.`, `spark.` (`console.` becomes real).
Memory target: `full` ≤ 24 GB of limits with one workspace.

## Conventions added at Phase 3 integration

- **Profiles:** compose has no profile inheritance, so every `engineer` service lists
  `profiles: [engineer, full]`; `full`-only services list `[full]`. The installer passes one
  `--profile`.
- **Restart on dependency update:** every long-running Postgres client declares
  `postgres: {condition: service_healthy, restart: true}`. Trino and the Spark services also
  declare it for `keycloak` and `lakekeeper`, plus `postgres` directly (`restart: true` is not
  transitive). Their Iceberg auth sessions do not recover from a Keycloak restart. This keeps
  an upgrade that recreates one of them from leaving dead pools or sessions behind
  (PHASE3_RESULTS, bugs 4-5).
- **One-shots on the postgres image** mount `tmpfs: /var/lib/postgresql/data` (no anonymous
  volumes).
- **Networks (Spark UI isolation, Phase 3 follow-up):** `lab` is no longer the only network.
  The internal network **`spark`** (`internal: true`, declared in `compose.yaml`) carries the
  Spark cluster, and workspaces never join it (they stay on `lab` only; the Docker proxy
  allowlist names `<project>_lab`).
  - `spark-master` and `spark-worker` are **only** on `spark`.
  - `spark-connect` is on `lab` (gRPC 15002 for workspaces and Airflow) and `spark`. Its
    driver RPC, block manager and application UI (4040) bind to its `spark` address alone
    (`images/spark/start-spark.sh` + `spark-bind-ip.py`: `spark.driver.bindAddress` and
    `SPARK_LOCAL_IP`); only 15002 listens on every interface.
  - Also on `spark`: what the executors call (`keycloak`, `lakekeeper`, `seaweedfs`, by
    internal names; no public hostname is used there, so no aliases), and `caddy`, whose
    `spark.` route (forward-auth, engineer/lab-admin) is the only way to any Spark UI.
    A service on two networks must listen on both: SeaweedFS needs `-ip.bind=0.0.0.0`
    (`config/seaweedfs/entrypoint.sh`), because weed otherwise binds only its detected `-ip`.
  - `spark.ui.killEnabled=false` everywhere (the Connect driver is shared).
  - A new service joins `spark` only if Spark calls it or it must proxy the Spark UI. Smoke
    check 15 proves from a viewer's workspace that 8080, 8081 and 4040 do not connect.

---

# Phase 4: Learning tracks

> Added by the lead after Phase 3 (verified, CI green). Everything above still applies.
> Design: ROADMAP Phase 4, OQ-10. The goal is that a beginner can **learn the job**, not
> just run the stack.

## Scope and exit

- **Two tracks**, each a sequence of short modules. A module is about 30–60 minutes and has:
  - a lesson (`README.md`: goal, concepts, steps);
  - starter files (notebook, SQL, dbt, DAG);
  - a **machine-checkable checkpoint**;
  - a `tutor.md` (learning objectives, common mistakes, hints). Phase 5's AI tutor mode
    reads this; nothing uses it before then.
- **Engineer track** (profile `engineer`):
  - E1 files → Iceberg with Spark;
  - E2 table maintenance (snapshots, time travel, compaction, snapshot expiry);
  - E3 author and schedule your own Airflow DAG;
  - E4 promote a notebook to a scheduled job (papermill), then to a Spark batch job
    (ADR-017).
- **Analyst track** (A1–A3 on `core`, A4 on `full`):
  - A1 SQL over `samples` (Superset SQL Lab on `full`; JupySQL on `core`);
  - A2 exploratory analysis in JupySQL + DuckDB;
  - A3 your first dbt model in your own schema;
  - A4 a chart and dashboard in Superset over your model.

**Exit:**
1. Every module's reference solution passes its checkpoint **as a seeded user, inside that
   user's workspace**, and `lab-tracks reset <module>` restores the module to its starting
   state:
   - module 1 of each track in the PR CI matrix;
   - all modules in the nightly `full` job.
2. **Content survives upgrades.** Tracks are copied into a new home as `~/tracks/`, and later
   image upgrades add new files without overwriting the user's edits. `lab-tracks reset`
   restores a pristine copy on request.
3. **Beginner validation** (ROADMAP exit): at least two real beginners complete module 1 of
   each track without help. **Owner-run; agents can't do this.** Agents deliver a short
   facilitator guide plus a feedback form (markdown).

## Content location (OQ-10, interim)

Tracks live in `v3/tracks/` inside this repo, laid out to move to their own repo later
without code changes. The workspace image copies them in at build time, the same way as
`starter/`. Moving them is a later owner decision, because creating a new public repo is an
outward-facing step.

```
v3/tracks/
  README.md                     track overview, prerequisites per profile
  engineer/E1-files-to-iceberg/ README.md  tutor.md  notebook.ipynb  checkpoint.py  (solution/ — see below)
  analyst/A1-sql-basics/        ...
  FACILITATOR.md  FEEDBACK.md   beginner-session guide and form (exit 3)
```

**Solutions:** reference solutions live under `v3/tests/tracks/solutions/` (test-only; not
copied into homes), so learners don't see answers by default. CI runs them.

## Workspace tooling

- `lab-tracks` CLI (in the workspace image):
  - `list` shows modules and status;
  - `check <module>` runs the checkpoint as the user, using `lab_token()`, and prints clear
    pass/fail hints;
  - `reset <module>` restores pristine files, and drops the module's objects in the user's
    own schema/namespace **only**.
- Progress goes to `~/.lab-progress.json`. The Console may later show it; not required now.
- Checkpoints verify *outcomes* (tables, rows, snapshots, DAG runs, dbt models, Superset
  objects through its API as the user), never file contents.

## E3 needs one piece of new infrastructure: user DAGs

- A shared volume `<project>_dags-user` holds one folder per user and is mounted read-only
  into Airflow's dag-processor/scheduler at `dags/user/`.
- **Each user's DAG files live in `~/airflow-dags/<username>/`.** An **engineer/lab-admin**
  workspace (group-based in `jupyterhub_config.py`) mounts **only its owner's folder**, as a
  volume mount with subpath `<username>`, read-write at `~/airflow-dags/<username>`; the
  hub creates the folder (owner 1000:100) in its own mount of the volume before the spawn.
  Every workspace runs as uid 1000, so only the mount can keep engineers out of each other's
  folders (repair round: the first design mounted the whole volume). The DAG id prefix
  `u_<username>_` is enforced by an Airflow DAG policy (which also refuses a longer
  username's prefix, e.g. `u_eddie_x_` in `eddie/`); files that break it are rejected with a
  visible import error.
- The **Docker access allowlist** (since the Phase 4 follow-up: enforced by `docker-guard`, see
  "Docker access design: the guard") gains exactly one `Mounts` entry: type `volume`, source
  `<project>_dags-user`, subpath one path segment equal to the target's last segment, target
  `~/airflow-dags/<segment>` (INV_V3_DOCKER_PROXY_PROJECT_SCOPE). A bind of the whole volume,
  any other `Mounts`, and a second `Mounts` key stay refused. Smoke check 11 covers these;
  check 17 proves, as an engineer, that a neighbour's folder cannot be written.
- Security note (to document): a user DAG runs with Airflow's worker identity (lab-batch
  for data access). That's acceptable because engineers are already trusted to trigger and
  edit DAGs; analysts and viewers never get the mount.

## Workstreams and ownership

| Workstream | Owns |
|---|---|
| **ENGINEER-TRACK** | `v3/tracks/engineer/`, `v3/tests/tracks/solutions/engineer/`, user-DAG infra (`config/airflow/` DAG policy, `compose/airflow.yaml` mount, `config/jupyterhub/` group mount, `config/jupyterhub/docker-proxy.cfg` + `tests/smoke/proxy_probe.py` new case) |
| **ANALYST-TRACK** | `v3/tracks/analyst/`, `v3/tests/tracks/solutions/analyst/`, Superset API helpers for A4 checkpoints |
| **TOOLING+CI** | `lab-tracks` CLI + progress + reset (`images/workspace/`), track copy-on-upgrade, `tests/smoke/` check 17 (run solution → checkpoint → reset per module), CI wiring (PR: module 1 of each track; nightly: all), `v3/tracks/README.md`, `FACILITATOR.md`, `FEEDBACK.md` |

The integrator owns `bootstrap/__main__.py`, `compose.yaml`, `versions.env` and this
contract, as before.

## Required: root-cause the intermittent workspace-kernel failures (TOOLING+CI)

Two intermittent failures have been seen in workspace kernels. Every Phase 4 module runs in
a kernel, and learners would see the same thing (a notebook that stops answering, or HTTP
403), so this is **not** a test-only problem:
- WATCH_V3_SPARK_CONNECT_INTERMITTENT_HANG: a kernel went silent after a Spark
  `ForbiddenException`.
- In the Phase 3 verification, alice's kernel returned **HTTP 403 / no result** on checks 8
  and 10 after a successful login and spawn. It passed on rerun. The stack-dump fetch also
  got HTTP 403.

**Required:**
1. **Reproduce.** Loop the in-workspace probe (login → spawn → kernel → Trino/Spark step →
   stop) at least 30 times per user on the dev host (project v3-p4-*, not v3-p1). Collect the
   thread dumps, the JupyterHub and single-user server logs, oauth/XSRF cookie state, and
   the Docker proxy logs for each failure.
2. **Find and fix the root cause** (candidates: hub-to-single-user OAuth token or cookie
   expiry, XSRF, spawn-readiness race, the proxy allowlist refusing a Docker call, the Spark
   Connect client). Record it as a Regression node with evidence.
3. **Retries only if the cause is external and outside our control.** In that case a
   *bounded* retry is allowed only for the "kernel never started/answered" class, and every
   retry is counted and shown in the smoke evidence; it must never hide an assertion
   failure. Justify it in `PHASE4_RESULTS.md`.
4. **Exit condition:** the 30-iteration loop runs with zero unexplained failures.

## Conventions added at Phase 4 integration

- **Module interface** (one for both tracks; `v3/tracks/README.md` is the reference, and
  `tools/check_tracks.py` enforces it in CI): `module.json` (`id`, `track`, `title`,
  `profile`, `groups`; optional `minutes`, `test_user`, `solution.timeout_s`,
  `solution.browser_logins`, and a free-form `reset` block), `README.md`, `tutor.md`, and
  `checkpoint.py` handling `--json` (last line `LAB_TRACKS_RESULT {...}`; exit 0 passed,
  1 not yet, 2 could not run) and `--reset`. Track helpers live in `<track>/_shared/`;
  solution helpers in `tests/tracks/solutions/<track>/_lib/`.
- **The learner's own objects** (what `reset` may drop): the module's namespace
  (`eng_<you>`), the analyst's schema `dbt_<you>` (only the module's tables), DAG files in
  `~/airflow-dags/<you>/`, Superset objects the learner owns, and **(lead decision)** the
  learner's production tables `lakehouse.analytics.u_<you>_*`, which their own DAGs write as
  `lab-batch` (E3/E4). `lab-batch` cannot write `eng_<you>`, and a prefixed table in the
  shared production schema is what a real team does.
- **Analysts own one schema, `lakehouse.dbt_<you>`.** Trino's file rules cannot put the user
  into a schema name, so bootstrap and identity-sync GENERATE the rules Trino reads
  (`trino-groups/rules.json` = `config/trino/rules.json` + one user-and-schema rule pair per
  `analyst` member; `bootstrap/trino_groups.py`). Access still comes only from the Keycloak
  group; leaving `analyst` removes the rule on the next sync tick.
- **Superset API as the user** (A4): Superset accepts the user's own Keycloak access token
  (`azp` `jupyterhub` only, existing active Superset user only, roles recomputed from the
  token's groups; `config/superset/lab_bearer.py`). Role `lab_author` (analyst, engineer) may
  add datasets; owners-only edits stay Superset's rule.
- **Workspace kernels:** `IPYKERNEL_VERSION` is pinned on the 6.x line
  (REG_V3_WORKSPACE_KERNEL_FIRST_MESSAGE_STALL). Caddy drops idle upstream connections to
  JupyterHub after 4 s, before the hub proxy's 5 s (WATCH_V3_CADDY_UPSTREAM_KEEPALIVE_502).

---

# Phase 5: Context-aware AI assist

> Added by the lead after Phase 4 (verified, CI green). Everything above still applies.
> Design: ADR-014. OQ-8 is decided (owner, 2026-09-26): **hosted providers are OFF by
> default**, only an admin can enable one with its own key, and local models run through a
> local OpenAI-compatible server. OQ-7 (gateway) and OQ-9 (Trino MCP) are decided in this
> phase, with evidence.

## ⚠ Quiet hours (owner rule): no inference on the owner's local LLM before 07:00

The dev host runs llama.cpp `llama-server` at `http://<host>:9999`, OpenAI-compatible,
serving a Qwen 27B model. Inference spins up the server's fans.

**Agents in this phase must not send a single inference or embedding request to it, at
any time.** Configure it as the default local provider, but every build and test uses a
**mock model**. `/health` and `/v1/models` metadata calls are allowed. The lead runs the
one real-model check after 07:00 America/New_York (11:00 UTC).

## Scope (profile `full`; the AI gateway is part of `full`)

1. **Model gateway** (`ai-gateway`):
   - LiteLLM proxy (OQ-7). Use **only** features available in its open-source license and
     record which ones.
   - It is pinned and has its own Postgres DB, created by bootstrap.
   - **Keys:** each user gets a per-user virtual key with a budget. JupyterHub mints it
     through bootstrap-created admin credentials and injects it into the workspace. Users
     never see provider keys.
   - **Providers:**
     - `local` (`LAB_AI_LOCAL_URL`, default unset; the installer asks; on the dev host it
       points at llama-server);
     - `hosted` (Anthropic/OpenAI), off unless enabled with
       `./lab ai enable-hosted --provider … --key-file …`;
     - `mock`, for tests only (a deterministic, scripted OpenAI-compatible server in
       `tests/ai/`).
   - With no provider enabled, AI features return a clear "AI isn't configured; ask your
     lab admin" message, and the lab makes **no outbound AI calls**. Tests assert this.
2. **Workspace:**
   - Jupyter AI v3 is configured to use the gateway with the user's key.
   - **Claude Code is not built into the image** (proprietary; the image is public). A
     user-initiated `lab-ai install-claude-code` installs it into the home folder, pinned
     and pointed at the gateway.
   - A `lab-ai` CLI: `status`, `tutor on|off`, `install-claude-code`.
3. **MCP servers, acting as the user** (the token from `lab_token()`; read-only; row and
   time limits; tokens never appear in tool output):
   - **dbt-mcp**, the official one: models, lineage, docs of the user's project and of
     `analytics`.
   - **Trino** (OQ-9): adopt a community server only if it can use the user's JWT and
     enforce read-only access. Otherwise build a thin wrapper (SELECT/SHOW/DESCRIBE only,
     ≤ 200 rows, ≤ 30 s).
   - **lab-context** (ours, thin):
     - `superset_dashboard_datasets`;
     - `table_last_snapshot` (Iceberg snapshot times via Lakekeeper/Trino as the user);
     - `airflow_runs` (as the user);
     - `catalog_list`;
     - `current_lesson` (from `~/.lab-progress.json` + the module's `tutor.md`).
4. **Tutor mode:** inside a track module, the assistant's system prompt comes from that
   module's `tutor.md`: explain and hint, don't hand over the solution. It is on by default
   for track work, and `lab-ai tutor off` turns it off per user.
5. **Safety:**
   - Tool outputs are untrusted input, and the docs say so (prompt injection).
   - Every tool call runs with the user's permissions, so victor sees nothing he couldn't
     query himself.
   - Per-user budgets are enforced: past the budget, requests get a clear error.

## Exit

1. **CI (mock model): smoke check 18.** A scripted agent loop, going through the gateway
   and the MCP servers **as alice**, answers **"Which tables feed the 'Revenue by region'
   dashboard, and when did each last load?"**:
   - the dataset and table names come from Superset + dbt lineage, and the load times from
     Iceberg snapshots;
   - the tool calls hit the real services;
   - the numbers are checked against Trino.
2. **As victor** (viewer), the same loop returns only what he may read: tool calls he
   isn't allowed to make are denied, with no leak in the output.
3. With no provider enabled, the lab makes no outbound AI calls (checked). A budget
   overrun gives an error. Tutor mode's prompt carries the module's `tutor.md`, and turning
   it off works.
4. **Real model: lead-run, after 07:00 only.** The same question through the gateway to the
   local llama-server Qwen model gives a correct, grounded answer. This is recorded as
   evidence, not a CI gate.
5. Upgrade in place and a clean install (`full`) pass all checks. Docker-safety invariants
   hold, including docker-guard. Non-v3 objects on the dev host are unchanged.

## Workstreams and ownership

| Workstream | Owns |
|---|---|
| **GATEWAY** | `images/ai-gateway/`, `compose/ai.yaml`, `config/ai/`, `bootstrap/ai_gateway.py`, installer/`lab ai` flags and subcommands, the mock LLM server in `tests/ai/mock_llm/` |
| **WORKSPACE-AI** | Jupyter AI config in `images/workspace/` and `config/jupyterhub/` (key injection), the `lab-ai` CLI, the Claude Code opt-in installer, MCP client configuration, tutor-mode prompt assembly |
| **MCP+TESTS** | `images/workspace/mcp/` (lab-context server, Trino MCP decision/wrapper, dbt-mcp integration), `tests/smoke/` check 18, CI wiring (mock only), OQ-9 evidence |

The integrator owns `bootstrap/__main__.py`, `compose.yaml`, `versions.env` and this
contract.

## Conventions added at Phase 5 integration

- **Profiles:** the AI gateway services (`ai-gateway-db`, `ai-gateway`, `ai-keys`, and since the follow-up `ai-frontdoor`) are `[full]`.
  The deterministic mock model `ai-mock` has its own profile `ai-mock`, added by `./lab` (and
  `lab_compose`) only when `.env` has `LAB_AI_MOCK=true` (`install.sh --ai-mock`; test installs
  and CI only). `compose.yaml` includes `compose/ai.yaml` before `compose/test.yaml`.
- **Providers are decided only by the lab's own files** (`.env`, `.secrets.env`): `lab_settings`
  unsets a stray `LAB_AI_MOCK`, `LAB_AI_LOCAL_URL` or `LAB_AI_*_API_KEY` from the caller's
  shell. `install.sh --non-interactive` never enables a provider; interactively, on `full`, it
  asks once for a local URL (default none).
- **Keys:** JupyterHub never holds the gateway master key. It mints a per-user key at every
  spawn through `ai-keys` with `AI_GATEWAY_HUB_TOKEN`, injects it only as container
  environment (`LAB_AI_*`, `OPENAI_*`), and revokes it at stop. docker-guard's allowlist is
  unchanged (Env entries are `NAME=value`); smoke check 11 stays at 54 cases.
- **Never call the gateway's `/health`** (it sends a request to every model). Liveness is
  `/health/liveliness`. The gateway has no retries and no background health checks.
- **MCP servers** live in their own venv (`/opt/lakehouse/mcp/venv`); pins `DBT_MCP_VERSION`,
  `MCP_SDK_VERSION`, `SQLGLOT_VERSION`. The registry is `/opt/lakehouse/mcp/servers.json`
  (`mcpServers` format). Airflow's plugin `config/airflow/plugins/lab_auth.py` (mounted into
  `airflow-api` only) exchanges a `jupyterhub`-azp Keycloak token for an Airflow API token
  that carries it; Keycloak UMA still decides every request.
- **Claude Code** is only pinned (`CLAUDE_CODE_VERSION` + per-platform sha256 in
  `versions.env`); the image carries the pin, never the binary.
- **Tests use the mock model only.** Smoke check 18 (profile `full`) always requests model
  `mock`; `tests/ai/gateway-e2e.sh` and `tests/smoke/ai-no-provider.sh` run in the nightly.
- **`tests/ai/gateway-e2e.sh` never configures the `local` provider by default.** It runs
  only on a lab whose gateway renders providers exactly `[mock]` (else it stops before any
  request). Its step 3 (`local-via-mock`: `LAB_AI_LOCAL_URL` pointed at `ai-mock`) is
  opt-in with `LAB_E2E_LOCAL_VIA_MOCK=1`, for hosts where no real model server can be
  reached (a CI runner). On the dev host (a real model server, quiet hours) leave it off.
  `tests/ai/test_gateway_e2e_script.py` checks this against a fake `docker`.

## AI front door and workspace AI boundaries (Phase 5 follow-up)

- **Workspaces never talk to the gateway directly.** `ai-gateway` is only on the `ai`
  network (`compose.yaml`: `ai-gateway`, `ai-frontdoor`, `ai-keys`, `postgres`, and on test
  installs `ai-mock` and the smoke driver). Workspaces are only on `lab` (docker-guard pins
  them there). The only path between the two is **`ai-frontdoor`**
  (`bootstrap/ai_frontdoor.py`, stdlib, on the bootstrap image, `lab` + `ai`, port 4000). The
  broker hands out `http://ai-frontdoor:4000` (`AI_GATEWAY_CLIENT_URL`) as `base_url`, so
  `LAB_AI_GATEWAY_URL` and `OPENAI_BASE_URL` in a workspace point at the front door. Nothing
  else (Superset, Airflow, Trino, the hub) calls the gateway. `ai-keys` uses the admin API on
  `ai`.
- **The front door's `ROUTES` is the single source of truth for what a user key may call:**
  - `POST /v1/chat/completions`, `POST /chat/completions`;
  - `POST /v1/messages` and `POST /v1/messages/count_tokens` (only query `beta=true`);
  - `POST /v1/embeddings`, `GET /v1/models`;
  - `GET /v2/user/info` (no query: the key's own user; `lab-ai status` budget).

  Everything else gets 403 and never reaches the gateway: `/health*`, `/model/info`,
  `/v1/model/info`, `/key/*`, `/user/*`, `/spend/*`, `/global/*`, `/config*`, the admin UI and
  every other LiteLLM route. The match is exact and case-sensitive. Paths may contain only
  `[A-Za-z0-9/_.-]` (so no %-encoding and no absolute-form) and no empty, `.` or `..` segment.
  The front door also requires `Authorization: Bearer sk-…`, and takes POST bodies only with
  one `Content-Length` (no chunked), ≤ `LAB_AI_FRONTDOOR_MAX_BODY` (16 MiB), as JSON. It
  forwards only the request headers `Authorization`, `Content-Type`, `Accept`, `User-Agent`,
  `anthropic-version` and `anthropic-beta`, and returns only `Content-Type`, `Cache-Control`
  and `Retry-After` (never `x-litellm-*`, which names the provider's `api_base`). Responses
  are streamed. A new client route must be added there, with a test.
- **End-user attribution:** the gateway's `lab_hooks` pre-call hook overwrites the body's
  `user` and the request's end-user id with the key's own `user_id`. So spend logs name the
  key's owner, whatever the caller sent.
- **Personas:** a workspace offers only the personas in
  `lakehouse/ai_persona_manager.py` `ALLOWED_PERSONAS` (today: the Lab Assistant).
  `LabPersonaManager` is installed as `PersonaManagerExtension.persona_manager_class`; it
  loads no other entry point and no `.jupyter/personas` files. So there are no
  `jupyter_ai_acp_client` agents (claude/codex/copilot/goose/kilo/kiro/mistral-vibe/opencode:
  their own providers) and no stock Jupyternaut (free model string and API base). Claude Code
  in the lab is only the `lab-ai install-claude-code` CLI, pointed at the front door.
- **Known gap: the host LAN.** `lab` is not an internal network (workspaces need internet,
  e.g. pip), so a workspace can open any address the Docker host can route to, including a
  model server listening on the host's LAN IP (llama-server on `:9999` on the dev host).
  That bypasses the gateway's keys, budgets and logs. The lab cannot close this from
  compose without taking egress away from workspaces. The owner's options, simplest first:
  1. **Give the model server its own API key**, known only to the gateway
     (`llama-server --api-key …`, then `LAB_AI_LOCAL_API_KEY` in `.secrets.env`). A workspace
     that reaches the port then gets 401 for every model call.
  2. **Host firewall, model server on the Docker host.** A container's packets to any
     address of the host itself (its LAN IP or a bridge gateway) go through the host's
     `INPUT` chain, not `DOCKER-USER`. So drop them there for the `lab` bridge only:
     `iptables -I INPUT -i br-<lab-network-id> -p tcp --dport 9999 -j DROP`. The `ai` bridge
     (the gateway) keeps access. `docker network inspect <project>_lab` gives the id; the
     bridge is `br-` plus its first 12 characters.
  3. **Host firewall, model server on another LAN machine.** Forwarded traffic passes
     `DOCKER-USER`:
     `iptables -I DOCKER-USER -i br-<lab-network-id> -d <server-ip> -p tcp --dport 9999 -j DROP`.
  4. **Bind the model server away from the LAN** (e.g. to `127.0.0.1`). This keeps other LAN
     machines out, but on the Docker host it also keeps the gateway out: containers reach
     the host only through a bridge address. So it is a fit only when the lab does not use
     that server.

  Tracked as `WATCH_V3_WORKSPACE_LAN_EGRESS_BYPASSES_GATEWAY`. No test probes the owner's
  model server.

---

# Phase 6: Migration guide, AI polish, cutover and beta release prep

> Added by the lead after Phase 5 (verified; real-model check passed twice, including with
> the gateway-held API key). Owner decisions, 2026-09-27:
> - No supported migration tool, just a **guide**. The owner copies MinIO files to the new
>   storage and starts fresh.
> - **Local-model quiet hours** go into the gateway.
> - Release by **merging to main as `v3.0.0-beta.1`**. The lead does the merge and tags
>   after showing the owner the finished cutover. **Agents never merge, tag, publish or
>   push.**

## ⚠ Quiet hours still apply

No inference on the owner's llama-server (:9999) by agents at any time. Use the MOCK model.
`v3-p1` is mock-only.

## Scope

1. **MIGRATION guide** (rewrite `docs/v3/MIGRATION.md`; a short user-facing version goes in
   the new README):
   - Copy the V2 MinIO buckets into V3 with `rclone` (or `mc mirror`), into a clearly named
     V3 location, then load what you want as Iceberg tables following E1's approach.
   - Optional notes: exporting and restoring Postgres, copying notebooks and DAGs (the
     Airflow 2 → 3 changes to check), exporting and importing Superset dashboards.
   - **Test the commands** on the dev host against a **throwaway MinIO container with
     synthetic data** (project `v3-p6-*`), copying into a throwaway V3 install. **Never
     touch the production `lakehouse-lab` project or its volumes.**
   - Record the commands exactly as run.
   - Remove the migration tool and nightly migration test from ROADMAP/ARCHITECTURE.
2. **AI polish** (gateway and workspace):
   - (a) **Quiet hours for the local provider:** `./lab ai quiet-hours HH:MM-HH:MM --tz
     Area/City` or `off`. Off by default for new installs; the installer asks when a local
     URL is set. During quiet hours, requests that would go to the `local` provider
     (directly or through `lab-default`) are refused **before routing**, with a friendly
     message ("The lab's local AI model is resting until 07:00 America/New_York…").
     Hosted providers, if an admin enabled them, are not affected. Unit tests use an
     injected clock, covering windows across midnight and DST days.
   - (b) **The Lab Assistant's system prompt carries the current date, time and time zone**
     (the model called today "yesterday").
   - (c) **Keep the model's planning text out of the final answer shown to beginners.**
     Either strip leading "The user is asking… / Let me…" narration, or show intermediate
     tool-use narration in a collapsed or secondary style. Keep the final answer intact.
     Test it with the mock scripted to produce narration.
3. **Cutover** (on branch `v3`, ready to merge):
   - V2 moves to `legacy/v2/`: the old compose, scripts, templates, docs, tests and V2
     workflows. V2 CI workflows are removed or disabled so they don't fail on moved files.
   - V3 **stays in `v3/`**, with no mass path moves.
   - The root README is rewritten for V3: what it is, the quick start (clone +
     `v3/install.sh`), profiles, links to docs and tracks, the AI policy (hosted off by
     default, local via any OpenAI-compatible server, quiet hours), and a short "coming
     from V2?" pointer to the migration guide.
   - The root `install.sh` becomes a thin bootstrap for the one-line install: fetch the repo
     at a given ref (default `main`), then run `v3/install.sh "$@"`. It must be safe when
     piped to bash, and show what it will do before doing it.
   - `docs/`: V3 docs become the main docs; V2 docs move to `legacy/v2/docs/`.
   - CHANGELOG entry for `v3.0.0-beta.1`. CONTRIBUTING updated for V3 (tests, contracts,
     memory graph).
   - `v3-nightly` works on `main` after the merge.
4. **Release prep (not the release):**
   - Draft release notes in `v3/RELEASE_NOTES_v3.0.0-beta.1.md`: highlights, known gaps,
     beta caveats, how to report issues.
   - A pre-merge checklist the lead runs: tag the old main as `v2.1.1-final`, merge, tag
     `v3.0.0-beta.1`, GitHub pre-release, the image publish that `v3-images` does on the
     tag, and a post-merge smoke check.

## Exit

- The migration commands are proven on synthetic data.
- Quiet hours: unit-tested, plus on the dev host with the mock provider standing in for
  local.
- The date is in the prompt, and the narration handling is tested.
- The cutover tree passes all lint and unit tests and `v3-ci` locally (actionlint,
  compose-check).
- Upgrade in place of `v3-p1` still passes all 18 smoke checks.
- A clean install from the new root bootstrap (pointed at the working tree or branch
  `v3`) passes.
- Docker safety holds; non-v3 objects are unchanged.

## Workstreams

| Workstream | Owns |
|---|---|
| **MIGRATION** | `docs/v3/MIGRATION.md`, test fixtures under `v3/tests/migration/` |
| **AI-POLISH** | `config/ai/`, `installer/ai.sh`, `lab` (ai subcommands), `images/workspace/lakehouse/ai*.py` |
| **CUTOVER** | repo root files, `legacy/`, `docs/`, V2 workflows, `v3/RELEASE_NOTES_*`, CHANGELOG, CONTRIBUTING |

The integrator owns `compose.yaml`, `versions.env`, `bootstrap/__main__.py` and this
contract.

## Conventions added at Phase 6 integration

- **Layout after the cutover:** V3 stays in `v3/`. V2 lives in `legacy/v2/` (inert; its
  workflows in `legacy/v2/workflows/` do not run). The design docs and the migration guide
  are in `docs/` (`docs/MIGRATION.md`; `docs/v3/` is gone). The root `install.sh` is only a
  bootstrap (clone/update at `--ref`, then `exec v3/install.sh`); root-level checks are
  `tests/bootstrap/`, `tests/shellcheck.sh`, `tests/docs/check-links.sh` and
  `.github/workflows/repo-checks.yml`. `check_versions.py` still scans only `v3/`.
- **Pins:** `RCLONE_IMAGE_*` (the guide and `tests/migration`) and
  `MIGRATION_TEST_MINIO_IMAGE_*` (the throwaway V2 in `tests/migration` only) are in
  `versions.env`. `v3/.pins/` is gone again.
- **Quiet hours:** `.env` `LAB_AI_QUIET_HOURS` / `LAB_AI_QUIET_TZ` (empty = off) reach only
  `ai-gateway` (`compose/ai.yaml`); `lab_settings` unsets both from the caller's shell like the
  other `LAB_AI_*` switches. The gateway refuses `local` (and `lab-default` when it resolves to
  local) before routing with HTTP 503 `ai_quiet_hours` + `Retry-After`. `install.sh` asks once,
  interactively on `full`, only when a local URL is set.
- **`tests/ai/quiet-hours-e2e.sh`** is opt-in exactly like `gateway-e2e.sh` step 3
  (`LAB_E2E_LOCAL_VIA_MOCK=1`, providers exactly `[mock]`). The nightly (a CI runner, no real
  model server) sets the switch for both scripts; on the dev host it is set only on a
  throwaway `v3-p6*` project, never on `v3-p1`.
- **Mock model:** a scripted tool step may carry `content` (narration sent with the tool
  calls) and any step `reasoning` (sent as `reasoning_content`); `plan()` is unchanged.
