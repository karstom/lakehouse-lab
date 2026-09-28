# Contributing to Lakehouse Lab

Thank you for helping. Lakehouse Lab V3 is a teaching lakehouse that has to install and work
for beginners, so most of this page is about keeping it testable.

## Reporting issues

Open a [GitHub issue](https://github.com/karstom/lakehouse-lab/issues) with:

- what you ran and what happened (paste the error);
- `v3/lab status` output, your profile (`core`, `engineer` or `full`), OS (Linux or WSL2),
  RAM, and `docker version` / `docker compose version`;
- for a service problem, `v3/lab logs --no-follow <service>` (check it for anything private
  before posting: hostnames, IPs, usernames).

**Never paste** `v3/.secrets.env`, API keys, tokens or passwords. For a security problem,
use GitHub's private vulnerability reporting instead of a public issue.

## Repository layout

| Path | What |
|---|---|
| `v3/` | Everything the lab runs: `compose.yaml` + `compose/`, `images/`, `config/`, `bootstrap/`, the installer (`install.sh`, `installer/`), the `lab` CLI, `tracks/`, `tests/`, `tools/` |
| `v3/versions.env` | The **only** place versions live (ADR-012) |
| `v3/CONTRACT.md` | The build contract: layout, runtime interfaces, test contract, per-phase scope |
| `v3/PHASE*_RESULTS.md` | What each phase built, measured and left open |
| `docs/` | Design (architecture, decisions, roadmap), migration guide, this file |
| `install.sh` | Thin bootstrap for the one-line install; it runs `v3/install.sh` |
| `core/` | The project memory graph (see below) |
| `spikes/` | Phase 0 throwaway stacks and their results |
| `legacy/v2/` | The archived V2 code and docs. Not developed; do not add to it |

## Ground rules

These come from V2's history (about 130 fix commits traced to a few root causes) and are
enforced by lint where possible:

- **Versions only in `v3/versions.env`.** Compose, scripts and Dockerfiles reference
  variables or build args. `v3/tools/check_versions.py` fails on literals elsewhere, and on
  `:latest`.
- **No logic in compose `command:`/`entrypoint:`** beyond calling a script. No package
  installs when a container starts; build them into an image.
- **Secrets** are generated with a CSPRNG, live only in `v3/.secrets.env` (never committed),
  and are never printed or baked into images.
- **Volumes** are declared once in compose, named from `COMPOSE_PROJECT_NAME`.
- **The repo is public:** never commit host IPs, hostnames, `.env`, `.secrets.env` or
  `state/`.
- **AI:** tests use only the deterministic mock model (`install.sh --ai-mock`). No test may
  configure or call a real local or hosted model.

## Tests

Everything CI runs is a script you can run locally from the repo root. The lint job
(`.github/workflows/v3-ci.yml`, no running lab needed):

```bash
python3 -m unittest discover -s v3/tests/lint -v
bash v3/tests/installer/test_unit.sh
python3 -m unittest discover -s v3/tests/bootstrap -v
python3 -m unittest discover -s v3/tests/smoke -p 'test_*.py' -v
python3 -m unittest discover -s v3/tests/ai -v
python3 -m unittest discover -s v3/tests/workspace -v
python3 v3/tools/check_tracks.py
python3 v3/tools/check_versions.py && python3 v3/tools/check_compat.py
v3/tools/shellcheck.sh && v3/tools/actionlint.sh
v3/tools/compose-check.sh --profile full
```

End to end, on a machine with Docker (it installs a real lab; use a spare project name and
ports if you already run one):

```bash
v3/install.sh --non-interactive --seed-test-users --domain lab.localhost --profile core
v3/lab test            # the smoke test: logs in as the test users and checks every service
v3/lab reset --yes     # delete this lab's containers and volumes afterwards
```

Repository checks (`.github/workflows/repo-checks.yml`): the root bootstrap test
(`tests/bootstrap/test_bootstrap.sh`, no network), ShellCheck on the root `install.sh`, and
actionlint on every workflow. The docs link check is `.github/workflows/documentation-check.yml`
(markdown-link-check with `mlc_config.json`).

A change to the installer, compose or an image should also pass an **upgrade in place**:
install from `main`, switch to your branch, run `v3/install.sh --non-interactive` again and
then `v3/lab test`.

## Contracts

V3 was built in phases, each against a written contract in `v3/CONTRACT.md` that fixes the
layout, the runtime interfaces (installer ⇄ compose ⇄ CI), the test contract and who owns
which paths. When a change needs a new interface (a new setting, secret, hostname or
profile), update the contract in the same pull request and say why in the description.
Design decisions go in `docs/DECISIONS.md` as an ADR.

## The memory graph (`core/`)

`core/` records what went wrong before and what must stay true: regressions (with how often
they recurred), invariants, decisions, watchlists and anti-patterns. Before changing an area:

1. Read `core/graph_index.md` and use its task-routing table to open only the relevant
   files.
2. Check `core/anti_patterns.md` before writing code, and the regressions and invariants
   that mention the files you touch.
3. A regression that has recurred twice or more is high-risk. Follow the root-cause gate
   in `core/HOW_TO_UPDATE.md` instead of adding another guard for the same symptom.
4. In the same pull request, record what you learned: a fixed bug as a Regression node, a
   decision as a Decision node (format and steps in `core/HOW_TO_UPDATE.md`).

The graph works with or without AI tooling; it is plain Markdown.

## Pull requests

1. Fork, then branch from `main`.
2. Keep the change focused, with tests. Run the lint commands above, and `v3/lab test` for
   anything that changes what the lab runs.
3. Update the docs you affected, and `docs/CHANGELOG.md` for user-visible changes.
4. Describe what you tested and on which profile.

## Code of conduct

Be respectful, helpful and inclusive. Many people here are learning; answer the question
they asked, kindly.
