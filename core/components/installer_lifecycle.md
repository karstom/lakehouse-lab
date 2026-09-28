## NODE: INSTALLER_LIFECYCLE
**Type:** Component
**Priority:** HIGH
**Label:** Install, start, upgrade, backup lifecycle scripts
**Summary:** `install.sh` (curl-piped one-liner) installs Docker if needed, downloads the repo into `INSTALL_DIR` (default `lakehouse-lab`, overridable with `--dir`), generates `.env`, and handles existing installs via smart/legacy upgrade or replace. `start-lakehouse.sh` detects the host IP, creates named volumes, and starts services in dependency order (with Iceberg/JupyterHub overlays when enabled); it also provides `reset`, `status` and `logs`. Backup/restore and volume migration live alongside. The volume prefix is derived from the directory name while compose hardcodes `lakehouse-lab_`, so a non-default `--dir` breaks startup.
**Tags:** installer, upgrade, startup, backup
**Edges:**
- CONTAINS → REG_UPGRADE_VOLUME_DATA_LOSS: upgrade/migration data loss
- CONTAINS → REG_HOST_IP_DETECTION: detect_host_ip lives here
- DEPENDS_ON → DEC_NAMED_EXTERNAL_VOLUMES: creates the external volumes
- RELATES_TO → WATCH_INSTALL_UPGRADE_PATH: high-risk upgrade code
**Files:** `install.sh`, `legacy/v2/start-lakehouse.sh`, `legacy/v2/scripts/backup-lakehouse.sh`, `legacy/v2/scripts/restore-lakehouse.sh`, `legacy/v2/scripts/setup-wizard.sh`, `legacy/v2/scripts/configure-services.sh`, `legacy/v2/scripts/health-summary.sh`, `legacy/v2/examples/cron-backup-setup.sh`
**Symbols:** `detect_host_ip`, `create_named_volumes`, `start_with_dependencies`, `reset_environment`, `perform_smart_upgrade`
**Paths:** `legacy/v2/scripts/install`
**LastUpdated:** 2026-09-25
