"""Criterion 3a: every client imports and reports the pinned version (expected via env)."""
import importlib
import importlib.metadata as md
import os
import sys

# (distribution, import name, env var holding the pin)
CHECKS = [
    ("jupyterhub", "jupyterhub", "JUPYTERHUB_VERSION"),
    ("jupyterlab", "jupyterlab", "JUPYTERLAB_VERSION"),
    ("jupysql", "sql", "JUPYSQL_VERSION"),
    ("jupyterlab-git", "jupyterlab_git", "JUPYTERLAB_GIT_VERSION"),
    ("jupyter-server-proxy", "jupyter_server_proxy", "JUPYTER_SERVER_PROXY_VERSION"),
    ("jupyter-ai", "jupyter_ai", "JUPYTER_AI_VERSION"),
    ("pyspark-client", "pyspark.sql.connect.session", "PYSPARK_VERSION"),
    ("duckdb", "duckdb", "DUCKDB_VERSION"),
    ("pyiceberg", "pyiceberg.catalog", "PYICEBERG_VERSION"),
    ("trino", "trino.dbapi", "TRINO_PYTHON_VERSION"),
    ("dbt-core", "dbt.cli.main", "DBT_CORE_VERSION"),
    ("dbt-trino", "dbt.adapters.trino", "DBT_TRINO_VERSION"),
]

bad = 0
for dist, mod, var in CHECKS:
    want = os.environ[var]
    try:
        importlib.import_module(mod)
        got = md.version(dist)
        ok = got == want
    except Exception as e:  # noqa: BLE001
        got, ok = f"IMPORT FAILED: {e!r}", False
    bad += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {dist:22s} import {mod:30s} {got} (pin {want})")

import pyspark  # noqa: E402
print(f"      pyspark.__version__ = {pyspark.__version__}")
sys.exit(1 if bad else 0)
