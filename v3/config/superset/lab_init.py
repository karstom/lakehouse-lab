"""Idempotent Superset setup, run by start.sh after `superset init` and before the server.

1. Role `lab_data` (superset_config.LAB_DATA_ROLE): lets the Gamma-based roles open datasets
   and databases. What a person can actually read is still decided by Trino, which runs every
   query as that person (lab_trino.py).
2. The bundled dashboard "Revenue by region" (dashboards/: a Superset v1 export over
   lakehouse.analytics.{fct_orders,dim_customers,revenue_by_region}), imported with no user
   session, like Superset's own example loader (ignore_permissions):
   * the database connection is created or refreshed on every run (its URI follows
     LAB_DOMAIN/LAB_HTTPS_PORT through LAB_AUTH_URL);
   * datasets, charts and the dashboard are created only when missing (matched by UUID), so
     edits made in the UI survive restarts and a second run changes nothing.
"""
import os
import sys
import time
from pathlib import Path

import yaml

BUNDLE = Path(os.environ.get("LAB_SUPERSET_BUNDLE", "/app/lakehouse/dashboards"))


def load_bundle(root):
    """{relative path: parsed YAML} for every YAML file in an export directory."""
    out = {}
    for p in sorted(root.rglob("*.yaml")):
        rel = p.relative_to(root).as_posix()
        with p.open() as f:
            out[rel] = yaml.safe_load(f)
    return out


def ensure_data_role(sm, name):
    changed = False
    role = sm.find_role(name)
    if role is None:
        role = sm.add_role(name)
        changed = True
    for perm in ("all_datasource_access", "all_database_access"):
        pv = sm.find_permission_view_menu(perm, perm)
        if pv is None:
            sm.add_permission_view_menu(perm, perm)
            pv = sm.find_permission_view_menu(perm, perm)
        if pv not in role.permissions:
            sm.add_permission_role(role, pv)
            changed = True
    return changed


def import_bundle(configs, trino_uri):
    # pylint: disable=import-outside-toplevel
    from superset import db
    from superset.charts.schemas import ImportV1ChartSchema
    from superset.commands.chart.importers.v1.utils import import_chart
    from superset.commands.dashboard.importers.v1.utils import (
        find_chart_uuids, import_dashboard, update_id_refs)
    from superset.commands.database.importers.v1.utils import import_database
    from superset.commands.dataset.importers.v1.utils import import_dataset
    from superset.commands.utils import update_chart_config_dataset
    from superset.dashboards.schemas import ImportV1DashboardSchema
    from superset.databases.schemas import ImportV1DatabaseSchema
    from superset.datasets.schemas import ImportV1DatasetSchema
    from superset.models.dashboard import Dashboard, dashboard_slices
    from superset.models.slice import Slice
    from superset.connectors.sqla.models import SqlaTable

    def of(prefix, schema):
        return {k: schema.load(v) for k, v in configs.items() if k.startswith(prefix)}

    report = []
    database_ids = {}
    for cfg in of("databases/", ImportV1DatabaseSchema()).values():
        cfg["sqlalchemy_uri"] = trino_uri
        database = import_database(cfg, overwrite=True, ignore_permissions=True)
        database_ids[str(database.uuid)] = database.id

    dataset_info = {}
    for cfg in of("datasets/", ImportV1DatasetSchema()).values():
        new = not db.session.query(SqlaTable).filter_by(uuid=cfg["uuid"]).first()
        cfg["database_id"] = database_ids[str(cfg["database_uuid"])]
        ds = import_dataset(cfg, overwrite=False, ignore_permissions=True)
        dataset_info[str(ds.uuid)] = {"datasource_id": ds.id, "datasource_type": ds.datasource_type,
                                      "datasource_name": ds.table_name}
        if new:
            report.append(f"dataset {ds.schema}.{ds.table_name}")

    chart_ids = {}
    for cfg in of("charts/", ImportV1ChartSchema()).values():
        new = not db.session.query(Slice).filter_by(uuid=cfg["uuid"]).first()
        cfg = update_chart_config_dataset(cfg, dataset_info[str(cfg["dataset_uuid"])])
        chart = import_chart(cfg, overwrite=False, ignore_permissions=True)
        chart_ids[str(chart.uuid)] = chart.id
        if new:
            report.append(f"chart {chart.slice_name!r}")

    for cfg in of("dashboards/", ImportV1DashboardSchema()).values():
        if db.session.query(Dashboard).filter_by(uuid=cfg["uuid"]).first():
            continue
        cfg = update_id_refs(cfg, chart_ids, dataset_info)
        dash = import_dashboard(cfg, overwrite=False, ignore_permissions=True)
        rows = [{"dashboard_id": dash.id, "slice_id": chart_ids[u]}
                for u in find_chart_uuids(cfg["position"]) if u in chart_ids]
        if rows:
            db.session.execute(dashboard_slices.insert(), rows)
        report.append(f"dashboard {dash.dashboard_title!r}")
    return report


def main():
    t0 = time.time()
    # pylint: disable=import-outside-toplevel
    from superset.app import create_app
    app = create_app()
    with app.app_context():
        from superset import db, security_manager
        import lab_trino
        role = app.config["LAB_DATA_ROLE"]
        role_changed = ensure_data_role(security_manager, role)
        host, port = lab_trino.trino_endpoint()
        uri = f"trino://{lab_trino.SERVICE_USER}@{host}:{port}/lakehouse"
        created = import_bundle(load_bundle(BUNDLE), uri)
        db.session.commit()
    print(f"[lab_init] role {role}: {'updated' if role_changed else 'unchanged'}; bundle: "
          f"{'created ' + ', '.join(created) if created else 'unchanged'} "
          f"({time.time() - t0:.1f}s)", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # fail the container start loudly (up --wait reports it)
        print(f"[lab_init] FAILED: {e!r}", file=sys.stderr, flush=True)
        raise
