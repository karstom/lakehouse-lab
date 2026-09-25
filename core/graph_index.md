# Lakehouse Lab Knowledge Graph — Index

> **Session-start mandatory read.** Read this file first, every session.
> Only load detail files listed below when working in those areas.
> **LastUpdated:** 2026-09-25

---

## Multi-Repo Projects

> If this repo is part of a larger multi-repo project, an **org-level shared graph** may exist.
> Check for a `shared/graph_index.md` alongside this file, or a dedicated org-memory repo.
> **If working across repo boundaries, read the shared graph index too.**
>
> Path to shared graph: _none — single-repo project._

---

## Quick Index

> **Compact edge notation:** When populating this table, include 1-hop edges inline
> for fast scanning, e.g.: `INV_AUTH_TOKEN ⚠ VIOLATED_BY:REG_TOKEN_LEAK(×2)`
> This lets the AI see high-risk relationships without loading detail files.

| Category | Nodes | File |
|---|---|---|
| **Components** | COMPOSE_STACK, CREDENTIALS, INIT_PIPELINE, INSTALLER_LIFECYCLE, JUPYTERHUB, TEMPLATES, TESTS | `components/{NAME}.md` |
| **Invariants** | INV_COMPOSE_DOLLAR_ESCAPING, INV_DB_PASSWORDS_URL_SAFE, INV_DO_NOT_EDIT_MANUALLY_USE_F164, INV_ENV_IS_CREDENTIAL_SOURCE, INV_SPARK_VERSION_ALIGNMENT, INV_TEMPLATES_ARE_REAL_FILES, INV_VOLUME_NAMES_SINGLE_SOURCE | `invariants.md` |
| **Active Regressions** | REG_AIRFLOW_DB_INIT(×7), REG_COMPOSE_INLINE_SHELL(×15), REG_CREDENTIAL_PROPAGATION(×16), REG_GENERATED_CODE_SYNTAX(×7), REG_HOST_IP_DETECTION(×3), REG_ICEBERG_JAR_VERSIONS(×6), REG_INIT_CONTAINER_BOOTSTRAP(×13), REG_JUPYTER_PYSPARK_VERSIONS(×12), REG_SUPERSET_SETUP(×6), REG_UPGRADE_VOLUME_DATA_LOSS(×12) | `regressions.md` |
| **Decisions** | DEC_INIT_CONTAINER_PYTHON_BASE, DEC_MIGRATE_FROM_BITNAMI_OFFICIAL_APACHE_4B39, DEC_NAMED_EXTERNAL_VOLUMES, DEC_REMOVE_DASHBOARD_FUNCTIONALITY_FOCUS_ON_8492, DEC_REMOVE_ICEBERG_ENABLED_FROM_SOURCE_1F54, DEC_REMOVE_MCP_SERVER_COMPLETELY_FROM_67B4, DEC_REMOVE_OAUTH_AUTHENTICATION_SYSTEM_ENTIRELY_2B27, DEC_REMOVE_ORPHANED_CONTAINERS_DURING_UPGRADES_5BC0, DEC_REMOVE_SUDO_DEPENDENCIES_FROM_ALPINE_6EF3, DEC_REMOVE_UNUSED_CODECOV_INTEGRATION_B8A6, DEC_REPLACE_UNRELIABLE_DOCKER_STARTUP_TEST_AD13, DEC_SWITCH_SPARK_3_5_3_A7AE, DEC_V3_AI_ASSIST_MCP_GATEWAY, DEC_V3_CATALOG_VENDED_STORAGE_ACCESS, DEC_V3_KEYCLOAK_SSO_SUBDOMAINS, DEC_V3_STACK_DIRECTION, DEC_V3_VERSIONS_FILE_PREBUILT_IMAGES, DEC_V3_WORKSPACE_JUPYTERHUB_CODESERVER_DBT | `decisions.md` |
| **Watchlists & Open Issues** | ISSUE_HARDCODED_MINIO_CREDS_IN_DAG, ISSUE_WEAK_CREDENTIAL_RNG, WATCH_CI_WORKFLOWS, WATCH_CONFIGURE_SERVICES, WATCH_DUPLICATED_HOST_IP_DETECTION, WATCH_ICEBERG_VERSION_SITES, WATCH_INSTALL_UPGRADE_PATH, WATCH_LEGACY_NAMED_INIT_ENTRYPOINT, WATCH_SPARK_PATCH_SKEW, WATCH_UNPINNED_IMAGES | `watchlists.md` |
| **Anti-Patterns** | _(things the AI should never generate)_ | `anti_patterns.md` |
| **Resolved (archive)** | _(resolved regressions go here)_ | `archive/resolved_regressions.md` |

---

## Task Routing — What to Load

> When a task matches multiple rows, load HIGH-priority nodes first.
> Regressions are grouped by root cause; the count is distinct fix commits for that cause.

| If working on... | Load these files |
|---|---|
| **docker-compose*.yml / adding or changing a service** | `components/compose_stack.md`, `invariants.md`, `regressions.md` (REG_COMPOSE_INLINE_SHELL, REG_SUPERSET_SETUP, REG_AIRFLOW_DB_INIT), `watchlists.md` (WATCH_UNPINNED_IMAGES) |
| **Init scripts (`scripts/init-*.sh`, `scripts/lib`, `scripts/legacy`)** | `components/init_pipeline.md`, `regressions.md` (REG_INIT_CONTAINER_BOOTSTRAP, REG_GENERATED_CODE_SYNTAX), `decisions.md` (DEC_INIT_CONTAINER_PYTHON_BASE) |
| **install.sh / start-lakehouse.sh / upgrade / volumes / backup** | `components/installer_lifecycle.md`, `regressions.md` (REG_UPGRADE_VOLUME_DATA_LOSS), `watchlists.md` (WATCH_INSTALL_UPGRADE_PATH), `decisions.md` (DEC_NAMED_EXTERNAL_VOLUMES) |
| **Credentials / .env / users / rotation** | `components/credentials.md`, `invariants.md` (INV_ENV_IS_CREDENTIAL_SOURCE, INV_DB_PASSWORDS_URL_SAFE), `regressions.md` (REG_CREDENTIAL_PROPAGATION) |
| **Spark / Jupyter / PySpark / Iceberg versions** | `invariants.md` (INV_SPARK_VERSION_ALIGNMENT), `regressions.md` (REG_JUPYTER_PYSPARK_VERSIONS, REG_ICEBERG_JAR_VERSIONS), `watchlists.md` (WATCH_ICEBERG_VERSION_SITES, WATCH_SPARK_PATCH_SKEW) |
| **JupyterHub / multi-user** | `components/jupyterhub.md`, `watchlists.md` (WATCH_SPARK_PATCH_SKEW) |
| **Notebooks / DAGs / templates / utils** | `components/templates.md`, `invariants.md` (INV_TEMPLATES_ARE_REAL_FILES), `watchlists.md` (ISSUE_HARDCODED_MINIO_CREDS_IN_DAG) |
| **Service presets / override generation** | `watchlists.md` (WATCH_CONFIGURE_SERVICES), `invariants.md` (INV_DO_NOT_EDIT_MANUALLY_USE_F164), `decisions.md` |
| **CI / GitHub Actions / tests** | `components/tests.md`, `watchlists.md` (WATCH_CI_WORKFLOWS), `decisions.md` (DEC_REPLACE_UNRELIABLE_DOCKER_STARTUP_TEST_AD13) |
| **Host IP / service URLs** | `regressions.md` (REG_HOST_IP_DETECTION), `watchlists.md` (WATCH_DUPLICATED_HOST_IP_DETECTION) |
| **V3 design / building V3 (`docs/v3/`, `v3` branch)** | `decisions.md` (DEC_V3_*), `regressions.md` (root causes V3 must retire), `anti_patterns.md` |
| **Investigating a past regression** | `regressions.md`, `archive/resolved_regressions.md` |
| **Locating code / understanding structure** | `auto_map.md` _(generated — run `core/scripts/auto_map.sh` first)_ |
| **Starting any new code generation** | `anti_patterns.md` _(always check before writing code)_ |
