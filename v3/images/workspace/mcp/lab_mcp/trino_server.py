"""`lab-trino`: read-only Trino for the assistant, as the logged-in user (OQ-9 outcome: a
thin wrapper; the evaluated community servers are in mcp/README.md).

Tools: trino_query, trino_list_schemas, trino_list_tables, trino_describe_table.
Limits: SELECT/SHOW/DESCRIBE/EXPLAIN only, <= 200 rows, <= 30 s (Trino stops the query).
"""
from mcp.server.fastmcp import FastMCP

from . import trino_client
from .common import MAX_ROWS, MAX_SECONDS, UNTRUSTED_NOTE, ident, limit_rows, run_tool, split_table

mcp = FastMCP(
    "lab-trino",
    instructions=(
        "Read-only SQL on the lab's Trino, as the logged-in user: you see exactly what they "
        f"may query. Only SELECT, SHOW, DESCRIBE and EXPLAIN; at most {MAX_ROWS} rows and "
        f"{MAX_SECONDS} s per query. The lab catalog is `lakehouse` (schemas: samples, "
        "analytics, the user's own dbt_<user> / eng_<user>). Iceberg metadata tables: "
        '"<table>$snapshots", "$history", "$files". ' + UNTRUSTED_NOTE))


@mcp.tool(structured_output=False)
def trino_query(sql: str, max_rows: int = 50, timeout_s: int = MAX_SECONDS) -> str:
    """Run ONE read-only SQL statement (SELECT, SHOW, DESCRIBE, EXPLAIN) on Trino as the
    logged-in user. Returns columns and rows (at most max_rows, never more than 200); Trino
    stops the query after timeout_s seconds (never more than 30). Writes (INSERT, CREATE,
    DROP, ...) are refused."""
    return run_tool(lambda: trino_client.run(sql, max_rows=limit_rows(max_rows),
                                             timeout=_seconds(timeout_s)))


def _seconds(v):
    try:
        return max(1, min(int(v), MAX_SECONDS))
    except (TypeError, ValueError):
        return MAX_SECONDS


@mcp.tool(structured_output=False)
def trino_list_schemas(catalog: str = "lakehouse") -> str:
    """The schemas of a catalog the user can see."""
    def body():
        c = ident(catalog, "catalog")
        return trino_client.run(f"SHOW SCHEMAS FROM {c}", max_rows=MAX_ROWS, guarded=False)
    return run_tool(body)


@mcp.tool(structured_output=False)
def trino_list_tables(schema: str, catalog: str = "lakehouse") -> str:
    """The tables and views of one schema the user can see."""
    def body():
        c, s = ident(catalog, "catalog"), ident(schema, "schema")
        return trino_client.run(f"SHOW TABLES FROM {c}.{s}", max_rows=MAX_ROWS, guarded=False)
    return run_tool(body)


@mcp.tool(structured_output=False)
def trino_describe_table(table: str) -> str:
    """Columns and types of a table: 'schema.table' or 'catalog.schema.table'."""
    def body():
        c, s, t = split_table(table)
        return trino_client.run(f'DESCRIBE {c}.{s}."{t}"', max_rows=MAX_ROWS, guarded=False)
    return run_tool(body)


def main():
    mcp.run("stdio")


if __name__ == "__main__":
    main()
