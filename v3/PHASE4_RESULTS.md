# V3 Phase 4 Results (learning tracks)

> Integration report for Phase 4, built against the "Phase 4" section of `v3/CONTRACT.md`.
> Three workstreams (ENGINEER-TRACK, ANALYST-TRACK, TOOLING+CI) built in parallel. A power
> outage on the dev host cut the first run off; the workstreams resumed from the files on
> disk. The integrator then:
> - merged the pins and the cross-cutting patches;
> - reconciled the module interface and made one lead decision (production tables);
> - fixed what integration exposed (re-running E3/E4 on the same install);
> - upgraded the running Phase 3 install (`v3-p1`, `full`) in place;
> - ran a clean-room `full` install with every module;
> - re-ran the kernel-flake loop on the integrated tree;
> - tore down every test project.
>
> Host names, IPs and domains of the dev host are left out on purpose.

## Exit criteria

| Criterion | Result |
|---|---|
| 1. Every module's reference solution passes its checkpoint as a seeded user in that user's workspace, and `lab-tracks reset` restores the start | **Met for all 8 modules** (smoke check 17, `LAB_SMOKE_TRACKS=all`), on the upgraded `v3-p1` and on the clean rooms `v3-p4` and (repair round) `v3-p4r`. For every module: reset → files pristine → check exits 1 → solve → check exits 0 → reset → files pristine → check exits 1. |
| — module 1 of each track in the PR CI matrix | **Wired**: `v3-ci.yml` sets `LAB_SMOKE_TRACKS=first` (A1 on `core`; A1 and E1 on `engineer`). Not yet run on GitHub (nothing committed). |
| — all modules in the nightly `full` job | **Wired**: `v3-nightly.yml` sets `LAB_SMOKE_TRACKS=all` (dispatch input `tracks`). Not yet run on GitHub. |
| 2. Content survives upgrades | **Met** on `v3-p1` with alice's home, over two image upgrades (see "Upgrade in place"). |
| 3. Beginner validation | **Owner-run.** `v3/tracks/FACILITATOR.md` and `v3/tracks/FEEDBACK.md` are ready (see "What the owner must do"). |
| Required: kernel-flake root cause, 30-iteration loop with zero unexplained failures | **Met.** Root cause: ipykernel 7.x (see "Kernel-flake root cause"). Loop on the integrated tree: see "Loop on the integrated tree". |

## Repair round (after the independent verification)

The verifier followed E1, A1, E3 and A3 as learners (all numbers matched the lessons) and
failed one check: **an engineer could write another user's DAG folder.** As eddie, a file
`~/airflow-dags/alice/planted_by_eddie.py` with dag_id `u_alice_planted_by_eddie` was
accepted by Airflow as alice's DAG and ran. Every workspace is uid 1000 and the whole
`<project>_dags-user` volume was mounted read-write, so the DAG-id policy was the only
separation, and it cannot know who wrote a file. What changed:

| Finding | Fix |
|---|---|
| **Engineers could write each other's DAG folders** (required) | Each engineer/lab-admin workspace now mounts **only its own folder**: a volume mount with `VolumeOptions.Subpath=<username>` at `~/airflow-dags/<username>` (`LabSpawner._workspace_volumes`). Docker mounts a subpath only if it exists, so JupyterHub mounts the volume itself at `/srv/dags-user` and creates `<username>/` (owner 1000:100; one path segment only; refuses symlinks and non-directories; `ensure_user_dag_folder`). The one-shot `airflow-dags-user` now makes the volume root `root:root 0755` and writes a marker, `.lab-user-dags`: the hub gives DAG folders only when it exists (on `core`, compose creates the volume for the hub's mount, but there is no Airflow). Docker proxy: the whole-volume bind is refused; exactly one `Mounts` entry of that shape is allowed (source `<project>_dags-user`, subpath equal to the target's last segment, a **named** PCRE group because HAProxy compiles without auto-capture); another volume, no subpath, `..`, a nested subpath, a mismatched target, a second entry and a second `Mounts` key are refused. The Airflow policy also refuses a dag_id with a longer user's prefix (`u_eddie_x_…` in `eddie/` when `eddie_x/` exists). |
| Proof | Smoke check 11: **30/30** cases (11 new). Check 17, new step `dags_isolation` for every test user on `engineer`/`full`: eddie sees exactly one mount under `~/airflow-dags` (his own, root `…/<project>_dags-user/_data/eddie`), `ls ~/airflow-dags` lists only `eddie`, his own write works, and `mkdir ~/airflow-dags/alice` fails with **EACCES**; anna has no mount at all. Passed on the clean room and on the upgraded `v3-p1` (eddie's home from earlier phases too). New unit tests `tests/lint/test_user_dags.py` (policy and hub folder helper). |
| `tracks/README.md` claimed the platform is the backstop for `reset` | Rewritten: true for analysts (Trino lets them write only `dbt_<you>`); for engineer and lab-admin Trino grants write on every `lakehouse` schema, so reset's own refusal (`_allowed_table`, `drop_own`) is the only guard. Narrowing the engineer rules is left to the lead (Known gaps). |
| E1: Run All before the step 5 TODO gives a Spark `AnalysisException` (`` `partition` cannot be resolved ``) that "Common mistakes" did not name | New row in E1's README and tutor.md with that symptom, pointing at the "No partitioning" fix and saying to read only the first line of a Spark error. |
| A1: JupySQL's "If using snippets, you may pass the --with argument" before Trino's `mismatched input '.'` | New row in A1's README and tutor.md: the skeleton's `...` is still there; ignore JupySQL's first line. |
| E3 checkpoint passed on any `.py` in the DAG folder | It now requires `orders_summary_dag.py` (and says what the folder holds when it is missing). The DAG-id prefix collision (`eddie` vs `eddie_x`) is closed in the policy (above); `safe_name` collisions (`a.b` vs `a_b`) are documented. |
| E3 lesson and tutor | Trust note, step 2 (`ls ~/airflow-dags` shows only your folder), step 3 (the folder already exists; no `mkdir`), and "Common mistakes" (`Permission denied` next to your folder) updated to the new mount. |

**A flake seen during the repair runs, and its mitigation.** The first clean-room run failed
E2's reference notebook once: Spark got `ServiceUnavailableException: Authorization service is
unavailable` from Lakekeeper, because one OpenFGA `Write` (the tuples of a new table) hit
OpenFGA's 3 s server deadline (`query_duration_ms 3001`, host load about 6, no outage). This is
`WATCH_V3_OPENFGA_WRITE_DEADLINE_UNDER_IO_LOAD`, now seen outside an overloaded host, and a
learner would hit it too (a `CREATE TABLE` that fails). OpenFGA's request timeout is now 10 s
(`OPENFGA_REQUEST_TIMEOUT`, `compose/catalog.yaml`). A slow write is still a correct write;
this is not a retry. Why a single write sometimes takes over 3 s is not yet known. E2 passed
on the rerun and in both final runs.

**Runs (dev host):**

| Run | Result |
|---|---|
| Clean room `v3-p4r` (`--profile full --seed-test-users`, ports 18543/18180): first install | Docker proxy unhealthy: `reference to non-existent subpattern` (HAProxy compiles regexes without auto-capture). Fixed with a named group. |
| `v3-p4r`: install, `LAB_SMOKE_LONG=1 ./lab test --tracks all` | 16/17: check 17 failed on (a) the new isolation step, which wrongly expected a DAG folder for anna (harness bug, fixed: analysts must have no mount), and (b) the E2 OpenFGA deadline above. `LAB_SMOKE_ONLY=17 --tracks E2,A1` then **PASS**. |
| `v3-p4r` final tree: `install.sh`, `LAB_SMOKE_LONG=1 ./lab test --tracks all` | **SMOKE: PASS (17/17; profile full)**, 21 min; check 11 30/30; check 13 success; check 17 all 8 modules + `dags_isolation` (eddie EACCES, anna no mount). |
| `v3-p4r`: `lab reset --yes` | rc 0; 0 `v3-p4r*` containers, volumes and networks left. |
| **Upgrade `v3-p1`** (rsync of `v3/` without `.env`, `.secrets.env`, `state/`, `out/`; `./install.sh --non-interactive`) | rc 0 in 2.5 min; recreated `docker-proxy`, `jupyterhub`, `openfga`, `workspace-image`, the Airflow services and `airflow-dags-user` (volume root now `root:root`, marker written, eddie's existing folder kept). |
| `v3-p1`: `LAB_SMOKE_LONG=1 ./lab test --tracks all` | **SMOKE: PASS (17/17; profile full)**, 20.5 min; check 11 30/30; check 13 success (312 s); check 17 all 8 modules + `dags_isolation`. `v3-p1` left running on this tree. |

Docker safety for the repair round: non-v3 containers, volumes and networks identical before
(21:42 UTC) and after (23:10 UTC) (`~/lakehouse-v3/p4r-audit/`). Only `v3-p4r` (created,
tested, reset) and `v3-p1` (upgraded, tested) were touched; no `sudo`, no `prune`. One
disclosure: a read-only look at `v3-p1_dags-user` used a `--rm`, `--network none` container
from a small public `busybox` image, labelled `com.docker.compose.project=v3-p1`; if that image
was not already on the daemon, it was pulled then. It was left in place.

## Follow-up: Docker guard, and terminals that lost the lab's commands

Two findings after the repair round, one security class and one beginner blocker. Both are
fixed at the root; the dev-host runs are below.

### 1. Docker socket proxy body regexes were bypassable (security, recurring class)

**What was proven.** The socket proxy checked container-create bodies with HAProxy regexes
over the raw JSON. Docker decodes bodies with Go's `encoding/json`, which matches keys to
fields **case-insensitively**, decodes **`\u` escapes**, and keeps the **last of duplicate
keys**; the regexes did none of that. Three bodies got **201** and mounted another project's
`postgres-data` volume: a lowercase `"binds"`, an escaped `"Mounts"`, and a second
escaped `Mounts` key after the allowed DAG mount. This is the third hole in the same class
(Phase 2 follow-up: volumes and networks unscoped; Phase 4 repair: the Mounts shape and a
second `Mounts` key), so it is recorded as `REG_V3_DOCKER_PROXY_BODY_REGEX_BYPASS` (×3) with
the root cause: the source of truth is the JSON **as Docker decodes it**, and every earlier
fix added one more regex for the spelling just shown to work.

**Fix: one body policy, which reads what Docker reads** (`DEC_V3_DOCKER_GUARD_PARSE_VALIDATE_RESERIALIZE`;
CONTRACT "Docker access design: the guard"):

```
jupyterhub --hub-docker--> docker-guard --docker-api--> docker-proxy --> /var/run/docker.sock
```

- **`docker-guard`** (`bootstrap/docker_guard.py`, Python stdlib, `python3 -m bootstrap.docker_guard`
  on the bootstrap image, which is pinned by tag and digest; 64 MiB / 0.25 CPU):
  - forwards only DockerSpawner's calls, by name, in this project's scope;
  - parses bodies strictly (UTF-8 only; duplicate keys at any level, NaN/Infinity, lone
    surrogates and NUL refused; ≤ 256 KiB; no chunked bodies);
  - requires every key at every level to be exactly one canonical spelling, then checks the
    values (image, name, labels, binds, the user's own DAG mount, network, no privileges,
    memory/CPU limits);
  - forwards only its own `json.dumps` of the validated object, with its own
    `Content-Length`, and a query rebuilt from validated values;
  - fails closed: 403 plus one log line with a short reason (never the body, which carries
    the server's API token); forwarded bodies are logged by sha256 and size.
- **`docker-proxy`** keeps a METHOD + PATH allowlist only. Every request-body ACL was
  **removed**, so the guard is the single source of the body policy (no second, weaker
  check). While there: network inspect (unused) is gone, and volume inspect is limited to
  `<project>-home-*`.
- **Networks:** new internal network `docker-api` with only the guard and the proxy. The hub
  is on `hub-docker` with the guard only, and cannot reach the proxy (check 11 tests this).

**The allowed calls come from real traffic.** docker-py 7.2.0 / DockerSpawner 14.0.0 (the
hub image's versions) were first captured against a recording server, then confirmed from
the guard's own log on the dev host. Hub traffic on the clean room, all allowed, **0 hub
requests refused**:

| Call | Count |
|---|---|
| `GET /version` (docker-py `version="auto"`) | 1 |
| `GET /v1.52/containers/<p>-ws-<user>/json` | 41 |
| `GET /v1.52/images/<workspace image>/json` | 5 |
| `GET /v1.52/volumes/<p>-home-<user>` | 5 (404 → create) |
| `POST /v1.52/volumes/create` | 4 |
| `POST /v1.52/containers/create?name=<p>-ws-<user>` | 5 |
| `POST …/start`, `POST …/stop` | 5, 5 |
| `DELETE /v1.52/containers/<p>-ws-<user>?v=1` (docker-py sends `v=True&link=False&force=False`) | 5 |

**Tests.**
- New unit tests `tests/bootstrap/test_docker_guard.py` (22 tests, many sub-tests), on the
  exact docker-py bytes:
  - the DockerSpawner body passes, and the forwarded bytes are its canonical re-serialization
    (equal as JSON, never the client's bytes);
  - the verifier's three bypasses are refused;
  - so is the rest of the class: case variants of 16 sensitive keys, `\u` escapes,
    duplicates at every level, unknown keys, nested tricks in `Mounts`/`VolumeOptions`/
    `NetworkingConfig`/`Volumes`/`Labels`, host-config values, invalid JSON/UTF-8/NaN/BOM/
    nesting/size, names and queries, and every other API call.
- **Smoke check 11** (`proxy_probe.py`) now has **54 cases** (was 30):
  - the verifier's bypasses plus case variants, escapes, duplicates, a second `HostConfig`,
    trailing data and invalid UTF-8, all **403**;
  - the hub cannot connect to `docker-proxy` directly.
  - It stays side-effect free: creates use the real workspace image with `Memory: 4`, below
    Docker's 6 MB minimum, so an allowed body reaches Docker and is refused there (400) before
    anything exists. The allowed cases require exactly that answer.
  - One allowed body is sent with `\u`-escaped, reversed keys; `run.sh` requires the guard's
    log to show the canonical body with the sha256 the probe computed.

### 2. JupyterLab terminals lost `/opt/lakehouse/bin` (beginner blocker)

JupyterLab terminals run `bash -l`, and Debian's `/etc/profile` resets `PATH`. The image's ENV
entry `/opt/lakehouse/bin` was dropped: `lab-tracks: command not found`, and `dbt` resolved
to `/usr/local/bin/dbt` **without the token shim**, so A3 failed entirely. Every check ran its
commands from kernels (non-login processes), so none saw it
(`REG_V3_WORKSPACE_LOGIN_SHELL_LOSES_LAB_PATH`).

- **Fix:** `images/workspace/etc/profile.d/lakehouse.sh` puts `/opt/lakehouse/bin` first
  again (idempotent: it removes any existing entry, then prepends, so the dbt shim always
  wins). `PYTHONPATH` and `JUPYTERHUB_USER` come from the server's environment and survive
  `/etc/profile`; the smoke check verifies both.
- **Smoke:** check 17 now opens a **real JupyterLab terminal** once per run, as the launcher
  does (`POST api/terminals`, then the `terminals/websocket` terminado protocol). It requires:
  - `command -v lab-tracks dbt lab-token` → all three under `/opt/lakehouse/bin`;
  - `JUPYTERHUB_USER` = the user, `/opt/lakehouse/python` on `PYTHONPATH`;
  - `python3 -c 'import lakehouse'` works;
  - `lab-tracks check A1` runs there (exit 0 or 1, "Checking A1" printed).
  The markers are split in the typed text, so the terminal's echo never matches. Unit tests:
  `test_tracks_unit.py` `Terminal` (4).
- **Lessons:** A3 README and tutor "Common mistakes" now say how to spot it (`command -v dbt`
  must print `/opt/lakehouse/bin/dbt`) and what to do (`source /etc/profile.d/lakehouse.sh`,
  a new terminal, or stop/start the server from the Hub Control Panel on an older image).
- **Minor:** E2's README said three YOUR TURN cells (there are two, in steps 4 and 6).
  `lab-tracks` now prints a friendly error and exits 2 when `HOME` is unset or missing,
  instead of a traceback (unit test added).

### Runs (dev host)

| Run | Result |
|---|---|
| Upgrade `v3-p1` in place (rsync without `.env`, `.secrets.env`, `state/`, `out/`; `./install.sh --non-interactive`) | rc 0 in 64 s. Created `docker-guard`; recreated `docker-proxy` (now only on `docker-api`), `jupyterhub` (`DOCKER_HOST` → guard), `workspace-image`, and the bootstrap-image services. A second install (guard log level for health pings, one probe case) recreated only the services on the rebuilt bootstrap image (the guard, bootstrap, identity-sync, samples, trust-init, console-health). |
| `v3-p1`: `LAB_SMOKE_ONLY=8,17 ./lab test --tracks A1` (quick check before the long run) | PASS; terminal step ok |
| `v3-p1`: `LAB_SMOKE_LONG=1 ./lab test --tracks all` | **SMOKE: PASS (17/17; profile full)**. Check 11 54/54, guard forwarded the canonical body. Check 13 success. Check 17: all 8 modules, terminal ok for anna (`check_rc` 1), `dags_isolation` (eddie EACCES next door; anna no mount). |
| Clean room `v3-p4g` (new dir, `--project-name v3-p4g --domain sslip --https-port 18543 --http-port 18180 --seed-test-users --profile full`) | install rc 0, 4 min 9 s |
| `v3-p4g`: `LAB_SMOKE_LONG=1 ./lab test --tracks all` | **SMOKE: PASS (17/17; profile full)**. Same result as `v3-p1`. New home volumes were created through the guard (4 `volumes/create`, 201). |
| `v3-p4g`: `lab reset --yes` | rc 0; 0 `v3-p4g*` containers, volumes and networks left |

**Lint and unit tests (final tree).**
- `unittest`: `tests/lint` 84 OK; `tests/bootstrap` 68 OK (22 new: docker-guard);
  `tests/smoke` 53 OK (4 new: terminal); `tests/workspace` 23 OK (1 new: missing HOME).
- `check_tracks.py`, `check_versions.py` and `check_compat.py`: OK.
- `shellcheck.sh` (46 files) and `actionlint.sh`: OK.
- `compose-check.sh` for `core`, `engineer` and `full`: OK.
- `tests/installer/run.sh`: 276 passed.
- `core/scripts/consistency_check.sh`: 97 nodes, all references resolve.

**Docker safety.** Non-v3 containers (11, same ids and states), volumes (22) and networks (4)
were **identical** before (00:06 UTC) and after (01:07 UTC) (`~/lakehouse-v3/p4g-audit/` on
the dev host). Only `v3-p1` (upgraded, tested, left running on this tree, 21 containers up)
and `v3-p4g` (created, tested, reset) were touched. No `sudo`, no `prune`. The clean room's
directory `~/lakehouse-v3/p4g` is left on the host; no Docker objects remain.

**Memory graph.**
- New: `REG_V3_DOCKER_PROXY_BODY_REGEX_BYPASS` (×3, with root cause),
  `DEC_V3_DOCKER_GUARD_PARSE_VALIDATE_RESERIALIZE` and
  `REG_V3_WORKSPACE_LOGIN_SHELL_LOSES_LAB_PATH`.
- Updated: `INV_V3_DOCKER_PROXY_PROJECT_SCOPE` (now enforced by the guard's
  parse-validate-reserialize; body regexes removed; 54 cases).
- Corrected: `DEC_V3_DOCKER_PROXY_NAME_ALLOWLIST` (the proxy checks paths only).

**Still open:** which users get the DAG mount is still the hub's group decision; the guard
only ensures it is the workspace user's own folder. A new DockerSpawner option, or anything
else that changes the create body, is refused until `validate_create` and its tests allow it
(fail closed, visible as a 403 in the guard's log).

## Modules

| Track | Module | Profile | Test user | Time (lesson) | What the checkpoint verifies (outcomes only) |
|---|---|---|---|---|---|
| Engineer | E1 Files to Iceberg with Spark | engineer | eddie | 45 min | namespace `eng_<you>`; table `shipments` with real column types, partitioned by day, all three generated files loaded exactly once |
| Engineer | E2 Table maintenance | engineer | eddie | 45 min | all 12 batches present with the deleted readings restored (time travel), the first batch saved from an old snapshot, small files compacted, old snapshots expired |
| Engineer | E3 Your first Airflow DAG | engineer | eddie | 50 min | a DAG file in `~/airflow-dags/<you>/`, and a table `analytics.u_<you>_orders_summary` whose provenance columns prove an Airflow run as `lab-batch` |
| Engineer | E4 Notebook → scheduled job → Spark batch | engineer | eddie | 60 min | the learner's interactive table (as themselves), then the same numbers written by papermill in Airflow and by a Spark batch job, both as `lab-batch` (ADR-017) |
| Analyst | A1 SQL basics | core | anna | 45 min | `dbt_<you>.a1_segment_revenue_1996` with the right rows and totals |
| Analyst | A2 Explore with DuckDB and JupySQL | core | anna | 50 min | `dbt_<you>.a2_late_by_shipmode` with the right counts and late percentage |
| Analyst | A3 Your first dbt model | core | anna | 55 min | model `dbt_<you>.segment_revenue`, its passing dbt tests, and its table comment |
| Analyst | A4 Superset chart and dashboard | full | anna | 45 min | a dataset, two charts and a dashboard owned by the learner, through Superset's API as the learner |

Every module has `README.md` (goal, concepts, short steps, expected output, common mistakes),
`tutor.md` (objectives, mistakes, hints; for Phase 5), starter files, `module.json` and
`checkpoint.py`. Reference solutions are in `v3/tests/tracks/solutions/` (not copied into
homes). Lessons use only lab data (`lakehouse.samples`, generated files); `check_tracks.py`
refuses downloads and Spark `DROP ... PURGE` in code.

### Per-module solve times (smoke check 17)

Seconds for `solve.py` (plus, for E3/E4, the Airflow runs), then the passing checkpoint.

| Module | `v3-p1` upgrade, run 1 | `v3-p4` clean room, run 1 | `v3-p1` final | `v3-p4` final |
|---|---|---|---|---|
| A1 | 1.6 / 1.5 | 1.5 / 1.5 | 1.6 / 1.6 | 1.6 / 1.4 |
| A2 | 3.0 / 1.3 | 2.4 / 1.3 | 3.5 / 2.1 | 2.7 / 1.2 |
| A3 | 20.1 / 11.0 | 19.1 / 10.4 | 30.3 / 16.7 | 29.7 / 17.5 ¹ |
| A4 | 5.8 / 3.2 | 5.5 / 3.4 | 9.0 / 5.1 | 6.6 / 3.6 |
| E1 | 22.6 / 1.6 | 26.3 / 1.6 | 29.6 / 1.6 | 59.9 / 2.6 |
| E2 | 99.8 / 1.7 | 101.6 / 1.6 | 97.1 / 1.8 | 105.3 / 2.4 |
| E3 | 16.3 / 1.1 | 16.4 / 1.2 | 0.7 + 101.3 (Trigger) / 1.2 | 0.8 + 65.2 (scheduled) / 3.9 |
| E4 | 24.1 / 3.5 | 55.0 / 3.5 | 7.6 + 212.5 (Trigger) / 3.6 | 10.4 + 30.7 (scheduled) / 5.2 |

The final runs use the `dag_runs` step (below): E3/E4 show `solve + dag_runs`. On the fresh
`v3-p4` the harness took Airflow's own first scheduled run (`scheduled__…`, no trigger); on
`v3-p1`, where the DAGs had already run that day, it pressed Trigger as eddie after the 90 s
grace (`manual__…`). The "final" columns were run in pieces because the host lost power
mid-run (see "Dev-host outages"); every module passed on the final tree on both projects.

¹ The first final-tree A3 attempt on `v3-p4` failed in dbt with `ICEBERG_CATALOG_ERROR: Failed
to create transaction`: Lakekeeper's writes to OpenFGA hit "Request Deadline Exceeded" while
the host was at load 10–50 with ~24 % iowait just after a power-outage reboot. The rerun two
minutes later passed (`WATCH_V3_OPENFGA_WRITE_DEADLINE_UNDER_IO_LOAD`).

## Integration changes

**Pins.** `IPYKERNEL_VERSION` (6.31.0) promoted from `v3/.pins/tooling.env` to `versions.env`
(with its reason); `.pins/` removed. `compose/workspace.yaml` passes it as a build arg. The
workspace lock was already regenerated by TOOLING.

**Wiring.**
- `compose.yaml`: volume `dags-user` (user DAGs, E3).
- `compose/workspace.yaml`: build context `tracks: ./tracks` (the image copies the pristine
  lessons to `/opt/lakehouse/tracks`) and the `IPYKERNEL_VERSION` arg.
- `config/caddy/Caddyfile`: `jupyter.` upstream `keepalive 4s` (WATCH_V3_CADDY_UPSTREAM_KEEPALIVE_502).
- User-DAG infrastructure as ENGINEER built it: the one-shot `airflow-dags-user`,
  read-only mounts at `dags/user/` in the dag-processor, scheduler and triggerer, the
  Airflow cluster policy (`u_<you>_` ids in `user/<you>/`), and a group-based mount for
  `engineer`/`lab-admin`. **Superseded in the repair round** (below): the first design
  mounted the whole volume read-write, so engineers could write each other's folders.

**ANALYST's cross-cutting patch, applied as is** (without it A1–A4 fail):
- Analysts own one schema, `lakehouse.dbt_<you>`. Trino's file rules cannot put the user
  into a schema name, so bootstrap and identity-sync now GENERATE the rules Trino reads
  (`trino-groups/rules.json` = `config/trino/rules.json` + one rule pair per `analyst`
  member). Access still comes only from the Keycloak group. Trino no longer bind-mounts
  `rules.json` (the unused mount was removed from `compose/engines.yaml`).
- Superset accepts the user's own Keycloak access token on its API (`lab_bearer.py`: `azp`
  `jupyterhub` only, existing active users only, roles recomputed from the token's groups),
  for the A4 checkpoint running in the workspace.
- New Superset role `lab_author` (analyst, engineer): may add datasets.
- New unit tests `tests/bootstrap/test_trino_user_schemas.py`.

**Module interface, reconciled.** Both tracks already used the interface TOOLING documented
in `v3/tracks/README.md` (`module.json` + `checkpoint.py --json/--reset`, exit 0/1/2), with
per-track helpers in `<track>/_shared/` and solution helpers in `solutions/<track>/_lib/`.
The contract now states it ("Conventions added at Phase 4 integration").

**Lead decision: the learner's production tables.** E3/E4 DAGs run as `lab-batch`, which can
write `analytics` but not `eng_<you>`. Their output is `lakehouse.analytics.u_<you>_*`, and
these count as the learner's own objects, so `reset` may drop them (only with that prefix).
`check_tracks.py` accepts `analytics.{prod}*` and still warns for any other shared schema.
Recorded as `DEC_V3_TRACK_USER_PRODUCTION_TABLES`.

### Bug found by integration (fixed)

**Re-running E3/E4 on the same install hung for 13 minutes and failed.** The reference
solutions relied on Airflow's first scheduled run of a new `@daily` DAG. On a fresh install
that run comes at once (46 s). On a second run the same day, the DAG (same id) already had
that day's interval, so no run came: `v3-p1` re-run of E3, `solve rc=1 (794 s)`, "not ready
after 780s". A learner is not affected (the lesson has them press Trigger), but a developer
re-running check 17, or an upgrade that runs smoke twice, would be.

Fix (`tests/smoke/tracks.py`): for modules with `solution.trigger_dags`, `solve.py` runs with
`--no-wait`, and the harness, logged into Airflow **as the test user** (no stored password
beyond the seeded one the smoke already uses), waits until the DAG is parsed, takes a run
queued after the solve started, or after 90 s presses Trigger as the user, and waits for the
run to succeed (new step `dag_runs`, part of the pass rule). After the fix, the same-day re-run
on `v3-p1` passed: E3 `dag_runs` triggered `manual__…` success; E4 both DAGs triggered,
success; checkpoints passed, resets pristine. Unit tests added (`test_tracks_unit.py`: 48 OK).

## Upgrade in place (how existing users get Phase 4)

`v3-p1` (profile `full`, the Phase 3 install; it had restarted by itself after the first
outage) was upgraded with rsync of `v3/` (excluding `.env`, `.secrets.env`, `state/`, `out/`)
and `./install.sh --non-interactive`:
- rc 0 in about 2.5 min. Created volume `v3-p1_dags-user` and the `airflow-dags-user`
  one-shot; recreated `workspace-image`, `caddy`, `docker-proxy`, `jupyterhub`, `trino`,
  `bootstrap`, `identity-sync`, `samples`, `superset` and the Airflow services (config hash
  and new mounts). Bootstrap logged `rules.json: written`.
- `./lab test --long --tracks all`: **SMOKE: PASS (17/17; profile full)** in 17.5 min.
  Check 13 (ADR-017, token 120 s): run 312 s, success.

**Learners' homes keep their edits (exit 2), proven in alice's existing home:**
1. Before the upgrade alice's home had no `~/tracks` (Phase 3 image). We wrote two files as
   her (uid 1000): her own `~/tracks/my-notes.txt`, and her own version of
   `~/tracks/engineer/E1-files-to-iceberg/README.md`.
2. After the upgrade and her next spawn: both files byte-identical (sha256 `cf05742d…`,
   `3800dd96…`), every other lesson file added (51 files in the manifest),
   `tracks-sync.err` empty.
3. Then alice edited `~/tracks/analyst/A1-sql-basics/tutor.md` (after the sync), and the
   image changed that file and `FACILITATOR.md` (a real doc improvement). After a second
   `install.sh` (only `workspace-image` recreated) and her next spawn: her edited
   `tutor.md` kept (sha256 `490b95fb…`, her line still last; manifest marks
   `newer_in_image: true`, so `lab-tracks reset A1` would get the new version), and the
   unedited `FACILITATOR.md` updated to the image's version (sha256 equal to
   `/opt/lakehouse/tracks/FACILITATOR.md`).

**Final tree on `v3-p1`, after the host's 18:42 outage and reboot** (the stack restarted by
itself): `./install.sh --non-interactive` rc 0, then `./lab test --long --tracks all`:
**SMOKE: PASS (17/17; profile full)** in 24 min. Check 13: run 312.6 s, last commit 305 s after
start. Check 11: 19/19. Check 17: all 8 modules (E3/E4 through the Trigger path, above).
`v3-p1` is left running on the final tree (profile `full`).

## Clean room (dev host)

Project `v3-p4` in a new directory, ports 18543/18180, `--domain sslip --seed-test-users
--profile full`:

| Run | Result |
|---|---|
| `install.sh` (images cached) | rc 0, 3.5 min |
| `./lab test --long --tracks all` | **SMOKE: PASS (17/17; profile full)**, 17.6 min; check 11 19/19; check 13 success |
| Final tree: `lab reset --yes`, fresh `install.sh` (same flags) | rc 0 (the first attempt died in `samples` when the VM was suspended for 17 min; reset and re-run) |
| Final tree: `./lab test --long --tracks all` | checks 1–16 **PASS** (check 13 success); check 17 reached A3 when the host was shut down (18:42) |
| After the reboot: `LAB_SMOKE_ONLY=17 ./lab test --tracks E1,E2,E3,E4` | **PASS (4/4)**; E3/E4 took Airflow's own scheduled runs |
| `--tracks A3,A4`, then `--tracks A3` | A4 PASS; A3 failed once (OpenFGA deadline under host IO load, ¹ above), then **PASS** |
| 30-iteration kernel loop (below) | **120/120 ok** |
| `lab reset --yes` | rc 0; 0 `v3-p4*` containers, volumes and networks left |

## Kernel-flake root cause (CONTRACT Phase 4, "Required")

**One bug explains every intermittent workspace-kernel failure** (TOOLING+CI; Regression
`REG_V3_WORKSPACE_KERNEL_FIRST_MESSAGE_STALL`):
- With **ipykernel 7.x** (7.3.0), a shell message that arrives right after the kernel starts
  sometimes stays unread on the kernel's shell socket. The kernel stays **idle** forever, so
  the first cell (or our probe's execute request) never runs. It is released only when a
  *new* zmq peer sends a shell message; not by a control message, and not by more messages
  on the same websocket. A learner would see a first cell that never runs.
- The Phase 3 **"HTTP 403"** was a harness bug on top: the stack-dump fetch sent no
  `X-XSRFToken`, which JupyterHub ≥ 4.1 requires on non-navigation GETs.
- WATCH_V3_SPARK_CONNECT_INTERMITTENT_HANG (a kernel silent after a Spark
  `ForbiddenException`) has the same signature: the refusal was logged when the stalled
  request finally ran at teardown.
- **Fix:** ipykernel held at **6.31.0** (`IPYKERNEL_VERSION`). The harness now sends the XSRF
  header, and on a timeout records the kernel's `execution_state` (idle = never processed,
  busy = user code hangs), a websocket message trace and `~/.smoke-progress.txt`.
- **No retries were added.** The cause is ours (a dependency we pin), not external, so the
  contract's retry allowance does not apply.

**A second, separate flake:** Caddy reused a keep-alive connection that JupyterHub's proxy
(node, 5 s idle timeout) was closing, so a `DELETE`/`POST` got **502 EOF** (a failed "Stop
server"). Fix: Caddy drops idle upstream connections to the hub after 4 s.

### Loop statistics (login → spawn → kernel → Trino + Spark step → stop)

| Run | Tree | Iterations | Failures |
|---|---|---|---|
| Baseline (interrupted by the first outage) | ipykernel 7.3.0 | 26 | 1 `kernel_timeout` (alice, 318 s) |
| `diag1`, project `v3-p4-tooling`, engineer | ipykernel 7.3.0 | 120 (30/user) | **3 `kernel_timeout`** (eddie, anna, victor): all idle after 300 s, 0 messages for our execute |
| `fix1` | ipykernel 6.31.0 | 120 | 0 kernel failures; 1 `stop_failed` = the Caddy 502 |
| `fix2` | 6.31.0 + Caddy keepalive 4s | 120 (30/user) | **0** |
| Lab-less repro `tools/kernel_ws_race.py` | 7.3.0 | 400 immediate / 80 handshakes | 43 / 6 lost |
| Lab-less repro | 6.31.0 | 400 | 0 |
| **Integrated tree, first try**, project `v3-p4`, full | 6.31.0 + keepalive 4s | 85 before a hypervisor shutdown | 0 before it; the only 5 non-ok iterations started at 17:54:30, while the host was powering down (hub 502, then no connection) |
| **Integrated tree, `integrated-v3-p4-full-2`**, project `v3-p4`, full | 6.31.0 + keepalive 4s | **120 (30/user)** | **0** (median 22.5 s, max 37.8 s per iteration) |

The exit condition ("the 30-iteration loop runs with zero unexplained failures") is met on the
integrated tree.

Reproduce: `tests/smoke/kernel-loop.sh [--iterations N] [--stress N] [--race N]` on a lab,
or `python3 v3/tools/kernel_ws_race.py` without one.

## Lint and checks (final tree)

All run on the final tree (after the repair round):

| Check | Result |
|---|---|
| `unittest` `tests/lint` | 84 OK (8 new in the repair round: `test_user_dags.py`) |
| `unittest` `tests/bootstrap` | 46 OK (6 new: generated Trino rules) |
| `unittest` `tests/smoke` | 49 OK (4 new: `dag_runs`; 1 new: `dags_isolation`) |
| `unittest` `tests/workspace` (`lab-tracks`) | 22 OK |
| `tools/check_tracks.py` | 0 errors, 0 warnings |
| `tools/check_versions.py`, `tools/check_compat.py` | OK, OK |
| `tools/shellcheck.sh` (45 files), `tools/actionlint.sh` | OK, OK |
| `tools/compose-check.sh --profile core / engineer / full` | OK ×3 |
| `tests/installer/run.sh` | 276 passed |
| `core/scripts/consistency_check.sh` (memory graph) | 94 nodes, all references resolve |

## Docker safety (the host runs production)

- Only `v3-*` projects were started, changed or reset: `v3-p1` (upgrade, tests, left
  running) and `v3-p4` (clean room, reset). No `sudo`, no `prune`.
- Before/after audit of non-v3 objects (`~/lakehouse-v3/p4-integ-audit/`): containers
  **identical** (11, same ids and states), volumes **identical** (22). Networks: 4 and 4; the
  only difference is the id of Docker's default `bridge` network, which the Docker daemon
  recreates at every boot (the host rebooted twice during this run).
- Test-only image tags left by the workstreams (`lakehouse-lab/v3p4an-*`, `v3p4en-*`, 13
  tags) were removed with `docker rmi` by name. The shared tag
  `lakehouse-lab/v3-workspace:<JUPYTERHUB_VERSION>` now holds the Phase 4 image (the same tree `v3-p1` runs).
- Short-lived probe containers used to read and edit alice's home carried
  `com.docker.compose.project=v3-p1` and `--rm`.
- Smoke check 11 passed in every run (19 cases before the repair round, 30 after it).

## Dev-host outages during this phase

The dev host is a VM on the owner's hardware. Its power failed four times during Phase 4:
- ~13:28 UTC: cut the first run of the workstreams off (host back 13:36).
- 17:54 UTC: "System is powering down (hypervisor initiated shutdown)" during the first
  integrated kernel loop (host back 18:02). That loop had 85 of 85 iterations ok before it;
  the only non-ok iterations (5) started at 17:54:30, while the hub was being stopped.
- about 18:07 host time: the VM was suspended for about 17 minutes (the owner reported UPS
  beeping and network switches down until power returned). The clean-room reinstall running
  then failed in `samples` (Trino `ABANDONED_QUERY`: no client for 17 min). It was reset and
  run again from scratch.
- 18:42 UTC: another hypervisor-initiated shutdown (host back 19:07), during the final-tree
  tests on both projects. The remaining parts were re-run after the reboot (see the tables).

None of these were caused by the lab; they are recorded in
`WATCH_V3_SHARED_DEV_HOST_OUTAGE_DURING_PARALLEL_TESTS`. After each, the running `v3-p1` came
back on its own (`restart: unless-stopped`) and was re-tested.

## Known gaps

- **Beginner validation (exit 3) is not done**: only the owner can run it.
- **GitHub CI has not run** the Phase 4 changes (nothing committed or pushed). `actionlint`
  passes. The nightly budget (`timeout-minutes: 120`) has room: check 17 with every module
  took 6–10 min on the dev host (more when E3/E4 need the 90 s Trigger grace).
- **Workspace image tag is shared across projects** on one Docker daemon
  (`lakehouse-lab/v3-workspace:<JUPYTERHUB_VERSION>`; WATCH_V3_WORKSPACE_IMAGE_TAG_SHARED_ACROSS_PROJECTS).
  Harmless here (every v3 project built the same tree), but parallel test stacks with
  different trees overwrite each other's image. A project-scoped tag is a later decision.
- **User DAG trust.** A user DAG runs with Airflow's worker identity (`lab-batch` for data).
  Engineers are trusted to author DAGs. Since the repair round each workspace mounts only its
  owner's DAG folder, so one engineer can no longer write another's (see "Repair round").
- **Engineers and lab admins can write every `lakehouse` schema** (`config/trino/rules.json`
  since Phase 2), including other learners' `eng_<name>`, `dbt_<name>` and
  `analytics.u_<name>_*`. `lab-tracks reset` refuses anything but the learner's own names
  (`_allowed_table`, `drop_own`), but the platform is not a backstop for these groups
  (`v3/tracks/README.md` says so). Narrowing it (generated owner-only rules for `eng_<name>`,
  like the analysts' `dbt_<name>`) is a lead decision.
- **Name collisions after `safe_name`**: logins that differ only in characters outside
  `a-z0-9_` (`a.b`, `a_b`) share `eng_a_b` and `u_a_b_*` tables. Documented in
  `v3/tracks/README.md`; DAG ids are not affected (they use the login as-is), and the DAG
  policy now refuses another user's longer prefix (`u_eddie_x_` in `eddie/`).
- **Superset keep-alive.** Superset's gunicorn (2 s keep-alive) may have the same Caddy race
  as the hub had; not observed.
- **OpenFGA write deadline**: failed one A3 dbt build during integration and one E2 table
  create in the repair round. Mitigated (OpenFGA request timeout 3 s → 10 s); the reason a
  single tuple write takes over 3 s on the shared host is not found
  (`WATCH_V3_OPENFGA_WRITE_DEADLINE_UNDER_IO_LOAD`).
- Checkpoints use `lakehouse.samples` reference numbers computed at check time; if the sample
  scale ever changes, the lessons' "expected output" numbers need updating.

## What the owner must do

1. **Beginner sessions (exit 3).** Follow `v3/tracks/FACILITATOR.md`: at least two real
   beginners each complete **E1** and **A1** without help, and each fills in
   `v3/tracks/FEEDBACK.md`. Use a lab with `--profile engineer` (or `full`) and give each
   person their own Keycloak account in the right group (`engineer` for E1, `analyst` for
   A1). After each session, fix what blocked people before the next one.
2. **Commit and push** the Phase 4 tree to `v3`, then watch the PR matrix (`core`,
   `engineer`: A1, E1) and dispatch `v3-nightly` (`full`, all modules).
3. Decide later whether the tracks move to their own repo (OQ-10), and whether the workspace
   image tag becomes project-scoped.

## Final state

- `v3-p1` (profile `full`) runs the Phase 4 tree: 30 containers healthy or completed; alice's
  home has `~/tracks` with her edits.
- No `v3-p4*` project, volume, network or test image is left. The server-side logs and
  audits are under `~/lakehouse-v3/p4-integ-*` and (repair round) `~/lakehouse-v3/p4r*` on
  the dev host.
- Repair round memory graph: new `REG_V3_USER_DAG_FOLDERS_WRITABLE_BY_ALL_ENGINEERS`; updated
  `DEC_V3_USER_DAGS_SHARED_VOLUME` (per-user subpath mounts), `INV_V3_DOCKER_PROXY_PROJECT_SCOPE`
  (the one allowed Mounts shape, 30 cases) and `WATCH_V3_OPENFGA_WRITE_DEADLINE_UNDER_IO_LOAD`
  (second occurrence, 10 s timeout).
- Memory graph: new `DEC_V3_ANALYST_OWN_SCHEMA_GENERATED_TRINO_RULES`,
  `DEC_V3_SUPERSET_API_BEARER_KEYCLOAK`, `DEC_V3_TRACK_USER_PRODUCTION_TABLES`,
  `WATCH_V3_OPENFGA_WRITE_DEADLINE_UNDER_IO_LOAD`; updated
  `REG_V3_WORKSPACE_KERNEL_FIRST_MESSAGE_STALL` (integrated loop), `WATCH_V3_CADDY_UPSTREAM_KEEPALIVE_502`
  (fix applied), `WATCH_V3_SHARED_DEV_HOST_OUTAGE_DURING_PARALLEL_TESTS` (these outages). The
  workstreams' nodes (`DEC_V3_USER_DAGS_SHARED_VOLUME`, `REG_V3_TRINO_CURRENT_USER_IN_AGGREGATE`,
  `WATCH_V3_WORKSPACE_IMAGE_TAG_SHARED_ACROSS_PROJECTS`) are kept.
- Nothing is committed or pushed.
