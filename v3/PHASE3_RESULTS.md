# V3 Phase 3 Results (orchestration, BI, Console, external login)

> Integration report for Phase 3, built against the "Phase 3" section of `v3/CONTRACT.md`.
> Three workstreams (AIRFLOW, BI+CONSOLE, IDP+TESTS+CI) built in parallel. The integrator then:
> - merged their pins and wiring;
> - fixed what integration exposed;
> - upgraded the running Phase 2 install in place, first on `engineer`, then on `full`;
> - ran a clean-room `full` install;
> - tore down every test project.
>
> Host names, IPs and domains of the dev host are left out on purpose.

## Repair round (after the independent verification)

The verifier found two problems; both are fixed.

1. **`v3-images.yml` could not build `superset`.** The workflow took build contexts from the compose JSON of the default profile `core`. Superset is profile `full`, so `images_matrix.py` gave it no `config` context and its `COPY --from=config` would fail in buildx on the first push to `v3`.
   - Fix: the step now runs `v3/tools/compose-check.sh --profile full --json-out "$RUNNER_TEMP/compose.json"` (every built service is in `full`).
   - Hardening: `images_matrix.py` now fails when a Dockerfile's `COPY --from=<name>` names neither a build stage, a build context nor an image reference. With the `core` JSON it returns rc 1 and names `superset`; with the `full` JSON, `superset` gets `config=v3/config/superset` and `workspace` gets `starter=v3/starter`. Four new tests in `v3/tests/lint/test_images_matrix.py`, one of them over the real Dockerfiles. `actionlint` passes. Recorded as `REG_V3_IMAGES_MATRIX_PROFILE_DROPS_BUILD_CONTEXT`.
2. **Default limits for `engineer` + one workspace (17.19 GiB) broke the Phase 2 "16 GB machine" budget.** Proposed by the repair round and **confirmed by the lead (2026-09-26)**: the budget is amended in `CONTRACT.md` to be measured on use. See "Memory budget decision" under Memory.

Reruns on the dev host after the fixes (runtime files unchanged; only `CONTRACT.md`, `tools/images_matrix.py` and its test differ from the verified tree):

| Run | Result |
|---|---|
| Upgrade path: `v3-p1` (`full`), `./install.sh --non-interactive` | rc 0, 27 s (no container changed) |
| `v3-p1`: `LAB_SMOKE_LONG=1 ./lab test` | **SMOKE: PASS (16/16; profile full)**, about 12 min. Check 13: token lifespan 120 s, run 313 s, commit 307 s after start. |
| Clean room: project `v3-p3r`, ports 18543/18180, `--domain sslip --profile full --seed-test-users` | `install.sh` rc 0, **412 s** (images cached) |
| `v3-p3r`: `LAB_SMOKE_LONG=1 ./lab test` | **SMOKE: PASS (16/16; profile full)**, 814 s. Check 13: token lifespan 120 s, run 313.9 s, commit 309 s after start. |
| `v3-p3r`: `lab reset --yes` | rc 0; 0 containers, 0 volumes, 0 networks; directory deleted |
| Non-v3 Docker objects before vs after | **identical** (11 containers, 22 volumes, 4 networks) |

## Exit criteria

| Criterion | Result |
|---|---|
| 1. Airflow (engineer): one Keycloak login; lab-admin Admin, engineer trigger/edit, analyst/viewer read-only | **Met.** Smoke check 12: alice lists DAGs (200) and creates a pool (201); victor lists (200) but trigger and unpause are 403; eddie edits a DAG (PATCH 200). AIRFLOW's per-user matrix also covered anna (all writes 403). |
| — `lab_ingest`, `lab_dbt_build`, `lab_notebook`, `lab_spark_batch` succeed | **Met** in every engineer and full run. Typical: ingest 10–26 s, dbt 40–51 s (dbt `PASS=27`), notebook 10 s, spark batch 50 s. |
| — **ADR-017 proof:** lab-batch token lifespan cut to 120 s; a >= 300 s Spark job completes and commits | **Met four times** (smoke check 13). See "ADR-017 proof". |
| 2. Superset (full): one Keycloak login; Admin / Gamma+SQL Lab / Gamma | **Met.** Check 14: alice `[Admin, Public]`, victor `[Gamma, Public, lab_data]` (no `sql_lab`). BI's probe: eddie and anna `[Gamma, Public, lab_data, sql_lab]`. |
| — queries run in Trino as the logged-in user | **Met.** Check 14: SQL Lab `SELECT current_user` returns `alice`. See "Superset as the user". |
| — bundled "Revenue by region" dashboard renders (chart-data API returns rows) | **Met.** All 4 charts return rows through their saved query context: 5 / 1 / 35 / 5. |
| 3. Console shows only reachable tiles plus health; Spark UI engineer/lab-admin 200, viewer 403 | **Met.** Check 15 on full: alice 8 tiles, victor 5 (no Airflow, Spark UI, Keycloak admin). The health list shows every service of the profile. Spark UI: alice 200, victor 403. |
| 4. GitHub login (optional): off by default; first login gets no group; access follows a group change; no email auto-link; mock provider in CI | **Met.** Check 16 (see "OQ-18 / ADR-016"). |
| 5. Upgrade in place from Phase 2; smoke on `core`, `engineer`, `full` | **Met on the dev host for `engineer` and `full`** (upgrade and clean room). `core` smoke runs in the PR matrix; locally it is covered by compose-check and the IDP workstream's core run (see Known gaps). |
| — PR CI matrix (`core`, `engineer`) green | **Not yet run on GitHub**: nothing is committed or pushed by this integration. `actionlint` passes. |
| — nightly/dispatch `full` job, ingest → dbt → dashboard | **Wired** (`v3-nightly.yml`), not yet run on GitHub. The same chain is green on the dev host (checks 12 → 14). |
| 6. Docker-safety invariants and smoke check 11; non-v3 objects unchanged | **Met.** Check 11 passes 14/14 in every run. The before/after audit of non-v3 objects is identical (see "Docker safety"). |

## What was built

**Airflow** (AIRFLOW: `compose/airflow.yaml`, `images/airflow/`, `config/airflow/`, `dags/`, `bootstrap/{airflow,batch}_client.py`)
- Airflow 3.3.2, LocalExecutor, with metadata in the shared Postgres. The `airflow-db` one-shot creates the role and database idempotently, also on existing installs.
- Services: `airflow-api`, `airflow-scheduler` (runs the tasks), `airflow-dag-processor`, `airflow-triggerer`, plus the one-shots `airflow-db` and `airflow-init`.
- The Keycloak client `airflow` and its UMA authorization model are built declaratively by bootstrap (OQ-16). Connections, Variables and Config are readable only by User, Op and Admin.
- The batch identity `lab-batch` uses client credentials only. Its tokens are for Trino and Lakekeeper, and their lifespan is `LAB_BATCH_TOKEN_LIFESPAN` (default 300 s).
- Four DAGs, all running as lab-batch and recording who triggered them. Tasks run in a separate `/opt/lab/jobs` venv.
- The Spark batch job gets the lab-batch **credential**, not a token, so Iceberg renews tokens itself (ADR-017). Stopping a task interrupts the Spark job.

**Superset and Console** (BI+CONSOLE: `compose/{superset,console}.yaml`, `images/superset/`, `config/{superset,console}/`, `bootstrap/superset_client.py`, Caddyfile, rules.json impersonation)
- Superset 6.1.0 (profile `full`): image pinned by digest with a generated lock, no runtime installs, config baked into the image.
- Login is FAB OAuth against the Keycloak client `superset`. Metadata lives in database `superset`, created by the `superset-db` one-shot.
- Queries go to Trino as the user: the service account `service-account-superset` impersonates the Superset username.
- The bundled dashboard (3 datasets, 4 charts) is imported only when missing, by UUID, so UI edits survive restarts.
- Lab Console v1 (every profile): oauth2-proxy (client `console`) behind Caddy `forward_auth`, a static page, and `console-health`.
- The Spark UI is at `spark.`, behind the same forward-auth with `allowed_groups=engineer,lab-admin`. The worker and application UIs are proxied through the master (`spark.ui.reverseProxy`).

**IdP, tests, CI** (IDP+TESTS+CI: `bootstrap/github_idp.py`, installer/`lab`, `tests/smoke/phase3.py`, workflows)
- ADR-016: the first-broker-login flow `lab-first-broker-login` is always ensured. The `github` IdP exists only when both GitHub values are set.
- Installer: `--profile full`, `--github-client-id/--github-client-secret/--no-github`, per-profile RAM warnings, `lab urls` for the new sites, and `lab test --long`.
- Smoke checks 12–16. Check 13 runs only with `LAB_SMOKE_LONG=1`.
- CI: `v3-ci.yml` keeps the core/engineer matrix and adds `compose-check --profile full` plus memory sampling. The new `v3-nightly.yml` runs `full` with the long check, then reinstall and check-reset.

## Integration changes

- **Pins** merged into `versions.env`: `AIRFLOW_IMAGE_DIGEST`, `PAPERMILL_VERSION`, `SUPERSET_IMAGE_DIGEST`, `OAUTH2_PROXY_IMAGE_TAG/_DIGEST`. `v3/.pins/` was removed.
- **`compose.yaml`:**
  - includes `compose/airflow.yaml`, `compose/console.yaml` and `compose/superset.yaml`;
  - declares the volume `airflow-data`.
- **Profiles:** `full` = engineer + Superset. Compose has no profile inheritance, so the Spark and Airflow services list `profiles: [engineer, full]` (BI's note 8). The installer passes one `--profile` as before.
- **`bootstrap/__main__.py`:**
  - ensures, in every profile: `airflow` (+ UMA model; password grant only with seeded test users), `lab-batch`, `superset`, `console` (repair), and ADR-016's flow plus the optional `github` IdP;
  - after the Lakekeeper sync, ensures namespace `analytics` and lab-batch's grants on it.
- **`identity-sync`** also re-ensures `analytics` and lab-batch's grants on every tick, quietly (`batch_client.ensure_lakekeeper(..., quiet=True)`, with a new unit test). A dropped `analytics` namespace comes back with its grants within one interval.
- **`compose/bootstrap.yaml`:** passes `OIDC_CLIENT_SECRET_{AIRFLOW,BATCH,SUPERSET,CONSOLE}`, `LAB_BATCH_TOKEN_LIFESPAN` and the optional `OIDC_CLIENT_ID_GITHUB`/`OIDC_CLIENT_SECRET_GITHUB`.
- **Caddy:** sites `console.` (forward-auth), `spark.`, `airflow.`, `superset.`; network aliases for `airflow.`, `superset.` and `spark.`.
- **Trino `rules.json`:** added rules for `service-account-lab-batch`, placed before the group rules:
  - catalogs: `lakehouse` all, `system` read-only;
  - it owns only the schema `lakehouse.analytics`;
  - tables: DML in `analytics`, SELECT+GRANT_SELECT in `samples`, SELECT in `system`, nothing else;
  - `execute`, and session properties.

  BI's `service-account-superset` rules (metadata only) and the `impersonation` section were already in place. The shared `analytics` rule of the contract holds: everyone reads it; only lab-batch, engineer and lab-admin write it (in Trino, and in Lakekeeper through OpenFGA grants).
- **Secrets:** nine new generated keys:
  - `OIDC_CLIENT_SECRET_AIRFLOW`, `OIDC_CLIENT_SECRET_BATCH`, `AIRFLOW_DB_PASSWORD`, `AIRFLOW_FERNET_KEY` (new `fernet` generator: URL-safe base64), `AIRFLOW_JWT_SECRET`;
  - `OIDC_CLIENT_SECRET_SUPERSET`, `SUPERSET_SECRET_KEY`, `SUPERSET_DB_PASSWORD`, `CONSOLE_COOKIE_SECRET` (32 chars).

  They are in `installer/secrets.sh`, the `compose-check.sh` fallback, `tests/smoke/dev-env.sh`, the installer unit test's contract list (with format checks for the Fernet and cookie keys) and the CONTRACT secrets table. The GitHub pair is documented there as optional and is never generated.
- **Spark:** `spark.ui.reverseProxy true` in `spark-defaults.conf`.
- **Anonymous volumes:** `airflow-db` got `tmpfs: /var/lib/postgresql/data`, like `superset-db`, so the one-shot no longer leaves an anonymous volume on each run.
- **Postgres limit 512m → 768m** (`POSTGRES_MEM`). It now also serves Airflow and Superset: about 60 connections and **399 MiB of 512 MiB** in use at idle on `full`, of which 340 MiB is backend (anon) memory. That was too close to an OOM kill of the database every service depends on.
- **CI:** Airflow memory overrides in `v3-ci.yml` and `v3-nightly.yml`: api 768m, scheduler 1g, dag-processor 384m, triggerer 384m. `v3/config/superset/**` was added to the `v3-images.yml` path filters (the Superset image bakes that directory).

### Bugs found by integration (fixed)

1. **Smoke check 12 never logged in to Airflow** (`REG_V3_SMOKE_AIRFLOW_SPA_LOGIN`).
   - Every API call returned 401. The helper opened `airflow./` and returned at once. Airflow 3's `/` is a SPA that redirects to the login only client-side, after the helper had already returned.
   - Fix: `Airflow.login()` starts at `/auth/login`. Re-run: check 12 PASS.
2. **Smoke check 14 SQL Lab returned 400** `{"json": ["Unknown field."]}`.
   - Superset 6.1's execute schema no longer has the `json` field.
   - Fix: the payload now matches BI's proven recipe (`catalog`, `schema`, no `json`). Re-run: PASS, `current_user = alice`.
3. **Postgres headroom** (above): found by measuring the upgraded `full` stack, not by a failure.
4. **An upgrade that recreates Postgres broke its clients** (`REG_V3_POSTGRES_RECREATE_BREAKS_DB_CLIENTS_ON_UPGRADE`).
   - Found by fix 3: `install.sh` recreated `postgres` for the new limit while keycloak, openfga, lakekeeper, Airflow and Superset kept running with dead connection pools.
   - Bootstrap then failed: `GET /management/v1/info -> HTTP 500 DatabaseError` from Lakekeeper, and `up --wait` reported "the stack did not become healthy".
   - The Airflow scheduler, dag-processor and triggerer crash-restarted after `up` had returned.
   - The same would happen on any future Postgres version bump.
   - **Fix:** every long-running Postgres client declares `depends_on: postgres: {condition: service_healthy, restart: true}` (`compose/identity.yaml`, `catalog.yaml`, `airflow.yaml`, `superset.yaml`). Compose then restarts them after recreating Postgres, and `--wait` waits for them. `depends_on` is not part of compose's config hash, so adding it recreated nothing.
   - **Verified** by forcing a recreate (`POSTGRES_MEM=800m ./install.sh`): postgres Recreated; keycloak, openfga, lakekeeper, airflow-* and superset were stopped and started by compose; rc 0; bootstrap `done`.
5. **Trino's catalog session never recovered from a Keycloak/Lakekeeper restart** (`REG_V3_TRINO_CATALOG_SESSION_DIES_ON_KEYCLOAK_RESTART`).
   - Found by fix 4. The next install (back to 768m) restarted Keycloak and Lakekeeper, but not Trino. Trino's Iceberg REST auth session then looped on `Unable to parse error response` / `404 undefined_endpoint`.
   - Every catalog call failed with `ICEBERG_CATALOG_ERROR: Failed to list namespaces`, so `samples` failed `up --wait`. A manual `samples` re-run a minute later failed the same way, so it does not heal by itself.
   - **Fix:** `trino` depends on `keycloak`, `lakekeeper` **and `postgres`** with `restart: true` (`compose/engines.yaml`).
     - The first attempt listed only keycloak and lakekeeper. The repeated forced-recreate test showed that `restart: true` is **not transitive**: compose restarted postgres's direct dependents but not Trino (samples passed that time only by timing). Hence the direct `postgres` entry, although Trino never talks to Postgres.
   - **The same failure class hit Spark.**
     - The next smoke run (after that upgrade had restarted Keycloak) failed `lab_spark_batch` even for its 30 s default job. The executors signed with an **expired** lab-batch token (Lakekeeper: `AuthenticationFailed ... ExpiredSignature` on `/catalog/v1/signer`).
     - Iceberg's auth session in the long-lived Connect executors had stopped refreshing after a refresh failed while Keycloak was down.
     - Fix: `spark-worker` and `spark-connect` depend on keycloak, lakekeeper and postgres with `restart: true` too (`compose/spark.yaml`).
   - The broken install was recovered once by restarting the trino and Spark containers. The forced-recreate test was then repeated with the final compose (see "Final state").
   - **Residual risk:** an *unplanned* Keycloak outage that compose does not manage (a crash or host restart ordering) still leaves Trino's catalog session and running batch Spark sessions broken until those services restart. Tracked in the graph; a proper fix needs Iceberg's AuthSession to retry refreshes (or a lab-side watchdog).

## Upgrade in place (how users get Phase 3)

The running Phase 2 install (`v3-p1`, `engineer`, ports 18443/18080) was synced with the new `v3/`, leaving out `.env`, `.secrets.env`, `state/` and `out/`.

| Step | Result |
|---|---|
| `./install.sh --non-interactive` (stays `engineer`) | rc 0, **5 min 9 s**, including the first build of the Airflow image. Nine secrets were appended to `.secrets.env`. Compose recreated caddy, trino, spark-* and the bootstrap-image services (config hash or new image), and created the Airflow services, oauth2-proxy and console-health. Bootstrap created `airflow` (+ UMA), `lab-batch`, `superset`, the broker flow and namespace `analytics` with lab-batch's grants, and repaired `console` (PKCE). CA root cert and key: unchanged sha256. |
| `./lab test` (engineer) | First run: 13/14 (check 12 bug 1). After the fix: **SMOKE: PASS (14/14; 2 skipped: 13 long-only, 14 full-only)** in 5 min 56 s |
| Re-run `install.sh` | rc 0, **28 s**, all 19 running container IDs identical, bootstrap `users: unchanged` / `lab-batch: unchanged` |
| `./install.sh --non-interactive --profile full` | rc 0, **6 min 29 s** (includes the cold Superset build). "Profile changed (engineer -> full): stopping the running lab first; data is kept". 29 containers, all healthy. Superset `lab_init` created 3 datasets, 4 charts and the dashboard. |
| `LAB_SMOKE_LONG=1 ./lab test` (full) | First run: 15/16 (check 14 bug 2; **check 13 already passed**). After the fix: **SMOKE: PASS (16/16; profile full)** in 12 min 8 s |
| Re-run `install.sh` on `full` | rc 0, **28.5 s**, all 20 running container IDs identical |
| Final tree: forced Postgres recreate (`POSTGRES_MEM=800m ./install.sh`), then a normal `install.sh` back to 768m | rc 0 / rc 0, **308 s / 310 s**. Each time compose stopped and started keycloak, openfga, lakekeeper, trino, spark-worker, spark-connect, airflow-* and superset around the recreated postgres; samples and bootstrap passed. An install that does not touch postgres stays at about 28 s. |
| Final tree `LAB_SMOKE_LONG=1 ./lab test` (full) | **SMOKE: PASS (16/16; profile full)** in 13 min 54 s |

Volumes were kept throughout; no step ran `down -v`. `v3-p1` is left running on `full`.

## Clean room (dev host)

New directory, project `v3-p3`, sslip domain, ports 18543/18180, `--seed-test-users --profile full`:

| Step | Wall clock |
|---|---|
| `install.sh` (checks, config, secrets, CA, build, `up --wait` to healthy) | **418 s** (7 min) |
| `LAB_SMOKE_LONG=1 lab test` | **12 min 9 s**, **SMOKE: PASS (16/16; profile full)**. The first run, with the pre-fix check 14, was 15/16. |
| **Total, fresh install to green `full` smoke including the >= 5 min ADR-017 run** | **about 19 min** |
| `lab reset --yes` | 0 containers, 0 volumes (including the 2 home volumes) and 0 networks left for `v3-p3` |

- **Caveats on these timings:**
  - Images were cached: the upgrade had just built them, and local tags are shared across projects.
  - The install ran at the same time as a `full` smoke run on `v3-p1`.
  - The smoke's fixed cost is 5 min for check 13 alone.
- BI measured a cold Superset build at 5 min 35 s for a whole clean install.

## ADR-017 proof (check 13)

The check:
- sets `lab-batch`'s `access.token.lifespan` to **120 s** through the Keycloak admin API;
- runs `lab_spark_batch` with `min_runtime_s=300` into `lakehouse.analytics.smoke_batch_longrun`;
- requires success, a run of at least 300 s, and the last Iceberg commit more than 120 s after the start;
- then restores the lifespan and drops the table.

| Run | Run length | Last commit after start | Token lifetimes outlived |
|---|---|---|---|
| upgraded `v3-p1` (full), run 1 | 312.7 s | 308.0 s | 2.6 |
| upgraded `v3-p1` (full), run 2 | 312.0 s | 307.0 s | 2.6 |
| upgraded `v3-p1` (full), final tree | 313.0 s | 307.9 s | 2.6 |
| clean room `v3-p3` | 311.4 s | 307.2 s | 2.6 |

- **AIRFLOW's negative control:** the same job with a fixed token fails at writer close with `NotAuthorizedException: Authentication failed`, and no snapshot is written. That shows the renewal is what makes it work.
- **The mechanism:**
  - the batch Spark session gets the lab-batch client **credential** (`token-refresh-enabled=true`, `token-exchange-enabled=false`), so Iceberg renews tokens itself;
  - dbt and the notebook are short jobs and get one freshly fetched token each.

## Superset as the user

- **Mechanism:**
  - Superset authenticates to Trino as `service-account-superset` (client credentials, `scope=openid`) and sets `X-Trino-User` to the Superset username.
  - `DB_CONNECTION_MUTATOR` forces this on every engine that points at the lab's Trino.
  - Trino's `impersonation` rules let only that principal impersonate, and never as a `service-account-*` name.
- **Evidence:**
  - Check 14: SQL Lab `SELECT current_user` returns **alice**.
  - victor has no `sql_lab` (SQL Lab 403) and cannot edit the dashboard (403).
  - BI's probe: `current_user` was alice, eddie and anna for each of them. In `system.runtime.queries` the chart queries appear under each person's own name (alice 6, anna 6, eddie 6, victor 4).
  - With the Superset service token and `X-Trino-User=victor`, an INSERT is denied by Trino.
  - anna's token cannot impersonate victor.
  - The service account alone cannot read `analytics` tables.
- **Limit:** Trino impersonation rules cannot test the target user's groups. So the rule allows any non-service-account name, and the group rules then give a no-group name no access (verified with `nobody` → "Cannot execute query").

## OQ-16 and OQ-18 outcomes

- **OQ-16 (Airflow UMA: scripted step or realm export):** **scripted bootstrap step, done declaratively** (`bootstrap/airflow_client.py`, DEC_V3_AIRFLOW_UMA_MODEL_IN_BOOTSTRAP).
  - It mirrors provider 0.10.0's non-team `create-all`, but is idempotent, repairs drift and never gives an Airflow container the Keycloak master admin password.
  - The upgrade created the model in one run; every later run reported `unchanged`.
  - The provider CLI was rejected because it cannot run twice.
- **OQ-18 (limit GitHub logins to an org/team):** **not needed for now; "no group until an admin approves" is implemented and proven.** Check 16, against the `github-mock` realm using bootstrap's flow:
  - A newcomer is created with **no group**. Trino refuses them ("Cannot execute query") and JupyterHub returns 403.
  - After an admin adds `engineer` in Keycloak, Trino allows them within **16.7–33.1 s** (budget 135 s) and JupyterHub opens `/hub/home`.
  - An external account showing **alice's e-mail** gets the link page, then alice's password prompt; nothing is linked and no user is created.
  - The flow has no `idp-auto-link` and no e-mail-verification branch.

  An org check stays optional, for when classroom self-service needs it.

## Memory

**Limits** (from `docker compose config`, long-running services; one-shots exit before workspaces start):

| Profile | Long-running | + one workspace (1.5 GiB) | One-shots | Target |
|---|---|---|---|---|
| `core` | 7.69 GiB | **9.19 GiB (9.9 GB)** | 0.88 GiB | ≤ 10 GB: met |
| `engineer` | 15.69 GiB | **17.19 GiB** | 1.75 GiB | 16 GB machine (Phase 2, **amended**: measured peak use ≤ 8 GiB): met on use (peak 6.25 GiB measured on `full` by the independent verifier); above 16 GB on limits, see "Memory budget decision" |
| `full` | 16.69 GiB | **18.19 GiB** | 1.81 GiB | ≤ 24 GB (Phase 3): met |
| `engineer`, CI overrides | 13.94 GiB | 15.44 GiB | | |
| `full`, CI overrides | 14.94 GiB | 16.44 GiB | | above the runner's physical RAM on limits |

**Memory budget decision (proposed in the repair round, confirmed by the lead 2026-09-26).** The Phase 2 budget "`engineer` + one workspace fits a 16 GB machine" was written before Airflow; Airflow adds 3.5 GiB of ceilings, so default limits total 17.19 GiB. `CONTRACT.md` (Phase 2, Budgets) is amended: for `engineer` the 16 GB budget is measured on **use** (whole-lab peak ≤ 8 GiB, half a 16 GB machine), not on the sum of limits; the CI runner keeps env overrides so `engineer` + one workspace is ≤ 16 GB of limits (15.44 GiB); `core` keeps ≤ 10 GB of limits. Defaults were **not** lowered: the CI values would give 16.44 GiB (still over), and airflow-triggerer peaked at 357 MiB, so the CI 384m would leave users almost no headroom. Recorded as `DEC_V3_ENGINEER_BUDGET_ON_MEASURED_USE`.

**Measured use.** Idle `docker stats` on `v3-p1` (`full`, after the smoke, workspaces stopped): **about 5.4 GiB** in total.

| Container | Use | Limit |
|---|---|---|
| trino | 1.11 GiB | 3 GiB |
| keycloak | 588 MiB | 1.25 GiB |
| spark-worker | 587 MiB | 2.5 GiB |
| spark-connect | 527 MiB | 1.5 GiB |
| superset | 493 MiB | 1 GiB |
| airflow-scheduler | 430 MiB | 1.5 GiB |
| postgres | 399 MiB | 512 MiB (now 768 MiB) |
| airflow-api | 324 MiB | 1 GiB |
| airflow-triggerer | 267 MiB | 512 MiB |
| spark-master | 197 MiB | 512 MiB |
| airflow-dag-processor | 172 MiB | 512 MiB |
| seaweedfs | 164 MiB | 1 GiB |
| jupyterhub | 132 MiB | 384 MiB |
| openfga, lakekeeper, caddy, docker-proxy, console-health, identity-sync, oauth2-proxy | 8–37 MiB each | |

**Does `full` fit a 16 GB runner?**
- **Yes on actual use; not on limits.**
- Measured idle is 5.4 GiB. Adding a workspace (0.45 GiB peak), Spark job growth (about 1.5), the Chromium smoke container (about 1), Airflow tasks (about 1) and Trino under load (about 0.5) gives an estimated peak of **about 10 GiB**. That leaves about 5 GiB of headroom on a 16 GB runner.
- Limits are ceilings that are never all reached at once. With the CI overrides they total 16.44 GiB including a workspace.
- **Measured during the smoke run.** `tests/smoke/mem-sample.sh` sampled every 10 s during the final `full` + long smoke run on the dev host (two workspaces, all four DAGs, the 5 min Spark batch job, Superset and the Chromium smoke container). The **peak for the whole lab at one instant was 5.5 GiB (5676 MiB)**; an earlier run peaked at 5794 MiB. **Correction (lead):** the independent verifier's own sampling during the long `full` smoke run measured **6.25 GiB (6401 MiB)** and 5.75 GiB idle right after, so 6.25 GiB is the figure of record. It is still within the ≤ 8 GiB budget.
  - Per-container peaks: trino 1111, airflow-scheduler 597, keycloak 559, spark-worker 559, smoke 517, spark-connect 514, superset 448, ws-alice 363, airflow-triggerer 357, airflow-api 301, postgres 293, airflow-dag-processor 276, ws-victor 266 MiB.
  - Workloads are tiny (tpch `tiny`), so a runner will see about the same.
  - The nightly job's summary will add runner numbers.
- Per the contract, `full` stays in the nightly job (not the PR matrix). If the nightly shows OOM kills, it becomes dev-host-only.

## Lint and checks (final tree)

| Check | Result |
|---|---|
| `python3 v3/tools/check_versions.py` | OK |
| `python3 v3/tools/check_compat.py` | OK (0 errors, 0 warnings) |
| `v3/tools/shellcheck.sh` (v0.11.0) | 43 files OK |
| `v3/tools/actionlint.sh` (1.7.12) | OK on `v3-ci.yml`, `v3-images.yml`, `v3-nightly.yml` |
| `v3/tools/compose-check.sh --profile core / engineer / full` | OK / OK / OK |
| `python3 -m unittest discover -s v3/tests/lint` | 68 tests OK (4 new `COPY --from` resolution tests, one over the real Dockerfiles) |
| `python3 -m unittest discover -s v3/tests/bootstrap` | 40 tests OK |
| `python3 -m unittest discover -s v3/tests/smoke -p 'test_*.py'` | 30 tests OK |
| `bash v3/tests/installer/run.sh` | shellcheck clean; **276** unit checks pass |
| `bash v3/tests/installer/test_e2e.sh` (local Docker) | 42 passed, 0 failed (isolation check included) |
| `v3/tools/compose-check.sh --profile full --json-out c.json && python3 v3/tools/images_matrix.py --compose-json c.json` (what `v3-images.yml` now runs) | 7 images; `superset` `build_contexts: config=v3/config/superset`, `workspace` `starter=v3/starter` |
| Same with the `core` JSON (the old workflow) | now **rc 1**: `COPY --from=config is neither a stage nor a build context` (was silently `''`) |

## Docker safety (the host runs production)

- The non-v3 containers (by ID, name, creation time), volumes and networks were recorded before any integration step and compared after teardown: **identical** (11 containers, 22 volumes, 4 networks).
- Only projects `v3-p1` and `v3-p3` were used by the integrator, on their assigned ports (18443/18080, 18543/18180). There was no `sudo` and no `prune`.
- The workstream projects (`v3-p3-airflow`, `v3-p3-bi`, `v3-p3-tests`) had already been reset by their owners; the audit found 0 containers, volumes or networks for them.

## Known gaps

- **GitHub CI has not run Phase 3.** Nothing was committed or pushed. The PR matrix and the nightly `full` job are validated only by actionlint and dev-host runs. Scheduled workflows run only from the default branch; until v3 is merged, use `gh workflow run v3-nightly.yml --ref v3`.
- **`core` smoke with the Phase 3 checks was not rerun on the dev host by the integrator.** On `core`, checks 12–14 skip by design, and 15 and 16 are exercised the same way as on engineer and full. IDP+TESTS ran core before integration, when check 15 failed only because oauth2-proxy was not yet included. The PR matrix covers `core`.
- **`engineer` + one workspace is 17.19 GiB of default limits**, over 16 GB; this is now within the amended budget (measured use, see "Memory budget decision"). The CI overrides bring limits to 15.44 GiB. Lower `AIRFLOW_*_MEM` limits remain the lever if a 16 GB host ever shows OOM kills.
- **Real GitHub login** remains a manual release check (ADR-016). CI and the smoke test use the mock realm.
- **Local image tags are still not project-scoped.** The clean room reused images the upgrade had built, so its timings are warm.
- **lab-batch and DAG authors:** engineers and lab admins who can edit DAG code can act as lab-batch. That is accepted, since they already write `analytics`.
- **Brokered-username collision:** a GitHub login named `service-account-lab-batch` would collide with that service account's username. The no-auto-link flow makes it fail as "user exists", but a username prefix for brokered users would be cleaner.
- **Docs outside `v3/`** (`docs/v3/OPEN_QUESTIONS.md` rows for OQ-16/OQ-18, and the ADR-016 "Open: OQ-18" line) still need the outcomes above. The integrator's edits were limited to `v3/` and the workflows.

## Follow-up: Spark UI isolation (in-lab bypass of the forward-auth)

**Problem (found by the independent verifier).** The Spark UI group check on `spark.<domain>` (engineer/lab-admin; viewer 403) could be bypassed from inside the lab. `spark-master` (8080), `spark-worker` (8081) and the Spark Connect application UI (4040) were on the flat `lab` network. Every workspace joins that network, viewer victor's included, so his notebook could open `http://spark-master:8080` directly.

**Design (built; CONTRACT Phase 3, "Networks").**
- New network `spark` (`internal: true`), declared in `compose.yaml`.
  - `spark-master` and `spark-worker` are **only** on `spark`.
  - `spark-connect` is on `lab` (gRPC 15002, used by workspaces and Airflow) and on `spark`.
  - Also on `spark`: `caddy` (to proxy the master UI) and the services the executors call by internal name: `keycloak` (token endpoint for the lab-batch credential flow), `lakekeeper` (catalog and S3 signer) and `seaweedfs` (S3). Executors use no public hostname, so `spark` needs no Caddy aliases.
  - Workspaces stay on `lab` only, and the Docker-proxy allowlist is unchanged (`<project>_lab`).
- **Connect driver bound to `spark` only** (the preferred option of the decision rule; no fallback was needed):
  - `start-spark.sh connect` runs the new `spark-bind-ip.py spark-master`. It takes the local address the kernel routes towards the master, which is only on `spark`, so that address is the container's `spark` IP. The script refuses 0.0.0.0 and 127.0.0.1.
  - The script then sets `spark.driver.bindAddress` and `SPARK_LOCAL_IP` (the host Spark's WebUI binds to) to that address.
  - `spark.driver.bindAddress 0.0.0.0` was removed from `spark-defaults.conf`.
  - Result: only gRPC 15002 listens on every interface. The driver RPC, the block manager and UI 4040 listen on the `spark` address alone.
- **The application UI is kept.** Engineers reach it through the master's reverse proxy at `https://spark.<domain>/proxy/<app-id>/`, behind the same forward-auth. This route is the only way to any Spark UI.
- `spark.ui.killEnabled false` is set in `spark-defaults.conf`, which the master, worker and driver all read. The master UI and the application's stages page show no kill links.
- `console-health` now probes Spark as `spark-connect:15002` (tcp) instead of `spark-master:8080`. It stays on `lab` only. Spark Connect is healthy only once the master has a registered worker.

**Bug found while deploying (fixed).**
- Symptom: every Spark write failed. The executors got `Connect to seaweedfs:8333 [seaweedfs/<spark IP>] failed: Connection refused`. This broke smoke 10 and `lab_spark_batch` in check 12.
- Cause: `weed server` binds all its ports to `-ip.bind`, which defaults to its auto-detected `-ip`. That is the address of one interface, here the `lab` one.
- Fix: `-ip.bind=0.0.0.0` in `config/seaweedfs/entrypoint.sh`. `-ip` stays as detected; it only names the in-container master, volume and filer to each other.
- Recorded as `REG_V3_SEAWEEDFS_BINDS_ONLY_DETECTED_IP`. Keycloak and Lakekeeper already listened on every interface.

**Smoke check 15, extended** (`tests/smoke/phase3.py`; new kernel step `internal_ports` in `kernel_probe.py`):
- **victor (viewer), from his own workspace kernel:** `http://spark-master:8080/`, `http://spark-worker:8081/` and `http://spark-connect:4040/` must fail to connect (no name, refused, timeout or no route). An HTTP answer of any status fails the check. `tcp://spark-connect:15002` must connect; it is the control that stops a network-less kernel from passing.
- **Browser:** eddie (engineer) gets 200 on `https://spark.<domain>/`. Through the master proxy he also gets the Spark Connect application UI: 200 and the Spark Jobs page. alice gets 200 and victor gets 403, as before.
- **New unit tests** in `test_smoke_unit.py`: the probe's outcomes against a closed port, an unknown name and a live HTTP server, and the pass rule (a UI that answers fails, and so does a control that is down).

**Evidence on `v3-p1` (profile `full`, upgraded in place with rsync + `./install.sh --non-interactive`; rc 0 both times, all services healthy):**
- **Networks:**
  - master: `spark` only.
  - worker: `spark` only.
  - spark-connect: `lab` and `spark`.
  - caddy, keycloak, lakekeeper, seaweedfs: `lab` and `spark`.
  - jupyterhub: `lab` and `hub-docker`.
  - `v3-p1_spark` is `Internal=true`.
- **Spark Connect's log:** `start-spark: driver and application UI bind to 172.21.0.8`, then `Start Jetty 172.21.0.8:4040 for SparkUI`. Its listeners (`/proc/net/tcp`) are `0.0.0.0:15002`, 172.21.0.8 on 4040 and the driver/block-manager ports, and the Docker DNS stub.
- **From a container on `lab`** (jupyterhub):
  - `spark-master:8080` and `spark-worker:8081`: no name.
  - `spark-connect:4040`: connection refused (lab IP).
  - The `spark` IPs of spark-connect (:4040) and the master (:8080), dialled directly: timeout (internal bridge, no route).
  - `spark-connect:15002`: connects.
- **`LAB_SMOKE_LONG=1 ./lab test`: `SMOKE: PASS (16/16; profile full)`.** Check 15's evidence:
  - victor's kernel: spark-master no-name, spark-worker no-name, spark-connect:4040 refused, spark-connect:15002 connected.
  - eddie: `/` gave 200, and `/proxy/app-…/jobs/` gave 200 "Spark Connect - Spark Jobs".
  - alice 200, victor 403.
- **Other checks:**
  - Check 10: Spark as alice passes.
  - Check 9: victor is denied through Spark.
  - Check 11: docker-proxy 14/14.
  - Check 12: all four DAGs succeed.
  - Check 13: `lab_spark_batch` ran 306 s with a 120 s token and committed 303.5 s after start.
- **The first smoke run** (before the SeaweedFS fix) failed 10 and 12 as described above. It was stopped (only its `v3-p1` smoke container) and rerun after the fix.
- **Lint and unit (final tree):**
  - `check_versions` OK; `shellcheck` OK (43 files).
  - `compose-check` OK for `core`, `engineer` and `full`.
  - Unit tests: lint 68, installer 276, bootstrap 40, smoke 32 (was 30), all OK.
- **Docker safety:** non-v3 objects before vs after are identical (11 containers, 22 volumes, 4 networks). Only 18443/18080 are published. No workspace containers are left.

**Known gaps / notes.**
- The driver RPC and block-manager ports, previously on `0.0.0.0` and so reachable from `lab`, now listen only on `spark`. That also closes a direct path from workspaces to the shared driver.
- SeaweedFS now listens on `spark` too, so its master (9333), volume and filer ports are reachable by Spark executors. They were already reachable from `lab`, and the filer and volume servers require the JWTs from `security.toml`. This adds no new principal: executors run user code, which could already reach them from a workspace.
- The `spark` network is also created on `core`, where caddy, keycloak, lakekeeper and seaweedfs join it with no Spark members. This is harmless, and it keeps one compose definition per service.
- The GitHub CI matrix has not run this change; nothing was committed or pushed.

## Final state

- **`v3-p1` runs the final tree on profile `full`:** 29 containers (20 running, all healthy; the rest are completed one-shots), and the last `LAB_SMOKE_LONG=1 ./lab test` gave 16/16.
  - Its volumes were kept throughout: postgres, seaweedfs, jupyterhub, trino-groups, caddy, trust, the new `airflow-data`, and the home volumes of alice and victor.
  - Published ports: 18443 and 18080 only.
- **`v3-p3r` (repair-round clean room)** was reset the same way (0 containers, volumes and networks; directory deleted).
- **`v3-p3` (clean room)** was reset: 0 containers, volumes and networks. Its directory was deleted. No `v3-p3-*` workstream project has any Docker object.
- **Non-v3 Docker objects before vs after: identical** (11 containers, 22 volumes, 4 networks).
- The workstreams' scratch directories (`~/lakehouse-v3/p3-airflow*`, `p3-tests*`) have no Docker objects. They are left for their owners, as in Phase 2.

## GitHub CI (commit 63b6edf)

- **`v3-ci`:** lint 25 s; **e2e (core) 7 m 06 s**; **e2e (engineer) 10 m 56 s**. Green.
- **`v3-nightly` on `full` with `LAB_SMOKE_LONG=1`:** **20 m 01 s**, green, on a standard
  GitHub runner. That answers "does `full` fit a 16 GB runner?": **yes**. Until V3 is on
  `main`, the nightly job also runs on `v3` whenever its workflow file changes, because
  scheduled and manual runs only fire from the default branch.
