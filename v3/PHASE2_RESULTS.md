# V3 Phase 2 Results (workspace and engines)

> Integration report for Phase 2, built against the "Phase 2" section of `v3/CONTRACT.md`.
> Three workstreams (WORKSPACE, SPARK+DATA, TESTS+CI) built in parallel. The integrator then:
> - merged their pins and wiring;
> - fixed what integration exposed;
> - upgraded the running Phase 1 install in place, first on `core`, then on `engineer`;
> - ran a clean-room install;
> - tore down every test project.
>
> Host names, IPs and domains of the dev host are left out on purpose.

## Exit criteria

| Criterion | Result |
|---|---|
| 1. Smoke test covers the workspace and passes for `core` and `engineer` | **Met on the dev host.** On `core`, 9/9 pass and check 10 is skipped by design. On `engineer`, 10/10 pass, both on the upgraded install and in the clean room. The CI matrix (`core`, `engineer`) is wired in `v3-ci.yml` but has not run on GitHub yet. |
| — alice logs into `jupyter.` in a headless browser; her workspace starts | Check 8: 1 password prompt, spawn in 11–13 s |
| — inside it, as alice: Trino over `samples`, DuckDB `ATTACH` with vended credentials, `dbt build` of the starter | Check 8: `current_user=alice`, orders 15000; DuckDB 15000 rows via vended credentials; dbt `PASS=27 ERROR=0` in 23 s |
| — `engineer` only: Spark Connect creates and reads an Iceberg table as alice | Check 10: `lakehouse.smoke.spark_probe` created, 2 rows read back, then dropped (plain `DROP`) |
| 2. `victor` is still denied writes from inside his workspace | Check 9: `PERMISSION_DENIED: Cannot insert into table lakehouse.smoke.events`; his reads work |
| 3. Idempotency, upgrade in place from Phase 1, and the existing 7 checks | **Met.** See "Upgrade in place" below. Checks 1–7 pass in every run. |

## What was built

**Workspace** (WORKSPACE: `compose/workspace.yaml`, `config/jupyterhub/`, `images/{jupyterhub,workspace}/`, `starter/`, `bootstrap/jupyterhub_client.py`)
- **JupyterHub**
  - Upstream hub image by tag and digest, plus OAuthenticator and DockerSpawner, with a generated lock.
  - GenericOAuthenticator against the Keycloak client `jupyterhub`.
  - `enable_auth_state` with `JUPYTERHUB_CRYPT_KEY`.
  - `lab-admin` members are hub admins; the four lab groups are allowed.
- **Workspace image** `lakehouse-lab/v3-workspace`, productionized from S-4:
  - JupyterLab, JupySQL, jupyterlab-git, a terminal, and code-server via jupyter-server-proxy;
  - Trino, DuckDB with its extensions baked in, PyIceberg, dbt-trino, the Spark Connect client, and jupyter-ai (not configured);
  - the `lakehouse` Python package, the `lab-token` CLI and a `dbt` wrapper.
- **Starter:** a README notebook and the `dbt_lakehouse` project (5 staging models and 3 marts, with tests) over `lakehouse.samples`. It is copied into `~/starter` on the first start of a new home and never overwritten.

**Engines and data** (SPARK+DATA: `compose/spark.yaml`, `images/spark/`, `config/spark/`, `bootstrap/samples.py`, `config/trino/catalog/tpch.properties`, `rules.json`)
- **Profile `engineer`:** Spark master, one worker, and one shared Spark Connect server on port 15002. They are on the `lab` network only; no port is published.
- **Spark image:** the workspace's Python base, with the JDK and `/opt/spark` copied from `apache/spark` (by tag and digest).
  - Why: Python UDFs need the same Python minor on client and workers.
  - The Iceberg jars are verified against sha256 pins.
  - It holds no S3 key and no catalog credential.
- **`samples` one-shot:** creates `lakehouse.samples.{region,nation,customer,orders,lineitem}` from `tpch.tiny` with Trino CTAS.
  - It runs as the `trino` client's service account.
  - First run takes 16 s; a re-run reports `unchanged` in 0.6 s.

**Tests and lifecycle** (TESTS+CI: `tests/smoke/`, `lab`, `installer/`, `bootstrap/keycloak.py`, `v3-ci.yml`)
- **Profiles:** `install.sh --profile engineer`. Switching profile on an existing install runs `down` first (volumes kept).
- **`lab down`** stops this project's workspaces before `compose down`.
- **`lab reset`** also deletes per-user home volumes.
- `lab down` and `lab reset` select workspaces **only** by the labels `com.docker.compose.project=<project>` AND `lab.role=workspace`.
- **Test users:** `remove_test_users` deletes seeded users once `LAB_SEED_TEST_USERS=false`, but only accounts that carry the seeding marker e-mail, and never the first admin.
- **Smoke checks 8–10** run *inside* the user's own Jupyter server, through its REST API and kernel websocket from the logged-in JupyterLab page. They need no docker exec and no hub admin token.
- **CI:** e2e is a matrix over `core` and `engineer`, with CI-sized memory overrides passed as job env. It ends with `check-reset.sh`.

## Integration changes

- **Pins** merged into `versions.env`:
  - `SPARK_IMAGE_DIGEST`, `ICEBERG_SPARK_RUNTIME_DIGEST`, `ICEBERG_AWS_BUNDLE_DIGEST`, `PANDAS_VERSION`;
  - `JUPYTERHUB_IMAGE_DIGEST`, `DOCKERSPAWNER_VERSION`, `DOCKER_SOCKET_PROXY_IMAGE_TAG`/`_DIGEST`.
  - `v3/.pins/` was removed.
- **`compose.yaml`:**
  - includes `compose/workspace.yaml` and `compose/spark.yaml`;
  - the `hub-docker` network (internal) and the `jupyterhub-data` volume moved here, so all volumes are declared in one place;
  - documents the per-user home volume exception.
- **`bootstrap/__main__.py`:**
  - `jupyterhub_client.ensure_jupyterhub_client(...)` after the sync client;
  - with seeding off, `keycloak.remove_test_users(kc, protected=(LAB_ADMIN_USER,))` runs *before* the Trino and Lakekeeper syncs, so both drop the users on the same run (verified: 4 deleted, group file and OpenFGA memberships updated, and the next run changes nothing).
- **`compose/bootstrap.yaml`:**
  - passes `OIDC_CLIENT_SECRET_JUPYTERHUB` to bootstrap;
  - adds the one-shot `samples` service (after Trino is healthy);
  - JupyterHub depends on `samples: service_completed_successfully`, so a samples failure fails `up --wait` (before this, `up --wait` returned 0 while samples was still running).
- **Caddy:** `jupyter.` site and network alias.
- **Secrets:**
  - `OIDC_CLIENT_SECRET_JUPYTERHUB` and `JUPYTERHUB_CRYPT_KEY` are in `installer/secrets.sh`, the `compose-check.sh` fallback list, `tests/smoke/dev-env.sh` and the CONTRACT secrets table.
  - The contract's `up` command now reads `--profile "$LAB_PROFILE"`.
- **Interface reconciliation:**
  - **Token:** `lab_token()` / `lab-token` is the single helper, as the contract requires.
  - **Starter path:** `~/starter/dbt_lakehouse`.
  - **Spark Connect:** `sc://spark-connect:15002`, as `SPARK_REMOTE`.
  - **Catalog:** `LAB_CATALOG_URL`.
  - **Spark sessions:** `lakehouse.spark()` and the probe's fallback now use `create()` instead of `getOrCreate()`, because an old session would carry an old catalog token (see OQ-15).
- **Smoke probe fixes** (both from WORKSPACE's report):
  - `dbt_summary` parses any `KEY=N` fields, since dbt 1.12 adds `NO-OP=` and `REUSED=`.
  - The DuckDB check no longer relies on `duckdb_secrets()`, which does not reliably list the vended secret. It now requires all three:
    - the read works with `ACCESS_DELEGATION_MODE 'vended_credentials'`;
    - the same ATTACH with `'none'` cannot read;
    - the workspace has no `AWS_*` env and no `~/.aws`.
- **Diagnostics and CI:**
  - `tools/ci-collect-logs.sh` uses `LAB_PROFILE` from `.env` and collects workspace container logs, selected by the project and `lab.role` labels.
  - `images_matrix.py` emits `build_contexts` from compose `additional_contexts`, and `v3-images.yml` passes them (`starter=v3/starter`) to buildx. `v3/starter/**` was added to its path filters.
- **Trino:** `iceberg.rest-catalog.oauth2.token-exchange-enabled=false`. Keycloak had logged about 2 `TOKEN_EXCHANGE_ERROR`s per second from Trino; after the change it logged 0 in 10 minutes. Trino 483 accepts the property.
- **Ownership ruling:** `images/jupyterhub/` is accepted as a separate image directory, because `images_matrix.py` builds one image per `images/*/Dockerfile`.

### Bugs found by integration (fixed)

1. **Upgrade kept stale bind-mounted config** (`REG_V3_STALE_BIND_MOUNT_CONFIG_ON_UPGRADE`).
   - Symptom: the first in-place upgrade failed. `samples` exited 1 with `Access Denied: Cannot execute query [SHOW SCHEMAS FROM lakehouse]`, because Trino still ran the Phase 1 `rules.json` and had no `tpch` catalog.
   - Cause: Compose ignores bind-mounted file contents. A single-file bind mount even keeps showing the *old* inode after the file is replaced.
   - Fix: `installer/lib.sh` derives `LAB_CONFIG_HASH_{CADDY,TRINO,SEAWEEDFS,JUPYTERHUB,SPARK}` (cksum over `config/<svc>`) on every start and never stores them. Each of those services carries `labels: lab.config-hash: ${LAB_CONFIG_HASH_<SVC>:-}`, so `up` recreates exactly the services whose config changed.
   - Tests: 11 new installer unit tests. An unchanged re-run keeps identical container IDs.
2. **Bootstrap was not idempotent for the `jupyterhub` client.** It printed `jupyterhub: updated webOrigins` on every run, because Keycloak returns `redirectUris`/`webOrigins` as unordered sets. The drift check now compares them sorted. New `tests/bootstrap/test_jupyterhub_client.py` (3 tests) fails if the fix is reverted.
3. **`config_hash` in a tree without `config/`** (the installer unit-test fixture) aborted `install.sh` under `pipefail`. It now hashes only paths that exist.

The three WORKSPACE bugs TESTS+CI hit (`2g` memory unit, empty `Cmd`, and empty auth state for non-admins) were already fixed in the WORKSPACE deliverable. The integrated runs confirm it.

## Upgrade in place (how real users get Phase 2)

The running Phase 1 install (`v3-p1`, `core`, ports 18443/18080) was synced with the new `v3/`, leaving out `.env`, `.secrets.env`, `state/` and `out/`. Then:

| Step | Result |
|---|---|
| `./install.sh --non-interactive` (first, before fix 1) | rc 1: `samples` denied by the stale Trino rules (see above) |
| `./install.sh --non-interactive` (after fix 1) | rc 0, **89 s**. Recreated caddy, trino, seaweedfs, jupyterhub and docker-proxy. Samples created. The two new secrets were appended to `.secrets.env`. `.env`, the CA root cert and key: unchanged sha256. |
| Re-run (idempotency) | rc 0, **11 s**. Container IDs identical; bootstrap `users: unchanged`; samples `unchanged (0.8s)` |
| `./lab test` on `core` | **SMOKE: PASS (9/9, 1 skipped: 10; profile core)** in 133 s. Check 7: grant 27 s, revoke 35 s. |
| `./install.sh --non-interactive --profile engineer` | rc 0, **124 s**. It printed "Profile changed (core -> engineer): stopping the running lab first; data is kept". 19 containers, all healthy. |
| `./lab test` on `engineer` | **SMOKE: PASS (10/10; profile engineer)** in 179 s |
| Re-run on `engineer` | rc 0, 12 s, container IDs identical; `.secrets.env` and CA unchanged |

`v3-p1` is left running on the `engineer` profile. Its volumes (Postgres, SeaweedFS and the rest) were kept through both upgrades; no step ran `down -v`.

## Clean room (dev host)

New directory, project `v3-p2`, sslip domain, ports 18543/18180, `--seed-test-users --profile engineer`:

| Step | Wall clock |
|---|---|
| `install.sh` (checks, config, secrets, CA, build, `up --wait` to healthy) | **136 s** |
| `lab test` (includes the smoke image build check) | **167 s**, **SMOKE: PASS (10/10; profile engineer)** |
| **Total, fresh install to green smoke** | **5 min 3 s** |
| `install.sh --no-seed-test-users` | test users deleted, group file shows `engineer=0, analyst=0, viewer=0`, OpenFGA has 4 membership changes. The next run changes nothing. |
| `lab reset --yes` | all containers, volumes (including the 2 JupyterHub-created home volumes) and networks of `v3-p2` gone |

Base and local images were cached on the host: the workstreams had built the same Dockerfiles, and local tags are shared across projects. So these timings do not include a cold build of the workspace image, measured by WORKSPACE at about 2.5 min for both images. The CI matrix will measure a cold run.

## Memory

Idle `docker stats` on `v3-p1`, engineer profile, after the smoke test (workspaces stopped):

| Container | In use | Limit |
|---|---|---|
| trino | 960 MiB | 3 GiB |
| keycloak | 525 MiB | 1.25 GiB |
| spark-worker | 526 MiB | 2.5 GiB |
| spark-connect | 477 MiB | 1.5 GiB |
| seaweedfs | 175 MiB | 1 GiB |
| spark-master | 164 MiB | 512 MiB |
| postgres | 152 MiB | 512 MiB |
| jupyterhub | 131 MiB | 384 MiB |
| openfga | 32 MiB | 256 MiB |
| lakekeeper | 25 MiB | 512 MiB |
| docker-proxy | 17 MiB | 64 MiB |
| caddy | 16 MiB | 256 MiB |
| identity-sync | 13 MiB | 128 MiB |
| workspace (WORKSPACE's measurement) | 166–171 MiB idle, 444 MiB peak (Trino + DuckDB + PyIceberg + JupySQL + dbt build) | 1.5 GiB, 2 CPUs |

**Budgets (limits):**

| Setup | Long-running only | Including exited one-shots |
|---|---|---|
| `core` + one workspace | 7.31 + 1.5 = **8.81 GiB (9.5 GB)** | 9.69 GiB |
| `engineer` + one workspace | **13.31 GiB** | 14.19 GiB |

- **`core`:** fits the ≤ 10 GB target when only long-running containers are counted. The one-shots (bootstrap, migrations, trust-init, workspace-image, samples) exit before any workspace starts.
- **`engineer`:** fits a 16 GB machine. The CI job lowers the Spark and workspace limits through env.
- About 3.2 GiB is actually in use at idle.

## OQ-15: Spark Connect identity (decision: per-session user token)

The decision rule is met: alice can write through Spark and victor is denied. The per-session token is adopted, so Spark has **no** service identity and there is **no** engineer-only restriction.

- **How it works:** each Spark Connect client sets `spark.sql.catalog.lakehouse.token` to its user's own token on its own session. `spark-defaults.conf` holds no catalog credential. Lakekeeper and OpenFGA authorize the real user.
- **Evidence** (SPARK+DATA, then integration):
  - alice creates a namespace and table, inserts, appends, reads, and runs Python and pandas UDFs;
  - victor gets `ForbiddenException ... can_write_data` / `can_create_table` / `can_drop`, and anna is denied too;
  - eddie can write;
  - a session with no token gets `NotAuthorizedException`;
  - the Lakekeeper audit log shows only user principals: commits from alice and eddie only, and victor's and anna's `write_data` signing denied;
  - smoke check 10 passes on both engineer installs, using `lakehouse.spark()` as alice.
- **Token lifetime:**
  - **The constraint:** the catalog token is fixed when the session starts. Iceberg's refresh needs an RFC 8693 exchange that Keycloak rejects, so it is off. A session loses catalog access about 60 s after its token expires.
  - **Decision (option (a)), for the workspace client only:**
    - the `jupyterhub` Keycloak client issues **1 h** access tokens (ensured by bootstrap);
    - `lakehouse.spark()` always opens a **new** session (`create()`) with a token that has at least 30 min left;
    - the realm default (5 min) is unchanged for every other client.
  - **What still applies at once:** group revocation, because Trino and Lakekeeper authorize per request from the group file and OpenFGA, not from token claims. Only a disabled user's token outlives the change, by up to 1 h.
- **Residual risks of one shared Connect server** (documented; engineer profile only):
  - Spark Connect itself has no authentication. Anyone on the `lab` network can run UDF code on the worker, but gets no catalog access without their own token.
  - Concurrent users share executor JVMs and spill directories. JVM attach and heap dumps are blocked with `-XX:+DisableAttachMechanism`.
  - The Spark Connect `user_id` is asserted by the client.

## Identity in the workspace

- **Where tokens come from:** `lab_token()` / `lab-token` is the only token source. It reads the user's auth state from the hub (`GET /hub/api/users/<name>` with the server's own API token). No client secret and no refresh token is stored in the workspace.
- **How they stay valid:**
  - The hub's `refresh_user_hook` refreshes when less than `LAB_TOKEN_MIN_TTL` (2700 s) is left.
  - The workspace's activity reports to the hub trigger it every few minutes, which also keeps the Keycloak SSO session alive.
  - Verified by WORKSPACE: with a forced TTL, a new token arrived in the same Keycloak session, and Trino accepted it.
- **Clients** (all pre-wired, all act as the user):
  - Trino and PyIceberg take a fresh token on every request;
  - DuckDB (`attach_lakehouse`) and dbt (`method: jwt`, via the `dbt` wrapper) take one token at start;
  - Spark: a new session per `spark()` call.
- **Non-admins:** the `user` role includes `admin:auth_state!user`, because a server token never has more scopes than its owner.

## Docker safety (the host runs production)

- **No direct socket for DockerSpawner.** It never mounts `/var/run/docker.sock`. A pinned `tecnativa/docker-socket-proxy` (tag and digest) is the only container that mounts it (read-only). The proxy sits on `hub-docker`, an **internal** network that only JupyterHub joins.
- **The proxy runs a custom HAProxy allowlist** (`config/jupyterhub/docker-proxy.cfg`):
  - Container calls are allowed by **name** only, and only for `<project>-ws-*`. DockerSpawner is subclassed to address containers by name, because Docker also accepts full IDs and unique ID prefixes, which would reach any container.
  - There is no listing, pull, exec, or volume/network delete.
  - Container creation is refused with host bind mounts, privileged mode, `cap_add`, devices, or the host's network or pid namespace.
  - WORKSPACE probed 19 disallowed calls; all got HTTP 403.
- **Spawned workspaces** are named `<project>-ws-<user>` and carry the labels `com.docker.compose.project=<project>` and `lab.role=workspace`. They join only the `lab` network, publish no ports, are auto-removed, and default to 1536m / 2 CPUs.
- **Home volumes** `<project>-home-<user>` are created by the spawner with the same labels. `lab reset` deletes them by those two exact labels; the name is never used as a selector.
- **Dev-host audit.** `docker ps -a`, `docker volume ls` and `docker network ls` were recorded before any work and after teardown. The non-`v3-` objects matched line for line, including container IDs and creation times (37 lines each).
- **What is left afterwards:**
  - `v3-p1` (19 containers, engineer, healthy);
  - its 9 volumes, including `v3-p1-home-alice` and `-victor`;
  - its 2 networks.
  - Nothing of `v3-p2`, `v3-p2-workspace`, `v3-p2-spark` or `v3-p2-tests` remains (0 containers, volumes and networks for each).
  - The only published ports are 18443 and 18080.

## Lint and checks (final tree)

| Check | Result |
|---|---|
| `python3 v3/tools/check_versions.py` | OK |
| `python3 v3/tools/check_compat.py` | OK (0 errors, 0 warnings) |
| `v3/tools/shellcheck.sh` (v0.11.0) | 35 files OK |
| `v3/tools/actionlint.sh` (1.7.12) | OK on `v3-ci.yml` and `v3-images.yml` |
| `v3/tools/compose-check.sh` / `--profile engineer` | OK / OK |
| `python3 -m unittest discover -s v3/tests/lint` | OK |
| `python3 -m unittest discover -s v3/tests/bootstrap` | 9 tests OK |
| `python3 -m unittest discover -s v3/tests/smoke -p 'test_*.py'` | 14 tests OK |
| `bash v3/tests/installer/run.sh` | shellcheck clean; **209** unit checks pass |
| `bash v3/tests/installer/test_e2e.sh` (local Docker) | 42 passed, 0 failed (isolation check included) |
| `python3 v3/tools/images_matrix.py` | 5 images, `build_contexts: starter=v3/starter` for the workspace |

## Known gaps

- **CI has not run Phase 2 on GitHub yet.**
  - The e2e matrix (`core`, `engineer`) and the `build-contexts` input in `v3-images.yml` are validated only by actionlint and local runs.
  - `engineer` + one workspace on a 16 GB runner relies on the CI memory overrides.
- **Local image tags are not project-scoped.** `lakehouse-lab/v3-bootstrap:${PYTHON_IMAGE_TAG}`, `v3-workspace`, `v3-spark` and `v3-smoke` are shared by every project on a daemon. Two installs of *different* code on one host overwrite each other's images; SPARK+DATA hit this during parallel development. Real users have one install per host. The follow-up is to scope tags by project, or to use prebuilt, versioned images (ADR-012).
- **Spark sessions are bounded by their token.** A single Spark job that runs longer than the session token (at least 30 min, at most 1 h) fails during signing. The user reopens `spark()`.
- **Shared Spark Connect server:** no per-user isolation of executors (see the OQ-15 risks above). Spark UI and forward-auth are Phase 3.
- **`jupyter-ai`** is installed but not configured (Phase 5).
- **The home-volume exception** means `compose down -v` alone leaves the home volumes; `lab reset` removes them.
- **The `lab.config-hash` labels** are set by `./lab` and `./install.sh`. A raw `docker compose up` without them (label empty) recreates those five services once. This is harmless but documented here.
- **Cold-cache timings** for the workspace (2.1 GB) and Spark (1.3 GB) images were not measured on the dev host (see Clean room).
- **Workstream scratch directories** (`~/lakehouse-v3/p2-workspace*`) are still on the dev host, with no Docker objects. They are left for their owners to delete.

## Lead follow-ups after verification (verifier notes 1-3)

1. **The Docker proxy scopes volumes and networks (allowlist).** A container create is
   accepted only if every `Binds` volume is `<project>-home-*` or `<project>_trust`, there
   are no `Mounts` and no `VolumesFrom`, there is no extra `EndpointsConfig`, and
   `NetworkMode` is exactly `<project>_lab`. Volumes can be created only as
   `<project>-home-*`. Before this, the hub could have mounted any named volume on the host
   (for example another project's database) if its config were changed or compromised. The
   rules are double-quoted, because HAProxy expands `${LAB_PROJECT}` only inside double
   quotes. **New smoke check 11** runs 14 cases from inside `jupyterhub` and passes 14/14.
   Denied cases are side-effect free even if a rule were wrong: they use a nonexistent image
   or volume driver. Real workspace spawns still work through the stricter proxy (checks 8
   and 10).
2. **The OQ-15 rule is now under test.** Check 9 also has victor attempt a Spark Connect
   table create (engineer profile) and requires Lakekeeper to refuse it (`ForbiddenException
   can_create_table`, in 2.4 s). With a shared service identity this would succeed, so the
   check proves the per-session user token reaches the catalog.
3. **The dbt check verifies results.** After `dbt build`, `fct_orders`, `dim_customers` and
   `revenue_by_region` must exist in `lakehouse.dbt_<user>`, and `revenue_by_region` must
   have rows.

**Intermittent hang (seen once, not reproduced).** On the first full run with (2), victor's
probe timed out after 300 s. Lakekeeper and Spark had refused his create in about 1 s, and
the client then went silent. It did not recur in an isolated run, in two more full runs, or
in a standalone client (refusal plus `stop()` in 2.0 s). To make any recurrence diagnosable,
the probe now writes all thread stacks to `~/.smoke-stack.txt` shortly before the harness
times out, and the harness attaches that dump to the check's evidence. Tracked as
WATCH_V3_SPARK_CONNECT_INTERMITTENT_HANG.
