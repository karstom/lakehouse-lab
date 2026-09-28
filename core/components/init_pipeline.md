## NODE: INIT_PIPELINE
**Type:** Component
**Priority:** HIGH
**Label:** lakehouse-init modular initialization
**Summary:** The `lakehouse-init` container runs `scripts/legacy/init-all-in-one-modular.sh`, which sources `scripts/lib/init-core.sh` (logging, `wait_for_service`, `wait_for_minio_api`, init markers, error handling) and runs the modules in order: infrastructure → storage → compute → workflows → analytics → dashboards → vizro → lancedb. Modules create MinIO buckets, download Iceberg JARs, and write notebooks/DAGs/services into the shared volume, many via heredocs. Markers from `create_init_marker` make re-runs skip completed work; modules must tolerate no network.
**Tags:** init, bootstrap, minio
**Edges:**
- CONTAINS → REG_INIT_CONTAINER_BOOTSTRAP: runtime deps/network/readiness failures
- CONTAINS → REG_GENERATED_CODE_SYNTAX: heredoc-emitted code
- CONTAINS → REG_ICEBERG_JAR_VERSIONS: init-compute.sh downloads JARs
- DEPENDS_ON → DEC_INIT_CONTAINER_PYTHON_BASE: assumes python:3.11 tooling
- RELATES_TO → WATCH_LEGACY_NAMED_INIT_ENTRYPOINT: live entrypoint is in scripts/legacy/
**Files:** `scripts/legacy/init-all-in-one-modular.sh`, `scripts/lib/init-core.sh`, `scripts/init-infrastructure.sh`, `scripts/init-storage.sh`, `scripts/init-compute.sh`, `scripts/init-workflows.sh`, `scripts/init-analytics.sh`, `scripts/init-dashboards.sh`, `scripts/init-vizro.sh`, `scripts/init-lancedb.sh`
**Symbols:** `wait_for_service`, `wait_for_minio_api`, `create_init_marker`, `check_already_initialized`, `handle_error`
**Paths:** `scripts/lib`, `scripts/legacy`
**LastUpdated:** 2026-09-25
