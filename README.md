# Lakehouse Lab

[![v3-ci](https://github.com/karstom/lakehouse-lab/actions/workflows/v3-ci.yml/badge.svg)](https://github.com/karstom/lakehouse-lab/actions/workflows/v3-ci.yml)
[![GitHub release](https://img.shields.io/github/v/release/karstom/lakehouse-lab?include_prereleases)](https://github.com/karstom/lakehouse-lab/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**A complete open-source lakehouse on one machine, with one login, for learning to work as a
data engineer or data analyst.**

> **Status: V3 beta (`v3.0.0-beta.1`).** V3 is a new stack, not an upgrade of V2. It is
> tested end to end in CI on every change, but it is new: expect rough edges, and please
> [report them](#reporting-problems). Known gaps are listed in the
> [release notes](v3/RELEASE_NOTES_v3.0.0-beta.1.md). Coming from V2? See
> [below](#coming-from-v2).

## What it is, and who it's for

Lakehouse Lab connects mature open-source tools into one working lakehouse: an Iceberg
catalog, object storage, SQL and Spark engines, notebooks, dbt, Airflow and Superset. You
sign in once, and every tool knows who you are and what you may see.

- **Learners** get two guided tracks (data engineer, data analyst) with a checkpoint at the
  end of every module, on a real platform rather than a toy.
- **Instructors and lab admins** run one lab for a class or team: add people to a group in
  Keycloak and they get the right access everywhere.
- **Practitioners** get a reproducible single-server lakehouse for real analysis, with the
  engines and formats used in production.

The "why" behind the design is in [docs/README.md](docs/README.md).

## Quick start

**You need:** Linux or Windows with WSL2, Docker 24+ with Compose 2.20+, git, and at least
8 GB of RAM for Docker (16 GB recommended; see [profiles](#profiles-and-memory)).

```bash
git clone https://github.com/karstom/lakehouse-lab.git
cd lakehouse-lab
v3/install.sh
```

Or as one line (the same thing: it clones into `./lakehouse-lab`, shows what it will do,
then runs `v3/install.sh`):

```bash
curl -fsSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
```

The installer:

1. checks Docker, memory, disk and ports;
2. asks for the lab's **domain** once: `lab.localhost` for this machine only (the default),
   `sslip` for other machines on your LAN (`<your-ip>.sslip.io`, no DNS setup), or your own
   domain;
3. writes `v3/.env` (settings) and `v3/.secrets.env` (generated passwords and keys, mode 600),
   and creates the lab's own certificate authority in `v3/state/ca/`;
4. starts the lab and prints the URLs and the first admin's login.

Then **trust the lab CA** in your browser once (`v3/lab ca` prints how; on WSL2, trust it in
Windows) and open `https://console.<your domain>/`.

Re-running `v3/install.sh` is safe: it keeps your settings, secrets and CA, and upgrades the
running lab in place. Day to day, use the `v3/lab` CLI:

```bash
v3/lab status      # health of every service
v3/lab urls        # where everything is
v3/lab down        # stop (data is kept);  v3/lab up  to start again
v3/lab logs trino  # a service's logs
v3/lab test        # the end-to-end smoke test
```

## Profiles and memory

Pick one with `v3/install.sh --profile NAME` (you can change it later the same way; data is
kept).

| Profile | Adds | Machine |
|---|---|---|
| `core` (default) | Keycloak login, SeaweedFS storage, Lakekeeper catalog, Trino, per-user JupyterLab + code-server workspaces with DuckDB and dbt, Lab Console | 8 GB minimum, 16 GB recommended; about 2 GiB in use at idle |
| `engineer` | Spark 4 (Spark Connect from notebooks), Airflow 3 | 16 GB; about 5 GiB in use at idle |
| `full` | Superset 6 dashboards, AI assist gateway | 16 GB minimum, 24 GB recommended; about 6 GiB in use at idle |

Memory limits are per-service ceilings; real use is much lower than their sum. The measured
numbers are in the `v3/PHASE*_RESULTS.md` files.

## Services and URLs

Every service is a subdomain of your lab domain behind one HTTPS port (443 by default,
`--https-port` to change it). `v3/lab urls` prints the exact addresses.

| URL | What | Profile |
|---|---|---|
| `https://console.<domain>/` | Lab Console: your tiles and service health | all |
| `https://auth.<domain>/` | Keycloak: sign-in, users and groups (admin console at `/admin/`) | all |
| `https://jupyter.<domain>/` | Your workspace: JupyterLab and code-server, with the learning tracks | all |
| `https://trino.<domain>/` | Trino (SQL engine) web UI | all |
| `https://catalog.<domain>/` | Lakekeeper (Iceberg catalog) UI | all |
| `https://airflow.<domain>/` | Airflow | `engineer`, `full` |
| `https://spark.<domain>/` | Spark UI | `engineer`, `full` |
| `https://superset.<domain>/` | Superset: SQL Lab and dashboards | `full` |

**Users and access** are managed in Keycloak: add a user, then add them to one group:
`lab-admin`, `engineer`, `analyst` or `viewer`. Access follows within about 30 seconds
everywhere (`v3/lab sync` applies it at once). "Sign in with GitHub" is optional
(`v3/install.sh --github-client-id … --github-client-secret …`); a new GitHub user gets no
access until an admin adds them to a group.

## AI assist

Profile `full` includes an AI assistant in JupyterLab that can look up tables, lineage and
dashboards **as the signed-in user** (read-only, only what that user may see). The policy:

- **Hosted models are off by default.** An admin turns one on explicitly, with its key:
  `v3/lab ai enable-hosted --provider anthropic|openai --key-file FILE`. Lab data is then
  sent to that provider.
- **Local models** work through any OpenAI-compatible server (llama.cpp `llama-server`,
  Ollama, vLLM): `v3/lab ai set-local http://<host>:<port>/v1`. The installer asks on `full`.
- **Quiet hours** keep the lab off a local model server at set times, e.g. overnight:
  `v3/lab ai quiet-hours 22:00-07:00 --tz Europe/Berlin` (`off` to remove). Hosted providers
  are not affected.
- **With nothing enabled, the lab makes no outbound AI calls**; AI features say they are
  not configured.

Keys stay in the gateway: users and workspaces never see a provider key, and each user has a
budget. Details: [v3/config/ai/README.md](v3/config/ai/README.md).

## Learning tracks

| Track | Modules |
|---|---|
| **Data engineer** (`engineer`/`full`) | E1 files → Iceberg with Spark · E2 table maintenance and time travel · E3 your own Airflow DAG · E4 notebook → scheduled Spark job |
| **Data analyst** (any profile; A4 needs `full`) | A1 SQL over the sample data · A2 exploration with JupySQL + DuckDB · A3 your first dbt model · A4 a Superset dashboard |

Open `https://jupyter.<domain>/`, go to the `tracks` folder, and follow a module's
`README.md`. `lab-tracks check E1` in a workspace terminal tells you whether you got there.
More: [v3/tracks/README.md](v3/tracks/README.md); for instructors,
[v3/tracks/FACILITATOR.md](v3/tracks/FACILITATOR.md).

## Documentation

| Doc | What |
|---|---|
| [docs/README.md](docs/README.md) | Docs index and design overview |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, networking, identity and data access |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Architecture decision records |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Phases and what each one delivered |
| [docs/MIGRATION.md](docs/MIGRATION.md) | Moving from V2 |
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | Version history |
| [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) | Tests, contracts, how to contribute |
| [v3/RELEASE_NOTES_v3.0.0-beta.1.md](v3/RELEASE_NOTES_v3.0.0-beta.1.md) | This release: highlights and known gaps |

## Coming from V2?

The [migration guide](docs/MIGRATION.md) has the commands. V2's code and docs are
archived in [legacy/v2/](legacy/v2/) ([what that means](legacy/README.md)). MinIO OSS
seems like it will get no more security fixes, so plan the move before a 0-day hits.

## Reporting problems

Open a [GitHub issue](https://github.com/karstom/lakehouse-lab/issues) with what you ran,
what happened, `v3/lab status`, your profile, OS and RAM. Never paste `v3/.secrets.env`, keys
or passwords. See [CONTRIBUTING](docs/CONTRIBUTING.md#reporting-issues).

## License

[MIT](LICENSE).
