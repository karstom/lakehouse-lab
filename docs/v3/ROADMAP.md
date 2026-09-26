# V3 Roadmap

> Draft · 2026-09-25. Phases are ordered by dependency. Each phase ends with exit criteria
> that CI checks, not a date.

## Branching

- `main` stays V2 (2.1.x) until V3.0 ships. It only gets security and bug fixes, e.g. the
  hardcoded MinIO secret in `data_quality_check.py` and the `$RANDOM` credential generator.
- V3 is built on a `v3` branch. The new layout lives next to V2 files until the cutover,
  then V2 files are removed in one commit.
- **MinIO note for V2 users:** V2 keeps working on the last MinIO image, but it gets no
  security fixes. The V2 README should say this and point to the migration path.

## Phase 0: Spikes (de-risk before building)

> **Status (2026-09-25): complete except the S-5 load test.** Every spike was redeployed from
> scratch and checked by an independent agent. Results: [`spikes/RESULTS.md`](../../spikes/RESULTS.md).
> S-1: partial (Trino has no remote signing, so ADR-006 was amended). S-2, S-3 and S-4: pass.
> S-5: idle use measured; the load test moves into Phase 1.

Each spike is a throwaway compose file plus a written result recorded in OPEN_QUESTIONS.md.

| Spike | Question | Pass criteria |
|---|---|---|
| **S-1** Catalog + storage | Do Lakekeeper + SeaweedFS ≥ 4.40 + Spark 4.1 + Trino work together with remote signing? | Spark writes an Iceberg table; Trino reads, updates and deletes it; no static keys in engine config |
| **S-2** STS for DuckDB | Does SeaweedFS STS issue working credentials for Lakekeeper vending? | DuckDB `ATTACH`es the catalog and reads the S-1 table. Otherwise ADR-006 fallback |
| **S-3** SSO bootstrap | Can a templated realm import configure JupyterHub, Superset, Airflow 3, Trino and Lakekeeper with no clicks? | Fresh `up` → one login works in all five; group changes show up in each |
| **S-4** Workspace image | JupyterLab + code-server + all clients in one image at a reasonable size | Image < 4 GB; Spark, Trino, DuckDB and dbt all connect as the logged-in user |
| **S-5** Resource floor | What does `core` actually need? | Measured RAM/CPU for each profile, written into ARCHITECTURE §8 |

## Phase 1: Foundation

- `versions.env`, image build pipeline (GHCR), version-literal lint, compatibility matrix check
- Caddy + Keycloak + Postgres + SeaweedFS + Lakekeeper + Trino, as the `core` profile
- Realm template and bootstrap job; installer v3 (Docker check, `LAB_DOMAIN`, profile choice)
- CI: start `core`, log in, create and query a table

**Exit:** a fresh install on Linux (and WSL2) reaches a logged-in Trino query in under 15
minutes, and CI shows it green.

> **Status (2026-09-25): built and independently verified.** Installs in about 1m40s on the
> dev host (images cached), about 2 minutes on WSL2, and the smoke test passes 6/6 on both.
> Details: [`v3/PHASE1_RESULTS.md`](../../v3/PHASE1_RESULTS.md). **GitHub `v3-ci` is green:**
> the e2e install and smoke test take 2m25s on a fresh runner. **Exit criteria met.**

## Phase 2: Workspace and engines

- `lakehouse-workspace` image; JupyterHub with OIDC; code-server; per-user volumes
- Spark 4.1 master/workers (`engineer` profile), Spark Connect from workspaces
- dbt starter project; sample datasets loaded as Iceberg tables by the bootstrap job

**Exit:** the smoke lesson (ADR-015) passes in CI for `core` and `engineer`.

> **Status (2026-09-26): built, independently verified, and CI green.** GitHub runs
> `v3-ci`: `core` e2e in 6m10s, `engineer` e2e in 7m42s, on fresh runners. The smoke test
> has 11 checks, including in-workspace Trino, DuckDB and dbt, and Spark as the real user.
> Details: [`v3/PHASE2_RESULTS.md`](../../v3/PHASE2_RESULTS.md).

## Phase 3: Orchestration and BI

- Airflow 3.1 with the Keycloak auth manager; sample DAGs: ingest, `dbt build`, papermill notebook
- Superset 6 with OIDC and a Trino connection; sample dashboard over dbt models
- Lab Console v1: login, service tiles, health
- Optional GitHub login through Keycloak (ADR-016): installer prompt, first-login flow with
  no group, admin approval in the Console, and a CI test against a mock provider

**Exit:** the `full` profile passes a nightly end-to-end run: ingest → dbt → dashboard renders.

## Phase 4: Learning tracks

- **Engineer track:** landing files → Iceberg with Spark → table maintenance (compaction,
  snapshots, time travel) → Airflow pipeline → promote notebook to job
- **Analyst track:** SQL in Superset → JupySQL exploration → dbt model → dashboard
- Each module: notebook/dbt/DAG files, a checkpoint the Console can verify, a reset script

**Exit:** a new user completes module 1 of each track with no out-of-band help (tested
with at least two real beginners).

## Phase 5: AI assist (ADR-014)

- Model gateway; Jupyter AI v3 configured to use it; Claude Code available in workspaces
- dbt-mcp and a Trino MCP server wired in with the user's token; `lab-context` MCP server
- Tutor-mode prompts attached to track modules; admin switches to turn it on or off

**Exit:** in a workspace, asking "which tables feed the orders dashboard and when did they
last load?" gets a correct answer that uses only data the user is allowed to see.

## Phase 6: Migration and release

- V2 → V3 migration tool ([MIGRATION.md](MIGRATION.md)); nightly migration test
- Docs rewrite; V2 docs archived under `docs/v2/`
- Release V3.0; V2 enters security-fix-only for 6 months

## Deferred (post-3.0)

Kubernetes/Helm, multi-node Spark across hosts, Superset AI features, streaming
(Flink/Kafka) track, Polaris as an alternative catalog profile.
