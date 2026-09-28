# Legacy: Lakehouse Lab V2

[`v2/`](v2/) holds the Lakehouse Lab **V2** code and docs (last release 2.1.1), moved here
unchanged when V3 was merged to `main` (`v3.0.0-beta.1`). It is kept for reference and
is **no longer developed**. V2's CI workflows are in [`v2/workflows/`](v2/workflows/),
where GitHub does not run them.

## If you run V2 today

Your install keeps working. Pin it to the last V2 commit so that a `git pull` does not
replace its files with V3:

```bash
cd ~/lakehouse-lab            # your V2 directory
git fetch --tags
git checkout v2.1.1-final
```

To install V2 somewhere new (not recommended; see below), use the V2 installer from that
tag:

```bash
curl -fsSL https://raw.githubusercontent.com/karstom/lakehouse-lab/v2.1.1-final/install.sh | bash -s -- --branch v2.1.1-final
```

**Do not run V2 from this `legacy/v2/` directory.** V2's scripts derive Docker volume names
from the name of the directory they run in, so here they would not match your install's
volumes (at best V2 fails to start; at worst it starts on new, empty volumes).

## Why move to V3

V2's object store, MinIO Community Edition, gets no more security fixes, and Spark, Airflow
and Superset in V2 are a major version behind. V3 replaces them and adds single sign-on,
a real Iceberg catalog, per-user workspaces and learning tracks. The
[migration guide](../docs/MIGRATION.md) moves your data across; V2 is only read, never
changed, so you can keep it until you are satisfied.
