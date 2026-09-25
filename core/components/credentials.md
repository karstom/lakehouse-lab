## NODE: CREDENTIALS
**Type:** Component
**Priority:** HIGH
**Label:** Credential generation, display, rotation, user provisioning
**Summary:** `generate-credentials.sh` writes `.env` with memorable passphrases for UI logins and URL-safe passwords for databases; `show-credentials.sh` prints URLs and logins; `rotate-credentials.sh` and `install/fix-credentials.sh` regenerate or repair them; `provision-user.sh` adds users with admin/analyst/viewer roles across services. Changing a password in `.env` does not change it inside already-initialized Postgres/MinIO volumes, which is how upgrade credential mismatches arise.
**Tags:** credentials, security, users
**Edges:**
- CONTAINS → REG_CREDENTIAL_PROPAGATION: consumers drifting from .env
- DEPENDS_ON → INV_ENV_IS_CREDENTIAL_SOURCE: single-source rule
- DEPENDS_ON → INV_DB_PASSWORDS_URL_SAFE: DB password charset
- RELATES_TO → ISSUE_WEAK_CREDENTIAL_RNG: $RANDOM-based generation
**Files:** `scripts/generate-credentials.sh`, `scripts/show-credentials.sh`, `scripts/rotate-credentials.sh`, `scripts/install/fix-credentials.sh`, `scripts/provision-user.sh`, `.github/workflows/credential-rotation-reminder.yml`
**Symbols:** `generate_passphrase`, `generate_strong_password`, `generate_db_safe_password`
**LastUpdated:** 2026-09-25
