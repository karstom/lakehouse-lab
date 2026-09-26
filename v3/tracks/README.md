# Learning tracks

Two tracks teach the job, not just the tools. Each is a short sequence of modules; a module
takes 30 to 60 minutes and ends with a **checkpoint** that tells you whether you got there.

| Track | Modules | You need |
|---|---|---|
| **Data engineer** | E1 files → Iceberg with Spark · E2 table maintenance (snapshots, time travel, compaction, snapshot expiry) · E3 your own scheduled Airflow DAG · E4 notebook → scheduled job → Spark batch job | profile `engineer` or `full`; Keycloak group `engineer` (or `lab-admin`) |
| **Data analyst** | A1 SQL over `samples` · A2 exploratory analysis with JupySQL + DuckDB · A3 your first dbt model · A4 a chart and a dashboard in Superset | A1–A3: any profile; A4: profile `full`. Keycloak group `analyst` (or `engineer`, `lab-admin`) |

Everything uses lab data only (`lakehouse.samples` and data the lessons generate). Nothing
is downloaded from the internet.

## For learners

1. Open `https://jupyter.<your lab domain>/` and log in. Your workspace starts.
2. In JupyterLab, open the `tracks` folder in the file browser, then your track and the first
   module (for example `tracks/analyst/A1-sql-basics/`). Open its `README.md`: it is the
   lesson.
3. Work through the steps. When you think you are done, open a terminal (File → New →
   Terminal) and run:

   ```
   lab-tracks check A1
   ```

   It checks what you built (tables, rows, DAG runs, dashboards), as you, and prints what
   passed and a hint for the first thing that did not.

Other commands:

| Command | What it does |
|---|---|
| `lab-tracks list` | all modules, how long they take, what they need, and your progress |
| `lab-tracks check <ID>` | run the module's checkpoint (you can run it as often as you like) |
| `lab-tracks reset <ID>` | start a module again: its original files come back, and what the module created **in your own schema and your own DAG folder** is dropped. Your changed files are moved to `~/.lakehouse/tracks-backup/`, never deleted. |
| `lab-tracks status <ID>` | which of your files in the module differ from the original |

Your copy of the tracks is yours: edit, rename or delete anything. When the lab is upgraded,
new lessons are added to `~/tracks` at your next workspace start, and **files you changed are
never overwritten**. A file you did not change is updated to the new version; a file you
deleted stays deleted (`lab-tracks reset <ID>` brings a module back as new). Your progress is
in `~/.lab-progress.json`.

If a check says it **could not run** (not "not yet"), the problem is not your work: check that
`lab-token` prints a token (if not, log out of the hub and in again) and that the lab is up.

---

## For module authors: the module interface

This is the contract between a module, the `lab-tracks` CLI (in the workspace image,
`v3/images/workspace/lakehouse/tracks.py`) and smoke check 17. The tracks are laid out so
they can move to their own repository later without code changes.

### Layout

```
v3/tracks/
  README.md  FACILITATOR.md  FEEDBACK.md
  <track>/                          engineer | analyst
    _shared/                        optional helpers for the track's checkpoints (not a module)
    <ID>-<slug>/                    one module, e.g. E1-files-to-iceberg
      module.json                   metadata (below); this file is what makes a folder a module
      README.md                     the lesson: goal, why, steps with expected output, common mistakes
      tutor.md                      learning objectives, common mistakes, hints (Phase 5 AI tutor)
      checkpoint.py                 the machine check (below)
      ...                           starter files: notebook.ipynb, SQL, dbt, DAG, data generator
v3/tests/tracks/solutions/<track>/<ID>-<slug>/
      solve.py                      the reference solution (test-only; never copied into homes)
      ...                           any files solve.py needs
v3/tests/tracks/solutions/<track>/_lib/   optional shared helpers for the track's solutions
```

The workspace image copies `v3/tracks/` to `/opt/lakehouse/tracks/` (read-only, the pristine
copy) and every workspace start copies it into `~/tracks/` (copy-on-upgrade, see above).
Everything in a module folder is delivered to learners, so keep answers out of it.

### `module.json`

```json
{
  "id": "E1",
  "track": "engineer",
  "title": "Files to Iceberg with Spark",
  "minutes": 45,
  "profile": "engineer",
  "groups": ["engineer", "lab-admin"],
  "test_user": "eddie",
  "requires": [],
  "checkpoint": "checkpoint.py",
  "solution": {"timeout_s": 600, "browser_logins": []},
  "reset": {"...": "free-form, read by the module's own checkpoint.py --reset"}
}
```

| Key | Required | Meaning |
|---|---|---|
| `id` | yes | Short, unique across tracks: `E1`…`E4`, `A1`…`A4`. `lab-tracks check e1` also works. |
| `track` | yes | Must equal the track folder name. |
| `title` | yes | Shown by `lab-tracks list`. |
| `profile` | yes | Lowest profile that has everything the module uses: `core`, `engineer` or `full` (each includes the ones before it). Check 17 skips the module on a smaller profile. |
| `groups` | yes | Keycloak groups that can do the module (any one is enough). `lab-tracks list` tells a learner who lacks all of them to ask an admin. |
| `minutes` | no | Estimated time, 30–60. |
| `test_user` | no | Seeded user check 17 runs the solution as. Default from the first known group: `engineer` → eddie, `analyst` → anna, `lab-admin` → alice, `viewer` → victor. |
| `order` | no | Integer position in the track; default: the number in `id`. |
| `requires` | no | Module ids to do first (shown to learners; not enforced). |
| `checkpoint` | no | Default `checkpoint.py`. |
| `solution.timeout_s` | no | Seconds check 17 allows `solve.py` (default 900). |
| `solution.browser_logins` | no | Apps the test user must have logged into once before `solve.py` runs, as a learner would: `"superset"`, `"airflow"` (Superset creates its user record at the first login). |
| anything else | no | Free for the module (e.g. `reset`, `lesson`, `start`); `lab-tracks` ignores it. |

### `checkpoint.py`

A plain Python script. `lab-tracks` runs it **as the learner** (their own Keycloak token via
`lakehouse.lab_token()`), always **from the pristine image copy**
(`/opt/lakehouse/tracks/<track>/<module>/checkpoint.py`), with the **current directory set to
the learner's copy** (`~/tracks/<track>/<module>`).

| Invocation | Must do | Exit code |
|---|---|---|
| `python checkpoint.py --json` | Check outcomes and print one `PASS`/`FAIL` line per check, each FAIL with a hint that says what to do next. As the **last** line, print `LAB_TRACKS_RESULT {"module": "E1", "passed": true, "checks": [{"name": "...", "ok": true, "detail": "...", "hint": "..."}]}`. (A last line that is just that JSON object is accepted too.) | `0` passed, `1` not yet, `2` could not run (no token, service down): never `1` for an infrastructure problem |
| `python checkpoint.py` | The same, for a learner who runs it directly; the result line is optional. | as above |
| `python checkpoint.py --reset` | Drop what the module creates, **only the learner's own objects** (below), with a plain `DROP` (never Spark `DROP ... PURGE` against Lakekeeper). Succeed when there is nothing to drop. Files in the learner's module folder are NOT its job: `lab-tracks` restores them. | `0` done, non-zero failed |

Rules:
- **Outcomes, not file contents.** Check tables, rows, snapshots, DAG runs, dbt models and
  Superset objects (through Superset's API as the user), never what the notebook says.
- **Imports** of the module's own helpers use `__file__` (`os.path.dirname(os.path.abspath(__file__))`),
  so the script works both from the image copy and when a learner runs it in `~/tracks`.
- **Learner files** (a data folder the lesson generates, a DAG they wrote) are found through
  `$LAB_MODULE_DIR`, falling back to the script's own folder. Environment set by `lab-tracks`:
  `LAB_MODULE_ID`, `LAB_MODULE_DIR` (learner's copy), `LAB_MODULE_SRC` (pristine copy),
  `LAB_TRACKS_HOME` (`~/tracks`).
- **Start state fails.** On a fresh home (and right after `reset`) the checkpoint must exit `1`.
  A module whose checkpoint passes before the learner did anything is broken; check 17
  asserts this.
- **Clear language.** A hint is for a beginner: name the lesson step, say what to run.
- **Time.** A checkpoint should finish in seconds; `lab-tracks` stops it after 15 minutes. A
  module that waits for an Airflow run polls with its own shorter timeout and says so.

### The learner's own objects (what `reset` may drop)

`reset` drops only objects that belong to the learner, named from their login `<you>` (in
names, every character other than `a-z0-9_` becomes `_`):

| Kind | Name | Used by |
|---|---|---|
| A module's own namespace | `lakehouse.<prefix>_<you>`, e.g. `eng_<you>` | engineer E1, E2 |
| The learner's dbt schema | `lakehouse.dbt_<you>`: only the tables the module's lesson creates, never the whole schema (the starter project uses it too) | analyst A3 |
| The learner's production tables | `lakehouse.analytics.u_<you>_*` (`{prod}` in module.json): tables the learner's own DAGs write as the batch identity `lab-batch`, which cannot write `eng_<you>` | engineer E3, E4 |
| DAG files | `~/airflow-dags/<you>/`, DAG ids `u_<you>_*` (Airflow's DAG policy enforces the prefix) | engineer E3, E4 |
| Superset objects | charts, datasets and dashboards the learner owns, by the names the lesson gives | analyst A4 |

Never `samples`, never another user's objects, and never anything a learner cannot drop
themselves: `reset` runs with the learner's own permissions, so the platform's access rules
are the backstop. Writing into a *shared* schema is a contract decision for the lead, not a
module's. The one such decision so far (Phase 4 integration, DEC_V3_TRACK_USER_PRODUCTION_TABLES):
engineer DAGs publish to `analytics` under the learner's prefix `u_<you>_`, like a real team's
production schema, and `reset` drops only tables with that prefix.

### Reference solutions and smoke check 17

`v3/tests/tracks/solutions/<track>/<ID>-<slug>/solve.py` does what a successful learner does,
end to end, and is safe to run twice. It runs as the learner inside their workspace:

```
cd ~/tracks/<track>/<ID>-<slug> && python ~/.lab-solutions/<ID>-<slug>/solve.py ~/tracks/<track>/<ID>-<slug>
```

(argument and current directory: the learner's module copy; `$LAB_SOLUTION_DIR`: the uploaded
solution folder; the environment of `lab-tracks` above). The track's shared helper folders
(`solutions/<track>/_*/`, e.g. `_lib`) are uploaded next to it, to `~/.lab-solutions/_lib/`, so
`os.path.join(os.path.dirname(__file__), "..", "_lib")` works as in the repository. Each solution must work from a fresh
home: if the module builds on an earlier module's result, `solve.py` creates it itself.

**Smoke check 17** (`tests/smoke/tracks.py`, run by `lab test`) does this for each selected
module, as the module's `test_user`, in that user's own workspace (headless login, spawn, the
Jupyter kernel; the same path as a learner):

1. `lab-tracks reset <ID> --yes` (a clean start), then the files must be pristine and
   `lab-tracks check <ID>` must exit `1` (not yet);
2. upload the solution folder to `~/.lab-solutions/`, run `solve.py` (exit `0`). A module
   whose solution writes Airflow DAGs lists them in `solution.trigger_dags` (`{dag}` =
   `u_<user>_`): `solve.py` then runs with `--no-wait`, and the harness, logged into Airflow
   as the test user, waits for a run of each DAG queued after the solve started. A new
   `@daily` DAG gets one on its own; a re-run on the same install and day does not (that
   day's interval already ran), so after 90 s the harness presses Trigger as the user, as
   the lesson does, and waits for the run to succeed (step `dag_runs`);
3. `lab-tracks check <ID>` must exit `0` (passed);
4. `lab-tracks reset <ID> --yes` must exit `0`, and then the files must be pristine and the
   checkpoint must exit `1` again (the start state);
5. remove `~/.lab-solutions/`.

Selection: `LAB_SMOKE_TRACKS=first` (default: module 1 of each track; the PR CI matrix),
`all` (the nightly `full` job), `none`, or a list such as `E1,A3`. Modules whose profile is
not included in the lab's profile are skipped with a reason. Run one module locally with
`LAB_SMOKE_ONLY=17 LAB_SMOKE_TRACKS=E1 ./lab test --no-build`.

### Lint

`python3 v3/tools/check_tracks.py` (CI lint job) checks every module: a valid `module.json`,
`README.md`, `tutor.md`, `checkpoint.py` supporting `--json` and `--reset`, a reference
`solve.py`, no Spark `DROP ... PURGE`, and no internet downloads (`pip install`, `wget`,
`curl http…`, `urlretrieve`, `read_csv("http…")`).
