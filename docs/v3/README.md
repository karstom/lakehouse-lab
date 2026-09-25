# Lakehouse Lab V3 — Design

> **Status:** Draft for review · **Date:** 2026-09-25 · **Supersedes:** V2.1.1 architecture
>
> V2 stays a maintained release while V3 is built. Nothing in this directory describes
> behavior that exists today; it describes what V3 will build.

## Why V3

V2 works: it has been used to analyze multi-TB datasets. But three things have changed:

1. **Parts of the stack are end-of-life or a major version behind.** MinIO Community Edition
   stopped being maintained in February 2026 and was locked in April 2026, so it gets no more
   security fixes. Spark (3.5 → 4.x), Airflow (2.10 → 3.x) and Superset (`:latest` → 6.x) all
   have breaking major releases. Doing these migrations together is cheaper than one at a time.
2. **Most V2 bugs came from architecture, not tools.** The project's memory graph (`core/`)
   groups ~130 fix commits into 10 root causes. Most trace back to three patterns:
   runtime `pip install` in containers, bash embedded in compose YAML, and credentials,
   versions and volume names defined in several places. A redesign can remove these as a
   class; upgrading versions alone can't.
3. **There is no unified experience.** V2 is a set of good tools with separate logins, separate
   URLs and no shared view of the data. Beginners have to put the platform together in their
   heads before they can learn anything on it.

## Goal

A **lab-quality** lakehouse that teaches people to work as a lakehouse **data engineer** or
**data analyst**, and is also good enough for real multi-TB analysis on one server.

It is not a Databricks clone. V3 does not build its own SQL editor, notebook or catalog UI. It
connects mature open-source tools through **one login, one catalog, one workspace and one
set of learning tracks**.

## Personas and where they work

| Persona | Primary home | Also uses |
|---|---|---|
| **Data analyst** | Superset (SQL Lab + dashboards) on Trino | JupyterLab with SQL cells, dbt models |
| **Analytics engineer** | Workspace: dbt project in code-server/JupyterLab | Superset, Airflow |
| **Data engineer** | Workspace: notebooks to explore, code in git for production | Airflow, Spark UI, catalog UI |
| **Lab admin / instructor** | Lab Console + Keycloak admin | Everything |

The per-user workspace (JupyterHub) is the center for engineers. It is **not** the whole
product: analysts mostly work in SQL and BI, and production engineering code is files in
git, not notebooks. See [ADR-007](DECISIONS.md#adr-007-per-user-workspace-jupyterlab--code-server-via-jupyterhub).

## Design principles

1. **One source of truth for everything.** Versions in one file, identities in Keycloak,
   table metadata in the catalog, storage access vended by the catalog. No mirrored copies.
   (Retires V2 regressions: credentials, Iceberg JARs, volume names.)
2. **Pre-built, pinned images.** No package installs when a container starts. No `:latest`.
3. **No logic in YAML.** Compose files declare services; behavior lives in scripts and images
   that can be linted and tested.
4. **Integrate, don't build.** Use a tool's native feature before writing glue. V2's custom
   auth service and in-stack MCP server were both removed as unstable; V3 composes existing
   components and keeps its own code thin.
5. **Beginner path first, expert path open.** Sensible defaults and guided tracks, with
   nothing hidden that a practitioner needs to reach.
6. **Tested the way users run it.** CI starts the core profile and runs a smoke lesson end
   to end.

## Documents

| Doc | Contents |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Components, networking, identity and data-access flows, AI assist layer, profiles |
| [DECISIONS.md](DECISIONS.md) | Architecture decision records (ADR-001 … ADR-016) |
| [ROADMAP.md](ROADMAP.md) | Phases, exit criteria, and validation spikes |
| [MIGRATION.md](MIGRATION.md) | V2 → V3 upgrade path for existing installs and data |
| [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) | Unresolved questions and who or what resolves them |
