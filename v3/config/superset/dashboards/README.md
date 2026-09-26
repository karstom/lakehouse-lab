# Bundled Superset content: "Revenue by region"

A Superset v1 export (`GET /api/v1/dashboard/export/`), imported by `../lab_init.py` at every
Superset start. It reads only the shared `lakehouse.analytics` tables that `lab_dbt_build` writes
(`fct_orders`, `dim_customers`, `revenue_by_region`; CONTRACT Phase 3).

- The database's `sqlalchemy_uri` here is a placeholder. `lab_init.py` replaces it with the lab's
  Trino (`trino.` next to `LAB_AUTH_URL`), and the connection always runs as the logged-in user
  (`../lab_trino.py`). Never commit a real host name here.
- Datasets, charts and the dashboard are created only when missing (matched by `uuid`), so edits
  made in the UI survive restarts. To ship a changed dashboard, give changed objects new UUIDs,
  or delete them in the UI before restarting Superset.
- To edit: change the dashboard in Superset, export it from the dashboard list, unzip it here
  (drop the numeric file-name suffixes), and restore the placeholder URI. Chart positions must keep
  `meta.uuid`, or the import cannot map them to charts.
