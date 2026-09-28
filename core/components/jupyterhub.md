## NODE: JUPYTERHUB
**Type:** Component
**Priority:** MEDIUM
**Label:** Multi-user JupyterHub overlay
**Summary:** `docker-compose.jupyterhub.yml` replaces the single-user `jupyter` service with a JupyterHub image built from `jupyterhub/Dockerfile.simple`, using DockerSpawner to start per-user notebook containers on the compose network; enabled via `scripts/install/enable-jupyterhub.sh`. Known drift: spawned users get `pyspark-notebook:spark-3.5.0` (single-user Jupyter uses 3.5.3, cluster 3.5.6), the network name `lakehouse-lab_lakehouse` is hardcoded, `db_url` is hardcoded to sqlite despite `JUPYTERHUB_DB_URL` being passed, and `JUPYTERHUB_API_TOKEN` falls back to the literal `lakehouse-admin-token`.
**Tags:** jupyterhub, multi-user, spawner
**Edges:**
- RELATES_TO → WATCH_SPARK_PATCH_SKEW: third Spark version in the stack
- RELATES_TO → INV_ENV_IS_CREDENTIAL_SOURCE: literal default API token
- RELATES_TO → INV_VOLUME_NAMES_SINGLE_SOURCE: same directory-name coupling for the network
**Files:** `legacy/v2/jupyterhub/jupyterhub_config.py`, `legacy/v2/jupyterhub/Dockerfile`, `legacy/v2/jupyterhub/Dockerfile.simple`, `legacy/v2/docker-compose.jupyterhub.yml`, `legacy/v2/scripts/install/enable-jupyterhub.sh`
**Paths:** `legacy/v2/jupyterhub`
**LastUpdated:** 2026-09-25
