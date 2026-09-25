# V3 Phase 1 Results (`core` profile)

> Integration report for Phase 1, built against `v3/CONTRACT.md`. The three workstreams (CORE,
> INSTALLER, TOOLING + CI) built in parallel; the integrator merged their pins, resolved
> interface mismatches, ran a clean-room install on the shared dev host, and checked
> idempotency. Host names, IPs and domains of the dev host are deliberately left out.

## Exit criteria

| Criterion | Result |
|---|---|
| Fresh Linux install reaches a Trino query **as a Keycloak-logged-in user** in < 15 min | **Met: 1 min 59 s** from `install.sh` to a green `lab test` (see Timings) |
| The Iceberg table from that query is readable through the catalog with vended credentials | **Met:** smoke check 4 (PyIceberg via Lakekeeper, STS credentials, sibling prefix denied) |
| CI runs the same path | **Wired, not yet run on GitHub:** `v3-ci.yml` e2e job runs `install.sh --non-interactive --seed-test-users --domain lab.localhost` then `lab test`. That domain's smoke path now passes 6/6 locally (see Repair round) |
| WSL2 fresh install | **Met after repair:** WSL2 (7.9 GB RAM), `lab.localhost`, ports 18443/18080: `install.sh` 118 s, `lab test` **6/6** (see Repair round) |

## What was built

**Stack (CORE)** — `compose.yaml` plus `compose/{edge,identity,storage,catalog,bootstrap,engines,test}.yaml`:

- **Caddy** with the installer's root CA from `${LAB_STATE_DIR}/ca` as its PKI root. Every
  public hostname (`auth.`, `trino.`, `catalog.`, `console.`) is a network alias on `lab`,
  so issuer URLs match inside containers and in browsers. An explicit HTTP site on
  `LAB_HTTP_PORT` redirects (308) to HTTPS and keeps a non-standard port.
- **Keycloak** imports the templated `lakehouse` realm (clients `trino`, `lakekeeper`,
  `lakekeeper-ui` (public, PKCE), `console`; groups `lab-admin`, `engineer`, `analyst`,
  `viewer`).
- **Postgres** with one database per service (Keycloak, Lakekeeper, OpenFGA).
- **SeaweedFS** with identities, STS and JWT security rendered at start by
  `config/seaweedfs/entrypoint.sh`. The STS trust policy names only the `lakekeeper` identity.
- **Lakekeeper** with OIDC and **OpenFGA** authorization (OQ-5 adopted).
- **Trino** using Iceberg REST through Lakekeeper with vended credentials, OAuth2 for the web
  UI, JWT for clients, file-based access control and a file group provider (OQ-17).
- **One-shots:** `trust-init` (CA bundle into the `trust` volume), `openfga-migrate`,
  `lakekeeper-migrate`, and the idempotent Python `bootstrap` (Keycloak users/groups, Trino
  group file, bucket via SigV4, Lakekeeper bootstrap + warehouse, OpenFGA grants).
- **Smoke test** (`tests/smoke/`): six contract checks; checks 2-5 run in a pinned Playwright
  container on the `lab` network that trusts only the lab CA.

**Installer (INSTALLER)** — `install.sh`, `lab`, `installer/*.sh`:

- Prerequisite checks (Docker >= 24, Compose >= 2.20 hard; RAM/disk warn; WSL2 hints).
- Chooses `LAB_DOMAIN` once (`lab.localhost`, `sslip` shortcut, or custom); changing domain
  or project needs `--reconfigure`.
- Writes `.env` and `.secrets.env` (mode 600) from a CSPRNG; the CA is created once (EC
  P-256, 10 years) and never regenerated.
- `.env` is authoritative over the calling shell, so a stray `COMPOSE_PROJECT_NAME` cannot
  redirect compose to another project.
- `lab up|down|status|urls|logs|reset|test|ca`; `down` refuses `-v`, `reset` needs
  confirmation and is scoped to the project.

**Tooling + CI (TOOLING)** — `tools/`, `tests/lint/`, `.github/workflows/v3-{ci,images}.yml`:

- `check_versions.py` (no version literals outside `versions.env`), `check_compat.py`
  (Iceberg/Spark/Scala/PySpark/Python), pinned `shellcheck.sh` and `actionlint.sh`,
  `compose-check.sh` (contract command with generated env files), `images_matrix.py`.
- `v3-ci.yml`: lint job, then e2e job (real install + `lab test`, redacted diagnostics on
  failure). `v3-images.yml`: image matrix from `images/*/Dockerfile`, pushes to GHCR only on
  dispatch or `v3.*` tags.

## Integration changes

- **Pins merged into `versions.env`:** `PYARROW_VERSION` (smoke image), `ACTIONLINT_IMAGE_TAG/DIGEST`,
  `SHELLCHECK_IMAGE_TAG/DIGEST`. `v3/.pins/` was removed. The tools still read
  `v3/.pins/*.env` if one appears, as a staging area for later phases.
- **Duplicate ShellCheck pin removed:** INSTALLER's `SHELLCHECK_VERSION` and TOOLING's
  `SHELLCHECK_IMAGE_TAG` named the same thing. `tests/installer/run.sh` now uses
  `SHELLCHECK_IMAGE_TAG@SHELLCHECK_IMAGE_DIGEST`, like `tools/shellcheck.sh`.
- **Bug fixed:** `tests/installer/run.sh` expanded its file globs relative to the caller's
  working directory, so it failed when run from the repo root (as CI does). It now `cd`s
  into `v3/` first.
- **check_versions findings fixed:** the installer's fake Docker/Compose versions (test
  data, not pins) now carry `# check-versions: ignore <reason>`.
- **CI:** the lint job also runs the installer unit tests (`tests/installer/test_unit.sh`,
  fake docker, no daemon).
- ~~No mismatch was found between installer, compose and CI~~ **Refuted by the verifier:**
  CI e2e uses `--domain lab.localhost`, and smoke check 2 failed on that domain (fixed in
  the Repair round below). Env var names, paths and commands do match: `lab test` calls `tests/smoke/run.sh`, both read `COMPOSE_PROJECT_NAME` and
  `LAB_PROFILE` from `.env`, the installer writes every secret key compose consumes, and
  `LAB_SEED_TEST_USERS` / `LAB_TEST_USER_PASSWORD` match between installer and bootstrap.

## Repair round (after independent verification)

The verifier failed the first integration on two points; both are fixed.

1. **Smoke check 2 failed on `lab.localhost`** (the WSL2 default and CI's domain) with
   `net::ERR_CONNECTION_REFUSED`: Chromium hard-wires `*.localhost` to loopback and never
   asks Docker DNS for Caddy's alias. `tests/smoke/smoke.py` now resolves
   `trino.<LAB_DOMAIN>` through Docker DNS (like every other client in the container) and
   launches Chromium with `--host-resolver-rules=MAP *.<LAB_DOMAIN> <that IP>`. Every lab
   hostname is a Caddy alias, so one IP covers all of them. The same code runs for every
   domain; the resolved IP is recorded in the check's evidence.
2. **ADR-012 amendment (base images by tag AND digest):** the smoke Dockerfile's
   Playwright base had no digest. Added `PLAYWRIGHT_IMAGE_DIGEST` to `versions.env` (the
   multi-arch index digest of `v1.63.0-noble`, identical to the one cached on the dev host),
   passed it as a build arg in `compose/test.yaml`, and changed the Dockerfile to
   `FROM ...:${PLAYWRIGHT_IMAGE_TAG}@${PLAYWRIGHT_IMAGE_DIGEST}`. `images_matrix.py` picks
   the new ARG up automatically.
3. **`check_versions.py` now enforces it:** new rule `from-digest` flags any Dockerfile
   `FROM` (other than `scratch` or an earlier stage) whose reference lacks
   `@${*_DIGEST}`, including a whole-reference variable (`FROM ${BASE_IMAGE}`), which
   would hide the digest. Two new unit tests; reverting the smoke Dockerfile makes the
   checker fail with `[from-digest]`.
4. **Host-tool thresholds documented as an exemption:** `LAB_MIN_DOCKER` / `LAB_MIN_COMPOSE`
   in `installer/checks.sh` gate the host, they do not pin anything the lab runs or builds.
   They stay there; the exemption is written in `checks.sh` and in the checker's docstring.
5. **Housekeeping:** `v3-images.yml` no longer lists `v3/.pins/**` in its path filters.
   Stale dev-host directories (`p1`, `p1.pre-integration-*`, `p1-verify`) were removed after
   `down -v` of `v3-p1`.

### WSL2 re-run (`lab.localhost`)

Local WSL2 machine (7.9 GB RAM), project `v3-wsl`, fresh copy of `v3/` (no `.env`,
`.secrets.env` or `state/`), ports 18443/18080:

```
v3/install.sh --non-interactive --seed-test-users --domain lab.localhost \
  --https-port 18443 --http-port 18080 --project-name v3-wsl      # rc 0, 118 s
v3/lab test                                                       # rc 0
```

```
[PASS] 1.stack_healthy: 11 services healthy or completed
[PASS] 6.no_static_s3_key_in_trino: 0 key settings and no admin key value in 125 lines ...
[PASS] 2.browser_login_trino_ui: final_url https://trino.lab.localhost:18443/ui/#/dashboard, keycloak_password_prompts 1, ui_api_stats 200, ui_api_cluster 200
[PASS] 3.trino_alice_create_insert_read: current_user alice, inserted 3, rows read back
[PASS] 4.pyiceberg_vended_credentials: STS key (ASIA...), own prefix write allowed, sibling prefix denied (AccessDenied)
[PASS] 5.viewer_write_denied: victor SELECT ok; INSERT -> PERMISSION_DENIED
SMOKE: PASS (6/6)
```

The build log shows the smoke image rebuilt from the base resolved by tag and
`PLAYWRIGHT_IMAGE_DIGEST`. Idle memory:
trino 827 MiB, keycloak 582, postgres 150, seaweedfs 69, openfga 42, lakekeeper 27,
caddy 17. Torn down with `down -v` of `v3-wsl` (0 containers, 0 volumes left).

### Dev-host re-run after repair: done by the independent verifier

The verifier started from a clean state (`v3-p1` had 0 containers and volumes) and ran on
the dev host with the sslip domain and ports 18443/18080:
- `install.sh`: **99 s**
- `lab test`: **SMOKE: PASS (6/6)** in 19 s, with 1 password prompt and `current_user=alice`
- Idempotent re-install: 8 s. Secrets, CA and container IDs unchanged; bootstrap reported
  all steps unchanged.
- `lab down` then `lab up`: data (3 rows, 2 snapshots) and the CA fingerprint kept.
- Independent WSL2 re-run on `lab.localhost`: install 118 s, smoke 6/6, peak host RAM
  3.5 GB of 7.9 GB.

Verdict: **pass**, no rule violations. The `v3-p1` stack is left running on the dev host.

## Timings (dev host, project `v3-p1`, ports 18443/18080)

Clean room: `down -v` of the previous `v3-p1`, a fresh remote directory (no `.env`,
`.secrets.env` or `state/`), then:

```
v3/install.sh --non-interactive --seed-test-users --project-name v3-p1 \
  --domain <dashed-ip>.sslip.io --https-port 18443 --http-port 18080
v3/lab test
```

| Step | Wall clock |
|---|---|
| `install.sh` (checks, config, secrets, CA, `up -d --wait` to healthy) | 99 s |
| `lab test` (includes smoke image build check) | 20 s |
| **Total, fresh install to green smoke** | **1 min 59 s** |
| Second `install.sh` (idempotent re-run) | 7 s |
| `lab test --no-build` on the re-run stack | 12 s |
| `lab reset` + `lab up` with `LAB_CATALOG_AUTHZ=allowall` | 97 s to healthy |
| `lab reset` + `install.sh` (back to OpenFGA) | 104 s to healthy |

Base images and the two local images (`v3-bootstrap`, `v3-smoke`) were already cached on the
host. A first install on a machine with nothing cached also pulls Trino, Keycloak,
SeaweedFS, Lakekeeper, OpenFGA, Postgres, Caddy and Playwright images and builds two small
images; that time depends on bandwidth and was not measured here.

## Idempotency

Second `install.sh` run on the running stack:

- `sha256` of `.secrets.env`, `.env`, `state/ca/root.crt` and `state/ca/root.key`, their
  modes (600), and the container IDs of every long-running service: **identical** before and
  after.
- `lab status`: 11 containers, all healthy or exited 0.
- Bootstrap re-run reports `unchanged` at every step (users, Trino group file, bucket,
  warehouse, permissions) and finishes in 0.7 s.
- `lab test`: **PASS (6/6)**.
- After two `lab reset` cycles the CA and secrets were still the same (reset keeps them).

## Smoke test (final run)

```
[PASS] 1.stack_healthy: 11 services healthy or completed
[PASS] 6.no_static_s3_key_in_trino: 0 key settings and no admin key value in 125 lines ...
[PASS] 2.browser_login_trino_ui: final_url https://trino.<domain>:18443/ui/#/dashboard, keycloak_password_prompts 1
[PASS] 3.trino_alice_create_insert_read: current_user alice, inserted 3, rows read back
[PASS] 4.pyiceberg_vended_credentials: STS key (ASIA...), own prefix write allowed, sibling prefix denied (AccessDenied)
[PASS] 5.viewer_write_denied: victor SELECT ok; INSERT -> PERMISSION_DENIED
SMOKE: PASS (6/6)
```

## Memory per container (`docker stats`, idle after smoke)

| Container | In use | Limit | CPUs |
|---|---|---|---|
| trino | 820 MiB | 3 GiB | 2.0 |
| keycloak | 559 MiB | 1.25 GiB | 2.0 |
| postgres | 149 MiB | 512 MiB | 1.0 |
| seaweedfs | 69 MiB | 1 GiB | 2.0 |
| openfga | 40 MiB | 256 MiB | 1.0 |
| lakekeeper | 23 MiB | 512 MiB | 1.0 |
| caddy | 13 MiB | 256 MiB | 1.0 |
| **Long-running total** | **~1.63 GiB** | **6.75 GiB** | |
| One-shots (bootstrap 256 MiB, lakekeeper-migrate 256 MiB, openfga-migrate 128 MiB, trust-init 64 MiB) | exited | 0.69 GiB | |
| **All limits** | | **7.44 GiB** (target ≤ 10 GB) | |

Only `18443` and `18080` are published on the host.

## Decisions and evidence

### OQ-5: Lakekeeper authorization — OpenFGA adopted

The contract's rule (adopt only if bootstrap stays click-free and the smoke test passes) is
met.

- First boot: `permissions: 8 grant(s) written, 5 membership change(s)`; re-runs:
  `permissions: unchanged`. Smoke checks 3 and 4 pass under OpenFGA.
- Model: one Lakekeeper role per Keycloak group. Warehouse grants: `lab-admin` ownership
  (plus project admin); `engineer` modify + create; `analyst` and `viewer` select; Trino's
  service account modify + create.
- `LAKEKEEPER__OPENID_ROLES_CLAIM` cannot replace the membership copy: Lakekeeper 0.13.6's
  OpenFGA authorizer ignores token roles (only Cedar reads them), so bootstrap copies Keycloak
  group membership into Lakekeeper roles. Group changes take effect after bootstrap re-runs
  (`docker compose ... run --rm bootstrap`, or `lab up`).
- OpenFGA stores its data in a separate `openfga` database; about 40 MiB at idle.
- **Fallback verified:** with `LAB_CATALOG_AUTHZ=allowall` in `.env`, `lab reset` + `lab up`
  reached healthy in 97 s, bootstrap logged `authz-backend allow-all (requested allowall)`,
  and the smoke test passed 6/6. The final stack runs OpenFGA again.

### OQ-17: Trino authorization — file-based rules with a Keycloak-generated group file

- Trino uses file-based access control (`config/trino/rules.json`) and the built-in file
  group provider (refresh 15 s).
- Bootstrap writes the group file from Keycloak group members into the `trino-groups`
  volume, atomically and only when it changed.
- Trino 483's `system_information` rules accept only user/role, not group, so that section is
  not used.
- Evidence: smoke check 5 (`victor`, group `viewer`, is denied `INSERT`; `alice`, group
  `lab-admin`, can create and write).

### Identity propagation: Lakekeeper trusts Trino's service identity

A Trino user's identity does **not** reach Lakekeeper with Trino 483.

- Experiment: a temporary catalog with `iceberg.rest-catalog.session=USER`. Keycloak rejected
  the resulting RFC 8693 token exchange (`TOKEN_EXCHANGE_ERROR`, `client_not_found`), and
  Trino failed with `NotAuthorizedException: invalid_client`. Trino's session mode sends a
  subject token it mints itself, not the user's Keycloak token.
- Lakekeeper audit logs show only the `trino` service principal for Trino traffic, and
  alice's own principal for direct PyIceberg access.
- Lakekeeper 0.13's `LAKEKEEPER__TRUSTED_ENGINES` (type trino) covers view run-as-owner
  only, not per-query users.
- **Consequence:** Trino queries are governed by Trino (OQ-17 rules); direct catalog clients
  (PyIceberg, DuckDB, later Spark) are governed per user by Lakekeeper + OpenFGA.

### Other decisions recorded by the workstreams

- No `LAKEKEEPER__BASE_URI`: with it, the catalog config returned the external HTTPS URI and
  Trino's JVM (which does not trust the lab CA) failed with PKIX errors. Lakekeeper builds
  links from `X-Forwarded-*` instead.
- Trino fetches catalog tokens from Keycloak's internal endpoint; `KC_HOSTNAME` keeps the
  issuer at the public HTTPS URL, so Lakekeeper still accepts them.
- SeaweedFS STS role `arn:aws:iam::000000000000:role/LakekeeperVended`, trusted only for
  `arn:aws:iam::000000000000:user/lakekeeper`. A vended (assumed-role) session calling
  AssumeRole gets 403. Filer/volume JWT keys are derived from `SEAWEEDFS_STS_SIGNING_KEY`.
- Test users and the first lab admin are created by bootstrap (not the realm template), so
  seeding follows `LAB_SEED_TEST_USERS`. With it false, bootstrap also disables the `trino`
  client's password grant.
- `.env` is authoritative over the shell; domain and project change only with
  `--reconfigure`; the CA is never regenerated (incomplete or mismatched CA is a hard error).

## Lint and checks

| Check | Result |
|---|---|
| `python3 -m unittest discover -s v3/tests/lint` | 64 tests OK (repair round) |
| `python3 v3/tools/check_versions.py` | OK, now including the `from-digest` rule (repair round) |
| `python3 v3/tools/check_compat.py` | OK (0 errors, 0 warnings) |
| `v3/tools/shellcheck.sh` (v0.11.0, pinned by digest) | 27 files OK |
| `v3/tools/actionlint.sh` (1.7.12, pinned by digest) | OK on both v3 workflows |
| `v3/tools/compose-check.sh` (contract command, `versions.env` only) | OK |
| `v3/tests/installer/run.sh` | shellcheck clean; 157 unit checks pass |

## Known gaps

- **CI e2e on GitHub:** see the lead's note at the end of this file for the first run.
- **Cold-cache install time not measured.** All images were cached on the dev host. The
  15-minute budget should hold on a normal connection, but CI's first run is the evidence.
- **WSL2 with `LAB_HTTPS_PORT=443`** not tested (the repair-round WSL2 run used 18443). Keycloak
  redirect URIs are registered both with and without `:${LAB_HTTPS_PORT}`; whether
  `KC_HOSTNAME` with an explicit `:443` still gives consistent issuers needs that check.
- **Realm import runs only on first start.** Changing `LAB_DOMAIN` or ports later needs
  `lab reset` (redirect URIs are baked into the imported realm).
- **Group changes** reach Trino and Lakekeeper only after bootstrap re-runs; there is no
  `lab` sub-command for that yet.
- **Smoke image transitive pip dependencies are unpinned** (only direct pins come from
  `versions.env`); a generated lock under ADR-012 is a follow-up.
- **Image names differ** between local builds (`lakehouse-lab/v3-<name>:<pin>`) and
  `v3-images.yml` (`ghcr.io/<owner>/lakehouse-<name>`). Align them before compose pulls
  prebuilt images (ADR-012 prebuilt images).
- ~~`up` does not pass `--remove-orphans`~~. **Lead ruling:** added to the contract,
  `install.sh` and `lab up`, consistent with DEC_REMOVE_ORPHANED_CONTAINERS_DURING_UPGRADES
  (it only affects this project). Installer unit tests are still 157/157.
- Under `allowall`, the OpenFGA containers still start (unused); harmless, about 40 MiB.
- **Turning `LAB_SEED_TEST_USERS` off later** disables the password grant but does not remove
  test users that were already seeded. Phase 2 should add removal to bootstrap.
- **Installer minimum Docker/Compose versions** (`LAB_MIN_DOCKER`, `LAB_MIN_COMPOSE`) are
  literals in `installer/checks.sh`. **Lead ruling:** allowed; these are host requirements,
  not pins of shipped software (recorded in ADR-012).
- **The smoke image's `apt-get install libnss3-tools` is unpinned.** It is build-time only
  and the base image is pinned by digest, so this is a reproducibility nit.
