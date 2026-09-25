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

**Rejected:**
- **Path prefixes:** sub-path bugs and fiddly OIDC.
- **Traefik:** capable, but Caddy's automatic TLS and forward-auth are simpler for a lab.

**Retires:** `REG_HOST_IP_DETECTION`.

---

## ADR-006: Storage access is given out by the catalog
**Status:** Pending spike S-2

**Decision:** Engines never hold static S3 keys. Lakekeeper authorizes each table access
and either **remote-signs** requests (the default for Spark and Trino; plain SigV4, works on
any S3 store) or gives out **short-lived STS credentials** (required for DuckDB, whose
Iceberg extension doesn't support remote signing yet).

**Why:** This removes storage credentials from notebooks, DAGs, tests and messages entirely,
which is the root cause behind 16 V2 fix commits.

**Spike S-2:** verify that SeaweedFS STS works with Lakekeeper-issued credentials.
- If it works, STS vending is enabled for DuckDB.
- If not, DuckDB in V3.0 reads through Trino (`duckdb` + `trino` attach) or uses a read-only
  scoped key, documented as a known limitation.

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
