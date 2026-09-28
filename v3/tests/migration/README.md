# Migration guide test

Proves the commands in [`docs/MIGRATION.md`](../../../docs/MIGRATION.md) (V2 → V3) against
a **throwaway V2**: a MinIO container running the same release V2 ships, and a Postgres,
both filled with synthetic data. They copy into the V3 install that this folder belongs to.
It never touches a real V2. Every object it creates is named `<COMPOSE_PROJECT_NAME>-v2src*`
and labelled `lab.test=migration`. It refuses to run for a project named like V2's
(`lakehouse-lab`).

```bash
v3/install.sh --seed-test-users --profile engineer   # or core: then the Spark part is skipped
v3/tests/migration/run.sh all                        # about 4 minutes; exit 0 = every step passed
```

`all` runs these steps in order. Each step also runs on its own (`run.sh <step>`), and each
writes `out/<step>.log` (`out/` is git-ignored, mode 700).

| Step | What it does | Guide section |
|---|---|---|
| `source-up` | Starts MinIO (network alias `minio`) and Postgres on network `<project>-v2src`, which stands in for V2's `lakehouse-lab_lakehouse` | — |
| `seed` | Runs `make_data.py` in the workspace image, uploads the result with rclone. A 150 MiB object goes up through MinIO's own `mc` (multipart, no MD5). Adds a Console-style empty folder, V2-style notebook and DAG volumes, and a Postgres table | — |
| `copy` | Writes the credentials file, then `rc lsd`, `rc size`, `rc mkdir v3:landing` and the copy loop; runs the loop again to show it resumes | 1–3 |
| `verify` | `rc size --json` on both sides, `rc check --one-way`, `check --download` for the large files, and the special-character key listing | 4 |
| `reader` | Creates the `landing-reader` identity (keys on stdin) | 5 |
| `postgres` | `pg_dump -Fc`, then one table streamed as CSV into `landing` with `rclone rcat` | Optional: Postgres |
| `login` | Logs alice in once in a headless browser, so JupyterHub creates her home volume | — |
| `files` | Copies the notebook and DAG volumes read-only into `~/migrated-from-v2/` as 1000:100 | Optional: notebooks and DAGs |
| `load` | Logs alice in (headless browser, `tests/smoke/workspace.py`) and runs `load_kernel.py` in her own workspace kernel. That file holds the guide's notebook cells: Spark as in E1, Trino with PyIceberg, a Trino check against the source sums, and the limits of the landing key. It also checks that alice owns the copied files | 6 |
| `reader-delete` | Removes the identity, then checks that its key gets a 403 | 7 |
| `source-down` | Removes the throwaway V2 (containers, volumes, network) and the generated data | — |

In `run.sh`, the lines marked `# guide:` are the guide's commands. Only the names differ:
`V2_ENV`, `V2_NET`, `V3_NET`, `~/lab-migration` (here `out/lab-migration`), and the
`lakehouse-…` container and volume names (here `<project>-…`). Pins come from
`versions.env` (`RCLONE_IMAGE_*`, `MIGRATION_TEST_MINIO_IMAGE_*`, `POSTGRES_VERSION`).

Files:

- `make_data.py`: the synthetic content, with its expected row counts and sums (`out/data/expected.json`).
- `load_kernel.py`: the guide's notebook cells plus checks. It runs inside the workspace.
- `load_driver.py`: the browser login and kernel run, inside the `smoke` container.
- `in-smoke.sh`: trusts the lab CA the way `tests/smoke/in-container.sh` does.

Results of the proof runs: [EVIDENCE.md](EVIDENCE.md).
