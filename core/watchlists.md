# Watchlists & Open Issues

> Code areas requiring extra caution, and known issues not yet fixed.

---

## NODE: WATCH_ICEBERG_VERSION_SITES
**Type:** Watchlist
**Priority:** HIGH
**Label:** Iceberg/AWS JAR versions are hardcoded in five places
**Summary:** The Iceberg JAR set (runtime 3.5_2.12-1.9.2, iceberg-aws 1.9.2, hadoop-aws 3.3.4, aws-java-sdk-bundle 1.12.262) appears independently in the five files below. Any version bump must change all five together, then run `tests/test_iceberg_integration.py`. Consolidating them into one source would retire this watchlist.
**Tags:** iceberg, jars, versions
**Edges:**
- CONTAINS → REG_ICEBERG_JAR_VERSIONS: the regression this duplication causes
**Files:** `docker-compose.iceberg.yml`, `scripts/init-compute.sh`, `utils/iceberg_jar_manager.py`, `templates/jupyter/notebooks/03_Iceberg_Tables.ipynb`, `tests/test_iceberg_integration.py`
**Evidence:** `grep -rln "1\.9\.2" --exclude-dir=.git --exclude-dir=core .` → the 5 files listed
**LastUpdated:** 2026-09-25

---

## NODE: WATCH_UNPINNED_IMAGES
**Type:** Watchlist
**Priority:** MEDIUM
**Label:** Unpinned `:latest` images
**Summary:** `apache/superset:latest` and `portainer/portainer-ce:latest` can change on any fresh pull, so an install can break with no repo change, and the Superset fixes in REG_SUPERSET_SETUP can be silently undone. The runtime `pip install` lines in the jupyter, airflow, superset, vizro and lancedb commands are also partially unpinned (`vizro[default]`, `lancedb`, `pandas`).
**Tags:** docker, images, pinning
**Edges:**
- RELATES_TO → REG_SUPERSET_SETUP: unpinned base under the fixes
**Files:** `docker-compose.yml`
**Evidence:** `grep -n "image:.*:latest" docker-compose.yml` → superset, portainer
**LastUpdated:** 2026-09-25

---

## NODE: WATCH_SPARK_PATCH_SKEW
**Type:** Watchlist
**Priority:** LOW
**Label:** Three Spark patch versions: 3.5.0 / 3.5.3 / 3.5.6
**Summary:** The cluster runs `apache/spark:3.5.6`, single-user Jupyter uses `pyspark-notebook:spark-3.5.3`, and JupyterHub-spawned user servers use `pyspark-notebook:spark-3.5.0` (`jupyterhub/jupyterhub_config.py`). Same-minor clients usually work in standalone mode, so this is tolerated, but it is the first suspect for odd driver/executor serialization errors. Align all three when a matching `pyspark-notebook` tag is available.
**Tags:** spark, jupyter, versions
**Edges:**
- RELATES_TO → INV_SPARK_VERSION_ALIGNMENT: minor-level rule this skew stays inside
**Files:** `docker-compose.yml`, `jupyterhub/jupyterhub_config.py`
**LastUpdated:** 2026-09-25

---

## NODE: WATCH_INSTALL_UPGRADE_PATH
**Type:** Watchlist
**Priority:** HIGH
**Label:** install.sh upgrade/replace and migration scripts
**Summary:** `install.sh` (about 1,000 lines, 13 fix commits) owns detection of existing installs, smart/legacy upgrade, replace, credential generation and volume migration — the paths where data loss happened. Test any change here against an existing install with data, not just a clean install; clean-install-only testing caused 24ccbc1 and b67b1a4.
**Tags:** installer, upgrade, data-loss
**Edges:**
- CONTAINS → REG_UPGRADE_VOLUME_DATA_LOSS: upgrade path data loss
- CONTAINS → REG_CREDENTIAL_PROPAGATION: upgrade credential mismatches
**Files:** `install.sh`, `scripts/install/fix-credentials.sh`, `scripts/install/migrate-to-named-volumes.sh`, `scripts/install/enable-jupyterhub.sh`
**Symbols:** `perform_upgrade`, `perform_smart_upgrade`, `perform_legacy_upgrade`, `perform_replace`, `configure_environment`
**LastUpdated:** 2026-09-25

---

## NODE: WATCH_DUPLICATED_HOST_IP_DETECTION
**Type:** Watchlist
**Priority:** MEDIUM
**Label:** Host-IP detection is copied in four scripts
**Summary:** Host-IP detection logic lives in `start-lakehouse.sh` (`detect_host_ip`, most complete: HOST_IP override, excludes 172.16/12 Docker ranges) and is reimplemented in three credential scripts. A fix to one does not reach the others; prefer moving it into a shared helper over patching a single copy.
**Tags:** networking, host-ip, duplication
**Edges:**
- CONTAINS → REG_HOST_IP_DETECTION: drift between the copies
**Files:** `start-lakehouse.sh`, `scripts/generate-credentials.sh`, `scripts/install/fix-credentials.sh`, `scripts/show-credentials.sh`
**Symbols:** `detect_host_ip`
**LastUpdated:** 2026-09-25

---

## NODE: WATCH_LEGACY_NAMED_INIT_ENTRYPOINT
**Type:** Watchlist
**Priority:** MEDIUM
**Label:** Live init entrypoint lives in scripts/legacy/
**Summary:** `docker-compose.yml` mounts `scripts/legacy/init-all-in-one-modular.sh` as the `lakehouse-init` entrypoint; it sources `scripts/lib/init-core.sh` and runs the `scripts/init-*.sh` modules. Despite the directory name it is the production path — do not delete or "clean up" `scripts/legacy/` without repointing compose. `init-all-in-one.sh` next to it is the actually-retired monolith.
**Tags:** init, naming, entrypoint
**Edges:**
- RELATES_TO → REG_INIT_CONTAINER_BOOTSTRAP: this script drives the init container
**Files:** `scripts/legacy/init-all-in-one-modular.sh`, `scripts/legacy/init-all-in-one.sh`, `docker-compose.yml`
**LastUpdated:** 2026-09-25

---

## NODE: WATCH_CONFIGURE_SERVICES
**Type:** Watchlist
**Priority:** MEDIUM
**Label:** configure-services.sh service presets and override generation
**Summary:** `scripts/configure-services.sh` (11 commits) maps presets and `.lakehouse-services.conf` to a generated `docker-compose.override.yml`. Every dashboard swap (Homer → Homepage → Dashy → static → removed) had to be mirrored here, so check it whenever a service is added or removed.
**Tags:** configuration, services, presets
**Edges:**
- RELATES_TO → DEC_REMOVE_DASHBOARD_FUNCTIONALITY_FOCUS_ON_8492: removal needed mirroring here
**Files:** `scripts/configure-services.sh`, `.lakehouse-services.conf`, `docker-compose.override.yml.example`
**Symbols:** `generate_compose_override`
**LastUpdated:** 2026-09-25

---

## NODE: WATCH_CI_WORKFLOWS
**Type:** Watchlist
**Priority:** MEDIUM
**Label:** CI workflows: high churn, weak coverage of real startup
**Summary:** The 10 workflows in `.github/workflows/` took about 20 fix commits (YAML lint, ShellCheck, flake8/black, link checks, secret-scan false positives from grep patterns matching "password"). None of them start the stack anymore (see DEC_REPLACE_UNRELIABLE_DOCKER_STARTUP_TEST_AD13), and pytest runs with `-k "not integration and not docker"`, so compose/init/upgrade regressions are not caught in CI.
**Tags:** ci, github-actions, testing
**Edges:**
- RELATES_TO → DEC_REPLACE_UNRELIABLE_DOCKER_STARTUP_TEST_AD13: why startup is not tested
**Files:** `.github/workflows/ci.yml`, `.github/workflows/security-scan.yml`, `.github/workflows/startup-test.yml`, `.github/workflows/documentation-check.yml`, `.github/workflows/environment-validation.yml`, `.github/workflows/docker-compose-validation.yml`, `.github/workflows/backup-system-test.yml`, `.github/workflows/storage-persistence-test.yml`
**LastUpdated:** 2026-09-25
**Provenance:** commits: `3907f45`, `f647427`, `179cebe`, `ed8eca8`, `cbc5569`, `0ab15fa`, `362b08c`, `f7320ca`, `4bd38ce`

---

## NODE: ISSUE_HARDCODED_MINIO_CREDS_IN_DAG
**Type:** Watchlist
**Priority:** HIGH
**Label:** OPEN: data_quality_check DAG hardcodes MinIO secret `minio123`
**Summary:** `templates/airflow/dags/data_quality_check.py:42` sets `s3_secret_access_key='minio123'`, which never matches generated credentials, so the DAG fails against a real install. The tests hardcode the same value. Fix by reading `MINIO_ROOT_PASSWORD` (or the Airflow connection) from the environment.
**Tags:** credentials, airflow, open-issue
**Edges:**
- CONTAINS → REG_CREDENTIAL_PROPAGATION: surviving instance of this regression
- RELATES_TO → INV_ENV_IS_CREDENTIAL_SOURCE: violates this rule
**Files:** `templates/airflow/dags/data_quality_check.py`, `tests/test_data_pipeline.py`, `tests/test_cross_service_integration.py`, `tests/test_service_health.py`
**Evidence:** `grep -n minio123 templates/airflow/dags/data_quality_check.py` → line 42
**LastUpdated:** 2026-09-25

---

## NODE: ISSUE_WEAK_CREDENTIAL_RNG
**Type:** Watchlist
**Priority:** MEDIUM
**Label:** OPEN: credentials generated with bash $RANDOM
**Summary:** `scripts/generate-credentials.sh` builds all passwords and passphrases from bash `$RANDOM` (15-bit, not cryptographically secure); passphrases have about 57.6M possible values (~26 bits). Replace with `/dev/urandom` or `openssl rand`, keeping the `generate_db_safe_password` character set.
**Tags:** credentials, security, open-issue
**Edges:**
- RELATES_TO → INV_DB_PASSWORDS_URL_SAFE: any replacement must keep the safe charset
**Files:** `scripts/generate-credentials.sh`
**Symbols:** `generate_passphrase`, `generate_strong_password`, `generate_db_safe_password`
**LastUpdated:** 2026-09-25

---

## NODE: WATCH_V3_SPARK_CONNECT_INTERMITTENT_HANG
**Type:** Watchlist
**Priority:** MEDIUM
**Label:** V3: Spark Connect client hung once after a Forbidden refusal (not reproduced)
**Summary:** On one full smoke run, victor's workspace probe hung for 300 s after Lakekeeper and Spark had refused his table create (ForbiddenException logged within about 1 s; the client then went silent with no further RPCs). It did not recur in an isolated run, two more full runs, or a standalone client (refusal plus stop() in 2 s). If learners' notebooks can freeze this way it matters, so the smoke probe now dumps all thread stacks to ~/.smoke-stack.txt before the harness times out, and the harness attaches the dump to the evidence. On recurrence, read that dump first.
**Tags:** v3, spark-connect, flaky, workspace
**Edges:** _(none)_
**Files:** `v3/tests/smoke/kernel_probe.py`, `v3/tests/smoke/workspace.py`, `v3/images/workspace/lakehouse/clients.py`
**Symbols:** `step_spark_write_denied`, `spark`
**Commit:** 6202fd0
**LastUpdated:** 2026-09-26
