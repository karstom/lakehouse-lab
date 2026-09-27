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

---

## NODE: REG_V3_OIDC_ISSUER_DEFAULT_PORT
**Type:** Regression
**Priority:** MEDIUM
**Label:** V3 Trino unhealthy on default port 443: OIDC issuer mismatch
**Summary:** The first GitHub CI e2e run (default ports 443/80, lab.localhost) failed because Trino never became healthy: 'issuer claim in Metadata document different than the Issuer URL'. Three configs each hand-built `https://auth.${LAB_DOMAIN}:${LAB_HTTPS_PORT}`, and Keycloak normalizes the default :443 away, so the issuers differed only at 443; the server (18443) and WSL2 (18443) validation runs could not catch it. Fixed by deriving the origin once (LAB_AUTH_URL in lab_settings) and requiring it (`:?`) in every consumer. The smoke test's URL helper had the same bug and now uses the derived suffix.
**Tags:** v3, oidc, issuer, ci, keycloak
**REGRESSED_N_TIMES:** 1
**Edges:**
- VIOLATED_BY → INV_V3_PUBLIC_ORIGIN_SINGLE_SOURCE: each consumer built its own copy of the origin
- RELATES_TO → REG_HOST_IP_DETECTION: same multiple-sources-of-truth class as V2's URL/IP bugs
**Files:** `v3/installer/lib.sh`, `v3/compose/identity.yaml`, `v3/compose/catalog.yaml`, `v3/compose/engines.yaml`, `v3/config/trino/config.properties`, `v3/tests/smoke/smoke.py`
**Symbols:** `lab_settings`
**Evidence:** WSL2 install on default 443/80 (lab.localhost) → lab test SMOKE: PASS (6/6); server 18443 → 6/6
**Commit:** 13770d3
**LastUpdated:** 2026-09-25

---

## NODE: REG_V3_STALE_LOCAL_IMAGES_ON_UPGRADE
**Type:** Regression
**Priority:** MEDIUM
**Label:** V3 re-install after code change kept running stale locally built images
**Summary:** Locally built images (bootstrap, smoke) were built only when missing, because install.sh ran `up` without `--build`. After new bootstrap code was synced, a re-install ran the old image: identity-sync fell through to the one-shot path and crash-looped. Fixed by having install.sh (the install and upgrade path) always run `up --build`; `lab up` stays fast. Anyone upgrading with `git pull` and install.sh would have hit this.
**Tags:** v3, upgrade, images, installer
**REGRESSED_N_TIMES:** 1
**Edges:**
- RELATES_TO → REG_UPGRADE_VOLUME_DATA_LOSS: another upgrade-path-only failure; test upgrades, not just clean installs
- RELATES_TO → WATCH_INSTALL_UPGRADE_PATH: V2 lesson that upgrade paths need their own testing
**Files:** `v3/install.sh`, `v3/compose/bootstrap.yaml`, `v3/tests/installer/test_unit.sh`
**Evidence:** dev host: install.sh re-run over existing v3-p1 → bootstrap 'created client lab-sync', identity-sync healthy, lab test 7/7
**Commit:** 39b2dce
**LastUpdated:** 2026-09-25

---

## NODE: REG_V3_STALE_BIND_MOUNT_CONFIG_ON_UPGRADE
**Type:** Regression
**Priority:** HIGH
**Label:** V3 upgrade kept services running old bind-mounted config (Trino rules.json, catalogs)
**Summary:** Upgrading Phase 1 to Phase 2 in place (install.sh re-run) failed: the new `samples` one-shot got PERMISSION_DENIED because Trino still ran the old rules.json and had no tpch catalog. Compose does not track bind-mounted file contents, and a single-file bind mount keeps the old inode after rsync/git replaces the file, so Trino/Caddy/JupyterHub/SeaweedFS/Spark were never restarted. Fix: installer/lib.sh lab_config_hashes derives LAB_CONFIG_HASH_<SVC> (cksum over config/<svc>) on every start (never stored), and each such service carries label lab.config-hash=${LAB_CONFIG_HASH_<SVC>:-}, so `up` recreates exactly the services whose config changed. Sibling of REG_V3_STALE_LOCAL_IMAGES_ON_UPGRADE (same class: upgrade leaves stale artifacts).
**Tags:** v3, upgrade, compose, bind-mount, config, trino
**REGRESSED_N_TIMES:** 1
**Edges:**
- RELATED_TO → REG_V3_STALE_LOCAL_IMAGES_ON_UPGRADE: same class (upgrade leaves stale local artifacts)
- RELATED_TO → WATCH_INSTALL_UPGRADE_PATH: upgrade path
**Files:** `v3/installer/lib.sh`, `v3/compose/edge.yaml`, `v3/compose/engines.yaml`, `v3/compose/storage.yaml`, `v3/compose/workspace.yaml`, `v3/compose/spark.yaml`, `v3/tests/installer/test_unit.sh`
**Symbols:** `lab_config_hashes`, `config_hash`, `lab_settings`
**Evidence:** Dev host upgrade of v3-p1: before fix samples exit 1 'Access Denied: Cannot execute query [SHOW SCHEMAS FROM lakehouse]'; after fix install.sh recreated caddy, trino, seaweedfs, jupyterhub, docker-proxy and samples created 5 tables; next re-run: identical container IDs. bash v3/tests/installer/run.sh -> 209 passed (config-hash section).
**LastVerified:** 2026-09-26
**Commit:** 6202fd0
**LastUpdated:** 2026-09-26

---

## NODE: REG_V3_SMOKE_AIRFLOW_SPA_LOGIN
**Type:** Regression
**Priority:** MEDIUM
**Label:** V3 smoke check 12: Airflow login from "/" returned before the SPA redirected to Keycloak
**Summary:** The first integrated engineer smoke failed check 12 with every Airflow API call 401: the browser helper opened airflow./ and returned as soon as the page was on the airflow host outside a login path, but Airflow 3's "/" is a SPA that redirects to /auth/login client-side, so no login ever happened. Fixed in tests/smoke/phase3.py: Airflow.login() starts at /auth/login (a LOGINISH path), so open() waits for the Keycloak round trip and the callback. Lesson: for SPA apps, start browser logins at the server-side login route, never at "/".
**Tags:** v3, smoke, airflow, login, spa, playwright
**REGRESSED_N_TIMES:** 1
**Edges:** _(none)_
**Files:** `v3/tests/smoke/phase3.py`
**Symbols:** `Airflow.login`, `UserSession.open`
**Evidence:** LAB_SMOKE_ONLY=12 ./lab test on the upgraded engineer install -> [PASS] 12 (alice 200/201, victor 403/403, eddie 200, 4 DAGs success)
**LastVerified:** 2026-09-26
**Commit:** 3b5516e
**LastUpdated:** 2026-09-26

---

## NODE: REG_V3_POSTGRES_HEALTHY_BEFORE_TCP
**Type:** Regression
**Priority:** MEDIUM
**Label:** V3: first-init Postgres reports healthy on the unix socket before it accepts TCP
**Summary:** On a fresh volume the postgres healthcheck passed while the server still refused TCP, so the superset-db one-shot failed. One-shots that talk to Postgres over the network (superset-db, airflow-db) must wait with `pg_isready -h postgres` first. Related: one-shots on the postgres image need a tmpfs at /var/lib/postgresql/data or each run leaves an anonymous volume (fixed for both airflow-db and superset-db at integration).
**Tags:** v3, postgres, one-shot, healthcheck, anonymous-volume
**REGRESSED_N_TIMES:** 1
**Edges:** _(none)_
**Files:** `v3/config/superset/init-db.sh`, `v3/config/airflow/init-db.sh`, `v3/compose/superset.yaml`, `v3/compose/airflow.yaml`
**LastVerified:** 2026-09-26
**Commit:** 3b5516e
**LastUpdated:** 2026-09-26

---

## NODE: REG_V3_TRINO_SERVICE_TOKEN_NEEDS_OPENID_SCOPE
**Type:** Regression
**Priority:** MEDIUM
**Label:** V3: Trino rejects service tokens without scope=openid (userinfo insufficient_scope)
**Summary:** Trino reads the principal from Keycloak's userinfo endpoint; a client-credentials token fetched without scope=openid makes userinfo answer insufficient_scope and Trino returns 401 "Invalid credentials". Every service client (superset, lab-batch, trino samples) must request scope=openid (keycloak.client_credentials_token defaults to it).
**Tags:** v3, trino, oidc, scope, service-account
**REGRESSED_N_TIMES:** 1
**Edges:** _(none)_
**Files:** `v3/config/superset/lab_trino.py`, `v3/dags/jobs/labjob.py`, `v3/bootstrap/keycloak.py`
**LastVerified:** 2026-09-26
**Commit:** 3b5516e
**LastUpdated:** 2026-09-26

---

## NODE: REG_V3_POSTGRES_RECREATE_BREAKS_DB_CLIENTS_ON_UPGRADE
**Type:** Regression
**Priority:** HIGH
**Label:** V3 upgrade that recreates postgres left DB clients with dead pools; bootstrap failed (Lakekeeper 500)
**Summary:** Raising POSTGRES_MEM made `install.sh` recreate postgres while keycloak, openfga, lakekeeper, Airflow and Superset kept running with dead connection pools. Bootstrap then got `GET /management/v1/info -> HTTP 500 DatabaseError` from Lakekeeper and `up --wait` failed; Airflow scheduler/dag-processor/triggerer crash-restarted after `up` had returned. Fix: every long-running postgres client declares `depends_on: postgres: {condition: service_healthy, restart: true}` (compose/identity.yaml, catalog.yaml, airflow.yaml, superset.yaml), so compose restarts them after recreating postgres and `--wait` waits for them. depends_on is not part of the compose config hash, so adding it recreates nothing.
**Tags:** v3, upgrade, postgres, compose, depends_on, restart
**REGRESSED_N_TIMES:** 1
**Edges:**
- RELATED_TO → REG_UPGRADE_VOLUME_DATA_LOSS: another upgrade-path failure class (in-place recreate of a shared dependency)
**Files:** `v3/compose/identity.yaml`, `v3/compose/catalog.yaml`, `v3/compose/airflow.yaml`, `v3/compose/superset.yaml`
**Evidence:** POSTGRES_MEM=800m ./install.sh on v3-p1 (full): postgres Recreated; keycloak, openfga, lakekeeper, airflow-*, superset Stopped/Started by compose; rc 0; bootstrap 'done'
**LastVerified:** 2026-09-26
**Commit:** 3b5516e
**LastUpdated:** 2026-09-26

---

## NODE: REG_V3_TRINO_CATALOG_SESSION_DIES_ON_KEYCLOAK_RESTART
**Type:** Regression
**Priority:** HIGH
**Label:** V3 Trino's Iceberg REST catalog auth session never recovers after Keycloak/Lakekeeper restart
**Summary:** Iceberg REST auth sessions stop refreshing after a refresh fails while Keycloak is restarting, then use an expired/invalid token forever. Seen twice at integration after an upgrade restarted Keycloak/Lakekeeper (postgres recreate + depends_on restart): (1) Trino (not restarted) failed every catalog call with ICEBERG_CATALOG_ERROR 'Failed to list namespaces' (refresh looping on 404 undefined_endpoint), failing `samples` and `up --wait`; (2) the Spark Connect executors' signer session for the lab-batch credential signed with an expired token (Lakekeeper 'ExpiredSignature' on /signer), so lab_spark_batch failed at writer close even for a 30 s job. Fix: trino, spark-worker and spark-connect depend on keycloak, lakekeeper AND postgres with `restart: true` (compose/engines.yaml, compose/spark.yaml). compose's `restart: true` is NOT transitive (recreating postgres restarts only its direct dependents), so the direct postgres entry is required. Residual: an unplanned Keycloak outage (not via compose) still breaks these sessions until Trino/Spark restart.
**Tags:** v3, trino, iceberg, rest-catalog, oauth2, keycloak, upgrade, restart
**REGRESSED_N_TIMES:** 1
**Edges:**
- RELATED_TO → REG_V3_POSTGRES_RECREATE_BREAKS_DB_CLIENTS_ON_UPGRADE: surfaced by that fix restarting Keycloak/Lakekeeper
**Files:** `v3/compose/engines.yaml`, `v3/compose/spark.yaml`, `v3/config/trino/catalog/lakehouse.properties`, `v3/dags/jobs/spark_batch.py`
**LastVerified:** 2026-09-26
**Commit:** 3b5516e
**LastUpdated:** 2026-09-26

---

## NODE: REG_V3_IMAGES_MATRIX_PROFILE_DROPS_BUILD_CONTEXT
**Type:** Regression
**Priority:** MEDIUM
**Label:** v3-images built the matrix from profile core; full-only superset lost its COPY --from=config context
**Summary:** v3-images.yml ran compose-check.sh --json-out with the default profile core, so services in [full] (superset) were absent from the compose JSON and images_matrix.py emitted build_contexts '' for them; 'COPY --from=config' would then be resolved by buildx as an image and fail. Fixed: the workflow uses --profile full (every built service), and images_matrix.py now errors when a Dockerfile's COPY --from names neither a stage, a build context nor an image reference (unit tests in v3/tests/lint/test_images_matrix.py, including one over the real Dockerfiles).
**Tags:** v3, ci, images, ghcr, compose-profile, buildx
**REGRESSED_N_TIMES:** 1
**Edges:**
- WATCHLIST → WATCH_CI_WORKFLOWS: images workflow must derive build contexts from the profile containing every built service
**Files:** `.github/workflows/v3-images.yml`, `v3/tools/images_matrix.py`, `v3/tests/lint/test_images_matrix.py`, `v3/images/superset/Dockerfile`
**Symbols:** `unresolved_copy_from`, `build_matrix`, `compose_extra_contexts`
**Evidence:** compose-check.sh --profile full --json-out c.json && images_matrix.py --compose-json c.json → superset build_contexts config=v3/config/superset; with the core JSON → ERROR COPY --from=config, rc 1
**LastVerified:** 2026-09-26
**Commit:** 3b5516e
**LastUpdated:** 2026-09-26

---

## NODE: REG_V3_SEAWEEDFS_BINDS_ONLY_DETECTED_IP
**Type:** Regression
**Priority:** MEDIUM
**Label:** V3 SeaweedFS listened only on its detected -ip; Spark executors on the `spark` network got Connection refused
**Summary:** After moving the Spark cluster to the internal `spark` network and attaching seaweedfs to lab+spark, every Spark write failed (smoke 10, lab_spark_batch in 12): executors got 'Connect to seaweedfs:8333 [seaweedfs/172.21.x.x] failed: Connection refused'. `weed server` binds all its ports to -ip.bind, which defaults to -ip, i.e. the one address it auto-detects (the lab interface). Fix: `-ip.bind=0.0.0.0` in config/seaweedfs/entrypoint.sh; -ip is left as detected (it only names in-container components). Any service added to a second network must be checked for single-address binding.
**Tags:** seaweedfs, network, bind, spark, v3
**REGRESSED_N_TIMES:** 1
**Edges:**
- RELATES_TO → DEC_V3_SPARK_INTERNAL_NETWORK: exposed by adding seaweedfs to the spark network
**Files:** `v3/config/seaweedfs/entrypoint.sh`, `v3/compose/storage.yaml`
**Evidence:** docker exec seaweedfs cat /proc/net/tcp: listeners 00000000:208D (8333) etc. after fix (were 020013AC only); smoke 10 PASS
**LastVerified:** 2026-09-26
**Commit:** 3b5516e
**LastUpdated:** 2026-09-26

---

## NODE: REG_V3_TRINO_CURRENT_USER_IN_AGGREGATE
**Type:** Regression
**Priority:** LOW
**Label:** Trino 483 fails on current_user in a GROUP BY select list (E3 job)
**Summary:** The E3 job's CREATE OR REPLACE TABLE ... SELECT ..., current_user AS written_by ... GROUP BY failed in Airflow with GENERIC_INTERNAL_ERROR "aggregation analysis not yet implemented for: io.trino.sql.tree.CurrentUser". Fixed by reading SELECT current_user first and binding it as a parameter. current_user in an outer non-aggregating SELECT over a grouped subquery (E4 notebook) works.
**Tags:** v3, trino, sql, tracks, e3
**REGRESSED_N_TIMES:** 1
**Edges:** _(none)_
**Files:** `v3/tracks/engineer/E3-your-first-dag/jobs/orders_summary.py`
**Symbols:** `build`
**Evidence:** task log dag_id=u_eddie_orders_summary scheduled__2026-09-26 build_summary: TrinoQueryError INTERNAL_ERROR; after fix manual run success, check E3 PASSED
**LastVerified:** 2026-09-26
**Commit:** 3e6f45c
**LastUpdated:** 2026-09-26
**Author:** engineer-track

---

## NODE: REG_V3_WORKSPACE_KERNEL_FIRST_MESSAGE_STALL
**Type:** Regression
**Priority:** HIGH
**Label:** V3 workspace kernel ignored its first execute (ipykernel 7.x shell-thread missed wakeup): smoke 'kernel timeout / HTTP 403'
**Summary:** Intermittent workspace-kernel failures (Phase 3 alice 'HTTP 403 / no result' on checks 8/10; Phase 4 loop kernel_timeout) were one bug: ipykernel 7.x (7.3.0) sometimes leaves a shell message that arrives right after kernel start unread on its shell socket; the kernel stays idle and processes it only when a NEW zmq peer sends a shell message (not a control message, not a second message from the same peer). A learner sees a first cell that never runs. The 'HTTP 403' was secondary: workspace.py's stack-dump fetch sent no X-XSRFToken, which JupyterHub >= 4.1 requires on non-navigation GETs. Fix: workspace image holds ipykernel at 6.31.0 (IPYKERNEL_VERSION, v3/.pins/tooling.env, requirements.in, relocked); harness read_file sends the XSRF header. Not an external cause, so no retries.
**Tags:** v3, workspace, jupyter, ipykernel, flaky, kernel, xsrf, smoke
**REGRESSED_N_TIMES:** 1
**Edges:**
- RELATED_TO → WATCH_V3_SPARK_CONNECT_INTERMITTENT_HANG: same signature is the likely explanation of that 'hang after refusal' (the refusal was logged when the stalled request ran at teardown)
- RELATED_TO → DEC_V3_WORKSPACE_JUPYTERHUB_CODESERVER_DBT: workspace image dependency pin
**Files:** `v3/images/workspace/requirements.in`, `v3/images/workspace/Dockerfile`, `v3/images/workspace/lock/constraints.txt`, `v3/versions.env`, `v3/compose/workspace.yaml`, `v3/tests/smoke/workspace.py`, `v3/tests/smoke/kernel_probe.py`, `v3/tests/smoke/kernel_loop.py`, `v3/tests/smoke/kernel-loop.sh`, `v3/tools/kernel_ws_race.py`
**Symbols:** `KERNEL_EXEC_JS`, `Workspace.read_file`, `Workspace.run_probe`, `probe`
**Evidence:** Dev host, project v3-p4-tooling (engineer), tests/smoke/kernel-loop.sh (login->spawn->kernel->Trino+Spark->stop): before the fix 3/120 kernel_timeout (eddie, anna, victor; plus 1/26 in the interrupted baseline), every one with kernel execution_state=idle after 300 s, 3 nudge status msgs and 0 msgs for our execute, and ~/.smoke-progress.txt showing the probe started only at websocket close. With ipykernel 6.31.0: 0/120 kernel failures (1 unrelated stop_failed: Caddy->CHP keep-alive 502 on DELETE). Lab-less repro v3/tools/kernel_ws_race.py on the image's Jupyter stack: 7.3.0 lost 43/400 (execute sent on open) and 6/80 kernel_info handshakes (JupyterLab style), each released only by a shell message from a second websocket; 6.31.0 lost 0/400 at normal load (1/300 more during a concurrent image build had state 'starting' after 10 s: a slow start, not this signature).
 Integrated tree (IPYKERNEL_VERSION promoted to versions.env, Caddy keepalive 4s): project v3-p4 (full), kernel-loop.sh --iterations 30 -> 120/120 ok (30 per user), 0 failures, median 22.5 s (dev host ~/lakehouse-v3/p4-integ-loop2). An earlier integrated loop had 85/85 ok before a hypervisor shutdown of the host.
**LastVerified:** 2026-09-26
**Commit:** 3e6f45c
**LastUpdated:** 2026-09-26
**Author:** tooling-ci

---

## NODE: REG_V3_USER_DAG_FOLDERS_WRITABLE_BY_ALL_ENGINEERS
**Type:** Regression
**Priority:** HIGH
**Label:** V3 Phase 4: any engineer could write another user's DAG folder (whole dags-user volume mounted rw)
**Summary:** Phase 4 verification: as eddie, mkdir ~/airflow-dags/alice and a file with dag_id u_alice_planted_by_eddie was accepted by Airflow (owner alice, tag user:alice) and ran to success; eddie could also edit or delete alice's DAGs. Cause: every workspace runs as uid 1000 and the whole <project>_dags-user volume was mounted rw, so the DAG-id policy (which cannot know who wrote a file) was the only separation. Fix: each engineer/lab-admin workspace mounts only its own folder (volume Mount, Subpath=<username>, at ~/airflow-dags/<username>); the hub creates the folder in its own mount of the volume; the Docker proxy allows exactly that one Mounts entry and no bind of the volume. Smoke check 17 now asserts, as eddie, one mount under ~/airflow-dags, own write ok, neighbour mkdir EACCES; as anna, no mount.
**Tags:** v3, phase4, airflow, user-dags, isolation, docker-proxy, jupyterhub
**REGRESSED_N_TIMES:** 1
**Edges:**
- RELATES_TO → DEC_V3_USER_DAGS_SHARED_VOLUME: the decision's first design; fixed by per-user subpath mounts
- RELATES_TO → INV_V3_DOCKER_PROXY_PROJECT_SCOPE: the allowlist gained one exact Mounts shape
**Files:** `v3/config/jupyterhub/jupyterhub_config.py`, `v3/config/jupyterhub/docker-proxy.cfg`, `v3/compose/workspace.yaml`, `v3/config/airflow/dags-user-init.sh`, `v3/tests/smoke/tracks.py`, `v3/tests/smoke/proxy_probe.py`
**Symbols:** `LabSpawner._workspace_volumes`, `ensure_user_dag_folder`, `dags_isolation_code`
**Evidence:** v3-p4r (full) check 17: dags_isolation_eddie {mounts:[/home/jovyan/airflow-dags/eddie root .../v3-p4r_dags-user/_data/eddie], listing:[eddie], own_write: ok, neighbour_write: EACCES}; dags_isolation_anna {mounts: []}; check 11 {"cases": 30, "unexpected": []}
**LastVerified:** 2026-09-26
**Commit:** 3e6f45c
**LastUpdated:** 2026-09-26

---

## NODE: REG_V3_DOCKER_PROXY_BODY_REGEX_BYPASS
**Type:** Regression
**Priority:** HIGH
**Label:** V3 Docker socket proxy body regexes bypassed (Docker decodes JSON case-insensitively, \u escapes, last duplicate wins)
**Summary:** The docker-socket-proxy validated container-create bodies with HAProxy regexes over raw JSON. Three rounds found holes in the same class: Phase 2 follow-up (foreign volumes via Binds/Mounts/VolumesFrom/endpoints were not scoped), Phase 4 repair (the DAG Mounts shape; a second Mounts key), and the Phase 4 follow-up verifier's proven 201 creates mounting another project's postgres-data volume with a lowercase "binds", an escaped "Mounts", and a second escaped Mounts key after the allowed DAG mount. Fixed at the root: a stdlib docker-guard service (bootstrap/docker_guard.py) between JupyterHub and the proxy parses bodies strictly (UTF-8, no duplicate keys, no NaN, no lone surrogates), requires every key to be one exact canonical spelling, validates every value, and forwards only its own json.dumps re-serialization; the proxy keeps only its method/path allowlist and its body ACLs were removed.
**Tags:** v3, docker, security, jupyterhub, socket-proxy, json, parser-differential
**REGRESSED_N_TIMES:** 3
**RootCause:** (1) Source of truth: the request body AS DOCKER DECODES IT (Go encoding/json: keys matched to struct fields case-insensitively, \u escapes decoded, the last of duplicate keys wins, unknown keys ignored). The proxy never read that; it pattern-matched the raw bytes, a different language than the one Docker executes. (2) Invariant violated: INV_V3_DOCKER_PROXY_PROJECT_SCOPE (a workspace container may use only this user's home, the trust volume, its own DAG folder and the lab network). (3) Why prior fixes were symptomatic: each round (Phase 2 follow-up allowlist regexes, Phase 4 Mounts-shape regex with a named group and a 'second Mounts key' regex) added another regex for the spelling that had just been shown to work, so every fix covered one encoding of the attack while any other encoding (other case, escapes, duplicates, key order) still meant the same thing to Docker. The fix removes the mismatch instead: the guard decodes with a strict JSON parser, refuses anything whose meaning could differ between decoders (duplicates, non-canonical keys, invalid UTF-8, surrogates), validates the decoded structure against an exact allowlist, and forwards only bytes it serialized itself, so Docker and the policy read the same object.
**Edges:**
- VIOLATED_BY → INV_V3_DOCKER_PROXY_PROJECT_SCOPE: bodies Docker decoded differently from the regexes mounted foreign volumes
- RELATES_TO → DEC_V3_DOCKER_PROXY_NAME_ALLOWLIST: the path/name allowlist stays in the proxy; bodies moved to docker-guard
- RELATES_TO → REG_V3_USER_DAG_FOLDERS_WRITABLE_BY_ALL_ENGINEERS: the Phase 4 repair added the Mounts regex this class then bypassed
**Files:** `v3/bootstrap/docker_guard.py`, `v3/config/jupyterhub/docker-proxy.cfg`, `v3/compose/workspace.yaml`, `v3/compose.yaml`, `v3/tests/bootstrap/test_docker_guard.py`, `v3/tests/smoke/proxy_probe.py`, `v3/tests/smoke/run.sh`
**Symbols:** `decide`, `validate_create`, `validate_volume_create`, `strict_loads`, `canonical`
**Evidence:** python3 -m unittest discover -s v3/tests/bootstrap (test_docker_guard: the verifier's three bypasses + case variants, escapes, duplicates, unknown keys, nested tricks all Reject); smoke check 11 → {"cases": 54, "unexpected": []} and the guard log holds the canonical body's sha256
**LastVerified:** 2026-09-26
**Commit:** 3e6f45c
**LastUpdated:** 2026-09-27

---

## NODE: REG_V3_WORKSPACE_LOGIN_SHELL_LOSES_LAB_PATH
**Type:** Regression
**Priority:** HIGH
**Label:** V3 workspace: JupyterLab terminals (bash -l) lost /opt/lakehouse/bin: lab-tracks not found, dbt without its token shim
**Summary:** JupyterLab terminals run `bash -l`; Debian's /etc/profile resets PATH, so the image's ENV PATH entry /opt/lakehouse/bin was dropped: `lab-tracks: command not found`, and `dbt` resolved to /usr/local/bin/dbt without the token shim, so A3 failed entirely for a beginner. Every smoke check ran commands from kernels (non-login subprocesses), so none saw it. Fix: /etc/profile.d/lakehouse.sh in the workspace image puts /opt/lakehouse/bin first again (idempotent: removes any existing entry, then prepends); PYTHONPATH/JUPYTERHUB_USER are inherited and verified. Smoke check 17 now opens a REAL JupyterLab terminal (POST api/terminals + terminals websocket) once per run and requires `command -v lab-tracks dbt lab-token` under /opt/lakehouse/bin, JUPYTERHUB_USER, PYTHONPATH, `import lakehouse`, and a `lab-tracks check A1` run there. A3 README/tutor common-mistakes rows updated.
**Tags:** v3, workspace, terminal, path, tracks, dbt, beginner
**REGRESSED_N_TIMES:** 1
**Edges:**
- RELATES_TO → DEC_V3_WORKSPACE_TOKEN_VIA_HUB_AUTH_STATE: the dbt shim that adds the token lives in /opt/lakehouse/bin
**Files:** `v3/images/workspace/etc/profile.d/lakehouse.sh`, `v3/images/workspace/Dockerfile`, `v3/tests/smoke/workspace.py`, `v3/tests/smoke/tracks.py`, `v3/tests/smoke/test_tracks_unit.py`, `v3/tracks/analyst/A3-first-dbt-model/README.md`, `v3/tracks/analyst/A3-first-dbt-model/tutor.md`
**Symbols:** `terminal_check`, `parse_terminal`, `Workspace.terminal`
**Evidence:** LAB_SMOKE_LONG=1 ./lab test --tracks all on upgraded v3-p1 and clean room v3-p4g → 17/17; '[info] 17 anna terminal ok=True' (real JupyterLab terminal: lab-tracks, dbt, lab-token under /opt/lakehouse/bin; lab-tracks check A1 rc=1)
**LastVerified:** 2026-09-26
**Commit:** 3e6f45c
**LastUpdated:** 2026-09-27

---

## NODE: REG_V3_AI_CHECK18_SPEND_RESTORE_RACE
**Type:** Regression
**Priority:** MEDIUM
**Label:** V3 smoke check 18 left users over their AI budget (restore raced LiteLLM's batched spend writes)
**Summary:** Check 18 lifts a test user's gateway budget, runs the ~100k-token mock loop, then restores budget and spend. LiteLLM writes spend to Postgres in batches (~10 s), so the loop's last batch landed after the restore: victor ended at 18.69 (v3-p1) / 10.15 (clean room) of 5 USD and his next real persona request was refused. Fixed: Gateway.settle_spend waits until spend is unchanged for 25 s before restoring, and the restore reports the spend read back. Same integration run: the persona's friendly_error did not recognise the lab gateway's 'budget ... used up' wording (written against a stand-in gateway); mapping and unit test fixed.
**Tags:** v3, phase5, ai, gateway, budget, litellm, smoke, race
**REGRESSED_N_TIMES:** 1
**Edges:**
- RELATES_TO → DEC_V3_AI_GATEWAY_LITELLM_OSS_BUILD: spend is batched by LiteLLM
- RELATES_TO → DEC_V3_WORKSPACE_AI_PERSONA_KEY_PER_SPAWN: persona error mapping
**Files:** `v3/tests/smoke/ai_check.py`, `v3/images/workspace/lakehouse/ai.py`, `v3/tests/workspace/test_lab_ai.py`
**Symbols:** `Gateway.restore_budget`, `Gateway.settle_spend`, `friendly_error`
**Evidence:** LAB_SMOKE_ONLY=18 ./lab test on v3-p1 and v3-p5 -> '[info] victor's AI budget restored: HTTP 200, spend now 0.0 (was 0)'; persona with victor budget 1e-6 -> 'You have used up your AI budget for now...'
**LastVerified:** 2026-09-27
**Commit:** bb0cd2f
**LastUpdated:** 2026-09-27

---

## NODE: REG_V3_AI_GATEWAY_USER_KEY_REACHES_ADMIN_ROUTES
**Type:** Regression
**Priority:** HIGH
**Label:** V3 Phase 5: workspaces talked to LiteLLM directly; a user key could call /health (fan-out to every model) and /model/info (api_base leak)
**Summary:** Phase 5 put ai-gateway on `lab` and gave workspaces http://ai-gateway:4000. LiteLLM's MIT build lets any virtual key call GET /health (a real request to every configured model, no budget charge: free load on the owner's GPU server) and /model/info, /v1/model/info (each deployment's api_base, e.g. the model server's host:port); x-litellm-model-api-base response headers leaked it too. Root cause: no single place decided which gateway routes users may call (LiteLLM's route checks are role-based and open for inference-adjacent routes). Fix: gateway only on the new `ai` network; ai-frontdoor (bootstrap/ai_frontdoor.py) is the only path and its ROUTES the only allowlist; broker hands out the front door URL.
**Tags:** v3, ai, gateway, litellm, health, model-info, api-base, leak, network
**REGRESSED_N_TIMES:** 1
**Edges:**
- RELATED_TO → DEC_V3_AI_GATEWAY_LITELLM_OSS_BUILD: gateway build that exposed the routes
- RELATED_TO → REG_V3_DOCKER_PROXY_BODY_REGEX_BYPASS: same class (a policy that depended on the upstream's own checks)
**Files:** `v3/compose/ai.yaml`, `v3/compose.yaml`, `v3/bootstrap/ai_frontdoor.py`, `v3/bootstrap/ai_gateway.py`, `v3/images/workspace/lakehouse/ai_cli.py`, `v3/tests/ai/test_ai_frontdoor.py`, `v3/tests/ai/gateway_e2e.py`, `v3/tests/smoke/ai_check.py`
**Symbols:** `ai_gateway.mint`, `ai_frontdoor.decide`
**Evidence:** v3-p1 upgrade + v3-p5h clean room (2026-09-27): ai-gateway only on <project>_ai; from a lab-only container ai-gateway:4000 fails (gaierror by name, timeout by IP); user key via ai-frontdoor: /health, /model/info, /v1/model/info 403, no x-litellm-* response header; smoke 18/18 PASS
**LastVerified:** 2026-09-27
**Commit:** 0dc8f05
**LastUpdated:** 2026-09-27

---

## NODE: REG_V3_AI_END_USER_SPOOFABLE_IN_SPEND_LOGS
**Type:** Regression
**Priority:** MEDIUM
**Label:** V3 Phase 5: a request body `user` (or customer-id header) set the spend-log end user to anyone
**Summary:** LiteLLM derives the end user from the body `user` (and x-litellm customer-id headers) and records it in SpendLogs.end_user and end-user spend, so alice's key could attribute calls to 'victor'. lab_hooks only checked configuration. Fix: config/ai/lab_hooks.py attribute_to_key_owner (async_pre_call_hook, which runs after add_litellm_data_to_request) OVERWRITES data['user'], user_api_key_dict.end_user_id and metadata/litellm_metadata user_api_key_end_user_id (+ the user_api_key_auth copy) with the key's user_id; a key without user drops it. The front door also drops customer-id headers. Tested: unit (test_render_config Hooks) and gateway_e2e spoofed_user_check (spend log end_user == key owner).
**Tags:** v3, ai, gateway, litellm, spend, attribution, end-user
**REGRESSED_N_TIMES:** 1
**Edges:**
- RELATED_TO → REG_V3_AI_GATEWAY_USER_KEY_REACHES_ADMIN_ROUTES: found in the same review
**Files:** `v3/config/ai/lab_hooks.py`, `v3/tests/ai/test_render_config.py`, `v3/tests/ai/gateway_e2e.py`
**Symbols:** `lab_hooks.attribute_to_key_owner`, `LabHooks.async_pre_call_hook`
**Evidence:** tests/ai/gateway-e2e.sh on v3-p1 and v3-p5h: chat via ai-frontdoor with user='e2e-spoof-victim' -> /spend/logs row user=end_user=<key owner>; spend_log_end_users == [owner]
**LastVerified:** 2026-09-27
**Commit:** 0dc8f05
**LastUpdated:** 2026-09-27

---

## NODE: REG_V3_GATEWAY_E2E_CONFIGURES_LOCAL_PROVIDER_BY_DEFAULT
**Type:** Regression
**Priority:** MEDIUM
**Label:** V3 Phase 5: tests/ai/gateway-e2e.sh always configured the `local` provider (pointed at the mock), breaking the dev-host quiet-hours rule
**Summary:** gateway-e2e.sh step 3 (local-via-mock) always recreated ai-gateway with LAB_AI_LOCAL_URL=http://ai-mock:8000/v1, so every run configured the `local` provider, which the owner's quiet-hours rule forbids on the dev host (a real llama-server listens there). No request reached llama-server, but the Phase 5 follow-up record wrongly said LAB_AI_LOCAL_URL stayed empty (it ran on v3-p5, v3-p1 at 09:59 UTC and v3-p5h). Fix at the root, in the script: step 3 is opt-in (LAB_E2E_LOCAL_VIA_MOCK=1, anything but 0/1 refused), and the script stops before any request unless the gateway's rendered state.json has providers exactly [mock] (steps 1 and 4 run with the lab's own settings). tests/ai/test_gateway_e2e_script.py runs the script against a fake docker and asserts every compose up has an empty LAB_AI_LOCAL_URL by default.
**Tags:** v3, ai, gateway, tests, quiet-hours, local-provider, mock
**Edges:**
- RELATED_TO → DEC_V3_PHASE5_INTEGRATION_WIRING: tests use the mock model only; now the local-provider path is opt-in too
- RELATED_TO → REG_V3_AI_GATEWAY_USER_KEY_REACHES_ADMIN_ROUTES: found in the same follow-up's verification
**Files:** `v3/tests/ai/gateway-e2e.sh`, `v3/tests/ai/test_gateway_e2e_script.py`, `v3/PHASE5_RESULTS.md`, `v3/CONTRACT.md`
**Evidence:** python3 -m unittest v3/tests/ai/test_gateway_e2e_script.py -> 4 OK (mutation: forcing step 3 on fails test_default_never_configures_the_local_provider); v3-p1 run 2026-09-27 12:46-12:51 UTC: '3. local provider path: SKIPPED', AI GATEWAY E2E: PASS, gateway env LAB_AI_LOCAL_URL empty, out/ai-e2e has no recreate-local.log
**LastVerified:** 2026-09-27
**Commit:** 0dc8f05
**LastUpdated:** 2026-09-27
**Author:** claude-code
