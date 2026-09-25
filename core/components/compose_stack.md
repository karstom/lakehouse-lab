## NODE: COMPOSE_STACK
**Type:** Component
**Priority:** HIGH
**Label:** Docker Compose stack definition
**Summary:** `docker-compose.yml` defines the core stack (postgres, minio, one-shot lakehouse-init, spark-master/worker, jupyter, airflow-init/scheduler/webserver, superset, portainer, vizro, lancedb) with env-driven memory limits and external named volumes. Overlays add Iceberg (`docker-compose.iceberg.yml`) and multi-user JupyterHub (`docker-compose.jupyterhub.yml`), and `configure-services.sh` generates `docker-compose.override.yml` to disable services. Several services run inline bash with runtime `pip install` in `command:` — the main source of the compose-file fix churn. Validate every edit with `docker compose config -q` for each overlay combination.
**Tags:** docker-compose, services, infrastructure
**Edges:**
- CONTAINS → REG_COMPOSE_INLINE_SHELL: inline command-block failures
- CONTAINS → REG_SUPERSET_SETUP: Superset startup lives in its command block
- CONTAINS → REG_AIRFLOW_DB_INIT: airflow-init lives here
- DEPENDS_ON → INV_COMPOSE_DOLLAR_ESCAPING: rule for every command block
- DEPENDS_ON → INV_VOLUME_NAMES_SINGLE_SOURCE: external volume names
- RELATES_TO → WATCH_UNPINNED_IMAGES: `:latest` images defined here
**Files:** `docker-compose.yml`, `docker-compose.iceberg.yml`, `docker-compose.jupyterhub.yml`, `docker-compose.override.yml.example`, `docker-compose.newservice.yml.example`, `.env.example`, `.env.default`, `.env.fat-server`
**LastUpdated:** 2026-09-25
