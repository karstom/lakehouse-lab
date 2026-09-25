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
**Commit:** 6f267e7
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
**Commit:** 6f267e7
**LastUpdated:** 2026-09-25

---

## NODE: DEC_V3_CATALOG_VENDED_STORAGE_ACCESS
**Type:** Decision
**Priority:** HIGH
**Label:** V3: storage access given out by Lakekeeper — no S3 keys for users
**Summary:** In V3, engines never hold static S3 keys: Lakekeeper authorizes table access and remote-signs requests (the default for Spark and Trino) or gives out STS credentials (needed for DuckDB, whose Iceberg extension can't do remote signing). SeaweedFS STS with Lakekeeper is unproven and gated on spike S-2, with a Trino-attach fallback for DuckDB. This removes the root cause of REG_CREDENTIAL_PROPAGATION instead of guarding against it. ADR-006.
**Tags:** v3, credentials, catalog, storage
**Edges:**
- MITIGATES → REG_CREDENTIAL_PROPAGATION: removes storage credentials from all consumers
- RELATES_TO → INV_ENV_IS_CREDENTIAL_SOURCE: V3 replaces the .env credential model
**Files:** `docs/v3/DECISIONS.md`, `docs/v3/OPEN_QUESTIONS.md`
**Commit:** 6f267e7
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
**Commit:** 6f267e7
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
