"""Lakehouse Lab workspace helpers.

    from lakehouse import lab_token, trino_connection, catalog, duckdb_connect, spark

lab_token() is the one place a token comes from; the helpers only wire it into each client.
Imports of the heavy client libraries happen inside the helpers, so `import lakehouse` is cheap.
"""
from .clients import (attach_lakehouse, catalog, duckdb_connect, spark, sql_engine,
                      trino_connection, whoami)
from .token import LabTokenError, lab_token, token_claims

__all__ = [
    "LabTokenError", "attach_lakehouse", "catalog", "duckdb_connect", "lab_token", "spark",
    "sql_engine", "token_claims", "trino_connection", "whoami",
]
