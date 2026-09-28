# V3 Phase 6 Results (migration guide, AI polish, cutover, beta release prep)

> Integration report for Phase 6, built against the "Phase 6" section of `v3/CONTRACT.md`.
> Three workstreams (MIGRATION, AI-POLISH, CUTOVER) worked in parallel, each in its own
> dev-host project. The integrator then:
> - promoted the pins and applied the cross-cutting patches;
> - finished the cutover (the migration guide moved to `docs/MIGRATION.md`, links fixed,
>   `v3/.pins/` gone, the git index back to plain renames);
> - ran every local check on the final tree;
> - upgraded the long-running `v3-p1` (`full`) in place;
> - ran a clean install through the **new root bootstrap**, piped to `bash` like the
>   one-liner, from a local snapshot of this tree;
> - ran the quiet-hours end-to-end test on that clean install, with the mock standing in
>   for the local model;
> - re-ran the migration proof on the integrated tree;
> - reset every test project.
>
> **Quiet hours were respected throughout.** No request of any kind was sent to the
> owner's llama-server. `v3-p1` stayed mock-only: `.env` `LAB_AI_MOCK=true`,
> `LAB_AI_LOCAL_URL=` (empty), no provider key, and the gateway renders providers `[mock]`.
> The only `local` provider ever configured pointed at `http://ai-mock:8000/v1`, on the
> throwaway `v3-p6` project, inside `quiet-hours-e2e.sh`.
>
> A repair round later fixed the gateway's startup log. See
> [Repair round](#repair-round-the-gateways-startup-log).
>
> Agents made no commit, push, merge, tag or publish. Host names, IPs and domains of the
> dev host are left out on purpose.

## Exit criteria

| Criterion | Result |
|---|---|
| The migration commands are proven on synthetic data | **Met.** MIGRATION: `tests/migration/run.sh all` ALL_RC=0 twice on `v3-p6-migration` (`engineer`), against a throwaway MinIO (V2's release) and Postgres (details in `v3/tests/migration/EVIDENCE.md`). Integrator re-run on the integrated tree: see [Migration re-run](#migration-re-run-integrated-tree). |
| Quiet hours: unit-tested, plus on the dev host with the mock standing in for local | **Met.** `tests/ai/test_quiet_hours.py` (30 tests, injected clock: windows across midnight, both 2026 New York DST days, skipped and repeated hour, Retry-After) and `test_lab_quiet_hours.py` (11). On the clean `v3-p6` install: `LAB_E2E_LOCAL_VIA_MOCK=1 tests/ai/quiet-hours-e2e.sh` **QUIET HOURS E2E: PASS**. See [Quiet hours](#quiet-hours-on-the-clean-install). |
| The date is in the prompt, and the narration handling is tested | **Met** by AI-POLISH: `tests/workspace/test_ai_polish.py` (clock block, ReplyShaper over a recorded LangChain 1.4.2 event fixture) and a dev-host persona run with the mock scripted for reasoning + narration + two tool calls + answer (11/11 checks). Smoke check 18's persona reply (`mock reply f97ec1be: …`) is unchanged on `v3-p1` and `v3-p6`. |
| The cutover tree passes all lint and unit tests and `v3-ci` locally (actionlint, compose-check) | **Met.** See [Local checks](#local-checks-final-tree). |
| Upgrade in place of `v3-p1` still passes all 18 smoke checks | **Met.** `./install.sh --non-interactive` rc 0, then `LAB_SMOKE_LONG=1 ./lab test --tracks all`: **SMOKE: PASS (18/18; profile full)**. |
| A clean install from the new root bootstrap passes | **Met.** Root `install.sh` piped to `bash -s -- --repo file://… --ref v3 …` → BOOTSTRAP_RC=0, then `LAB_SMOKE_LONG=1 ./lab test --tracks all`: **SMOKE: PASS (18/18; profile full)**; `gateway-e2e.sh` PASS. |
| Docker safety holds; non-v3 objects are unchanged | **Met.** Non-v3 containers (id, name, image, state, created), volumes and networks: 39 lines before and after the last reset, `diff` empty. Every `v3-p6*` project reset to 0 containers, volumes and networks. |

## What was integrated

| Piece | Where |
|---|---|
| **Pins** (MIGRATION): `RCLONE_IMAGE_TAG/DIGEST` 1.75.1, `MIGRATION_TEST_MINIO_IMAGE_TAG/DIGEST` `RELEASE.2024-12-18T13-15-44Z` | `v3/versions.env`; `v3/.pins/` removed; `tests/migration/run.sh` now reads `versions.env` only |
| **Quiet hours wiring** (AI-POLISH patch 1–3): `LAB_AI_QUIET_HOURS`, `LAB_AI_QUIET_TZ` into `ai-gateway`'s environment; the installer question after the AI-assist block; both variables unset from the caller's shell by `lab_settings` | `v3/compose/ai.yaml`, `v3/install.sh`, `v3/installer/lib.sh` |
| **Mock model narration** (AI-POLISH patch 4): a tool step may carry `content`, any step `reasoning` (as `reasoning_content`); `plan()` unchanged, `plan_full()` added; new unit test | `v3/tests/ai/mock_llm/server.py`, `v3/tests/ai/test_mock_llm.py` |
| **Migration guide location**: `git mv docs/v3/MIGRATION.md docs/MIGRATION.md`; links fixed in `docs/*.md`, `README.md`, root `install.sh` (V2-refusal message), `legacy/README.md`, release notes, `tests/migration/*`; the guide's own relative links moved up one level; `docs/v3/` is gone | `docs/`, and the files named |
| **ROADMAP** (MIGRATION's request): "with `rclone` (or `mc mirror`)" → "with `rclone`" (only rclone is documented and tested) | `docs/ROADMAP.md` |
| **Stale `docs/v3/` references** (CUTOVER's list) | `v3/installer/lib.sh` comment, `spikes/README.md`, `v3/CONTRACT.md` header, `core/graph_index.md` routing rows |
| **Docs workflow**: the migration guide must be at `docs/MIGRATION.md` (the either-location check is gone) | `.github/workflows/documentation-check.yml` |
| **Nightly**: `gateway-e2e.sh` and the new `quiet-hours-e2e.sh` run with `LAB_E2E_LOCAL_VIA_MOCK=1` (a CI runner has no real model server, which is what the opt-in exists for) | `.github/workflows/v3-nightly.yml` |
| **Link check**: `opensource.org` added to `mlc_config.json` `ignorePatterns`. It now answers 403 to every non-browser client (also plain `curl`), so the V2 README's license badge failed the check | `mlc_config.json` |
| **Release checklist**: the "move the migration guide" step and recipe removed (done here) | `v3/RELEASE_CHECKLIST.md` |
| **CONTRACT**: `.env` rows for the quiet-hours variables; "Conventions added at Phase 6 integration" | `v3/CONTRACT.md` |
| **Git index**: AI-POLISH's `git stash`/`pop` had left CUTOVER's moves as 109 staged adds plus 106 unstaged deletes. The integrator staged those deletions only (`git rm --cached` of the moved-away paths, every one checked to exist under `legacy/v2/` or `docs/`), so `git status` again shows 104 plain renames (`R`) plus 2 renamed-and-modified (`RM`). File contents were not touched. New and edited files stay unstaged for the lead | index only |

Checked and unchanged: `check_versions.py` still scans only `v3/`. The root-level
`markdown-link-check@3.15.0` pin lives in `tests/docs/check-links.sh`, outside that scope, as
CUTOVER reported. `compose-check.sh` and the v3 workflows only reference `v3/` paths, and a
grep of `v3/` finds no reference to a moved V2 path (`start-lakehouse.sh`,
`docker-compose.yml`, `scripts/`, `templates/`, `utils/`, `jupyterhub/`).

## Local checks (final tree)

| Check | Result |
|---|---|
| `python3 v3/tools/check_versions.py` | OK |
| `python3 v3/tools/check_compat.py` | OK (0 errors, 0 warnings) |
| `python3 v3/tools/check_tracks.py` | 0 errors, 0 warnings |
| `unittest discover -s v3/tests/lint` | 93 OK |
| `unittest discover -s v3/tests/bootstrap` | 68 OK |
| `unittest discover -s v3/tests/ai` | 114 OK (incl. 30 quiet-hours, 11 `lab ai quiet-hours`, the new mock narration test); 119 OK after the repair round (5 `MainLog` tests) |
| `unittest discover -s v3/tests/workspace` | 97 OK |
| `unittest discover -s v3/tests/smoke -p 'test_*.py'` | 84 OK (2 skipped) |
| `bash v3/tests/installer/test_unit.sh` | 338 passed, 0 failed |
| `v3/tools/shellcheck.sh` (pinned v0.11.0) | 58 files, OK (incl. `tests/migration/run.sh`) |
| `v3/tools/actionlint.sh .github/workflows/*.yml` (pinned 1.7.12) | 6 workflows, OK |
| `v3/tools/compose-check.sh --profile core / engineer / full` | OK / OK / OK |
| `bash tests/bootstrap/test_bootstrap.sh` | 43 passed, 0 failed |
| `bash tests/shellcheck.sh` (root `install.sh`, `tests/`) | OK |
| `bash tests/docs/check-links.sh` (web links included) | 89 files, OK |
| `bash core/scripts/consistency_check.sh` | 116 nodes, all references resolve |

## Upgrade in place: `v3-p1`

rsync of `v3/` into the `v3-p1` directory, leaving out `.env`, `.secrets.env`, `state/`, `out/`
and `__pycache__/` (no file deleted on the target), then:

| Step | Result |
|---|---|
| `./install.sh --non-interactive` (no AI flags) | rc 0, 19:03:16 to 19:05:36 UTC. Recreated only `workspace-image`, `ai-mock` (the mock's code changed) and `ai-gateway` (new environment variables). Still mock-only: `lab ai status` local/anthropic/openai off, mock on, **quiet off**; gateway `state.json` `providers: ["mock"]`, `local_models: []`, `quiet_hours: null`; container env `LAB_AI_LOCAL_URL=` and `LAB_AI_QUIET_HOURS=` empty |
| `LAB_SMOKE_LONG=1 ./lab test --tracks all` | **SMOKE: PASS (18/18; profile full)**, 19:05:36 to 19:35:32 UTC. Check 11: 54 cases, 0 unexpected. Check 13: the Spark batch ran 306.7 s past a 120 s token. Check 17: all tracks. Check 18: alice (workspace key, 29 tool calls, every check true, front door checks all true, persona reply `mock reply f97ec1be: …`) and victor (private dashboard refused, write refused, 0 of alice's queries) |

## Clean install through the new root bootstrap: `v3-p6`

The tree was snapshotted **without committing to this repository**: every tracked and
untracked, non-ignored file of the working tree (582 files; local, untracked agent configuration left out) was copied into a scratch directory, made into a throwaway one-commit
git repository on branch `v3`, and copied to the dev host as a bare repository. Its `v3/`
was checked to be byte-identical to this tree's. It was never pushed anywhere, and was
deleted afterwards.

The one-liner path, with the installer taken from that snapshot and piped to `bash`:

```
git -C <bare repo> show v3:install.sh | bash -s -- --repo file://<bare repo> --ref v3 \
  --dir <p6-clean> --project-name v3-p6 --domain sslip --https-port 18543 --http-port 18180 \
  --seed-test-users --profile full --ai-mock --ai-local-url none --non-interactive
```

| Step | Result |
|---|---|
| Bootstrap | Printed the plan (repository, ref, directory, `git clone --branch v3 …`, the exact `v3/install.sh` command), cloned, and exec'd `v3/install.sh`. rc 0 in about 9 min (19:36:06 to 19:45:04 UTC; the images for this tree were already built by the `v3-p1` upgrade). 32 secrets (mode 600), new lab CA, `Local AI model: none`. The checkout was clean afterwards (`git status --porcelain` empty: `.env`, `.secrets.env`, `state/` are ignored) |
| `LAB_SMOKE_LONG=1 ./lab test --tracks all` | **SMOKE: PASS (18/18; profile full)**, 19:45:04 to 20:12:32 UTC |
| `tests/ai/gateway-e2e.sh` (default mode, no opt-in) | **AI GATEWAY E2E: PASS**. Step 3 (local-via-mock) printed SKIPPED as designed; no connection outside the lab's networks |
| Bootstrap again on the existing checkout (update path) | rc 0. Plan: "update the existing checkout to v3 (fast-forward only …)". Then `v3/install.sh --non-interactive`: "Kept existing secrets", "Kept existing lab CA"; the `.secrets.env` md5 was the same before and after |
| `./lab reset --all --yes` | rc 0. 0 containers, volumes and networks left for `v3-p6`, 4 per-user home volumes deleted, `state/` removed, then the directory and the bare repository were deleted |

### Quiet hours on the clean install

`LAB_E2E_LOCAL_VIA_MOCK=1 tests/ai/quiet-hours-e2e.sh` on `v3-p6` (providers exactly `[mock]`
beforehand, as the script requires): **QUIET HOURS E2E: PASS** (20:12:32 to 20:15:36 UTC).

| Mode | Window (America/New_York) | Result |
|---|---|---|
| quiet | `15:12-17:12` (covers now) | `local` and `lab-default` (→ local) refused for chat, Anthropic messages and embeddings, as admin and with a user key through `ai-frontdoor`: HTTP 503 "The lab's local AI model is resting until 17:12 America/New_York (quiet hours 15:12-17:12). Please try again after that; your lab admin can change this with './lab ai quiet-hours'." `Retry-After=3529`. **No refused request reached the model server** (mock request log). The `mock` model was not affected |
| outside | `18:13-19:13` | every request answered by the local provider (the mock) |
| off | empty | every request answered |
| restore | — | the gateway back on the lab's own settings, providers `[mock]` |

The real CLI on the same lab: `./lab ai quiet-hours 22:00-07:00 --tz America/New_York` rc 0,
`lab ai status` → `quiet 22:00-07:00 America/New_York, local model only (now: outside the
window)`, gateway `state.json` `quiet_hours {"tz": "America/New_York", "window":
"22:00-07:00"}`; `25:00-07:00` refused (rc 1); `off` rc 0 → `quiet off`, `quiet_hours: null`,
`.env` keeps both keys empty.

## Migration re-run (integrated tree)

MIGRATION's last full runs were on its own copy, before two changes: its `source-down` fix
(`docker rm -f -v`) and the integrator's removal of the `.pins/` loop from `run.sh`.
So the integrator re-ran the proof on the integrated tree: project `v3-p6-migint`
(`engineer`, seeded test users, ports 18543/18180), `tests/migration/run.sh all`, then
`./lab reset --all --yes`.

| Step | Result |
|---|---|
| `./install.sh --non-interactive --project-name v3-p6-migint --domain sslip … --seed-test-users --profile engineer` | rc 0, 20:23:27 to 20:27:24 UTC |
| `tests/migration/run.sh all` | **ALL_RC=0** in about 3 min (20:27:24 to 20:30:32 UTC). Seed as documented (orders 5,000 rows, trips 300,000 rows, 6 special-character keys, a 300 MiB object). `rclone check --one-way`: "0 differences found" for all three buckets (60, 2 and 10 matching files); `check --download` on `big-files`: 0 differences, 2 matching. The copy re-run transferred nothing. Postgres: `customers.csv` in `landing` has 1,000 rows (V2 table: 1,000). In alice's workspace kernel: Spark loaded the three trip files (100,000 rows each); Trino + PyIceberg appended 5,000 orders; Trino check `matches_source: true`. The landing key could not write to `landing` or list or read `warehouse`. After deletion, the old key was refused |
| Leftovers of the migration test | 0 containers, 0 volumes, 0 networks labelled `lab.test=migration` (so the `rm -f -v` fix holds in a full run) |
| `./lab reset --all --yes` | rc 0; 0 `v3-p6-migint` containers, volumes and networks left; directory deleted (including its `out/`, which held the test's credentials file) |

## Repair round: the gateway's startup log

The verifier refuted the claim that AI-POLISH's patch was applied correctly. In
`v3/config/ai/render_config.py` `main()`, the quiet-hours `if` had been inserted between
`if state["configured"]:` and its `else:`, so the `else` belonged to the quiet-hours check.
As a result:
- every configured gateway without quiet hours logged the providers line **and**
  "no AI provider enabled: … makes no outbound AI calls" (seen on `v3-p1` and on the verifier's
  clean install);
- with a hosted provider enabled, that line was a false no-egress statement;
- an unconfigured gateway with quiet hours set lost the not-configured notice.

The rendered config and `state.json` were always right; only the log was wrong.

| Step | Result |
|---|---|
| Fix | The `else:` is back under `if state["configured"]:`; quiet hours are now a separate `if` that follows it |
| Test | New `MainLog` class in `v3/tests/ai/test_render_config.py` runs `main()` into a temp dir with stdout captured. It covers mock only (providers line, no "no AI provider enabled", no quiet hours), hosted (Anthropic) enabled (no no-egress line, key not printed), empty env ("no AI provider enabled"), empty env + `LAB_AI_QUIET_HOURS=22:00-07:00` (both lines), and mock + quiet hours (both, no no-egress line). On a copy of the old code, 3 of these fail |
| `unittest discover -s v3/tests/ai` | 119 OK. `check_versions.py` OK; `tests/lint` OK; `tests/docs/check-links.sh` 90 files OK |
| `v3-p1` upgrade in place (rsync as above, then `./install.sh --non-interactive`) | rc 0, 21:26:59 to 21:28:12 UTC. Recreated **only** `v3-p1-ai-gateway-1`. `docker logs v3-p1-ai-gateway-1 \| grep ai-gateway`: only `[ai-gateway] providers: mock; lab-default -> mock; models: lab-default, mock` (0 "no AI provider enabled" lines). `state.json`: providers `["mock"]`, `local_models: []`, `quiet_hours: null` |
| `v3-p1` `LAB_SMOKE_LONG=1 ./lab test --tracks all` | **SMOKE: PASS (18/18; profile full)**, 21:28:27 to 21:58:33 UTC. Check 11: 54 cases, 0 unexpected. Check 18: alice and victor all checks true, 29 tool calls each, front door checks all true, persona reply `mock reply f97ec1be: …`, `no_outbound: true` |
| Clean install `v3-p6r` (`full`, `--seed-test-users --ai-mock --ai-local-url none`, ports 18543/18180) | Done with `v3/install.sh`, **not** through the root bootstrap (see below). The fixed `v3/` tree was copied on the dev host from the `v3-p1` directory, leaving out `.env`, `.secrets.env`, `state/`, `out/`. Install 22:20:05 to 22:24:10 UTC: 32 secrets, new lab CA, `Local AI model: none`. Gateway log: only the providers line. `lab ai status`: local/anthropic/openai off, mock on, quiet off |
| `v3-p6r` `LAB_SMOKE_LONG=1 ./lab test --tracks all` | **SMOKE: PASS (18/18; profile full)**, 23:05:03 to 23:33:29 UTC. Check 11: 54 cases, 0 unexpected. Check 18: persona reply `mock reply f97ec1be: …`, `no_outbound: true` |
| `v3-p6r` gateway log with quiet hours | `./lab ai quiet-hours 22:00-07:00 --tz America/New_York` rc 0. Gateway log: the providers line, then `local model quiet hours: 22:00-07:00 America/New_York (models refused then: none now)`, and no "no AI provider enabled". `./lab ai quiet-hours off` rc 0, and the log again shows only the providers line. Only the mock was configured, so no request went to any model server |
| `./lab reset --all --yes` on `v3-p6r` | rc 0. 0 `v3-p6r` containers, volumes and networks left, 4 per-user home volumes deleted, directory removed. Non-v3 containers, volumes and networks (37 lines), from while `v3-p6r` was running to after the reset: `diff` empty. After the reset, the only `v3-*` objects belong to `v3-p1` (25 containers) |

**The root bootstrap was not re-run in this round.** Last time, a throwaway snapshot
repository of the whole tree was copied to the dev host. This round, that copy was blocked
by the agent's permission policy (a data-exfiltration rule), and the agent did not work
around it. The repair does not touch the root `install.sh`, `README.md` or anything the
bootstrap runs before it hands over to `v3/install.sh`. The verifier's own clean run through
the bootstrap (18/18) still stands for that path. The lead's release checklist runs the
public one-liner against branch `v3` anyway.

Optional cleanups done in this round:
- `core/decisions.md`: the V3 decision nodes whose **Files** (and two **Summary** lines)
  named `docs/v3/*.md` now name `docs/*.md` (`docs/v3/README.md` → `docs/README.md`), so
  `check_files` on `docs/DECISIONS.md` finds them (8 nodes). The history in
  `DEC_V3_CI_TOOLING` (V2 workflows ignored `docs/v3/**`) and `DEC_V3_CUTOVER_LEGACY_LAYOUT`
  is left as it was.
- The empty, untracked local `docs/v3/` directory was removed.
- New regression node `REG_V3_AI_GATEWAY_FALSE_NO_EGRESS_LOG`; `consistency_check.sh`: 117
  nodes, all references resolve.

## Docker safety

- Only `v3-*` projects were created or changed: `v3-p1` (upgrade), `v3-p6` (clean install),
  `v3-p6-migint` (migration re-run), plus the migration test's own `v3-p6-migint-v2src*`
  objects (labelled `lab.test=migration`).
- Snapshot of every non-v3 container (id, name, image, state, created time), volume and
  network, taken before the first dev-host step, after the `v3-p6` reset and again after
  the `v3-p6-migint` reset: 39 lines each time, `diff` empty both times. Afterwards the only
  `v3-*` objects on the daemon belong to `v3-p1`. The production project was never read, written, stopped or restarted.
- No `sudo`, no `prune`.
- Shared local image tags (`WATCH_V3_WORKSPACE_IMAGE_TAG_SHARED_ACROSS_PROJECTS`): the
  `v3-p1` upgrade and the clean install ran one after the other, from the same tree, so
  every project on the daemon runs the same images.

## Workstream notes carried forward

- **AI-POLISH `git stash`**: contents were restored by its `pop`. The index state it changed
  is repaired (see "Git index" above). Nothing else was affected.
- **AI-POLISH `<details>` rendering**: not looked at in a browser. JupyterLab's own HTML
  sanitizer in the workspace image (`jlab_core…js`, `allowedTags`) allows `details` and
  `summary`. jupyterlab-chat renders messages through JupyterLab's markdown renderer, so the
  collapsed section should survive. A visual check is on the lead's list (below).
- **MIGRATION**: the guide needs Docker 25 or newer for the two `--network` flags on one
  `docker run` (the installer's minimum is 24.0.0). The guide says so and gives the
  V2-on-another-host variant, which is untested.
- **PyIceberg** cannot write to tables partitioned by a transform in the workspace
  (pyiceberg-core is not in the image). The guide uses unpartitioned tables on that path.
  This is recorded as `WATCH_V3_PYICEBERG_NO_TRANSFORM_PARTITION_WRITES`.

## Memory graph

- New: `DEC_V3_MIGRATION_LANDING_BUCKET_READONLY_KEY`, `DEC_V3_CUTOVER_LEGACY_LAYOUT`,
  `WATCH_V3_PYICEBERG_NO_TRANSFORM_PARTITION_WRITES` (AI-POLISH added
  `DEC_V3_LOCAL_MODEL_QUIET_HOURS_IN_GATEWAY` and `REG_V3_LAB_ASSISTANT_NARRATION_AND_DATE`).
- `core/graph_index.md` routing: the V3 row now points at `docs/` and `v3/`. The V2 installer
  row names `legacy/v2/` and says that the root `install.sh` is now the V3 bootstrap.
- Not done (release checklist §6): re-anchoring the older V2 nodes whose files moved to
  `legacy/v2/` (`core/scripts/stale_check.sh`).

## For the lead

1. Review and commit the integration on `v3`. New and edited files are unstaged; only the
   renames are staged. Local agent configuration files must stay out.
2. Open one Lab Assistant chat with tool use and check in a browser that the collapsed
   "steps" section renders.
3. Then follow `v3/RELEASE_CHECKLIST.md` (GitHub CI on the `v3` head, nightly dispatch, the
   public one-liner against branch `v3`, tags, merge).
