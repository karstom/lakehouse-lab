# Lakehouse Lab v3.0.0-beta.1 (draft release notes)

> Draft for the GitHub pre-release. The lead finalizes it when tagging (see
> [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)).

**The first beta of Lakehouse Lab V3**: a rebuilt, single-sign-on lakehouse for learning to
work as a data engineer or data analyst, and for real analysis on one server. V3 is a new
stack, not an in-place upgrade of V2; V2 users should read
[Coming from V2](#coming-from-v2) first.

## Install

```bash
git clone https://github.com/karstom/lakehouse-lab.git && cd lakehouse-lab && v3/install.sh
# or
curl -fsSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
```

To install exactly this release, add `--ref v3.0.0-beta.1` to the one-liner
(`… | bash -s -- --ref v3.0.0-beta.1`), or `git checkout v3.0.0-beta.1` after cloning.
Linux or WSL2 with Docker 24+ / Compose 2.20+; 16 GB of RAM recommended. Full instructions:
[README](../README.md#quick-start).

## Highlights

- **One login for everything.** Keycloak single sign-on across the Console, JupyterHub,
  Trino, the catalog, Airflow, the Spark UI and Superset. Access is set by one Keycloak
  group per person (`lab-admin`, `engineer`, `analyst`, `viewer`) and reaches every tool
  within about 30 seconds. Optional "Sign in with GitHub", where new users get no access
  until an admin approves them.
- **A real Iceberg lakehouse.** Lakekeeper (Iceberg REST catalog, OpenFGA authorization) on
  SeaweedFS storage, which replaces MinIO. Engines get short-lived credentials limited to
  one table from the catalog. Trino, Spark and the notebooks hold no static storage keys.
- **Current engines.** Trino, Spark 4.1 through Spark Connect (the notebook user's identity
  per session), DuckDB and dbt, plus Airflow 3 and Superset 6. Superset queries run in
  Trino as the signed-in user.
- **A workspace per user.** JupyterLab and code-server, with Trino, Spark, DuckDB,
  PyIceberg, JupySQL and dbt preconfigured as that user, a starter dbt project, and a
  personal Airflow DAG folder for engineers.
- **Learning tracks.** Data engineer (E1–E4) and data analyst (A1–A4) modules, each with
  a checkpoint (`lab-tracks check`) and a safe reset. They use lab data only, with no
  downloads.
- **AI assist (profile `full`).** A Lab Assistant in JupyterLab whose tools (Trino, dbt,
  Superset, lab context) act as the user and are read-only. A model gateway holds the keys
  and gives each user a budget. **Hosted models are off by default**. Local models work
  through any OpenAI-compatible server, with optional **quiet hours**. With no provider
  enabled, the lab makes no outbound AI calls.
- **Profiles** `core`, `engineer` and `full`. Every version is pinned in one file
  (`v3/versions.env`), and nothing is installed when a container starts.
- **Tested the way you run it.** On every change, CI does a real install of `core` and
  `engineer` and runs an end-to-end smoke test as real users. A nightly job does the same
  for `full`, including every track module and the AI assistant against a mock model.
- **Safe re-runs.** `v3/install.sh` keeps your settings, secrets and certificate authority,
  and upgrades the running lab in place. `v3/lab` handles day-to-day operations.

## Beta caveats

- **Expect rough edges.** Every piece passes CI and was independently verified on a
  test server. But V3 has not yet been used by many people on many machines.
- **Upgrades between betas** are designed to work in place (re-run the installer). Still,
  keep anything you cannot lose outside the lab until 3.0 is final.
- **Images are built on your machine** during the first install. This is slower the first
  time, and cold-cache install times have not been measured. The images that `v3-images`
  publishes for this tag are not yet used by the installer.
- **Changing the domain or ports after install** needs `v3/install.sh --reconfigure`, and
  may also need a `v3/lab reset`, because parts of the sign-in configuration are created on
  first start. Choose the domain carefully the first time.
- **Linux and WSL2 only.** macOS and native Windows Docker are not tested.
- **Real beginners** have not yet completed the tracks' first modules without help. This
  exit criterion is scheduled with real learners, and the lessons may change after it.

## Known gaps

Collected from the phase results (`v3/PHASE1_RESULTS.md` … `v3/PHASE5_RESULTS.md`), where each
one is described in more detail.

**Security and multi-user**
- **A workspace can reach machines on the Docker host's LAN directly**, so it could call
  a local model server without going through the gateway's keys and budgets. If you use a
  local model server, give it an API key (`v3/lab ai set-local … --api-key-file`), or
  firewall the lab's network from it. See the options in `v3/CONTRACT.md` (Phase 5, "AI
  front door and workspace AI boundaries").
- **Engineers and lab admins can write every schema** in the `lakehouse` catalog,
  including other learners' track schemas. The track tools only ever touch your own
  names, but the platform does not enforce this for these groups. Analysts are limited
  to their own schema.
- **Anyone who can edit DAGs can act as the batch identity** (`lab-batch`), which writes
  the shared `analytics` schema. This is accepted for trusted engineers.
- **The Spark Connect server is shared.** Sessions carry each user's identity, but
  executors are not isolated per user.
- **A revoked catalog grant can keep working for up to an hour**, because vended storage
  credentials are cached until they expire.
- **Grants made directly in the Lakekeeper UI do not apply to Trino or Superset.** Grant
  access through Keycloak groups.
- **Provider error messages pass through the AI gateway unchanged.** Such a message could
  name the local model server's address.

**Behaviour and operations**
- **A single Spark job cannot outlive its session token** (at most 1 hour). Long jobs
  should run through Airflow as the batch identity, which renews its token.
- **Locally built image tags are shared by every lab on one Docker host.** Run one lab
  per host, or keep every lab on the same code.
- **Turning test users off** (`--no-seed-test-users`) does not delete test users that
  were already created.
- **Tutor mode off** gives Jupyter AI's normal tools, which can edit notebooks and run
  commands as the user in their own workspace. Whether Jupyter AI asks before each tool
  call has not been tested.
- **The OpenFGA write deadline** was hit twice under heavy I/O on a busy shared test host.
  It is mitigated with a longer timeout. If a table create or dbt build fails with a
  deadline error, retry it.
- **Real "Sign in with GitHub"** is checked by hand; CI tests the flow against a mock
  provider.
- **Name collisions:** usernames that differ only in punctuation (`a.b`, `a_b`) share
  track schema names.

**Not in 3.0:** a migration *tool* (there is a tested [guide](../docs/MIGRATION.md)),
the `server` profile for multi-TB work, add-ons (Vizro, LanceDB, Portainer, Spark History),
Kubernetes, and a separate repository for the learning tracks.

## Coming from V2

V3 does not upgrade V2 in place, and it leaves V2's data untouched.

1. **Before pulling `main`, pin your V2 install:** `git fetch --tags && git checkout
   v2.1.1-final` in your V2 directory. Otherwise `git pull` replaces V2's files with V3,
   and V2's code is now under `legacy/v2/`. The new one-line installer refuses to touch a
   V2 directory.
2. Install V3 in a new directory, copy your MinIO data across with `rclone`, and load what
   you need as Iceberg tables: see the [migration guide](../docs/MIGRATION.md).
3. V2 is no longer developed. Its MinIO image gets no security fixes, so plan the move.

## Reporting issues

Please open a [GitHub issue](https://github.com/karstom/lakehouse-lab/issues) and include:

- what you ran and what happened, with the error text;
- the output of `v3/lab status`, your profile, OS (Linux or WSL2), RAM, `docker version`
  and `docker compose version`;
- for a failing service, the relevant part of `v3/lab logs --no-follow <service>`.

**Never post** `v3/.secrets.env`, passwords, API keys or tokens. Also check logs for
hostnames and IP addresses before you post them. Report security problems privately
through the repository's **Security → Report a vulnerability** page, not in a public issue.
