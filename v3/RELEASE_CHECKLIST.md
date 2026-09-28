# Release checklist: v3.0.0-beta.1

Run by the lead, in order, after the owner has seen the finished cutover. Agents never
merge, tag, push or publish. Tick each box in the release PR description.

Placeholders: `<lab-host>` is a test host that is **not** a production machine, and
`<domain>` is that lab's domain. Never write real hosts into this repo.

## 0. Before merging (branch `v3`)

- [ ] The Phase 6 integration is committed on `v3`: MIGRATION, AI-POLISH and CUTOVER
      (integrated in `v3/PHASE6_RESULTS.md`: pins in `v3/versions.env`, no `v3/.pins/`, the
      migration guide at `docs/MIGRATION.md`).
- [ ] Local checks are green on the final tree:
      - `bash tests/bootstrap/test_bootstrap.sh`
      - `bash tests/shellcheck.sh`
      - `bash tests/docs/check-links.sh`
      - the v3 lint list in `docs/CONTRIBUTING.md` ("Tests"), including
        `v3/tools/actionlint.sh .github/workflows/*.yml` and
        `v3/tools/compose-check.sh --profile full`.
- [ ] GitHub is green on the `v3` head: `v3-ci` (core + engineer e2e), `repo-checks`,
      `Documentation Check` and `Security Scan`. Also dispatch `v3-nightly` (full, long,
      all tracks) and wait for it:
      `gh workflow run v3-nightly.yml --ref v3`.
- [ ] An upgrade in place of the long-running test lab passes all 18 smoke checks, with the
      mock AI model only.
- [ ] A clean install from the root bootstrap, pointed at branch `v3`, passes `v3/lab test`:
      `curl -fsSL https://raw.githubusercontent.com/karstom/lakehouse-lab/v3/install.sh | bash -s -- --ref v3 --dir <fresh dir> --project-name <test project> --https-port <port> --http-port <port> --seed-test-users --non-interactive`
- [ ] Nothing private is in the diff: no host IPs, sslip domains, hostnames, personal paths,
      `.env`, `.secrets.env` or `state/`. Check with
      `git diff main...v3 | grep -nE '([0-9]{1,3}\.){3}[0-9]{1,3}|sslip\.io|/home/'`,
      and review each hit (documentation examples like `<a-b-c-d>.sslip.io` are fine).
- [ ] Only intended files are in the diff: `git diff --stat main...v3` lists no local
      tool or editor configuration.
- [ ] The release notes (`v3/RELEASE_NOTES_v3.0.0-beta.1.md`) and the CHANGELOG entry
      match what is merged. Set the CHANGELOG date (it says "unreleased").
- [ ] Repository settings: private vulnerability reporting is on (Settings → Code security),
      because the release notes and CONTRIBUTING point to it.

## 1. Tag the last V2 commit

```bash
git fetch origin
git tag -a v2.1.1-final origin/main -m "Last V2 release before V3 (archived in legacy/v2/)"
git push origin v2.1.1-final
```

- [ ] Check that the V2 one-liner from `legacy/README.md` resolves:
      `curl -fsSI https://raw.githubusercontent.com/karstom/lakehouse-lab/v2.1.1-final/install.sh`
      returns 200.
- [ ] Optional: mark the GitHub release for 2.1.1 as the last V2 release, with a link to
      the migration guide.

## 2. Merge `v3` into `main`

- [ ] `main` has no commits that `v3` lacks: `git merge-base --is-ancestor origin/main
      origin/v3` succeeds. If not, merge `main` into `v3` first. A V2 fix belongs under
      `legacy/v2/`, and V2 is archived, so usually only security fixes matter.

Open a PR from `v3` to `main` (title: "V3: v3.0.0-beta.1"), paste the release notes'
highlights, and wait for the checks. Merge with a **merge commit**, not a squash, so the V3
history and the `git mv` renames into `legacy/v2/` survive.

- [ ] After the merge, `main` shows the V3 README, and `legacy/v2/` holds V2.
- [ ] Workflows on `main`: the merge push runs `v3-ci`, `v3-images` (build only),
      `repo-checks`, `Documentation Check` and `Security Scan`. All are green. No V2
      workflow runs (they are in `legacy/v2/workflows/`).

## 3. Tag `v3.0.0-beta.1`

```bash
git fetch origin
git tag -a v3.0.0-beta.1 origin/main -m "Lakehouse Lab v3.0.0-beta.1"
git push origin v3.0.0-beta.1
```

- [ ] The tag push starts `v3-images` with `PUSH=true`. Every image in the matrix is built
      and pushed as `ghcr.io/<owner>/lakehouse-<name>:v3.0.0-beta.1` (plus `sha-<commit>`).
- [ ] The packages are public (GHCR → package settings → visibility) if they should be.
      A new package is private by default.

## 4. GitHub pre-release

```bash
gh release create v3.0.0-beta.1 --prerelease --verify-tag \
  --title "Lakehouse Lab v3.0.0-beta.1" \
  --notes-file v3/RELEASE_NOTES_v3.0.0-beta.1.md
```

- [ ] Remove the "Draft" note at the top of the notes file in the release text (or edit it
      out before running the command). Tick **pre-release**, not "latest".
- [ ] The README badge shows the pre-release.

## 5. Post-merge smoke

- [ ] **One-liner from `main`**, on a clean test machine or a spare directory and project
      on `<lab-host>`:
      `curl -fsSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --dir <fresh dir> --project-name <test project> --https-port <port> --http-port <port> --seed-test-users --non-interactive`,
      then `v3/lab test` passes. Remove it afterwards with `v3/lab reset --all --yes`.
- [ ] **The pinned tag works:** the same command with `--ref v3.0.0-beta.1` clones the tag.
- [ ] **V2 protection:** run the one-liner in a copy of a V2 checkout (no running stack
      needed); it refuses and prints the `v2.1.1-final` instructions.
- [ ] **Scheduled nightly:** the next day, `v3-nightly` ran from its schedule on `main` and
      passed (`gh run list --workflow v3-nightly.yml --branch main`).
- [ ] **Existing test lab:** `git pull` of `main` on the long-running test lab, then
      `v3/install.sh --non-interactive` and `v3/lab test` pass (upgrade in place from the
      branch to the release).

## 6. After the release

- [ ] Announce: the README, the release, and the V2 pointer (legacy/README.md).
- [ ] Keep `v3` as a branch for work in flight, or delete it once nothing points at it.
      The workflows trigger on both `main` and `v3`.
- [ ] Record the release in the memory graph (a Decision node for the cutover, in
      `core/`). Refresh the file anchors that moved to `legacy/v2/`
      (`core/scripts/auto_map.sh`, `core/scripts/stale_check.sh`).
