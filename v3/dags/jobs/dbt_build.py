"""lab_dbt_build job: `dbt build` of the starter project with target `analytics` into
lakehouse.analytics, as lab-batch (CONTRACT Phase 3 "analytics" schema), then check the tables
the bundled dashboard needs.

dbt-trino authenticates with the token in DBT_ENV_SECRET_LAB_TOKEN (profiles.yml in
config/airflow/dbt; dbt scrubs DBT_ENV_SECRET_* from its logs). The project is mounted
read-only, so dbt's target/ and logs/ go to a per-run temp dir.

Usage: dbt_build.py RUN_ID
"""
import os
import subprocess
import sys
import tempfile

from labjob import query, trino

REQUIRED = ("fct_orders", "dim_customers", "revenue_by_region")


def main():
    run_id = sys.argv[1]
    project = os.environ["LAB_DBT_PROJECT_DIR"]
    with tempfile.TemporaryDirectory(prefix="dbt-") as tmp:
        env = dict(os.environ, DBT_ENV_SECRET_LAB_TOKEN=os.environ["LAB_BATCH_TOKEN"],
                   DBT_TARGET_PATH=os.path.join(tmp, "target"),
                   DBT_LOG_PATH=os.path.join(tmp, "logs"))
        cmd = ["dbt", "build", "--target", "analytics", "--project-dir", project,
               "--profiles-dir", os.environ["DBT_PROFILES_DIR"], "--no-use-colors",
               "--vars", f"{{lab_run_id: '{run_id}'}}"]
        print("[dbt]", " ".join(cmd), flush=True)
        rc = subprocess.run(cmd, env=env).returncode
    if rc != 0:
        raise SystemExit(f"[dbt] dbt build failed (exit {rc})")
    cur = trino().cursor()
    have = {r[0] for r in query(cur, "SHOW TABLES FROM lakehouse.analytics")}
    missing = [t for t in REQUIRED if t not in have]
    if missing:
        raise SystemExit(f"[dbt] missing in lakehouse.analytics: {missing}")
    n = query(cur, "SELECT count(*) FROM lakehouse.analytics.revenue_by_region")[0][0]
    if not n:
        raise SystemExit("[dbt] lakehouse.analytics.revenue_by_region is empty")
    print(f"[dbt] lakehouse.analytics has {', '.join(REQUIRED)}; revenue_by_region: {n} rows")


if __name__ == "__main__":
    main()
