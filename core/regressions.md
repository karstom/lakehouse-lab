# Regressions

> Bugs that have occurred, especially recurring ones. A high `REGRESSED_N_TIMES` count signals high-risk code.
> When a regression is fully resolved, move it to `archive/resolved_regressions.md`.
>
> Nodes here are grouped by **root cause**, not by file. `REGRESSED_N_TIMES` counts the
> distinct fix commits for that root cause (listed in Provenance), mined 2025-06 → 2025-09.

---

## NODE: REG_CREDENTIAL_PROPAGATION
**Type:** Regression
**Priority:** HIGH
**Label:** Credentials hardcoded or out of sync between .env and consumers
**Summary:** Services, init scripts, DAGs, notebooks and completion messages repeatedly used hardcoded credentials (`minio123`, etc.) or values that no longer matched `.env` after an upgrade or regeneration. Root cause: there was no single source of truth — each consumer embedded its own copy, so every regeneration or upgrade path desynced some of them. Still live: `templates/airflow/dags/data_quality_check.py:42` and several tests hardcode `minio123`.
**Tags:** credentials, env, upgrade, minio
**REGRESSED_N_TIMES:** 16
**Edges:**
- VIOLATED_BY → INV_ENV_IS_CREDENTIAL_SOURCE: each fix removed one more hardcoded or mirrored copy
- RELATES_TO → REG_UPGRADE_VOLUME_DATA_LOSS: upgrades regenerated .env while volumes kept old passwords
**Files:** `scripts/generate-credentials.sh`, `scripts/install/fix-credentials.sh`, `scripts/show-credentials.sh`, `install.sh`, `templates/airflow/dags/data_quality_check.py`, `docker-compose.yml`
**Symbols:** `generate_passphrase`, `generate_strong_password`, `generate_db_safe_password`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `61ffcbf`, `6291038`, `1003d38`, `0a470b2`, `1fc1300`, `dba8f9d`, `659ac5f`, `eb6c03e`, `dd10dbf`, `b67b1a4`, `e6d5675`, `24ccbc1`, `5a684f3`, `4b9c2f2`, `3c45c39`, `a9330b7`

---

## NODE: REG_COMPOSE_INLINE_SHELL
**Type:** Regression
**Priority:** HIGH
**Label:** Inline bash in docker-compose `command:` blocks breaks on YAML/interpolation
**Summary:** Multi-line bash embedded in compose `command:`/`entrypoint:` blocks broke repeatedly: `$VAR` interpolated by Compose at parse time instead of by the container shell, heredoc terminators and quoting invalidating YAML, duplicate `deploy:` keys, and version specifiers like `>=` being shell-interpreted. This is the main driver of the 56 fix commits touching `docker-compose.yml`. Root cause: application logic lives inside YAML strings where neither YAML nor shell tooling can validate it.
**Tags:** docker-compose, yaml, interpolation, shell
**REGRESSED_N_TIMES:** 15
**Edges:**
- VIOLATED_BY → INV_COMPOSE_DOLLAR_ESCAPING: unescaped `$` evaluated by Compose, not the container
- RELATES_TO → REG_AIRFLOW_DB_INIT: several Airflow init failures were command-block syntax bugs
**Files:** `docker-compose.yml`, `docker-compose.iceberg.yml`, `docker-compose.jupyterhub.yml`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `086d414`, `299a2e5`, `04af791`, `eb05139`, `c2ec6b2`, `25e4dac`, `3ab7b72`, `2801401`, `354089b`, `3819f75`, `fb466e4`, `f6a71b4`, `e9badc8`, `f68964c`, `77c0ea9`

---

## NODE: REG_INIT_CONTAINER_BOOTSTRAP
**Type:** Regression
**Priority:** HIGH
**Label:** lakehouse-init fails on runtime deps, network, or MinIO readiness
**Summary:** The one-shot `lakehouse-init` container repeatedly failed: missing bash/sudo on Alpine, apk/pip installs failing in network-restricted hosts, MinIO not ready when buckets were created, and Docker-CLI checks aborting modules. Root cause: the init container installs its own tooling at runtime from the network and assumes a particular base image, so any base-image or network change breaks it. Partially addressed by switching to `python:3.11` (237e4d7) and making modules tolerate missing network (8b07634, 4070f9e).
**Tags:** init, minio, network, bootstrap
**REGRESSED_N_TIMES:** 13
**Edges:**
- FIXED_BY → DEC_INIT_CONTAINER_PYTHON_BASE: latest mitigation for the base-image class
- RELATES_TO → REG_ICEBERG_JAR_VERSIONS: JAR downloads happen inside this container
**Files:** `scripts/lib/init-core.sh`, `scripts/init-infrastructure.sh`, `scripts/init-storage.sh`, `scripts/init-compute.sh`, `scripts/legacy/init-all-in-one-modular.sh`, `docker-compose.yml`
**Symbols:** `wait_for_minio_api`, `check_docker_services`, `check_docker_cli_available`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `913cd65`, `87b90fa`, `181d213`, `dbbfb4a`, `43fc4ca`, `4c5a4d5`, `2475ce2`, `680b017`, `237e4d7`, `8b07634`, `4070f9e`, `cf81b23`, `18fc04d`

---

## NODE: REG_JUPYTER_PYSPARK_VERSIONS
**Type:** Regression
**Priority:** HIGH
**Label:** PySpark/PyArrow version conflicts in the Jupyter container
**Summary:** Jupyter repeatedly failed to import PySpark or crashed on PyArrow/Python incompatibilities after runtime `pip install` layered packages over the image's own versions. Root cause: two sources of truth for PySpark/PyArrow (image vs pip at container start). Mitigated by pinning the Spark-matched image `quay.io/jupyter/pyspark-notebook:spark-3.5.3` and no longer pip-installing PySpark.
**Tags:** jupyter, pyspark, pyarrow, versions
**REGRESSED_N_TIMES:** 12
**Edges:**
- FIXED_BY → DEC_SWITCH_SPARK_3_5_3_A7AE: pinned Spark-matched Jupyter image
- VIOLATED_BY → INV_SPARK_VERSION_ALIGNMENT: client/cluster/package versions diverged
**Files:** `docker-compose.yml`, `scripts/init-analytics.sh`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `054e830`, `5c248d3`, `173ab95`, `68d7424`, `10823ce`, `328739e`, `707a1a9`, `42ee206`, `4ed2cb5`, `d532f0e`, `62ac053`, `044c333`

---

## NODE: REG_UPGRADE_VOLUME_DATA_LOSS
**Type:** Regression
**Priority:** HIGH
**Label:** Upgrades lose data or fail on volume paths/names
**Summary:** The install.sh upgrade/replace path repeatedly lost data (bind-mount overlays), nested install directories, mismatched external volume names, and dropped service files during migration. Root cause: volume identity is defined in several places — compose `name:` fields, `start-lakehouse.sh create_named_volumes`, and `migrate-to-named-volumes.sh` — that must agree by convention. Still latent: compose hardcodes `lakehouse-lab_*` while the scripts derive the prefix from `basename $PWD`, so `install.sh --dir <other>` recreates the 5ab9aa2 failure.
**Tags:** upgrade, volumes, data-loss, installer
**REGRESSED_N_TIMES:** 12
**Edges:**
- VIOLATED_BY → INV_VOLUME_NAMES_SINGLE_SOURCE: volume names disagreed between compose and scripts
- FIXED_BY → DEC_NAMED_EXTERNAL_VOLUMES: moved data off bind mounts
**Files:** `install.sh`, `start-lakehouse.sh`, `scripts/install/migrate-to-named-volumes.sh`, `docker-compose.yml`
**Symbols:** `create_named_volumes`, `perform_smart_upgrade`, `perform_upgrade`, `perform_replace`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `3f06179`, `9ab71ec`, `98da41e`, `a4a8b91`, `3b43c4f`, `5ab9aa2`, `5782f5d`, `09ef0cf`, `5cfafd8`, `42a33c5`, `04a0d20`, `b66f739`

---

## NODE: REG_AIRFLOW_DB_INIT
**Type:** Regression
**Priority:** HIGH
**Label:** Airflow database init boot loops / connection failures
**Summary:** airflow-init and airflow-webserver repeatedly boot-looped or failed to reach Postgres: migrations running from the wrong service, DB connection strings built with stale or URL-unsafe passwords, and volume permissions on named volumes. Root cause is shared with REG_COMPOSE_INLINE_SHELL and REG_CREDENTIAL_PROPAGATION — init logic in YAML strings plus credentials assembled into URLs.
**Tags:** airflow, postgres, init
**REGRESSED_N_TIMES:** 7
**Edges:**
- RELATES_TO → REG_COMPOSE_INLINE_SHELL: init commands live in compose YAML
- VIOLATED_BY → INV_DB_PASSWORDS_URL_SAFE: passwords embedded in SQLAlchemy URLs
**Files:** `docker-compose.yml`, `scripts/init-workflows.sh`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `04ea8a9`, `2a735b3`, `efa8fc4`, `a0d93b5`, `213a8d7`, `dbac3f7`, `68058a7`

---

## NODE: REG_GENERATED_CODE_SYNTAX
**Type:** Regression
**Priority:** HIGH
**Label:** Shell-generated notebooks/Python/DAGs ship with syntax errors
**Summary:** Notebooks, DAGs, the sample-data generator and the LanceDB service were shipped with invalid JSON/Python several times. Root cause: code is emitted from bash heredocs in `scripts/init-*.sh` where no linter or JSON parser sees it, and some files exist twice — `scripts/init-lancedb.sh` writes `lancedb_service.py` from a heredoc that has already diverged from `templates/lancedb/service/lancedb_service.py`.
**Tags:** templates, notebooks, heredoc, codegen
**REGRESSED_N_TIMES:** 7
**Edges:**
- VIOLATED_BY → INV_TEMPLATES_ARE_REAL_FILES: code embedded in heredocs instead of copied from templates/
**Files:** `scripts/init-lancedb.sh`, `scripts/init-analytics.sh`, `scripts/init-workflows.sh`, `templates/lancedb/service/lancedb_service.py`, `templates/jupyter/notebooks/03_Iceberg_Tables.ipynb`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `6ed0e37`, `5f6e905`, `792b7a2`, `a3d7616`, `cce2c99`, `924dc6a`, `1dedb57`

---

## NODE: REG_ICEBERG_JAR_VERSIONS
**Type:** Regression
**Priority:** HIGH
**Label:** Iceberg / hadoop-aws / AWS SDK JAR version mismatches
**Summary:** Iceberg integration broke on unavailable JAR versions, malformed download URLs, and AWS SDK / S3FileIO incompatibility. Root cause: the JAR set (iceberg-spark-runtime 3.5_2.12-1.9.2, iceberg-aws 1.9.2, hadoop-aws 3.3.4, aws-java-sdk-bundle 1.12.262) is hardcoded independently in five places, so a bump in one leaves the others stale.
**Tags:** iceberg, spark, jars, versions
**REGRESSED_N_TIMES:** 6
**Edges:**
- VIOLATED_BY → INV_SPARK_VERSION_ALIGNMENT: JAR Spark/Scala suffix must match the cluster
- RELATES_TO → WATCH_ICEBERG_VERSION_SITES: the five places that must change together
**Files:** `docker-compose.iceberg.yml`, `scripts/init-compute.sh`, `utils/iceberg_jar_manager.py`, `templates/jupyter/notebooks/03_Iceberg_Tables.ipynb`, `tests/test_iceberg_integration.py`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `a0766af`, `959ca82`, `1fd1749`, `42adb94`, `62e8115`, `8a4333e`

---

## NODE: REG_SUPERSET_SETUP
**Type:** Regression
**Priority:** HIGH
**Label:** Superset startup: permissions, pip installs, DB setup timing
**Summary:** Superset repeatedly failed on chown/permission errors, runtime `pip install` as a non-root user, and database-connection setup running before the app context or DB was ready. Root cause: runtime package installs into an unpinned `apache/superset:latest` image plus setup racing startup. The unpinned tag means upstream changes can reintroduce this with no repo change.
**Tags:** superset, permissions, startup
**REGRESSED_N_TIMES:** 6
**Edges:**
- RELATES_TO → WATCH_UNPINNED_IMAGES: `superset:latest` can shift underneath the fixes
**Files:** `docker-compose.yml`, `scripts/init-dashboards.sh`, `templates/superset/database_setup.py`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `b4493db`, `bbba7e0`, `838bdd9`, `56451b5`, `3b8b0b3`, `208b4e4`

---

## NODE: REG_HOST_IP_DETECTION
**Type:** Regression
**Priority:** HIGH
**Label:** Service URLs show localhost/Docker IP instead of host IP
**Summary:** URLs shown to users pointed at localhost or a Docker bridge IP, breaking remote-server installs. Root cause: host-IP detection is reimplemented in four scripts that drift apart; `start-lakehouse.sh detect_host_ip` is the most complete version.
**Tags:** networking, host-ip, remote
**REGRESSED_N_TIMES:** 3
**Edges:**
- RELATES_TO → WATCH_DUPLICATED_HOST_IP_DETECTION: the four copies
**Files:** `start-lakehouse.sh`, `scripts/generate-credentials.sh`, `scripts/install/fix-credentials.sh`, `scripts/show-credentials.sh`
**Symbols:** `detect_host_ip`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `8e7ac1d`, `082cfd4`, `556e661`

---

## NODE: REG_V3_CHROMIUM_LOCALHOST_LOOPBACK
**Type:** Regression
**Priority:** MEDIUM
**Label:** V3 smoke browser check fails on lab.localhost: Chromium maps *.localhost to loopback
**Summary:** On LAB_DOMAIN=lab.localhost (the WSL2 and CI default), the Playwright check in v3/tests/smoke/smoke.py failed with net::ERR_CONNECTION_REFUSED. Chromium hard-wires *.localhost to 127.0.0.1 and ignores the Docker DNS alias that points at Caddy. Validation had only covered the sslip domain. Fix: resolve trino.<domain> through Docker DNS and launch Chromium with --host-resolver-rules=MAP *.<domain> <ip>. Mapping to the hostname 'caddy' did not work. Validate every change on both lab.localhost and sslip.
**Tags:** v3, smoke, playwright, chromium, localhost, wsl2, ci, dns
**REGRESSED_N_TIMES:** 1
**Edges:** _(none)_
**Files:** `v3/tests/smoke/smoke.py`
**Symbols:** `check_browser_login`
**Evidence:** WSL2, install.sh --domain lab.localhost --project-name v3-wsl, then lab test: SMOKE PASS (6/6), check 2 final_url https://trino.lab.localhost:18443/ui/#/dashboard
**LastVerified:** 2026-09-25
**Commit:** 4dd6c9a
**LastUpdated:** 2026-09-25
**Author:** claude-v3-p1-repair
