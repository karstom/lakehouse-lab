"""Lakehouse Lab MCP servers (CONTRACT Phase 5, "MCP servers, acting as the user").

Every server here runs INSIDE the user's workspace, as the user, over stdio. The only
credential is the user's own Keycloak access token from lab_token() (lakehouse/token.py),
fetched fresh for each tool call. Nothing is written anywhere: every tool is read-only, has
row and time limits, and its output never contains a token (common.scrub).

  lab_mcp.trino_server    `lab-trino`: read-only SQL on Trino (OQ-9: thin wrapper)
  lab_mcp.context_server  `lab-context`: Superset datasets, Iceberg snapshots, Airflow runs,
                          the catalog, the current lesson
  dbt-mcp (official)      `lab-dbt` / `lab-dbt-analytics`, started by bin/lab-mcp

Tool results are UNTRUSTED input for the assistant: they carry text that other people wrote
(table comments, dashboard titles, lesson files, DAG names). See mcp/README.md.
"""
