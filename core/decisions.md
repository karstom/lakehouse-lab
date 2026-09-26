# Decisions

> Intentional architectural or design choices with non-obvious rationale.
> The goal: the AI never "helpfully" refactors away a decision that was made for a reason.

---

## NODE: DEC_MIGRATE_FROM_BITNAMI_OFFICIAL_APACHE_4B39
**Type:** Decision
**Priority:** MEDIUM
**Label:** Use official apache/spark images, not Bitnami
**Summary:** Spark master and worker moved from `bitnami/spark:3.5.0` to official `apache/spark` 3.5.x images, which changed JAR paths from `/opt/bitnami/spark` to `/opt/spark` and switched entrypoints to native Spark class invocation. Do not reintroduce Bitnami paths or health checks (8b988f4 was a Bitnami-specific health-check fix).
**Tags:** spark, docker, images
**Edges:**
- RELATES_TO → INV_SPARK_VERSION_ALIGNMENT: sets the cluster side of the version triple
**Files:** `docker-compose.yml`, `docker-compose.iceberg.yml`, `scripts/init-compute.sh`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `422b08a`

---

## NODE: DEC_SWITCH_SPARK_3_5_3_A7AE
**Type:** Decision
**Priority:** MEDIUM
**Label:** Use Spark-matched Jupyter image; no runtime PySpark install
**Summary:** Jupyter uses `quay.io/jupyter/pyspark-notebook:spark-3.5.3` and the stock start scripts, so the image supplies PySpark instead of `pip install` at container start. This ended a long run of PySpark/PyArrow import conflicts. Quay.io, not Docker Hub, is where current jupyter images are published (d532f0e).
**Tags:** jupyter, pyspark, images
**Edges:**
- MITIGATES → REG_JUPYTER_PYSPARK_VERSIONS: removed the second PySpark source
**Files:** `docker-compose.yml`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `8191f56`, `d532f0e`

---

## NODE: DEC_NAMED_EXTERNAL_VOLUMES
**Type:** Decision
**Priority:** HIGH
**Label:** All persistent data lives in external named volumes
**Summary:** Every stateful service (Postgres, MinIO, Jupyter, Airflow, Spark, Superset, Vizro, LanceDB, Portainer, shared) uses a named volume declared `external: true`, created by `start-lakehouse.sh`/migration scripts, so `docker compose down` and upgrades cannot delete data. This replaced bind mounts under `./lakehouse-data` after overlay switches and upgrades lost data. Do not revert to bind mounts or non-external volumes.
**Tags:** volumes, data-loss, upgrade
**Edges:**
- MITIGATES → REG_UPGRADE_VOLUME_DATA_LOSS: removed the bind-mount data-loss class
- DEPENDS_ON → INV_VOLUME_NAMES_SINGLE_SOURCE: external volumes need exact name agreement
**Files:** `docker-compose.yml`, `start-lakehouse.sh`, `scripts/install/migrate-to-named-volumes.sh`
**Symbols:** `create_named_volumes`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `98da41e`, `9ab71ec`, `3b43c4f`, `5ab9aa2`

---

## NODE: DEC_INIT_CONTAINER_PYTHON_BASE
**Type:** Decision
**Priority:** MEDIUM
**Label:** lakehouse-init runs on python:3.11 (Debian), not Alpine
**Summary:** The init container moved from Alpine to `python:3.11` because Alpine lacked bash/curl and needed runtime installs that failed in restricted networks. Init modules must also degrade gracefully when the network is unavailable (e.g. skip optional downloads) rather than fail the whole init. Do not switch back to Alpine or `-slim` without re-checking every tool `scripts/lib/init-core.sh` assumes.
**Tags:** init, docker, images
**Edges:**
- MITIGATES → REG_INIT_CONTAINER_BOOTSTRAP: removed the missing-tooling failures
**Files:** `docker-compose.yml`, `scripts/lib/init-core.sh`, `scripts/init-infrastructure.sh`, `scripts/init-compute.sh`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `237e4d7`, `680b017`, `8b07634`, `4070f9e`

---

## NODE: DEC_REMOVE_SUDO_DEPENDENCIES_FROM_ALPINE_6EF3
**Type:** Decision
**Priority:** LOW
**Label:** Init scripts run as root — never use sudo
**Summary:** Init scripts run as root inside the init container, where `sudo` is not installed; `sudo` calls broke MinIO client installation and permission setting. Originally made for the Alpine image, and still applies on the current `python:3.11` base.
**Tags:** init, permissions
**Edges:**
- RELATES_TO → DEC_INIT_CONTAINER_PYTHON_BASE: base image later changed; rule still holds
**Files:** `scripts/init-infrastructure.sh`, `scripts/lib/init-core.sh`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `07adab4`

---

## NODE: DEC_REMOVE_DASHBOARD_FUNCTIONALITY_FOCUS_ON_8492
**Type:** Decision
**Priority:** MEDIUM
**Label:** No landing-page dashboard service
**Summary:** After cycling Homer → Homepage → Dashy → static nginx page in about two months (each swap fixing config, API-widget, host-validation and volume problems), all landing-page dashboards were removed in v2.1.1 to focus on core-stack stability. Service URLs come from `scripts/show-credentials.sh` instead. Do not add a new dashboard service without a strong reason; `scripts/init-dashboards.sh` now only sets up Superset BI.
**Tags:** dashboard, scope
**Edges:**
- RELATES_TO → WATCH_CONFIGURE_SERVICES: every swap had to be mirrored in presets
**Files:** `docker-compose.yml`, `scripts/configure-services.sh`, `scripts/init-dashboards.sh`, `scripts/show-credentials.sh`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `397126a`, `d38bcf2`, `193ecd1`, `f251471`

---

## NODE: DEC_REMOVE_OAUTH_AUTHENTICATION_SYSTEM_ENTIRELY_2B27
**Type:** Decision
**Priority:** LOW
**Label:** No OAuth / auth service — lab platform scope
**Summary:** The auth-service, `docker-compose.auth.yml` overlay and `install-with-auth.sh` were removed as unstable and unnecessary for a learning lab; access control is per-service credentials plus `provision-user.sh` roles. Leftover: `start-lakehouse.sh` still creates `auth_data`/`audit_logs` volumes for the removed overlay.
**Tags:** auth, scope
**Edges:** _(none)_
**Files:** `start-lakehouse.sh`, `scripts/provision-user.sh`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `494f04f`

---

## NODE: DEC_REMOVE_MCP_SERVER_COMPLETELY_FROM_67B4
**Type:** Decision
**Priority:** LOW
**Label:** No in-stack MCP server
**Summary:** The incomplete `mcp-server/` service was removed along with all README/architecture references to AI-powered APIs. `config/mcp-server.yaml` and `docs/MCP.md` remain as leftovers. This is unrelated to the simplegraph MCP server configured in `.mcp.json` for development.
**Tags:** mcp, scope
**Edges:** _(none)_
**Files:** `config/mcp-server.yaml`, `docs/MCP.md`, `.lakehouse-services.conf`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `750c37f`

---

## NODE: DEC_REMOVE_ORPHANED_CONTAINERS_DURING_UPGRADES_5BC0
**Type:** Decision
**Priority:** LOW
**Label:** Always `docker compose up -d --remove-orphans`
**Summary:** All `docker compose up -d` calls in install, upgrade, migration and start scripts pass `--remove-orphans` so containers from removed or replaced services (e.g. old dashboards) don't linger after upgrades. Keep the flag on any new `up` invocation.
**Tags:** docker-compose, upgrade
**Edges:**
- RELATES_TO → WATCH_INSTALL_UPGRADE_PATH: applied across the upgrade path
**Files:** `install.sh`, `start-lakehouse.sh`, `scripts/install/fix-credentials.sh`, `scripts/install/migrate-to-named-volumes.sh`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `a45e861`

---

## NODE: DEC_REPLACE_UNRELIABLE_DOCKER_STARTUP_TEST_AD13
**Type:** Decision
**Priority:** MEDIUM
**Label:** CI validates compose config instead of starting the stack
**Summary:** The CI startup test was replaced with `docker compose config` validation plus required-service checks because image pulls and container startup timed out on GitHub runners. Trade-off: CI no longer catches runtime startup, init or upgrade failures — those need manual or `tests/run_stack_health_tests.sh` verification.
**Tags:** ci, testing
**Edges:**
- RELATES_TO → WATCH_CI_WORKFLOWS: leaves runtime regressions uncaught
**Files:** `.github/workflows/startup-test.yml`, `tests/run_stack_health_tests.sh`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `4dbfda8`

---

## NODE: DEC_REMOVE_ICEBERG_ENABLED_FROM_SOURCE_1F54
**Type:** Decision
**Priority:** LOW
**Label:** `.iceberg-enabled` is a local marker, not tracked
**Summary:** `.iceberg-enabled` marks an install that uses the Iceberg overlay; it is created locally and gitignored so different installs don't conflict. Scripts decide whether to add `docker-compose.iceberg.yml` based on it.
**Tags:** iceberg, configuration
**Edges:** _(none)_
**Files:** `.gitignore`, `start-lakehouse.sh`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `c32029b`

---

## NODE: DEC_REMOVE_UNUSED_CODECOV_INTEGRATION_B8A6
**Type:** Decision
**Priority:** LOW
**Label:** No coverage reporting
**Summary:** Codecov upload, badge and pytest-cov were removed because CI never produced `coverage.xml`. Don't re-add a coverage badge without also generating coverage.
**Tags:** ci, testing
**Edges:** _(none)_
**Files:** `.github/workflows/ci.yml`, `docs/TESTING.md`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `e7047ce`

---

## NODE: DEC_V3_STACK_DIRECTION
**Type:** Decision
**Priority:** HIGH
**Label:** V3: new stack — SeaweedFS, Lakekeeper, Spark 4.1, Trino, Airflow 3, Superset 6
**Summary:** Agreed 2026-09-25 to build V3 on a `v3` branch while V2 stays maintained on main. MinIO (unmaintained since Feb 2026) is replaced by SeaweedFS ≥4.40. All tables become Iceberg tables in a Lakekeeper REST catalog. Engines are Spark 4.1 (Iceberg 1.11 runtime; 4.2 waits for Iceberg support), Trino and DuckDB, with Airflow 3.1+ and pinned Superset 6. Full rationale: docs/v3/DECISIONS.md ADR-001/002/003/009/013.
**Tags:** v3, architecture, storage, catalog, spark
**Edges:**
- MITIGATES → REG_ICEBERG_JAR_VERSIONS: Iceberg becomes core with a REST catalog instead of an overlay
- RELATES_TO → DEC_MIGRATE_FROM_BITNAMI_OFFICIAL_APACHE_4B39: V3 keeps official apache/spark images, moving 3.5 → 4.1
**Files:** `docs/v3/README.md`, `docs/v3/ARCHITECTURE.md`, `docs/v3/DECISIONS.md`, `docs/v3/ROADMAP.md`
**LastVerified:** 2026-09-25
**Commit:** 4dd6c9a
**LastUpdated:** 2026-09-25

---

## NODE: DEC_V3_KEYCLOAK_SSO_SUBDOMAINS
**Type:** Decision
**Priority:** HIGH
**Label:** V3: Keycloak SSO for every service, subdomain routing via Caddy
**Summary:** V3 uses Keycloak as the only identity store: each service uses its native OIDC integration (JupyterHub, Superset, Airflow 3 Keycloak auth manager, Trino, Lakekeeper), or Caddy forward-auth where it has none. Services live on subdomains of LAB_DOMAIN (default lab.localhost, sslip.io for remote hosts), and the installer works out the host once. V2's SSO failed because it was a custom auth service; V3 writes no authentication code, and the realm is imported from a template with no clicks. ADR-004/005.
**Tags:** v3, sso, keycloak, networking
**Edges:**
- MITIGATES → REG_HOST_IP_DETECTION: single LAB_DOMAIN replaces four detection copies
- RELATES_TO → DEC_REMOVE_OAUTH_AUTHENTICATION_SYSTEM_ENTIRELY_2B27: revisits SSO without custom auth code
**Files:** `docs/v3/DECISIONS.md`, `docs/v3/ARCHITECTURE.md`
**LastVerified:** 2026-09-25
**Commit:** 4dd6c9a
**LastUpdated:** 2026-09-25

---

## NODE: DEC_V3_CATALOG_VENDED_STORAGE_ACCESS
**Type:** Decision
**Priority:** HIGH
**Label:** V3: storage access given out by Lakekeeper — no S3 keys for users
**Summary:** In V3, engines never hold static S3 keys; Lakekeeper authorizes every table access. Spark and PyIceberg use remote signing. Trino (483 has no remote signing, trinodb/trino#21189) and DuckDB use STS credentials vended by SeaweedFS, which spikes S-1/S-2 showed are enforced per table and expire within 1 hour. SeaweedFS STS is therefore required in every profile. This removes the root cause of REG_CREDENTIAL_PROPAGATION. ADR-006, amended 2026-09-25.
**Tags:** v3, credentials, catalog, storage
**Edges:**
- MITIGATES → REG_CREDENTIAL_PROPAGATION: removes storage credentials from all consumers
- RELATES_TO → INV_ENV_IS_CREDENTIAL_SOURCE: V3 replaces the .env credential model
**Files:** `docs/v3/DECISIONS.md`, `docs/v3/OPEN_QUESTIONS.md`, `spikes/s1-catalog-storage/RESULTS.md`, `spikes/s2-duckdb-sts/RESULTS.md`
**Evidence:** `ssh $LAB_SERVER 'cd lakehouse-v3/spikes/s2-duckdb-sts && ./test.sh'` → EXIT=0, C1–C3 PASS (vended ASIA… creds, DuckDB read+insert, table-scoped probe 200/403)
**LastVerified:** 2026-09-25
**Commit:** 4dd6c9a
**LastUpdated:** 2026-09-25

---

## NODE: DEC_V3_VERSIONS_FILE_PREBUILT_IMAGES
**Type:** Decision
**Priority:** HIGH
**Label:** V3: one versions.env, pre-built pinned images, no logic in compose
**Summary:** In V3, `versions.env` is the only place a version is written; CI rejects version literals elsewhere and checks the Spark↔Iceberg↔Scala↔PySpark matrix. Custom images are built in CI and published to GHCR, with no pip/apt installs at container start, no :latest, and no logic in compose command blocks. CI starts the core profile and runs a smoke lesson on every PR. ADR-012/015.
**Tags:** v3, versions, images, ci
**Edges:**
- MITIGATES → REG_COMPOSE_INLINE_SHELL: no logic in YAML
- MITIGATES → REG_JUPYTER_PYSPARK_VERSIONS: no runtime installs
- MITIGATES → REG_INIT_CONTAINER_BOOTSTRAP: images replace runtime-installing init container
- MITIGATES → REG_SUPERSET_SETUP: pinned pre-built Superset image
- RELATES_TO → WATCH_CI_WORKFLOWS: restores a real startup test
**Files:** `docs/v3/DECISIONS.md`, `docs/v3/ROADMAP.md`
**LastVerified:** 2026-09-25
**Commit:** 4dd6c9a
**LastUpdated:** 2026-09-25

---

## NODE: DEC_V3_WORKSPACE_JUPYTERHUB_CODESERVER_DBT
**Type:** Decision
**Priority:** MEDIUM
**Label:** V3: JupyterHub workspace (JupyterLab + code-server) with dbt in core
**Summary:** Every V3 user, including single-user installs, gets a JupyterHub-spawned workspace from one pre-built image: JupyterLab with SQL cells, git and terminal, code-server via jupyter-server-proxy, and Spark/Trino/DuckDB/PyIceberg/dbt clients wired to the catalog. The workspace is the engineers' home, not the whole product: analysts mostly work in Superset on Trino. dbt-core + dbt-trino is in core, and the Lab Console stays a thin static landing page. ADR-007/008/010.
**Tags:** v3, workspace, jupyterhub, dbt
**Edges:**
- RELATES_TO → JUPYTERHUB: replaces the V2 jupyter/jupyterhub dual mode
**Files:** `docs/v3/DECISIONS.md`, `docs/v3/ARCHITECTURE.md`
**Commit:** 6f267e7
**LastUpdated:** 2026-09-25

---

## NODE: DEC_V3_AI_ASSIST_MCP_GATEWAY
**Type:** Decision
**Priority:** MEDIUM
**Label:** V3 (proposed): context-aware AI via MCP, user-scoped, through a model gateway
**Summary:** Proposed for V3 Phase 5: lab context (dbt lineage, catalog, Trino, Airflow runs, current lesson) comes from MCP servers, using the official dbt-mcp and existing servers first plus a thin lab-context server. Assistants are Jupyter AI v3 (ACP agents) and Claude Code in the workspace. The assistant acts as the user through their Keycloak token, read-only by default. A model gateway holds keys and budgets and can use local models, and tutor mode applies inside learning tracks. ADR-014; OQ-7/8/9 open.
**Tags:** v3, ai, mcp, tutor
**Edges:**
- RELATES_TO → DEC_REMOVE_MCP_SERVER_COMPLETELY_FROM_67B4: V2's custom MCP server was removed; V3 composes existing servers
**Files:** `docs/v3/DECISIONS.md`, `docs/v3/ARCHITECTURE.md`, `docs/v3/OPEN_QUESTIONS.md`
**Commit:** 6f267e7
**LastUpdated:** 2026-09-25

---

## NODE: DEC_V3_EXTERNAL_IDP_GITHUB
**Type:** Decision
**Priority:** MEDIUM
**Label:** V3 (proposed): optional external IdP via Keycloak brokering — GitHub first
**Summary:** V3 can optionally hand logins to an external provider through Keycloak, with GitHub as the proof of concept. Apps are unchanged, and the installer renders the provider into the realm. A first GitHub login gets no group until an admin approves it. A GitHub login is never linked to an existing local account by email alone (that would allow account takeover); linking requires the local password. A local admin always remains. ADR-016, Phase 3; org restriction is OQ-18.
**Tags:** v3, sso, keycloak, github, identity
**Edges:**
- DEPENDS_ON → DEC_V3_KEYCLOAK_SSO_SUBDOMAINS: brokering is Keycloak configuration on top of V3 SSO
**Files:** `docs/v3/DECISIONS.md`, `docs/v3/ARCHITECTURE.md`, `docs/v3/OPEN_QUESTIONS.md`
**Commit:** 8ae54c6
**LastUpdated:** 2026-09-25

---

## NODE: DEC_V3_CI_TOOLING
**Type:** Decision
**Priority:** MEDIUM
**Label:** V3 CI: scripted lint (versions, compat, shellcheck, compose, actionlint) + real install e2e
**Summary:** V3 CI (.github/workflows/v3-ci.yml) calls only scripts in v3/tools/ so every check runs identically locally: check_versions.py (version literals outside versions.env; GENERATED lockfiles and a per-line '# check-versions: ignore <reason>' pragma are the only escapes), check_compat.py (Spark minor/Iceberg runtime/Scala/PySpark offline table, --online verifies Maven Central/PyPI/Docker Hub), shellcheck.sh and actionlint.sh (pinned containers, tag+digest in v3/.pins/tooling.env), and compose-check.sh (contract compose command on a throwaway copy with generated .env/.secrets.env; fails on unset variables). The e2e job runs install.sh + lab test (ADR-015), retiring V2's config-only startup test. v3-images.yml pushes to GHCR only on workflow_dispatch or v3.* tags. Actions are pinned by commit SHA. V2 workflows ignore v3/**, spikes/**, docs/v3/**, core/**.
**Tags:** ci, github-actions, versions, v3, lint
**Edges:**
- RELATES_TO → WATCH_CI_WORKFLOWS: V3 replacement with real startup coverage
- RELATES_TO → DEC_V3_VERSIONS_FILE_PREBUILT_IMAGES: enforces ADR-012
- RELATES_TO → INV_SPARK_VERSION_ALIGNMENT: check_compat enforces it
**Files:** `.github/workflows/v3-ci.yml`, `.github/workflows/v3-images.yml`, `v3/tools/check_versions.py`, `v3/tools/check_compat.py`, `v3/tools/compose-check.sh`, `v3/tools/images_matrix.py`, `v3/.pins/tooling.env`
**Paths:** `v3/tools`, `v3/tests/lint`
**Evidence:** python3 -m unittest discover -s v3/tests/lint → OK (63 tests); python3 v3/tools/check_compat.py --online → OK; v3/tools/actionlint.sh → OK
**LastVerified:** 2026-09-25
**Commit:** 4dd6c9a
**LastUpdated:** 2026-09-25
**Author:** tooling-workstream

---

## NODE: DEC_V3_IDENTITY_SYNC_SERVICE
**Type:** Decision
**Priority:** HIGH
**Label:** V3: access granted only via Keycloak groups; identity-sync keeps Trino + Lakekeeper in step
**Summary:** Because Trino 483 can't pass user identity to Lakekeeper (OQ-19), Trino and Lakekeeper keep separate permission rules. Both are generated from Keycloak groups by the identity-sync service every 30 s, using a read-only lab-sync account created by bootstrap (never the master admin); `lab sync` runs it immediately. Access is granted only through Keycloak groups, so an admin needs no shell (OQ-20). New Keycloak clients are created idempotently by bootstrap rather than the realm template, so existing installs also get them.
**Tags:** v3, identity, keycloak, trino, lakekeeper
**Edges:**
- DEPENDS_ON → DEC_V3_KEYCLOAK_SSO_SUBDOMAINS: Keycloak groups are the single place access is granted
**Files:** `v3/bootstrap/__main__.py`, `v3/bootstrap/keycloak.py`, `v3/bootstrap/lakekeeper_authz.py`, `v3/compose/bootstrap.yaml`, `v3/lab`, `v3/tests/smoke/smoke.py`
**Symbols:** `sync_once`, `sync_loop`, `ensure_sync_client`
**Evidence:** lab test check 7: victor granted after 32.8s, revoked after 29.0s via Keycloak admin API only
**Commit:** 39b2dce
**LastUpdated:** 2026-09-25

---

## NODE: DEC_V3_WORKSPACE_CLEANUP_BY_LABEL
**Type:** Decision
**Priority:** MEDIUM
**Label:** V3: lab down/reset select per-user workspaces only by exact project + lab.role labels, workspaces first
**Summary:** JupyterHub creates workspace containers and home volumes outside compose. `lab down` stops/removes this project's workspace containers and `lab reset` also deletes the home volumes. Both select objects only with the exact label filters com.docker.compose.project=<project> AND lab.role=workspace (installer/lib.sh lab_workspace_ids), never a name pattern, so the JupyterHub name template stays the only copy of the names. Workspaces go first: compose ignores containers without a com.docker.compose.service label (not orphans, not in ps), and a running one keeps the `lab` network in use, so `compose down` exits 0 but leaves the network behind. A profile switch in install.sh stops the lab first because `up --remove-orphans` keeps containers of services that only the old profile enabled (e.g. Spark after engineer -> core).
**Tags:** v3, workspace, jupyterhub, volumes, reset, docker-safety, profile
**Edges:**
- RELATES_TO → INV_VOLUME_NAMES_SINGLE_SOURCE: home volume names live only in the JupyterHub template; the lab selects by label
- RELATES_TO → DEC_REMOVE_ORPHANED_CONTAINERS_DURING_UPGRADES_5BC0: --remove-orphans does not remove other-profile services nor label-only workspace containers
**Files:** `v3/installer/lib.sh`, `v3/lab`, `v3/install.sh`, `v3/tests/installer/test_unit.sh`, `v3/tests/installer/test_e2e.sh`, `v3/tests/smoke/check-reset.sh`
**Symbols:** `lab_workspace_ids`, `lab_stop_workspaces`, `lab_remove_home_volumes`, `cmd_down`, `cmd_reset`
**Evidence:** bash v3/tests/installer/test_unit.sh (fake-docker inventory with look-alike projects) -> 198 passed; bash v3/tests/installer/test_e2e.sh (real docker, compose 5.1.4) -> 42 passed; local Phase-2 stack: check-reset.sh deleted 2 JupyterHub-created home volumes, nothing of other projects changed
**LastVerified:** 2026-09-25
**Commit:** 6202fd0
**LastUpdated:** 2026-09-25
**Author:** tests-ci-workstream

---

## NODE: DEC_V3_SPARK_CONNECT_PER_SESSION_TOKEN
**Type:** Decision
**Priority:** HIGH
**Label:** V3 OQ-15: Spark Connect uses a per-session user catalog token (no Spark service identity)
**Summary:** Each Spark Connect client sets spark.sql.catalog.lakehouse.token to the user's own Keycloak token on its own session; spark-defaults holds no catalog credential, so Lakekeeper/OpenFGA authorize the real user (alice writes, victor/anna denied, no-token session 401; audit log shows only user principals). Adopted under the contract's decision rule; no engineer-only restriction. The token is fixed per session (Iceberg refresh needs an RFC 8693 exchange Keycloak rejects, so token-refresh-enabled=false): lakehouse.spark() therefore always create()s a NEW session with a token having >= 30 min left, and the jupyterhub client's access tokens live 1 h. Invariant: never put a catalog credential in config/spark/spark-defaults.conf. Watch: the Spark image's Python minor must equal the workspace's (both from PYTHON_IMAGE_TAG).
**Tags:** v3, spark, spark-connect, identity, oq-15, lakekeeper, token
**Edges:** _(none)_
**Files:** `v3/config/spark/spark-defaults.conf`, `v3/images/workspace/lakehouse/clients.py`, `v3/images/spark/Dockerfile`, `v3/bootstrap/jupyterhub_client.py`
**Symbols:** `spark`, `ensure_jupyterhub_client`
**Evidence:** Smoke check 10 (engineer) PASS on upgraded v3-p1 and clean-room v3-p2: alice creates/reads lakehouse.smoke.spark_probe via lakehouse.spark(). SPARK+DATA: victor INSERT -> ForbiddenException can_write_data; no-token -> NotAuthorizedException.
**LastVerified:** 2026-09-26
**Commit:** 6202fd0
**LastUpdated:** 2026-09-26

---

## NODE: DEC_V3_WORKSPACE_TOKEN_VIA_HUB_AUTH_STATE
**Type:** Decision
**Priority:** HIGH
**Label:** V3 workspace tokens come from JupyterHub auth state (lab_token), refreshed by the hub
**Summary:** lab_token() (and the lab-token CLI) in the workspace image is the one place clients get the user's Keycloak token: it reads the hub's auth state via GET /hub/api/users/<name> with the server's own API token (/hub/api/user never includes auth_state). A hub refresh_user_hook refreshes when less than LAB_TOKEN_MIN_TTL (2700 s) is left; the `jupyterhub` Keycloak client (ensured by bootstrap, never only in the realm template) issues 1 h access tokens with trino+lakekeeper audiences. Role `user` needs admin:auth_state!user, else non-admin server tokens get no auth state. offline_access was rejected (30-day refresh tokens). Keycloak returns redirectUris/webOrigins as unordered sets, so drift checks compare them sorted.
**Tags:** v3, jupyterhub, token, identity, keycloak, workspace
**Edges:** _(none)_
**Files:** `v3/images/workspace/lakehouse/token.py`, `v3/config/jupyterhub/jupyterhub_config.py`, `v3/bootstrap/jupyterhub_client.py`, `v3/tests/bootstrap/test_jupyterhub_client.py`
**Symbols:** `lab_token`, `ensure_jupyterhub_client`
**Evidence:** Smoke check 8/9 PASS (token_source python:lakehouse.lab_token, azp jupyterhub). bootstrap re-run: 'users: unchanged' after the sorted-compare fix (was 'jupyterhub: updated webOrigins' every run).
**LastVerified:** 2026-09-26
**Commit:** 6202fd0
**LastUpdated:** 2026-09-26

---

## NODE: DEC_V3_DOCKER_PROXY_NAME_ALLOWLIST
**Type:** Decision
**Priority:** HIGH
**Label:** V3 DockerSpawner reaches Docker only via a name-prefix HAProxy allowlist (docker-socket-proxy)
**Summary:** The dev/prod host shares one Docker daemon, so JupyterHub never mounts the socket. A pinned tecnativa/docker-socket-proxy on the internal hub-docker network runs a custom HAProxy allowlist (config/jupyterhub/docker-proxy.cfg): container calls only by name and only for <project>-ws-*; no listing, pull, exec or volume/network delete; creation refused with host binds, privileged, cap_add, devices or host namespaces. DockerSpawner is subclassed to address containers by name, because Docker also accepts full IDs and unique ID prefixes, which are enumerable and would reach any container. Anti-pattern: never allow container IDs through a Docker socket proxy on a shared daemon.
**Tags:** v3, docker, security, jupyterhub, dockerspawner, socket-proxy
**Edges:** _(none)_
**Files:** `v3/config/jupyterhub/docker-proxy.cfg`, `v3/config/jupyterhub/jupyterhub_config.py`, `v3/compose/workspace.yaml`
**Evidence:** WORKSPACE proxy probe: 19 disallowed calls -> HTTP 403 (listing, pull, exec, create outside prefix / with host bind / privileged, inspect of non-workspace container by name, full ID or ID prefix). Integration: before/after docker ps -a / volume ls / network ls of non-v3 objects identical on the dev host.
**LastVerified:** 2026-09-26
**Commit:** 6202fd0
**LastUpdated:** 2026-09-26

---

## NODE: DEC_V3_LONG_SPARK_JOBS_VIA_AIRFLOW
**Type:** Decision
**Priority:** HIGH
**Label:** V3: long Spark jobs run as Airflow batch jobs (service identity); session renewal later
**Summary:** Owner chose option c on 2026-09-26. Interactive Spark Connect sessions are limited by the user's token (30 to 60 min), so long-running Spark work runs as Airflow batch jobs under a client-credentials service identity whose catalog token the Iceberg client renews. Only engineer and lab-admin may trigger them, and Airflow records who did. Token renewal for interactive sessions is a later follow-up (Keycloak rejects the token exchange Iceberg uses). ADR-017.
**Tags:** v3, spark, airflow, identity, batch
**Edges:**
- RELATES_TO → DEC_V3_SPARK_CONNECT_PER_SESSION_TOKEN: interactive sessions keep the user's token and its lifetime limit
**Files:** `docs/v3/DECISIONS.md`, `v3/images/workspace/lakehouse/clients.py`
**Commit:** 1afab2f
**LastUpdated:** 2026-09-26

---

## NODE: DEC_V3_AIRFLOW_UMA_MODEL_IN_BOOTSTRAP
**Type:** Decision
**Priority:** HIGH
**Label:** V3: bootstrap builds Airflow's Keycloak UMA model declaratively (not the provider's create-all CLI)
**Summary:** Airflow's Keycloak auth manager authorizes every call through a UMA decision on '<Resource>#<METHOD>' (audience airflow), so roles live in the airflow client's Authorization Services model. The provider CLI 'create-all' cannot run twice and needs the master admin password inside an Airflow container, so bootstrap/airflow_client.py builds the same model (provider 0.10.0 non-team layout) itself and repairs drift each run; resource server decisionStrategy AFFIRMATIVE, Keycloak's grant-all Default Policy/Permission removed. Groups: lab-admin Admin, engineer User+Op, analyst/viewer Viewer; Connections/Variables/Config are split into ReadSensitive (not Viewer). If the provider or Airflow adds resources or menu items, update RESOURCES/MENU_ITEMS (missing ones are denied, not granted).
**Tags:** v3, airflow, keycloak, uma, authorization, oq-16
**Edges:**
- RELATES_TO → DEC_V3_KEYCLOAK_SSO_SUBDOMAINS: Airflow's native Keycloak integration
- RELATES_TO → DEC_V3_LONG_SPARK_JOBS_VIA_AIRFLOW: only engineer/lab-admin may trigger batch DAGs
**Files:** `v3/bootstrap/airflow_client.py`, `v3/tests/bootstrap/test_airflow_client.py`, `v3/compose/airflow.yaml`
**Symbols:** `ensure_airflow_client`, `ensure_authz`, `PERMISSIONS`
**Evidence:** v3-p3-airflow 2026-09-26: alice/eddie trigger+pause 200, pool create 201; anna/victor list 200, trigger/pause/connections/variables/pool 403; second bootstrap run 'users: unchanged'; unittest test_airflow_client 8 OK
**LastVerified:** 2026-09-26
**Commit:** 3b5516e
**LastUpdated:** 2026-09-26

---

## NODE: DEC_V3_BATCH_SPARK_CREDENTIAL_NOT_TOKEN
**Type:** Decision
**Priority:** HIGH
**Label:** V3: batch Spark sessions get the lab-batch client CREDENTIAL (Iceberg renews tokens), never a fixed token
**Summary:** ADR-017 proof. lab_spark_batch opens a Spark Connect session with spark.sql.catalog.lakehouse.credential=lab-batch:<secret>, scope=openid, token-refresh-enabled=true, token-exchange-enabled=false; the Iceberg REST client and the executors' S3 remote signer then fetch/renew client-credentials tokens themselves. With lab-batch tokens cut to 120 s, a 338 s write committed (snapshot at +338 s); the same job with a fixed token failed at task close with NotAuthorizedException (no snapshot). Also: killing the Airflow task must interrupt the Spark job (SIGTERM -> spark.interruptAll), or it keeps holding the shared cluster's cores.
**Tags:** v3, spark, airflow, iceberg, token, adr-017, batch
**Edges:**
- RELATES_TO → DEC_V3_LONG_SPARK_JOBS_VIA_AIRFLOW: implements and proves it
- RELATES_TO → DEC_V3_SPARK_CONNECT_PER_SESSION_TOKEN: interactive sessions keep a fixed user token
**Files:** `v3/dags/jobs/spark_batch.py`, `v3/dags/lab_batch/__init__.py`, `v3/bootstrap/batch_client.py`
**Symbols:** `session`, `run_job`, `ensure_batch_client`, `ensure_lakekeeper`
**Evidence:** v3-p3-airflow 2026-09-26: LAB_BATCH_TOKEN_LIFESPAN=120; lab_spark_batch min_runtime_s=330 -> success, 'job took 338s = 2.8 token lifetimes', adr017_proof$snapshots committed 03:54:31; --auth static-token control -> Spark job FAILED, NotAuthorizedException, 0 snapshots
**LastVerified:** 2026-09-26
**Commit:** 3b5516e
**LastUpdated:** 2026-09-26

---

## NODE: DEC_V3_SUPERSET_TRINO_IMPERSONATION
**Type:** Decision
**Priority:** HIGH
**Label:** V3: Superset queries Trino as the logged-in user via service-account-superset impersonation
**Summary:** Superset authenticates to Trino as service-account-superset (client credentials, scope=openid) through DB_CONNECTION_MUTATOR (config/superset/lab_trino.py) and sets X-Trino-User to the Superset username for every engine pointing at the lab Trino, whatever an admin types into the URI. rules.json `impersonation` lets only that principal impersonate, never a service-account-* name; the service account itself has metadata-only rights. Trino impersonation rules cannot test the target's groups, so a no-group name gets through impersonation but then has no access (verified).
**Tags:** v3, superset, trino, impersonation, identity
**Edges:** _(none)_
**Files:** `v3/config/superset/lab_trino.py`, `v3/config/trino/rules.json`, `v3/bootstrap/superset_client.py`
**LastVerified:** 2026-09-26
**Commit:** 3b5516e
**LastUpdated:** 2026-09-26

---

## NODE: DEC_V3_FORWARD_AUTH_OAUTH2_PROXY
**Type:** Decision
**Priority:** MEDIUM
**Label:** V3: one oauth2-proxy (client console) behind Caddy forward_auth for Console and Spark UI
**Summary:** oauth2-proxy (pinned by digest) runs as Keycloak client `console` (repaired by bootstrap), cookie scoped to .LAB_DOMAIN with 1m refresh so group changes apply without a new login. Every 401 redirects to console./oauth2/start (the only registered callback); spark. uses /oauth2/auth?allowed_groups=engineer,lab-admin. Console tiles are cosmetic; each service enforces its own access. Spark UI needs spark.ui.reverseProxy=true plus Caddy stripping the Cookie header (large cookie -> 502) and rewriting http Location headers.
**Tags:** v3, console, oauth2-proxy, forward-auth, spark-ui, caddy
**Edges:** _(none)_
**Files:** `v3/compose/console.yaml`, `v3/config/caddy/Caddyfile`, `v3/config/console/index.html`, `v3/config/spark/spark-defaults.conf`
**LastVerified:** 2026-09-26
**Commit:** 3b5516e
**LastUpdated:** 2026-09-26

---

## NODE: DEC_V3_GITHUB_IDP_FIRST_BROKER_FLOW
**Type:** Decision
**Priority:** HIGH
**Label:** V3 ADR-016: custom first-broker-login flow (no auto-link, no email verification); IdP secret drift via stored SHA-256
**Summary:** bootstrap/github_idp.py always ensures flow lab-first-broker-login: review profile if missing, create user if unique with no group, else confirm link + REQUIRED re-authentication with the existing account's password. The github IdP exists only while OIDC_CLIENT_ID_GITHUB and OIDC_CLIENT_SECRET_GITHUB are both set (trustEmail off, no mappers); unset removes it and keeps its users. Keycloak masks IdP secrets on GET, so rotation is detected by a SHA-256 in the IdP config. Smoke check 16 proves it with a mock realm brokered as github-mock using the same flow.
**Tags:** v3, keycloak, github, idp, first-broker-login, adr-016
**Edges:** _(none)_
**Files:** `v3/bootstrap/github_idp.py`, `v3/tests/smoke/phase3.py`, `v3/installer/secrets.sh`
**LastVerified:** 2026-09-26
**Commit:** 3b5516e
**LastUpdated:** 2026-09-26

---

## NODE: DEC_V3_PHASE3_INTEGRATION_WIRING
**Type:** Decision
**Priority:** MEDIUM
**Label:** V3 Phase 3 integration: profile full = services listing [engineer, full]; all Phase 3 clients ensured in every profile; identity-sync re-ensures analytics
**Summary:** Compose has no profile inheritance, so Spark and Airflow services list `profiles: [engineer, full]` and the installer still passes a single --profile. Bootstrap ensures airflow (+UMA), lab-batch, superset, console and the ADR-016 flow in every profile so a profile switch needs nothing special. The shared `analytics` namespace and lab-batch's Lakekeeper grants are ensured by bootstrap and re-ensured quietly by identity-sync each tick. Postgres default limit raised to 768m (Airflow + Superset DBs, ~60 connections).
**Tags:** v3, phase3, profiles, bootstrap, identity-sync, analytics
**Edges:** _(none)_
**Files:** `v3/compose.yaml`, `v3/compose/spark.yaml`, `v3/compose/airflow.yaml`, `v3/bootstrap/__main__.py`, `v3/bootstrap/batch_client.py`, `v3/compose/identity.yaml`
**LastVerified:** 2026-09-26
**Commit:** 3b5516e
**LastUpdated:** 2026-09-26

---

## NODE: DEC_V3_ENGINEER_BUDGET_ON_MEASURED_USE
**Type:** Decision
**Priority:** MEDIUM
**Label:** V3: engineer 16 GB budget is measured on use (peak ≤ 8 GiB), not the sum of default limits
**Summary:** Phase 3 Airflow adds 3.5 GiB of ceilings, so engineer + one workspace has 17.19 GiB of default limits, over the Phase 2 '16 GB machine' budget. Lead decision (CONTRACT.md Phase 2 Budgets, amended): the engineer budget is measured on peak whole-lab use (≤ 8 GiB; measured 5.5 GiB on full with two workspaces and the 5 min Spark job); CI keeps env overrides so engineer + workspace ≤ 16 GB of limits (15.44 GiB). Defaults were not lowered (triggerer peaks at 357 MiB, so the CI 384m value leaves no headroom for users). core keeps ≤ 10 GB of limits.
**Tags:** v3, memory, budget, airflow, ci
**Edges:** _(none)_
**Files:** `v3/CONTRACT.md`, `v3/PHASE3_RESULTS.md`, `v3/compose/airflow.yaml`, `.github/workflows/v3-ci.yml`
**Evidence:** docker compose config (engineer) sum of mem_limit long-running = 15.69 GiB + WORKSPACE_MEM 1.5 GiB; tests/smoke/mem-sample.sh peak 5676 MiB on v3-p1 full
**LastVerified:** 2026-09-26
**Commit:** 3b5516e
**LastUpdated:** 2026-09-26

---

## NODE: DEC_V3_SPARK_INTERNAL_NETWORK
**Type:** Decision
**Priority:** HIGH
**Label:** V3: Spark cluster on internal `spark` network; Connect driver/UI bind to it; only gRPC 15002 on `lab`
**Summary:** The Spark UI forward-auth (spark.<domain>, engineer/lab-admin) was bypassable because spark-master:8080, spark-worker:8081 and spark-connect:4040 sat on the flat `lab` network every workspace joins. Fix: internal network `spark`; master and worker only there; spark-connect on lab+spark with driver bindAddress and SPARK_LOCAL_IP (WebUI bind host) set by start-spark.sh to its spark IP (spark-bind-ip.py: route to spark-master), so only 15002 listens on lab. caddy, keycloak, lakekeeper, seaweedfs also join `spark` (executors use internal names). App UI stays visible through the master reverse proxy at spark.<domain>/proxy/<app-id>/. spark.ui.killEnabled=false. console-health probes spark-connect:15002 instead of the master. Smoke check 15 probes the three UIs from victor's workspace kernel (must not connect) with 15002 as positive control.
**Tags:** spark, network, forward-auth, isolation, v3, security
**Edges:**
- RELATES_TO → DEC_V3_FORWARD_AUTH_OAUTH2_PROXY: closes the in-lab bypass of the Spark UI group check
- RELATES_TO → INV_V3_DOCKER_PROXY_PROJECT_SCOPE: workspaces stay on <project>_lab only
**Files:** `v3/compose.yaml`, `v3/compose/spark.yaml`, `v3/images/spark/start-spark.sh`, `v3/images/spark/spark-bind-ip.py`, `v3/config/spark/spark-defaults.conf`, `v3/tests/smoke/phase3.py`, `v3/tests/smoke/kernel_probe.py`, `v3/config/console/health/health.py`
**Evidence:** From a lab container: spark-master/spark-worker no-name, spark-connect:4040 refused, spark IPs time out, spark-connect:15002 connects; Spark log 'Start Jetty 172.21.0.x:4040 for SparkUI'; smoke check 15 PASS
**LastVerified:** 2026-09-26
**Commit:** 3b5516e
**LastUpdated:** 2026-09-26

---

## NODE: DEC_V3_USER_DAGS_SHARED_VOLUME
**Type:** Decision
**Priority:** HIGH
**Label:** V3 Phase 4: user DAGs via one shared volume, group-based rw mount, Airflow cluster policy
**Summary:** Engineer track E3/E4 needs learners to author Airflow DAGs. One compose volume <project>_dags-user is mounted rw at ~/airflow-dags in engineer/lab-admin workspaces only (LabSpawner._workspace_volumes decides per start from hub groups synced from Keycloak; mounted only if the volume exists, so profile core never creates it) and ro into dag-processor/scheduler/triggerer at dags/user/. A one-shot airflow-dags-user chowns the volume root to the workspace uid. config/airflow/policy/airflow_local_settings.py (mounted as $AIRFLOW_HOME/config) refuses DAGs not in user/<name>/ or whose id lacks u_<name>_ (visible import error), reserves u_ for user DAGs, sets task owner and tag user:<name>. The Docker proxy allowlist gains exactly <project>_dags-user (check 11 has 5 new cases). User DAGs run as lab-batch and write lakehouse.analytics.u_<user>_* (lab-batch cannot write eng_<user>); check_tracks warns this needs a lead decision. Folder separation is by policy on dag ids, not by file permissions (all workspaces are uid 1000): documented trust decision.
**Tags:** v3, phase4, airflow, user-dags, docker-proxy, jupyterhub, tracks
**Edges:**
- RELATES_TO → INV_V3_DOCKER_PROXY_PROJECT_SCOPE: the allowlist gains one named volume, still project-scoped
- RELATES_TO → DEC_V3_LONG_SPARK_JOBS_VIA_AIRFLOW: user DAGs act as lab-batch
**Files:** `v3/config/airflow/policy/airflow_local_settings.py`, `v3/config/airflow/dags-user-init.sh`, `v3/compose/airflow.yaml`, `v3/config/jupyterhub/jupyterhub_config.py`, `v3/config/jupyterhub/docker-proxy.cfg`, `v3/tests/smoke/proxy_probe.py`, `v3/tracks/engineer/_shared/trackcheck.py`
**Symbols:** `LabSpawner._workspace_volumes`, `dag_policy`, `check`
**Evidence:** dev host v3-p4-engineer: proxy_probe {"cases": 19, "unexpected": []}; docker inspect ws-eddie/ws-alice show v3-p4-engineer_dags-user:/home/jovyan/airflow-dags rw, ws-victor/ws-anna have no such mount; airflow dags list-import-errors shows the policy messages for user/stray_dag.py and user/eddie/orders_summary_dag.py
**LastVerified:** 2026-09-26
**Commit:** 3e6f45c
**LastUpdated:** 2026-09-26
**Author:** engineer-track

---

## NODE: DEC_V3_ANALYST_OWN_SCHEMA_GENERATED_TRINO_RULES
**Type:** Decision
**Priority:** HIGH
**Label:** V3 Phase 4: analysts own lakehouse.dbt_<user>; Trino rules generated from Keycloak groups
**Summary:** Analyst track A1-A3 writes lakehouse.dbt_<user>, but analysts were read-only in config/trino/rules.json. Trino file rules cannot substitute the user into a schema pattern (no ${USER}; the file then fails to load on Trino 483), so bootstrap and identity-sync generate the rules Trino reads (trino-groups/rules.json = static config/trino/rules.json + one user-and-schema rule pair per analyst member, java-regex-escaped). access-control.properties points at the generated file; bootstrap/identity-sync mount ./config/trino read-only as a directory. Access still comes only from the Keycloak group; removal takes effect on the next sync tick (measured 25 s).
**Tags:** v3, trino, authorization, analyst, phase4, identity-sync
**Edges:**
- RELATED_TO → DEC_V3_IDENTITY_SYNC_SERVICE: same sync loop writes the rules
- RELATED_TO → REG_V3_STALE_BIND_MOUNT_CONFIG_ON_UPGRADE: Trino no longer bind-mounts rules.json; config hash still covers config/trino
**Files:** `v3/bootstrap/trino_groups.py`, `v3/bootstrap/__main__.py`, `v3/config/trino/access-control.properties`, `v3/config/trino/rules.json`, `v3/compose/bootstrap.yaml`, `v3/compose/engines.yaml`, `v3/tests/bootstrap/test_trino_user_schemas.py`
**Symbols:** `trino_groups.write_rules`, `trino_groups.render_rules`, `trino_groups.user_schema_rules`, `sync_trino_groups`
**Evidence:** python3 -m unittest discover -s v3/tests/bootstrap -> 46 OK (6 in test_trino_user_schemas); v3-p1 upgrade: bootstrap log '[trino] /var/lib/lab/trino-groups/rules.json: written'; smoke check 17 A1-A4 as anna PASS; analyst workstream: anna denied in analytics/dbt_eddie, victor denied creating dbt_victor
**LastVerified:** 2026-09-26
**Commit:** 3e6f45c
**LastUpdated:** 2026-09-26
**Author:** integrator

---

## NODE: DEC_V3_SUPERSET_API_BEARER_KEYCLOAK
**Type:** Decision
**Priority:** MEDIUM
**Label:** V3 Phase 4: Superset API accepts the user's own Keycloak token (azp jupyterhub); role lab_author
**Summary:** The A4 checkpoint must read and reset Superset objects as the learner, from the workspace, where the only credential is lab_token(). LabSecurityManager.request_loader (config/superset/lab_bearer.py) accepts a Bearer access token verified against the realm JWKS, issuer from LAB_AUTH_URL, typ Bearer, azp in LAB_SUPERSET_BEARER_CLIENTS (default jupyterhub), for an existing active Superset user only; roles are recomputed from the token groups via AUTH_ROLES_MAPPING. Writes still need Superset's CSRF token. New role lab_author (can_write Dataset) for analyst and engineer, since Gamma cannot create datasets (HTTP 403).
**Tags:** v3, superset, auth, analyst, phase4
**Edges:**
- RELATED_TO → DEC_V3_SUPERSET_TRINO_IMPERSONATION: queries still run in Trino as the user
- RELATED_TO → INV_V3_PUBLIC_ORIGIN_SINGLE_SOURCE: issuer derived from LAB_AUTH_URL
**Files:** `v3/config/superset/lab_bearer.py`, `v3/config/superset/superset_config.py`, `v3/config/superset/lab_init.py`, `v3/images/superset/Dockerfile`, `v3/tracks/analyst/_shared/superset_api.py`
**Symbols:** `lab_bearer.load_user`, `lab_bearer.verify`, `LabSecurityManager.request_loader`, `ensure_role_permissions`
**Evidence:** smoke check 17 A4 as anna: solve, check PASS, reset, check not-yet (v3-p1 upgrade and v3-p4 clean runs, PHASE4_RESULTS.md)
**LastVerified:** 2026-09-26
**Commit:** 3e6f45c
**LastUpdated:** 2026-09-26
**Author:** integrator

---

## NODE: DEC_V3_TRACK_USER_PRODUCTION_TABLES
**Type:** Decision
**Priority:** MEDIUM
**Label:** V3 Phase 4: engineer DAG output goes to lakehouse.analytics.u_<user>_*, and counts as the learner's own
**Summary:** E3/E4 DAGs run as lab-batch, which can write analytics but not eng_<user>. Lead decision at Phase 4 integration: their output tables are lakehouse.analytics.u_<user>_* ({prod} in module.json), treated as the learner's own objects, so lab-tracks reset may drop them (trackcheck only drops analytics tables with the user's prefix). check_tracks.py accepts analytics.{prod}* and still warns for any other shared-schema reset. Documented in v3/tracks/README.md and CONTRACT.md (Phase 4 integration conventions).
**Tags:** v3, tracks, airflow, phase4, reset
**Edges:**
- RELATED_TO → DEC_V3_USER_DAGS_SHARED_VOLUME: the DAGs that write these tables
- RELATED_TO → DEC_V3_LONG_SPARK_JOBS_VIA_AIRFLOW: lab-batch identity
**Files:** `v3/tools/check_tracks.py`, `v3/tests/lint/test_check_tracks.py`, `v3/tracks/README.md`, `v3/tracks/engineer/_shared/trackcheck.py`, `v3/CONTRACT.md`
**Evidence:** python3 v3/tools/check_tracks.py -> 0 error(s), 0 warning(s); test_check_tracks OK
**LastVerified:** 2026-09-26
**Commit:** 3e6f45c
**LastUpdated:** 2026-09-26
**Author:** integrator
