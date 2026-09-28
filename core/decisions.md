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
**Files:** `legacy/v2/docker-compose.yml`, `legacy/v2/docker-compose.iceberg.yml`, `legacy/v2/scripts/init-compute.sh`
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
**Files:** `legacy/v2/docker-compose.yml`
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
**Files:** `legacy/v2/docker-compose.yml`, `legacy/v2/start-lakehouse.sh`, `legacy/v2/scripts/install/migrate-to-named-volumes.sh`
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
**Files:** `legacy/v2/docker-compose.yml`, `legacy/v2/scripts/lib/init-core.sh`, `legacy/v2/scripts/init-infrastructure.sh`, `legacy/v2/scripts/init-compute.sh`
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
**Files:** `legacy/v2/scripts/init-infrastructure.sh`, `legacy/v2/scripts/lib/init-core.sh`
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
**Files:** `legacy/v2/docker-compose.yml`, `legacy/v2/scripts/configure-services.sh`, `legacy/v2/scripts/init-dashboards.sh`, `legacy/v2/scripts/show-credentials.sh`
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
**Files:** `legacy/v2/start-lakehouse.sh`, `legacy/v2/scripts/provision-user.sh`
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
**Files:** `legacy/v2/config/mcp-server.yaml`, `legacy/v2/docs/MCP.md`, `legacy/v2/.lakehouse-services.conf`
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
**Files:** `install.sh`, `legacy/v2/start-lakehouse.sh`, `legacy/v2/scripts/install/fix-credentials.sh`, `legacy/v2/scripts/install/migrate-to-named-volumes.sh`
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
**Files:** `.github/workflows/startup-test.yml`, `legacy/v2/tests/run_stack_health_tests.sh`
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
**Files:** `.gitignore`, `legacy/v2/start-lakehouse.sh`
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
**Files:** `.github/workflows/ci.yml`, `legacy/v2/docs/TESTING.md`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `e7047ce`

---

## NODE: DEC_V3_STACK_DIRECTION
**Type:** Decision
**Priority:** HIGH
**Label:** V3: new stack — SeaweedFS, Lakekeeper, Spark 4.1, Trino, Airflow 3, Superset 6
**Summary:** Agreed 2026-09-25 to build V3 on a `v3` branch while V2 stays maintained on main. MinIO (unmaintained since Feb 2026) is replaced by SeaweedFS ≥4.40. All tables become Iceberg tables in a Lakekeeper REST catalog. Engines are Spark 4.1 (Iceberg 1.11 runtime; 4.2 waits for Iceberg support), Trino and DuckDB, with Airflow 3.1+ and pinned Superset 6. Full rationale: docs/DECISIONS.md ADR-001/002/003/009/013.
**Tags:** v3, architecture, storage, catalog, spark
**Edges:**
- MITIGATES → REG_ICEBERG_JAR_VERSIONS: Iceberg becomes core with a REST catalog instead of an overlay
- RELATES_TO → DEC_MIGRATE_FROM_BITNAMI_OFFICIAL_APACHE_4B39: V3 keeps official apache/spark images, moving 3.5 → 4.1
**Files:** `docs/README.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/ROADMAP.md`
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
**Files:** `docs/DECISIONS.md`, `docs/ARCHITECTURE.md`
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
**Files:** `docs/DECISIONS.md`, `docs/OPEN_QUESTIONS.md`, `spikes/s1-catalog-storage/RESULTS.md`, `spikes/s2-duckdb-sts/RESULTS.md`
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
**Files:** `docs/DECISIONS.md`, `docs/ROADMAP.md`
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
**Files:** `docs/DECISIONS.md`, `docs/ARCHITECTURE.md`
**Commit:** 6f267e7
**LastUpdated:** 2026-09-25

---

## NODE: DEC_V3_AI_ASSIST_MCP_GATEWAY
**Type:** Decision
**Priority:** MEDIUM
**Label:** V3 (proposed): context-aware AI via MCP, user-scoped, through a model gateway
**Summary:** V3 Phase 5: lab context (dbt lineage, catalog, Trino, Airflow runs, current lesson) comes from MCP servers, using the official dbt-mcp and existing servers first plus a thin lab-context server. Assistants are Jupyter AI v3 and Claude Code in the workspace. The assistant acts as the user via their Keycloak token, read-only by default. A model gateway holds keys and budgets, and tutor mode applies inside learning tracks. OQ-8 decided by the owner 2026-09-26: hosted providers are OFF by default; only an admin can enable one, with its key. Local models are offered for private data through any local OpenAI-compatible server (the owner runs llama.cpp llama-server); with nothing enabled, no outbound AI calls. ADR-014.
**Tags:** v3, ai, mcp, tutor
**Edges:**
- RELATES_TO → DEC_REMOVE_MCP_SERVER_COMPLETELY_FROM_67B4: V2's custom MCP server was removed; V3 composes existing servers
**Files:** `docs/DECISIONS.md`, `docs/ARCHITECTURE.md`, `docs/OPEN_QUESTIONS.md`
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
**Files:** `docs/DECISIONS.md`, `docs/ARCHITECTURE.md`, `docs/OPEN_QUESTIONS.md`
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

⚠ CORRECTED 2026-09-27: Since the Phase 4 follow-up the proxy's HAProxy file checks METHOD and PATH only (container names by prefix, no ids, no listing). The create-body refusals (host binds, privileged, cap_add, devices, host namespaces, foreign volumes/mounts/networks) moved to docker-guard (bootstrap/docker_guard.py), which parses, validates and re-serializes bodies; the proxy's body regexes were bypassable and are removed (DEC_V3_DOCKER_GUARD_PARSE_VALIDATE_RESERIALIZE, REG_V3_DOCKER_PROXY_BODY_REGEX_BYPASS). The proxy is reachable only from the guard (network docker-api).
**Tags:** v3, docker, security, jupyterhub, dockerspawner, socket-proxy
**Edges:** _(none)_
**Files:** `v3/config/jupyterhub/docker-proxy.cfg`, `v3/config/jupyterhub/jupyterhub_config.py`, `v3/compose/workspace.yaml`
**Evidence:** WORKSPACE proxy probe: 19 disallowed calls -> HTTP 403 (listing, pull, exec, create outside prefix / with host bind / privileged, inspect of non-workspace container by name, full ID or ID prefix). Integration: before/after docker ps -a / volume ls / network ls of non-v3 objects identical on the dev host.
**LastVerified:** 2026-09-26
**Commit:** 3e6f45c
**LastUpdated:** 2026-09-27

---

## NODE: DEC_V3_LONG_SPARK_JOBS_VIA_AIRFLOW
**Type:** Decision
**Priority:** HIGH
**Label:** V3: long Spark jobs run as Airflow batch jobs (service identity); session renewal later
**Summary:** Owner chose option c on 2026-09-26. Interactive Spark Connect sessions are limited by the user's token (30 to 60 min), so long-running Spark work runs as Airflow batch jobs under a client-credentials service identity whose catalog token the Iceberg client renews. Only engineer and lab-admin may trigger them, and Airflow records who did. Token renewal for interactive sessions is a later follow-up (Keycloak rejects the token exchange Iceberg uses). ADR-017.
**Tags:** v3, spark, airflow, identity, batch
**Edges:**
- RELATES_TO → DEC_V3_SPARK_CONNECT_PER_SESSION_TOKEN: interactive sessions keep the user's token and its lifetime limit
**Files:** `docs/DECISIONS.md`, `v3/images/workspace/lakehouse/clients.py`
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
**Summary:** Engineer track E3/E4 needs learners to author Airflow DAGs. One compose volume <project>_dags-user holds one folder per user and is mounted ro into dag-processor/scheduler/triggerer at dags/user/. REPAIR ROUND (verifier: eddie could plant ~/airflow-dags/alice/x.py, accepted as alice's DAG, because every workspace is uid 1000 and the whole volume was mounted rw): an engineer/lab-admin workspace now mounts ONLY its own folder, a volume Mount with VolumeOptions.Subpath=<username> at ~/airflow-dags/<username> (LabSpawner._workspace_volumes sets self.mounts per start). Docker needs the subpath to exist, so JupyterHub (root in its container) mounts the volume at /srv/dags-user and creates <username>/ owned 1000:100 (ensure_user_dag_folder: one-segment name, refuses symlinks/non-dirs). The one-shot airflow-dags-user makes the volume root root:root 0755 and writes the marker .lab-user-dags; the hub gives DAG folders only when the marker exists (profile core: the volume exists for the hub mount but no Airflow). docker-proxy.cfg: no Binds of dags-user; exactly one Mounts entry (docker-py field order, Source <project>_dags-user, Subpath = target's last segment via a NAMED PCRE group — HAProxy compiles without auto-capture, \1 fails), a second Mounts key refused. The policy (airflow_local_settings.py) also refuses a dag_id carrying a longer existing user's prefix (u_eddie_x_ in eddie/). Smoke: check 11 30 cases; check 17 dags_isolation (only own mount under ~/airflow-dags, own write ok, neighbour mkdir EACCES). User DAGs still run as lab-batch (trusted engineers).
**Tags:** v3, phase4, airflow, user-dags, docker-proxy, jupyterhub, tracks
**Edges:**
- RELATES_TO → INV_V3_DOCKER_PROXY_PROJECT_SCOPE: the allowlist gains one named volume, still project-scoped
- RELATES_TO → DEC_V3_LONG_SPARK_JOBS_VIA_AIRFLOW: user DAGs act as lab-batch
**Files:** `v3/config/airflow/policy/airflow_local_settings.py`, `v3/config/airflow/dags-user-init.sh`, `v3/compose/airflow.yaml`, `v3/compose/workspace.yaml`, `v3/config/jupyterhub/jupyterhub_config.py`, `v3/config/jupyterhub/docker-proxy.cfg`, `v3/tests/smoke/proxy_probe.py`, `v3/tests/smoke/tracks.py`, `v3/tests/lint/test_user_dags.py`, `v3/tracks/engineer/_shared/trackcheck.py`
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

---

## NODE: DEC_V3_DOCKER_GUARD_PARSE_VALIDATE_RESERIALIZE
**Type:** Decision
**Priority:** HIGH
**Label:** V3: request bodies to Docker are checked by a stdlib docker-guard that parses, validates and re-serializes (no body regexes)
**Summary:** Topology jupyterhub -> docker-guard (hub-docker) -> docker-socket-proxy (docker-api, only guard+proxy) -> socket. The guard (bootstrap/docker_guard.py, python -m bootstrap.docker_guard on the pinned bootstrap image) is the single source of the request-body policy: it allows only DockerSpawner's calls (derived from real traffic: version, image/volume/container inspect by name, container create/start/stop/delete, volume create), decodes strictly, allows only exact canonical keys, validates values, and forwards only its json.dumps output with a new Content-Length and a query rebuilt from validated values; failures are 403 + one log line (never the body). The socket proxy keeps a method/path allowlist, no body ACLs. Chosen over more HAProxy regexes because the policy must read the same object Docker reads. Changing what DockerSpawner sends requires changing validate_create and its unit tests together.
**Tags:** v3, docker, security, jupyterhub, socket-proxy, docker-guard
**Edges:**
- IMPLEMENTS → INV_V3_DOCKER_PROXY_PROJECT_SCOPE: the guard enforces the project scope on decoded bodies
- FIXES → REG_V3_DOCKER_PROXY_BODY_REGEX_BYPASS: parser differential removed
- AMENDS → DEC_V3_DOCKER_PROXY_NAME_ALLOWLIST: bodies moved out of the proxy
**Files:** `v3/bootstrap/docker_guard.py`, `v3/compose/workspace.yaml`, `v3/compose.yaml`, `v3/config/jupyterhub/docker-proxy.cfg`, `v3/tests/bootstrap/test_docker_guard.py`, `v3/CONTRACT.md`
**LastVerified:** 2026-09-26
**Commit:** 3e6f45c
**LastUpdated:** 2026-09-27

---

## NODE: DEC_V3_AI_GATEWAY_LITELLM_OSS_BUILD
**Type:** Decision
**Priority:** HIGH
**Label:** V3 Phase 5: ai-gateway = LiteLLM built from PyPI without litellm-enterprise; keys minted only via the ai-keys broker; providers off by default
**Summary:** OQ-7: the model gateway is LiteLLM 1.102.1, but NOT the upstream image: it ships enterprise/ and the proprietary litellm-enterprise package (no redistribution, production needs a subscription), and our images are public. images/ai-gateway installs a GENERATED full lock (relock.sh drops litellm-enterprise, fails on any other proprietary license) with --no-deps; verify.py fails the build if a proprietary package/module is present; Prisma client/engines generated at build, PRISMA_OFFLINE_MODE at runtime; cost map/beta headers/presets local (no GitHub fetch). Only ai-gateway and ai-keys (bootstrap/ai_gateway.py) hold the master key; JupyterHub mints/rotates/revokes per-user keys through ai-keys with AI_GATEWAY_HUB_TOKEN. Users are role internal_user_viewer with a per-USER budget (rotation never resets spend). Providers exist only when enabled in .env/.secrets.env (render_config.py); none -> empty model list + 'AI isn't configured; ask your lab admin.' (503) from a CustomLogger pre-call hook. Never call the gateway's /health (it calls every model) — use /health/liveliness.

 Follow-up (2026-09-27): the gateway is no longer reachable by users directly. It lives only on the `ai` network, and user keys reach it only through ai-frontdoor, whose ROUTES are the single allowlist of user-callable routes (INV_V3_AI_FRONTDOOR_ONLY_USER_PATH). lab_hooks' pre-call hook sets the end user of every call to the key's own user_id (REG_V3_AI_END_USER_SPOOFABLE_IN_SPEND_LOGS).
**Tags:** v3, ai, gateway, litellm, license, budget, phase5
**Edges:**
- RELATES_TO → DEC_V3_AI_ASSIST_MCP_GATEWAY: implements the gateway half of ADR-014
**Files:** `v3/images/ai-gateway/Dockerfile`, `v3/images/ai-gateway/relock.sh`, `v3/images/ai-gateway/verify.py`, `v3/config/ai/render_config.py`, `v3/config/ai/lab_hooks.py`, `v3/bootstrap/ai_gateway.py`, `v3/compose/ai.yaml`, `v3/installer/ai.sh`
**Symbols:** `render`, `LabHooks`, `mint`, `Gateway`
**Evidence:** python3 -m unittest discover -s v3/tests/ai -> OK; v3/tests/ai/gateway-e2e.sh on a --ai-mock full lab -> AI GATEWAY E2E: PASS
**LastVerified:** 2026-09-27
**Commit:** bb0cd2f
**LastUpdated:** 2026-09-27
**Author:** GATEWAY workstream

---

## NODE: DEC_V3_WORKSPACE_AI_PERSONA_KEY_PER_SPAWN
**Type:** Decision
**Priority:** HIGH
**Label:** V3 Phase 5 workspace AI: Jupyternaut-based "Lab Assistant" persona, per-spawn gateway key via ai-keys broker, tutor mode from pristine tutor.md
**Summary:** Jupyter AI v3 is installed with the [jupyternaut] extra (LiteLLM+LangChain+MCP) and a lab persona lakehouse.ai_persona:LabAssistant (entry point via a hand-written dist-info in /opt/lakehouse/python) is the default persona; it only ever calls the lab gateway (openai/<LAB_AI_MODEL>, api_base LAB_AI_GATEWAY_URL/v1, the user's LAB_AI_KEY) and answers "AI isn't configured; ask your lab admin." without a key. JupyterHub mints a NEW key at every spawn through the ai-keys broker (AI_GATEWAY_HUB_TOKEN; never the master key) and revokes it on stop; the key reaches the workspace only as container Env (LAB_AI_*, OPENAI_*), so docker-guard's create allowlist needed no change (Env is NAME=value only). Tutor mode (default on, `lab-ai tutor off` in ~/.lakehouse/ai.json) puts the module's PRISTINE /opt/lakehouse/tracks/.../tutor.md into the system prompt and restricts tools to read-only notebook tools + the lab's stdio MCP servers. Claude Code is never in the image: `lab-ai install-claude-code` downloads the pinned version, checks its sha256 pin (versions.env), installs into ~/.local with a wrapper pointing at the gateway.

 Follow-up (2026-09-27): only gateway-routed personas are offered. lakehouse/ai_persona_manager.py LabPersonaManager (PersonaManagerExtension.persona_manager_class) loads only ALLOWED_PERSONAS {lab-assistant: lakehouse.ai_persona:LabAssistant}, matched by name and object reference, and no .jupyter/personas files. It drops the jupyter_ai_acp_client ACP agents (claude/codex/copilot/goose/kilo/kiro/mistral-vibe/opencode), which talk to their own providers, and the stock Jupyternaut, whose model string and api_base are free. The Claude ACP persona was not kept because it needs claude-agent-acp and is not wired to the gateway. Claude Code = the lab-ai CLI pointed at the front door. Workspace env LAB_AI_GATEWAY_URL/OPENAI_BASE_URL = http://ai-frontdoor:4000.
**Tags:** v3, phase5, ai, jupyter-ai, tutor, gateway, claude-code, mcp
**Edges:**
- RELATES_TO → DEC_V3_AI_ASSIST_MCP_GATEWAY: implements the workspace side
- RELATES_TO → INV_V3_DOCKER_PROXY_PROJECT_SCOPE: AI key injected as Env only; guard unchanged
- RELATES_TO → DEC_V3_WORKSPACE_TOKEN_VIA_HUB_AUTH_STATE: MCP stdio servers get JUPYTERHUB_* in memory so lab_token() works
**Files:** `v3/config/jupyterhub/jupyterhub_config.py`, `v3/images/workspace/lakehouse/ai.py`, `v3/images/workspace/lakehouse/ai_persona.py`, `v3/images/workspace/lakehouse/ai_cli.py`, `v3/images/workspace/config/jupyter_server_config.py`, `v3/images/workspace/Dockerfile`, `v3/images/workspace/requirements.in`, `v3/tests/workspace/test_lab_ai.py`, `v3/tests/workspace/ai_chat_probe.py`
**Symbols:** `mint_ai_key`, `LabSpawner.get_env`, `LabSpawner.stop`, `LabAssistant`, `current_module`, `system_prompt`, `cmd_install_claude_code`
**Evidence:** v3-p5-wsai (full, mock gateway): wsai_test.sh 0 failures (chat round-trip, tutor.md verbatim in the mock's recorded system prompt, tutor off removes it, victor own key); stop->revoke, start->new key; unittest tests/workspace/test_lab_ai.py 39 OK
**LastVerified:** 2026-09-27
**Commit:** bb0cd2f
**LastUpdated:** 2026-09-27
**Author:** WORKSPACE-AI

---

## NODE: DEC_V3_MCP_SERVERS_AS_USER
**Type:** Decision
**Priority:** HIGH
**Label:** V3 Phase 5: workspace MCP servers act as the user (lab_token per call), read-only; OQ-9 = own thin Trino wrapper
**Summary:** The assistant's MCP servers run in the user's workspace over stdio (images/workspace/mcp, `lab-mcp`, registry /opt/lakehouse/mcp/servers.json) in their own venv (dbt-mcp pins mcp==1.26.0; the notebook env has mcp 1.30.0). Each tool call fetches a fresh token from lab_token(); outputs are scrubbed of token-shaped strings; Trino tool is SELECT/SHOW/DESCRIBE/EXPLAIN only (sqlglot AST), <=200 rows, <=30 s via Trino query_max_run_time. OQ-9: community Trino MCP servers rejected (tuannvm: service identity + impersonation; weijie-tan3/mcp-trino-python: no bearer passthrough; akko-mcp-trino: JWT fixed at process start, no refresh). dbt-mcp 2.4.0 runs with an allowlist (list, parse, get_lineage_dev, get_node_details_dev) and every dbt-Platform feature off; verified working with --network none. airflow_runs needs an Airflow plugin (lab_auth: POST /lab-auth/token exchanges a jupyterhub-azp Keycloak token for an Airflow API JWT carrying it) because the Keycloak auth manager mints API tokens only from passwords.
**Tags:** v3, phase5, mcp, ai, trino, dbt, oq-9, identity
**Edges:**
- RELATES_TO → DEC_V3_AI_ASSIST_MCP_GATEWAY: implements the MCP half of ADR-014
- RELATES_TO → DEC_V3_WORKSPACE_TOKEN_VIA_HUB_AUTH_STATE: every tool gets its token from lab_token()
- RELATES_TO → DEC_V3_SUPERSET_API_BEARER_KEYCLOAK: superset_dashboard_datasets uses the same bearer path
**Files:** `v3/images/workspace/mcp/lab_mcp/common.py`, `v3/images/workspace/mcp/lab_mcp/trino_client.py`, `v3/images/workspace/mcp/lab_mcp/sqlguard.py`, `v3/images/workspace/mcp/lab_mcp/context.py`, `v3/images/workspace/mcp/lab_mcp/dbt_launcher.py`, `v3/images/workspace/mcp/README.md`, `v3/tests/smoke/ai_check.py`, `v3/tests/smoke/ai_agent_probe.py`
**Symbols:** `trino_client.run`, `sqlguard.check`, `common.scrub`, `context.airflow_runs`, `dbt_launcher.server_env`
**Evidence:** v3-p5-mcp (full, --ai-mock): LAB_SMOKE_ONLY=18 ./lab test -> alice: 8 Iceberg tables from Superset + dbt lineage, load times == Trino $snapshots; victor: private draft dashboard refused, write refused, system.runtime.queries of alice = 0; no JWT/key in outputs; mock-only (ai-mock saw only model mock-model)
**LastVerified:** 2026-09-27
**Commit:** bb0cd2f
**LastUpdated:** 2026-09-27
**Author:** MCP+TESTS (Phase 5)

---

## NODE: DEC_V3_PHASE5_INTEGRATION_WIRING
**Type:** Decision
**Priority:** MEDIUM
**Label:** V3 Phase 5 integration: ai profile wiring, mock-only tests, no bootstrap step for the gateway
**Summary:** compose.yaml includes compose/ai.yaml (ai-gateway-db, ai-gateway, ai-keys in [full]; ai-mock in its own profile ai-mock, added by lab_compose only when .env has LAB_AI_MOCK=true). Pins (LiteLLM, Prisma, dbt-mcp, MCP SDK, sqlglot, Claude Code version+sha256) promoted to versions.env; .pins/ removed. bootstrap/__main__.py gets no AI step: the gateway DB is a postgres-image one-shot and the admin side is the long-lived ai-keys broker. Workspace image merges WORKSPACE-AI (Jupyter AI persona, Claude Code pin) with MCP+TESTS (separate MCP venv); Airflow lab_auth plugin mounted into airflow-api only. install.sh --non-interactive never enables a provider; tests configure only the mock.

 Follow-up (2026-09-27): new `ai` network (compose.yaml; members ai-gateway only there, ai-frontdoor/ai-keys also on lab, postgres, test-only ai-mock and smoke). Adding it to postgres recreates postgres once on upgrade (dependents restart via depends_on restart:true, REG_V3_POSTGRES_RECREATE_BREAKS_DB_CLIENTS_ON_UPGRADE). New [full] service ai-frontdoor on the bootstrap image. Smoke check 18 now also asserts the front door from inside alice's workspace and the persona list; run.sh mounts tests/workspace at /opt/tests-workspace.

Repair round (2026-09-27): tests/ai/gateway-e2e.sh never configures the `local` provider by default; its local-via-mock step is opt-in (LAB_E2E_LOCAL_VIA_MOCK=1, for hosts with no real model server such as CI), and it refuses to run unless the gateway's rendered providers are exactly [mock] (REG_V3_GATEWAY_E2E_CONFIGURES_LOCAL_PROVIDER_BY_DEFAULT).
**Tags:** v3, phase5, ai, gateway, integration, compose, profiles
**Edges:**
- RELATES_TO → DEC_V3_AI_GATEWAY_LITELLM_OSS_BUILD: gateway image and broker wired here
- RELATES_TO → DEC_V3_MCP_SERVERS_AS_USER: MCP venv and lab_auth plugin wired here
- RELATES_TO → DEC_V3_WORKSPACE_AI_PERSONA_KEY_PER_SPAWN: hub env LAB_AI_KEYS_URL/AI_GATEWAY_HUB_TOKEN wired here
- RELATES_TO → INV_V3_DOCKER_PROXY_PROJECT_SCOPE: key injected as Env only; guard allowlist unchanged, check 11 stays 54 cases
- RELATES_TO → INV_V3_PUBLIC_ORIGIN_SINGLE_SOURCE: ai-no-provider.sh now sources lib.sh lab_settings for LAB_AUTH_URL
**Files:** `v3/compose.yaml`, `v3/compose/ai.yaml`, `v3/compose/workspace.yaml`, `v3/compose/airflow.yaml`, `v3/versions.env`, `v3/images/workspace/Dockerfile`, `v3/config/airflow/plugins/lab_auth.py`, `v3/tests/smoke/ai-no-provider.sh`, `v3/tools/compose-check.sh`, `v3/tests/lint/test_images_matrix.py`, `.github/workflows/v3-ci.yml`, `.github/workflows/v3-nightly.yml`, `.github/workflows/v3-images.yml`
**Evidence:** v3-p1 upgrade: ./install.sh --non-interactive rc 0, then ./lab ai status models [] and tests/smoke/ai-no-provider.sh PASS; compose-check core/engineer/full OK
**LastVerified:** 2026-09-27
**Commit:** bb0cd2f
**LastUpdated:** 2026-09-27

---

## NODE: DEC_V3_AI_FRONTDOOR_ALLOWLIST_PROXY
**Type:** Decision
**Priority:** HIGH
**Label:** V3 Phase 5 follow-up: stdlib ai-frontdoor proxy with an exact route allowlist between workspaces and LiteLLM
**Summary:** LiteLLM's MIT build has no admin_only_routes, and a user key could call GET /health (fans out real requests to every model, no budget charge) and /model/info, /v1/model/info (each deployment's api_base). Chosen: a small stdlib proxy on the bootstrap image (like docker-guard), not Caddy, because it also needs per-route query rules, a Bearer-key requirement, header allowlists in both directions (drops x-litellm-* response headers that name api_base, and LiteLLM customer-id/control request headers), body caps and SSE streaming. It matches (method, path) exactly and case-sensitively, refuses %-encoding/dot segments/`//` rather than normalizing, rebuilds the query, and forwards the canonical target. The gateway moved to a new `ai` network (with postgres, ai-keys, ai-frontdoor, test-only ai-mock/smoke). Budget display in lab-ai uses GET /v2/user/info (own user, no keys) instead of /user/info or /key/info.
**Tags:** v3, ai, gateway, proxy, allowlist, decision, phase5
**Edges:**
- ESTABLISHES → INV_V3_AI_FRONTDOOR_ONLY_USER_PATH: front door = single source of truth for user-callable routes
- FIXES → REG_V3_AI_GATEWAY_USER_KEY_REACHES_ADMIN_ROUTES
- RELATES_TO → DEC_V3_DOCKER_GUARD_PARSE_VALIDATE_RESERIALIZE: same pattern (validate, forward only canonical values)
- RELATES_TO → DEC_V3_AI_GATEWAY_LITELLM_OSS_BUILD
**Files:** `v3/bootstrap/ai_frontdoor.py`, `v3/compose/ai.yaml`, `v3/compose.yaml`, `v3/compose/identity.yaml`, `v3/compose/test.yaml`, `v3/images/workspace/lakehouse/ai_cli.py`
**LastVerified:** 2026-09-27
**Commit:** 0dc8f05
**LastUpdated:** 2026-09-27

---

## NODE: DEC_V3_LOCAL_MODEL_API_KEY_GATEWAY_ONLY
**Type:** Decision
**Priority:** HIGH
**Label:** V3: the local model server's API key is held only by the ai-gateway
**Summary:** Owner chose option 1 for the host-LAN gap (2026-09-27): protect the local model server (llama.cpp llama-server) with an API key that only the ai-gateway knows. `./lab ai set-local URL --api-key-file FILE` stores it as LAB_AI_LOCAL_API_KEY in .secrets.env (mode 600, never printed; status shows only 'set'). `--no-api-key` and `set-local none` remove it, and render_config passes it to the local deployment. This only closes the gap once the model server enforces the key (llama-server --api-key-file). Note that llama.cpp leaves /health and /v1/models public even with a key; check enforcement with a protected endpoint such as /props.
**Tags:** v3, ai, llama.cpp, security, gateway
**Edges:**
- MITIGATES → WATCH_V3_WORKSPACE_LAN_EGRESS_BYPASSES_GATEWAY: a keyed model server refuses direct calls from workspaces
**Files:** `v3/lab`, `v3/installer/ai.sh`, `v3/config/ai/render_config.py`, `v3/tests/installer/test_unit.sh`
**Symbols:** `ai_set_local_key`, `cmd_ai`
**Evidence:** bash v3/tests/installer/run.sh -> 338 passed (key in .secrets.env only, never printed, removed by --no-api-key and set-local none); dev host: gateway env LAB_AI_LOCAL_API_KEY length 64
**Commit:** c885a8a
**LastUpdated:** 2026-09-27

---

## NODE: DEC_V3_LOCAL_MODEL_QUIET_HOURS_IN_GATEWAY
**Type:** Decision
**Priority:** HIGH
**Label:** V3 Phase 6: local-model quiet hours are enforced in the gateway pre-call hook, before routing
**Summary:** Owner decision (2026-09-27): quiet hours for the local model live in the ai-gateway. `./lab ai quiet-hours HH:MM-HH:MM --tz Area/City | off` writes LAB_AI_QUIET_HOURS/LAB_AI_QUIET_TZ to .env (off = empty values, default off; installer asks once when a local URL is set). render_config.py writes the window plus `local_models` (local, and lab-default when it resolves to local) into state.json; lab_hooks' pre-call hook calls the pure render_config.quiet_refusal(state, model, now) and raises 503 type ai_quiet_hours with "The lab's local AI model is resting until HH:MM <tz> ..." and Retry-After. Hosted and mock are unaffected; lab-default is not re-routed to hosted. Wall-clock window in the zone (DST-aware); a bad setting stops the gateway at start. Needs compose/ai.yaml to pass LAB_AI_QUIET_HOURS/LAB_AI_QUIET_TZ to ai-gateway.
**Tags:** ai, gateway, quiet-hours, local-model, v3, phase6
**Edges:**
- RELATES_TO → DEC_V3_AI_GATEWAY_LITELLM_OSS_BUILD: another lab_hooks pre-call rule
- RELATES_TO → REG_V3_GATEWAY_E2E_CONFIGURES_LOCAL_PROVIDER_BY_DEFAULT: quiet-hours-e2e.sh configures local (pointed at the mock) only with LAB_E2E_LOCAL_VIA_MOCK=1
**Files:** `v3/config/ai/render_config.py`, `v3/config/ai/lab_hooks.py`, `v3/config/ai/start.sh`, `v3/installer/ai.sh`, `v3/lab`, `v3/tests/ai/test_quiet_hours.py`, `v3/tests/ai/test_lab_quiet_hours.py`, `v3/tests/ai/quiet-hours-e2e.sh`, `v3/tests/ai/quiet_hours_e2e.py`
**Symbols:** `quiet_refusal`, `quiet_until`, `parse_quiet_hours`, `LabHooks.async_pre_call_hook`, `ai_set_quiet_hours`, `ai_ask_quiet_hours`
**Evidence:** python3 -m unittest discover -s v3/tests/ai -> OK (quiet hours: injected clock, midnight, DST); LAB_E2E_LOCAL_VIA_MOCK=1 v3/tests/ai/quiet-hours-e2e.sh on a mock-only lab -> QUIET HOURS E2E: PASS (refused requests never reach the mock)
**LastVerified:** 2026-09-27
**Commit:** 699c5a1
**LastUpdated:** 2026-09-27
**Author:** AI-POLISH workstream

---

## NODE: DEC_V3_MIGRATION_LANDING_BUCKET_READONLY_KEY
**Type:** Decision
**Priority:** MEDIUM
**Label:** V3 Phase 6: V2 -> V3 migration is a tested guide (rclone into bucket `landing`, read-only landing key), not a tool
**Summary:** Owner decision 2026-09-27: no migration tool. docs/MIGRATION.md copies each V2 MinIO bucket with a digest-pinned rclone container (on V2's and V3's networks at once, Docker >= 25) into SeaweedFS bucket `landing` under v2/<bucket>/ (never `warehouse`, which the catalog owns), `copy` only, verified with size --json + check --one-way (--download for objects without MD5). Admin keys live only in a mode-600 --env-file; notebooks read `landing` with a dynamic `landing-reader` identity (weed shell s3.configure -actions=Read,List -buckets=landing, keys on stdin) deleted after use. Loading follows E1 (Spark) or Trino + PyIceberg (unpartitioned). Proven by v3/tests/migration/run.sh against a throwaway MinIO with synthetic data.
**Tags:** v3, migration, rclone, seaweedfs, credentials, phase6
**Edges:** _(none)_
**Files:** `docs/MIGRATION.md`, `v3/tests/migration/run.sh`, `v3/tests/migration/load_kernel.py`, `v3/versions.env`
**Evidence:** v3/tests/migration/run.sh all -> ALL_RC=0 (v3/tests/migration/EVIDENCE.md)
**LastVerified:** 2026-09-27
**Commit:** 699c5a1
**LastUpdated:** 2026-09-27
**Author:** p6-integrator

---

## NODE: DEC_V3_CUTOVER_LEGACY_LAYOUT
**Type:** Decision
**Priority:** HIGH
**Label:** V3 cutover: V2 moved to legacy/v2/ (inert), docs/v3 promoted to docs/, root install.sh is a thin V3 bootstrap
**Summary:** Phase 6 cutover: V2 compose/scripts/templates/utils/jupyterhub/tests/config/services/examples, its .env files, README and install.sh moved with git mv to legacy/v2/ (docs to legacy/v2/docs/, workflows to legacy/v2/workflows/ where GitHub does not run them). V3 stays in v3/; docs/v3/* (incl. MIGRATION.md) promoted to docs/. Root install.sh: everything in main() (partial download runs nothing), --ref/--dir/--repo/--yes, prints the plan, execs v3/install.sh with stdin from /dev/tty; refuses V2 installs, non-checkout dirs, dirty checkouts and refs without v3/, updates fast-forward only, never nests. Why: V2 installs are git clones of main, so a pull/re-run after the merge would swap V3 files under a running V2 (REG_UPGRADE_VOLUME_DATA_LOSS class); V2 is pinned to tag v2.1.1-final. Core nodes anchored to V2 root paths (install.sh, start-lakehouse.sh, docker-compose.yml, scripts/) now refer to legacy/v2/.
**Tags:** v3, cutover, bootstrap, legacy, install, phase6
**Edges:**
- RELATES_TO → REG_UPGRADE_VOLUME_DATA_LOSS: bootstrap refuses V2 installs so a V3 update never lands under a running V2
**Files:** `install.sh`, `legacy/README.md`, `tests/bootstrap/test_bootstrap.sh`, `README.md`, `docs/README.md`
**Evidence:** bash tests/bootstrap/test_bootstrap.sh -> 43 passed; clean install via piped root bootstrap on the dev host (v3/PHASE6_RESULTS.md)
**LastVerified:** 2026-09-27
**Commit:** 699c5a1
**LastUpdated:** 2026-09-27
**Author:** p6-integrator

---

## NODE: DEC_V3_RELEASE_BETA1_CUTOVER
**Type:** Decision
**Priority:** HIGH
**Label:** V3 released as v3.0.0-beta.1 on main; V2 archived in legacy/v2 and tagged v2.1.1-final
**Summary:** Owner approved on 2026-09-28. The last V2 main (6f267e7) was tagged v2.1.1-final, and PR #29 (v3 to main) was merged with a merge commit, e7966d7, keeping V3 history and the git-mv renames into legacy/v2/. The tag v3.0.0-beta.1 published images via v3-images, and a GitHub pre-release was created ('latest' stays V2 2.1.1). The migration path is a guide only (docs/MIGRATION.md; owner decision: no other V2 users). Gates before merge: v3-ci core+engineer green, v3-nightly full 18/18, a real one-liner install from GitHub 17/17, v3-p1 upgrade 18/18, and private-data and local-config checks on the diff. Graph anchors for V2 files were repointed to legacy/v2/.
**Tags:** v3, release, cutover, legacy
**Edges:**
- RELATES_TO → DEC_V3_STACK_DIRECTION: the stack decided on day 1, now released
**Files:** `README.md`, `install.sh`, `docs/CHANGELOG.md`, `v3/RELEASE_NOTES_v3.0.0-beta.1.md`, `v3/RELEASE_CHECKLIST.md`, `legacy/README.md`
**Commit:** e7966d7
**LastUpdated:** 2026-09-28
