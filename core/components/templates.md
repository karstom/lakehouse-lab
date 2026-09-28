## NODE: TEMPLATES
**Type:** Component
**Priority:** MEDIUM
**Label:** User-facing templates: notebooks, DAGs, services, utilities
**Summary:** `templates/` holds what users see first: 8 Jupyter notebooks (00–07), Airflow DAGs, the LanceDB FastAPI service, Superset DB setup and a sample-data generator; `utils/` holds Iceberg JAR management helpers used from notebooks. Some of these are also emitted by heredocs in `scripts/init-*.sh`, and the copies have diverged (LanceDB service). Notebooks must stay valid JSON and must read credentials from the environment.
**Tags:** templates, notebooks, airflow, lancedb
**Edges:**
- CONTAINS → REG_GENERATED_CODE_SYNTAX: corrupted notebooks/DAGs
- CONTAINS → ISSUE_HARDCODED_MINIO_CREDS_IN_DAG: data_quality_check.py
- DEPENDS_ON → INV_TEMPLATES_ARE_REAL_FILES: templates are the canonical copy
- RELATES_TO → WATCH_ICEBERG_VERSION_SITES: notebook 03 and utils pin JAR versions
**Files:** `templates/jupyter/notebooks/03_Iceberg_Tables.ipynb`, `templates/airflow/dags/data_quality_check.py`, `templates/lancedb/service/lancedb_service.py`, `templates/superset/database_setup.py`, `utils/iceberg_jar_manager.py`, `utils/jar_manager_cell.py`
**Paths:** `templates`, `utils`
**LastUpdated:** 2026-09-25
