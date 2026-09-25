# Phase 0 Results: Checkpoint A

> 2026-09-25 · Ran on $LAB_SERVER as isolated `v3-s*` compose projects. Each spike was
> built by one agent, then **redeployed from scratch (`down -v` → up → `test.sh`) and
> audited by a separate verifier agent**; any failure got one repair round. Details are in
> each spike's `RESULTS.md`.

| Spike | Result | One-line finding |
|---|---|---|
| **S-1** Catalog + storage | ⚠️ **Partial** (reproduced) | Lakekeeper + SeaweedFS 4.47 + Spark 4.1.3 + Trino 483 work together, including cross-engine UPDATE/DELETE. **Trino 483 has no remote signing**, so it uses vended STS credentials limited to one table |
| **S-2** DuckDB via STS | ✅ **Pass** | DuckDB 1.5.5 reads **and writes** Iceberg with credentials Lakekeeper vends (limited to one table, ≤1 h). No fallback needed |
| **S-3** SSO bootstrap | ✅ **Pass** | From `down -v` to five apps behind one Keycloak login in ~2 min, zero clicks. Group → role mapping and group changes work in Superset and Airflow |
| **S-4** Workspace image | ✅ **Pass** (policy ruling below) | 2.11 GB image with JupyterLab, code-server, Spark Connect, DuckDB (extensions work offline), dbt, and jupyter-ai. No network needed at start |
| **S-5** Resource floor | ⏳ **Idle measured** | Idle use: S-1 1.3 GB, S-2 0.2 GB, S-3 2.4 GB, S-4 0.9 GB. Load test moved to Phase 1 |

## What changed in the design

1. **ADR-006 amended.** Spark and PyIceberg use remote signing; Trino and DuckDB use vended
   STS credentials limited to one table. SeaweedFS STS is required in every profile.
   Evidence:
   - Jar scan of Trino 483; upstream trinodb/trino#21189 is still open.
   - SeaweedFS enforced Lakekeeper's per-table session policy: the credentials' own table
     returned 200; a sibling table, paths outside the warehouse, and bucket listing all
     returned 403.
2. **ADR-012 ruling: generated lockfiles are allowed.** The S-4 verifier failed the image
   under a strict reading of "no version literals outside `versions.env`", because of a
   generated 226-line pip constraints lock. **I'm ruling the lock allowed**:
   - It is generated from `versions.env`, marked `GENERATED`, and never hand-edited.
   - CI regenerates it and fails if it differs from the committed copy.
   - Base images are also pinned by digest.

   This is recorded in ADR-012.
3. **OQ-1, OQ-2, OQ-3 resolved.**
   - OQ-1: STS works.
   - OQ-2: Spark Connect by default, classic driver opt-in.
   - OQ-3: HTTP only on `*.localhost`. Remote installs import the Caddy root CA once, or
     use real ACME.
4. **New questions OQ-13 … OQ-17:** STS credential refresh, credentials cached after a
   grant is revoked, Spark Connect identity, the Airflow UMA bootstrap, and the Trino group
   provider.
5. **Pins to promote into `versions.env`:**
   - Airflow Keycloak provider 0.10.0
   - OAuthenticator 17.4.0
   - authlib 1.8.0
   - psycopg2-binary 2.9.9
   - JupySQL 0.11.1
   - jupyterlab-git 0.54.1
   - Python 3.12.14-slim-bookworm (+ digest)
   - Playwright 1.63.0

## Things that went better than planned

- **SeaweedFS STS is solid on 4.47.** The "incomplete STS" reports don't apply at this version.
- **Spark needs no `hadoop-aws` or AWS SDK JARs** with the Iceberg AWS bundle. That removes
  two of V2's five version sites.
- **The SSO test is fast** (~3 min with builds) with headless Chromium, so it works as
  ADR-015's CI test.

## Gotchas for Phase 1 and lesson content

- **Never use Spark `DROP TABLE … PURGE`** against Lakekeeper with remote signing; use a
  plain `DROP`.
- **Airflow 3's Keycloak auth manager maps roles through Keycloak Authorization Services
  (UMA),** not token claims. Viewers can still see admin menus, read-only.
- **Superset 6.1's lean image** needs authlib and psycopg2 built in, and runs Python 3.10
  in `/app/.venv`.
- **JupyterHub's OAuthenticator ignores `SSL_CERT_FILE`** (it uses pycurl). The CA must be
  passed through `http_request_kwargs`.
- **Caddy's internal CA must survive reinstalls.** Otherwise every browser has to re-trust it.
- **jupyter-ai 3.2 has no assistant that works out of the box.** Its agent personas need
  their CLIs; Phase 5 decides which to use.
- **Lakekeeper caches STS credentials,** so a revoked grant can keep working for up to 1 hour.

## Stacks left running on the server (for review)

`v3-s1`, `v3-s2`, `v3-s3` (SSO, browsable after importing
`s3-sso-bootstrap/out/caddy-root.crt`: `https://superset.<lab-ip>.sslip.io:18443`),
`v3-s4`. Together they use ~5 GB. Tear down with `docker compose -p v3-sN … down -v`;
each spike's RESULTS.md has the exact command.
