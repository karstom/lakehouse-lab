# V3 Architecture Decision Records

> Status legend: **Accepted** (agreed in design review 2026-09-25) · **Proposed** (direction
> agreed, details open) · **Pending spike** (accepted, subject to a validation spike in
> [ROADMAP.md](ROADMAP.md)).
>
> Each record states the decision, why, what was rejected, and which V2 regression it retires
> (IDs from the memory graph in `core/regressions.md`).

---

## ADR-001: SeaweedFS replaces MinIO for object storage
**Status:** Accepted

**Decision:** Use SeaweedFS (Apache 2.0) as the S3-compatible store. Pin **≥ 4.40**. Every
other component talks to "an S3 endpoint", so the store can be swapped later.

**Why:** MinIO Community Edition was marked unmaintained in February 2026 and locked in
April 2026, so it gets no security fixes. SeaweedFS is actively released (36 releases in 2026)
and stable, has an S3 API with IAM/STS, and has been tested as a Lakekeeper backend.

**Rejected:**
- **RustFS:** promising, but still 1.0 release candidates only.
- **Garage:** AGPL, and a smaller S3 feature set.
- **Ceph RGW:** too heavy for a lab.

**Notes:** SeaweedFS ≤ 4.39 has an OIDC trust-policy bypass (CVE-2026-77298), and some 4.1x
releases had IAM regressions. Hence the version floor, and an S3 conformance smoke test in CI.

---

## ADR-002: Lakekeeper as the Iceberg REST catalog
**Status:** Accepted

**Decision:** All tables are Apache Iceberg tables registered in Lakekeeper. Lakekeeper is
also the authorization point for table access and gives out storage access (ADR-006).

**Why:** A shared catalog is what makes separate engines feel like one platform: a table
created in Spark appears right away in Trino, DuckDB and Superset. Lakekeeper is a single
Rust binary with a small footprint, native OIDC, and support for both remote signing and
vended credentials on S3-compatible storage. Its latest release (0.12, April 2026)
focuses on authorization.

**Phase 1 result:**
- **Authorization uses OpenFGA (OQ-5).** One Lakekeeper role per Keycloak group, written by
  the bootstrap job. `LAB_CATALOG_AUTHZ=allowall` is a verified fallback.
- **A Trino user's identity does not reach Lakekeeper in Trino 483.** Lakekeeper
  authorizes Trino's service identity, and per-user rules for SQL users are enforced in
  Trino (file-based rules plus a group file generated from Keycloak, OQ-17).
- **Lakekeeper's per-user rules apply** to clients that call the catalog directly: PyIceberg,
  DuckDB and Spark.

**Rejected:**
- **Apache Polaris:** the ASF reference implementation and has more resume value, but it
  is JVM-based and heavier. It stays a documented alternative, since engines only depend
  on the Iceberg REST spec.
- **Nessie, Hive Metastore:** not REST-first, weaker authorization story.
- **No catalog (V2):** path-based tables and no shared view.

**Retires:** part of `REG_ICEBERG_JAR_VERSIONS` (Iceberg is no longer an overlay).

---

## ADR-003: Engines: Spark 4.1, Trino, DuckDB
**Status:** Accepted

**Decision:**
- **Spark 4.1** for batch/ETL and large jobs, with `iceberg-spark-runtime-4.1_2.13` from
  Iceberg 1.11.
- **Trino** as the interactive SQL engine, i.e. the "SQL warehouse" for analysts, Superset
  and dbt.
- **DuckDB** for single-node work inside workspaces.

**Why:**
- Spark 4.1 is the newest version with an Iceberg runtime. Spark 4.2 (July 2026) has no
  Iceberg runtime yet, so we move to it once one ships.
- Trino fills the gap V2 had: fast shared SQL over the catalog for BI and analysts,
  without going through Spark.
- DuckDB covers laptop-scale work and teaching.

**Spike S-1 result:** Spark 4.1.3 with the `iceberg-spark-runtime-4.1_2.13:1.11.0` and
`iceberg-aws-bundle:1.11.0` JARs built into its image works. It needs no `hadoop-aws` or AWS
SDK JARs, which removes two of V2's five version sites. Trino 483 reads, UPDATEs and DELETEs
the same tables, and each engine sees the other's snapshots.

**Lesson content must not use Spark `DROP TABLE … PURGE`** against Lakekeeper: Spark deletes
the files itself after the catalog drop, and the signer rejects those requests. Use a plain
`DROP` and let Lakekeeper clean up.

**Rejected:**
- Staying on Spark 3.5, which is on its way to end of life.
- Dremio, which has an open-core licensing split.
- Spark Thrift server as the SQL endpoint, which is weaker for BI concurrency.

---

## ADR-004: Keycloak for single sign-on
**Status:** Accepted

**Decision:** Keycloak is the only identity store. Every service logs in through OIDC, using
the service's native integration where one exists, or Caddy forward-auth where it doesn't.
Groups: `lab-admin`, `engineer`, `analyst`, `viewer`. The installer imports a templated
realm and creates the first admin without any manual clicking.

**Why:** Every V3 service except Spark UI and the storage console supports OIDC natively,
including an official Keycloak auth manager for Airflow 3. Keycloak also has the most
integration recipes, and it's a skill employers ask for. V2's SSO attempt failed because it was a
**custom auth service**. V3 writes no authentication code.

**Rejected:**
- **Authentik:** friendlier UI, but fewer data-tool recipes.
- **Zitadel:** lightest, but the fewest examples.
- **Per-service logins (V2):** no unified experience, and credentials sprawl.

**Retires:** `REG_CREDENTIAL_PROPAGATION` (together with ADR-006); replaces the
per-service user writes in `provision-user.sh`.

**Risk:** first-run bootstrap is where fragility would come back. It gets its own CI test
(ADR-015).

**Spike S-3 result (passed, verified from a clean start):**
- One templated realm (`start --import-realm` with `${ENV}` placeholders) goes from
  `down -v` to five working apps in about 2 minutes, with zero clicks.
- One login reaches JupyterHub, Superset, Airflow, Trino and Lakekeeper.
- Admin and viewer users get different roles in Superset and Airflow, and moving a user
  between groups takes effect at their next login.

What Phase 1 needs to know:
- **Airflow 3's Keycloak auth manager gets roles from Keycloak Authorization Services**
  (UMA permissions), not from token claims. That setup is one scripted bootstrap step, or it
  can be exported into the realm template.
- **Trino 483 removed `oauth2.groups-field`,** so group-based access rules need a Trino
  group provider.
- **Replace the spike's wildcard redirect URIs** with exact callback paths.

---

## ADR-005: Subdomain routing through Caddy
**Status:** Accepted

**Decision:** Each service has its own subdomain under `LAB_DOMAIN` (default
`lab.localhost`; remote servers use `<ip>.sslip.io` or real wildcard DNS). Caddy handles TLS
and routing.

**Why:** OIDC redirect URIs and cookies are simplest per host, and several tools (Superset
especially) behave badly under a URL sub-path. `*.localhost` resolves in browsers with no
setup. The installer works out the host once and writes `LAB_DOMAIN`, which retires V2's four
copies of IP detection.

**Spike S-3 results:**
- **The pattern works.** Caddy carries every public hostname as a Docker network alias, so
  the OIDC issuer URL is the same inside containers and in the browser, with no hairpin NAT.
- **Proxy settings each service needs:**
  - Superset: `ENABLE_PROXY_FIX`
  - Airflow: `--proxy-headers` + `[api] base_url`
  - Trino: `http-server.process-forwarded`
  - Keycloak: `KC_PROXY_HEADERS=xforwarded`
  - Lakekeeper: `BASE_URI`
- **Plain HTTP on `sslip.io` is not viable** (OQ-3). The page isn't a secure context, so
  browser PKCE breaks, Secure cookies break and the Trino UI disables itself. HTTP only works
  on `*.localhost`.
- **Remote installs therefore need the Caddy root CA trusted, or a real domain with ACME.**
  The root CA must be generated once by the installer and kept outside any volume that
  upgrades or `down -v` can wipe.

**Rejected:**
- **Path prefixes:** sub-path bugs and fiddly OIDC.
- **Traefik:** capable, but Caddy's automatic TLS and forward-auth are simpler for a lab.

**Retires:** `REG_HOST_IP_DETECTION`.

---

## ADR-006: Storage access is given out by the catalog
**Status:** Accepted (amended after spikes S-1/S-2, 2026-09-25)

**Decision:** Engines never hold static S3 keys. Lakekeeper authorizes each table access and
gives storage access in one of two ways:
- **Remote signing:** Spark and PyIceberg.
- **Vended STS credentials:** Trino and DuckDB. These are limited to one table and last at
  most 1 hour.

**SeaweedFS STS is therefore required in every profile.** That means an `-s3.iam.config`
file with a signing key, a vending role and a policy. The trust policy is narrowed to
Lakekeeper's identity.

**Why:** This removes storage credentials from notebooks, DAGs, tests and messages entirely,
which is the root cause behind 16 V2 fix commits.

**Spike evidence:**
- **Trino 483 has no remote signing.** Its Iceberg REST client only asks for vended
  credentials (confirmed by a jar scan; upstream trinodb/trino#21189 is open), which is why
  the original "remote signing for Trino" plan was dropped.
- **SeaweedFS 4.47 enforces Lakekeeper's per-table session policy.** Vended credentials
  could read and write their own table's prefix; the sibling table, paths outside the
  warehouse, and bucket listing were all denied.
- **DuckDB 1.5.5 works with vended credentials,** for both reads and INSERTs. The planned
  fallbacks (going through Trino, or a scoped static key) are not needed.

**Follow-ups (Phase 1):**
- Test credential refresh after the 1-hour expiry.
- Test read-only vending once authorization is on (OQ-5).
- Lakekeeper caches STS credentials, so a revoked grant can keep working until the cached
  credentials expire (OQ-14).
- Revisit remote signing for Trino when upstream ships it.

---

## ADR-007: Per-user workspace: JupyterLab + code-server via JupyterHub
**Status:** Accepted

**Decision:** JupyterHub (always, including single-user installs) spawns one workspace
container per user from a pre-built `lakehouse-workspace` image. It contains:
- JupyterLab with SQL cells (JupySQL), git and terminal
- VS Code in the browser (code-server via `jupyter-server-proxy`)
- Spark, Trino, DuckDB, PyIceberg and dbt clients pre-wired to the catalog

**Why:** Analysts mostly work in SQL and BI, and engineers explore in notebooks but ship
code in git. A notebooks-only lab would teach a Databricks-shop habit. One workspace that
does both covers the engineering personas without building a custom IDE.

**Spike S-4 result:** the image works and is **2.11 GB**, well under the 4 GB budget. Every
pinned client imports correctly, code-server runs through `jupyter-server-proxy`, and DuckDB
extensions are built into the image and load offline. The container needs no network at
start.

**Spark: Spark Connect by default (OQ-2).** The workspace carries a ~2 MB client and no JVM,
and each session is isolated. A "classic driver" image variant is opt-in for Spark UI and
RDD lessons, at about +722 MB and ~466 MB of JVM memory per user.

**Rules the spike surfaced:**
- Per-home wiring goes in the image ENTRYPOINT, not CMD, so the spawner's command overrides
  still work.
- dbt telemetry is turned off in the image.

**Rejected:**
- **JupyterLab only:** unrealistic for pipeline-as-code work.
- **Separate code-server service:** more services, and per-user isolation is harder.
- **Keeping separate `jupyter` and `jupyterhub` modes (V2):** two code paths that drifted apart.

---

## ADR-008: dbt is part of the core stack
**Status:** Accepted

**Decision:** Every workspace has dbt-core + dbt-trino installed, and each user gets a starter
dbt project over the sample data. Airflow ships a DAG that runs `dbt build`.

**Why:** dbt is the transformation layer between raw Iceberg tables and dashboards, and it's
the daily tool of analytics engineers. It also gives analysts a way into engineering.

---

## ADR-009: Airflow 3.1+ and Superset 6.x
**Status:** Accepted

**Decision:** Airflow ≥ 3.1 with the Keycloak auth manager; DAGs support papermill so a
notebook can be scheduled as a job. Superset 6.x, pinned, built into a custom image with
the Trino driver and OIDC configuration included.

**Why:** Airflow 2 is behind. Airflow 3 changes the auth model and APIs, so it's best adopted
in a major release. Scheduling notebooks with papermill teaches "prototype in a notebook →
schedule it → rewrite as a proper job". Pinning Superset retires `REG_SUPERSET_SETUP`.

---

## ADR-010: Lab Console is a thin static home page
**Status:** Accepted

**Decision:** The Console is a static site served by Caddy: OIDC login, tiles for the services
the user's groups can reach, a service health view, and the learning tracks. It has no SQL
editor, notebook or catalog UI of its own.

**Why:** V3 is not rebuilding Databricks. JupyterLab, Superset and Lakekeeper's UI already
cover those jobs. The Console's job is to be the obvious starting point for a beginner.

**Rejected:** a custom web app with an embedded editor and catalog browser. Too much to
build and maintain for the value it adds.

---

## ADR-011: Optional add-on modules
**Status:** Accepted

**Decision:** Vizro, LanceDB, Portainer, Spark History Server and local LLM hosting are
opt-in modules (compose profiles). They are not part of core.

**Why:** A smaller core is easier to start, learn and test.

---

## ADR-012: One version file, pre-built pinned images
**Status:** Accepted

**Decision:**
- `versions.env` is the only place a version is written. CI fails on version literals
  anywhere else, and checks the Spark ↔ Iceberg ↔ Scala ↔ PySpark matrix.
- Custom images are built in CI and published to GHCR.
- No `pip install` or `apt-get` when a container starts, and no `:latest`.
- No logic in compose `command:` blocks beyond calling an entrypoint script.

**Amendments from spike S-4 (Accepted):**
- **Generated lockfiles are exempt from the version-literal rule.** The pip constraints
  lock for the ~226 transitive dependencies is generated from `versions.env` by
  `build.sh --relock`, starts with a `# GENERATED … do not edit` header, and is never
  hand-edited. CI regenerates it whenever `versions.env` changes and fails if the committed
  copy differs, so it stays derived rather than becoming a second source.
- **Base images are pinned by tag and digest** (`*_IMAGE_TAG` + `*_IMAGE_DIGEST`), including
  the Dockerfile syntax frontend.
- **Host requirement thresholds are exempt** (Phase 1 ruling): the installer's minimum
  Docker/Compose versions (`LAB_MIN_DOCKER`, `LAB_MIN_COMPOSE` in `installer/checks.sh`)
  describe the host, not software we ship.
- **Pins that spikes needed get promoted into `versions.env`:** OAuthenticator, the Airflow
  Keycloak provider, authlib, psycopg2, JupySQL, jupyterlab-git, the Python base image, and
  Playwright (for tests).

**Why:** This removes the three root causes behind most V2 fixes: runtime installs
(`REG_JUPYTER_PYSPARK_VERSIONS`, `REG_SUPERSET_SETUP`, `REG_INIT_CONTAINER_BOOTSTRAP`),
logic in YAML (`REG_COMPOSE_INLINE_SHELL`), and versions defined in several places
(`REG_ICEBERG_JAR_VERSIONS`).

---

## ADR-013: Docker Compose remains the runtime
**Status:** Proposed

**Decision:** V3 targets a single host with Docker Compose and profiles. Kubernetes/Helm is
out of scope for V3.0.

**Why:** The audience is learners and single-server analysis. Compose keeps the install
to one command. The design (OIDC, REST catalog, S3) moves to Kubernetes later without
changes. See OQ-6.

---

## ADR-014: Context-aware AI assist through MCP and a model gateway
**Status:** Proposed

**Decision:**
- **Context through MCP servers,** independent of the assistant. Use existing servers
  first (official dbt-mcp; evaluate a Trino MCP server), plus a thin `lab-context` server
  for the catalog, Airflow run status and the current lesson.
- **Surfaces:** Jupyter AI v3 in JupyterLab (agents over ACP, approval before writes), and
  Claude Code in the workspace terminal and code-server.
- **The assistant acts as the user:** MCP servers forward the user's Keycloak token.
  Read-only by default, with query limits.
- **A model gateway** holds provider keys and per-user budgets, and can route to local
  models for private data.
- **Tutor mode** inside learning tracks: explain and hint, don't hand over solutions.

**Why:** AI help is only useful if it knows the lab: tables, lineage, pipeline state, and
what the learner is working on. Putting that context in MCP makes it portable across
assistants. Acting as the user makes it safe on shared or private data.

**Rejected:** V2's approach of a custom in-stack MCP API, which was removed as incomplete.
V3 writes only thin glue.

**Open:** OQ-7 (gateway choice), OQ-8 (default providers and data policy).

**Spike S-4 note:** jupyter-ai 3.2 installs cleanly, but no assistant persona works out of
the box: each of its 8 ACP agent personas needs its agent's CLI installed, and there is no
default chat model. Phase 5 must choose between the built-in `jupyternaut` extra (it uses
LiteLLM, which fits the gateway plan) and building an ACP agent CLI into the image, or both.
jupyter-ai also starts its own MCP server, which the `lab-context` design should reuse.

---

## ADR-015: CI starts the core profile and runs a smoke lesson
**Status:** Accepted

**Decision:** On every PR, CI brings up the `core` profile from the published images and
runs a smoke lesson end to end:
1. Log in through Keycloak
2. Create an Iceberg table in Spark (or Trino, for the core profile)
3. Query it from Trino and DuckDB
4. Run `dbt build`

A nightly job does the same for `full` and for a V2 → V3 migration.

**Why:** V2 replaced its startup test with config validation, so startup, init and upgrade
regressions only reached users (`WATCH_CI_WORKFLOWS`). Pre-built images keep the V3 test fast.

---

## ADR-016: External identity providers through Keycloak (GitHub first)
**Status:** Proposed (Phase 3)

**Decision:** Keycloak can optionally hand logins to an external identity provider. **GitHub
is the provider used to prove the concept.** The applications are unchanged: they only talk
to Keycloak.
- **Off by default.** The installer asks for a GitHub OAuth App client ID and secret and
  renders the provider into the realm template. The app's callback URL is
  `https://auth.<LAB_DOMAIN>/realms/lakehouse/broker/github/endpoint`.
- **Signing in does not grant access.** A first GitHub login creates a Keycloak user with
  **no group**, so it can reach nothing until an admin adds it to a group. Alternatively,
  the admin pre-creates users, and GitHub logins only link to those existing accounts.
- **No automatic linking by email.** A GitHub login is linked to an existing local account
  only after the user proves they own that account (Keycloak's "link with existing account"
  flow, which asks for the local password). Otherwise a GitHub account showing someone
  else's email could take over their account.
- **Local accounts always remain,** including a local admin, so a GitHub outage or no
  network never locks anyone out.

**Why:** Classrooms and teams shouldn't manage another set of passwords, and learners
already have GitHub accounts. Because every app goes through Keycloak (ADR-004), this is
configuration, not code. GitHub proves the concept with the least setup: an OAuth App takes
minutes to register, and since the callback is a browser redirect, it should work with
`sslip.io` and `localhost` addresses. Google and Microsoft check return URLs more strictly
and in practice need a real domain.

**Rejected / deferred:**
- **Google, Microsoft Entra and generic OIDC/SAML:** same mechanism, deferred until GitHub
  is proven.
- **Giving new external users a default group like `viewer`:** convenient, but it grants
  access to anyone with an account at the provider. It is only acceptable together with a
  membership restriction (OQ-18).

**Testing:** CI can't use real GitHub. It runs a second Keycloak realm acting as the
external provider, to test the brokering, first-login and no-group behavior. The real GitHub
login is a manual release check.

**Open:** OQ-18.

---

## ADR-017: Long-running Spark work: Airflow batch jobs now, session token renewal later
**Status:** Accepted (owner decision, 2026-09-26; option "c")

**Context:** An interactive Spark Connect session carries the user's token as its catalog
token (OQ-15). That token can't be refreshed inside a running session, so one Spark job
from a workspace can't outlive it (30 to 60 minutes). That is fine for lessons and
interactive analysis, but not for multi-TB batch work.

**Decision:**
- **Now (Phase 3):** long-running Spark work runs as **Airflow batch jobs** submitted to the
  cluster under a **service identity**: a Keycloak client-credentials account whose catalog
  token the Iceberg client renews itself.
  - Only `engineer` and `lab-admin` can trigger or edit these DAGs, enforced by Airflow's
    Keycloak authorization.
  - Lakekeeper sees the service identity, and Airflow's run log records which person
    triggered it.
  - The job must survive well past a token lifetime; this is tested with a deliberately
    short token lifetime.
- **Later (follow-up, not scheduled):** token renewal for interactive Spark Connect
  sessions, so workspace jobs can run longer too. Keycloak rejects the token exchange that
  Iceberg's own refresh uses today; the options are enabling token exchange for the
  `jupyterhub` client or a Spark-side refresh hook.

**Why:** It reuses Phase 3's Airflow, matches how production teams separate interactive
exploration from scheduled batch jobs (a lesson in itself), and doesn't block on the harder
renewal work.
