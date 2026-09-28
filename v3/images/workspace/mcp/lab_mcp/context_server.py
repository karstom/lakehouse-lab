"""`lab-context`: what the assistant needs to know about THIS lab, as the logged-in user.

Tools: superset_dashboard_datasets, table_last_snapshot, airflow_runs, catalog_list,
current_lesson. All read-only; each call uses the user's own fresh token.
"""
from mcp.server.fastmcp import FastMCP

from . import context
from .common import UNTRUSTED_NOTE, run_tool

mcp = FastMCP(
    "lab-context",
    instructions=(
        "Context about the user's lab, fetched as the user (you only see what they may see): "
        "which tables feed a Superset dashboard, when an Iceberg table last changed, recent "
        "Airflow runs, the catalog's namespaces and tables, and the learning-track module "
        "the user is working on (with its tutor notes: explain and hint, never hand over "
        "the solution). " + UNTRUSTED_NOTE))


@mcp.tool(structured_output=False)
def superset_dashboard_datasets(dashboard: str) -> str:
    """The datasets behind a Superset dashboard (title, slug or id) and the table each one
    reads, e.g. 'Revenue by region'. Use dbt lineage to go further upstream."""
    return run_tool(context.superset_dashboard_datasets, dashboard)


@mcp.tool(structured_output=False)
def table_last_snapshot(table: str) -> str:
    """When an Iceberg table last changed (loaded): its newest snapshot's commit time,
    operation and record counts. table = 'schema.table' or 'lakehouse.schema.table'."""
    return run_tool(context.table_last_snapshot, table)


@mcp.tool(structured_output=False)
def airflow_runs(dag_id: str | None = None, limit: int = 10, state: str | None = None) -> str:
    """Recent Airflow DAG runs (newest first) for one DAG or all DAGs the user may see.
    state: queued | running | success | failed."""
    return run_tool(context.airflow_runs, dag_id, limit, state)


@mcp.tool(structured_output=False)
def catalog_list(namespace: str | None = None) -> str:
    """The lab catalog (Iceberg, Lakekeeper): without namespace, the namespaces the user can
    see; with one (e.g. 'analytics'), its tables and views."""
    return run_tool(context.catalog_list, namespace)


@mcp.tool(structured_output=False)
def current_lesson(module: str | None = None) -> str:
    """The learning-track module the user is working on (or `module`, e.g. 'A1'), their
    progress, and the module's tutor notes (tutor.md) for tutor mode."""
    return run_tool(context.current_lesson, module)


def main():
    mcp.run("stdio")


if __name__ == "__main__":
    main()
