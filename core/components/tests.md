## NODE: TESTS
**Type:** Component
**Priority:** MEDIUM
**Label:** pytest suite and stack health checks
**Summary:** About 100 pytest tests cover compose structure, init scripts, docs, Iceberg, service health, cross-service integration and data pipelines; `conftest.py` uses the Docker SDK. CI runs only `-k "not integration and not docker"`, so the integration/health tests (and `run_stack_health_tests.sh`) are manual-only against a running stack. Integration tests hardcode MinIO credentials (`minio123`) and fail against generated credentials.
**Tags:** testing, pytest, ci
**Edges:**
- RELATES_TO → WATCH_CI_WORKFLOWS: what CI actually runs
- RELATES_TO → ISSUE_HARDCODED_MINIO_CREDS_IN_DAG: same hardcoded secret
**Files:** `tests/conftest.py`, `tests/run_tests.sh`, `tests/run_stack_health_tests.sh`, `tests/test_docker_compose.py`, `tests/test_init_scripts.py`, `tests/test_iceberg_integration.py`
**Paths:** `tests`
**LastUpdated:** 2026-09-25
