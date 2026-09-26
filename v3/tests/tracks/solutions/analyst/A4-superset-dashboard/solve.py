#!/usr/bin/env python3
"""Reference solution for A4 (test-only; never copied into homes). Runs inside the user's
workspace, as the user, after the user logged in to Superset once in the browser
(module.json solution.browser_logins).

What a learner does in the Superset UI, through the same REST API the UI uses:
  1. (A3's result, made here so this works from a fresh home) the table
     lakehouse.dbt_<you>.segment_revenue, built with the same SQL as A3's model;
  2. a dataset on it; 3. the charts "A4 Revenue by segment" (bar) and "A4 Revenue by
  year" (line, one line per segment); 4. the dashboard "A4 Segment revenue" with both.
Safe to run twice: existing objects of the user's with these names are reused.

  python solve.py [<module dir>]
"""
import json
import os
import sys

MODULE_DIR = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.getcwd())
sys.path.insert(0, os.path.join(os.path.dirname(MODULE_DIR), "_shared"))
import trackkit as tk  # noqa: E402
from superset_api import Superset  # noqa: E402

DASHBOARD = "A4 Segment revenue"
BAR = "A4 Revenue by segment"
LINE = "A4 Revenue by year"
TABLE = "segment_revenue"
A3_SQL = """
CREATE TABLE IF NOT EXISTS lakehouse.{schema}.segment_revenue AS
WITH lines AS (
    SELECT orderkey, sum(extendedprice * (1 - discount)) AS net
    FROM lakehouse.samples.lineitem GROUP BY orderkey)
SELECT c.mktsegment AS market_segment, year(o.orderdate) AS order_year, count(*) AS orders,
       count(DISTINCT o.custkey) AS customers, round(sum(l.net), 2) AS net_revenue
FROM lakehouse.samples.orders o
JOIN lines l ON o.orderkey = l.orderkey
JOIN lakehouse.samples.customer c ON o.custkey = c.custkey
GROUP BY 1, 2
"""
METRIC = {"expressionType": "SIMPLE", "column": {"column_name": "net_revenue"},
          "aggregate": "SUM", "label": "Net revenue"}


def ensure_table(schema):
    tk.query(f"CREATE SCHEMA IF NOT EXISTS lakehouse.{schema}")
    tk.query(A3_SQL.format(schema=schema))


def database_id(ss):
    for d in ss.list("database", []):
        if d.get("backend") == "trino" or "Trino" in (d.get("database_name") or ""):
            return d["id"]
    raise SystemExit("no Trino database in Superset")


def ensure_dataset(ss, uid, schema):
    mine = ss.my_datasets(schema, TABLE, uid)
    if mine:
        return mine[0]["id"]
    r = ss.api("POST", "/dataset/", {"database": database_id(ss), "catalog": "lakehouse",
                                     "schema": schema, "table_name": TABLE})
    return r["id"]


def chart_body(name, viz, ds_id, form, query):
    form = dict(form, viz_type=viz, datasource=f"{ds_id}__table")
    qc = {"datasource": {"id": ds_id, "type": "table"}, "force": False, "form_data": form,
          "queries": [query], "result_format": "json", "result_type": "full"}
    return {"slice_name": name, "viz_type": viz, "datasource_id": ds_id,
            "datasource_type": "table", "params": json.dumps(form), "query_context": json.dumps(qc)}


def bar(ds_id):
    form = {"x_axis": "market_segment", "metrics": [METRIC], "groupby": [], "row_limit": 100,
            "orientation": "vertical", "x_axis_sort": "Net revenue", "x_axis_sort_asc": False,
            "show_legend": False, "y_axis_format": "SMART_NUMBER", "adhoc_filters": []}
    query = {"columns": ["market_segment"], "metrics": [METRIC], "filters": [],
             "orderby": [[METRIC, False]], "row_limit": 100, "extras": {"having": "", "where": ""}}
    return chart_body(BAR, "echarts_timeseries_bar", ds_id, form, query)


def line(ds_id):
    form = {"x_axis": "order_year", "metrics": [METRIC], "groupby": ["market_segment"],
            "row_limit": 1000, "show_legend": True, "y_axis_format": "SMART_NUMBER",
            "adhoc_filters": [], "x_axis_sort_asc": True}
    query = {"columns": ["order_year", "market_segment"], "metrics": [METRIC], "filters": [],
             "orderby": [[METRIC, False]], "row_limit": 1000, "extras": {"having": "", "where": ""},
             "series_columns": ["market_segment"]}
    return chart_body(LINE, "echarts_timeseries_line", ds_id, form, query)


def position(chart_ids):
    pos = {"DASHBOARD_VERSION_KEY": "v2",
           "ROOT_ID": {"id": "ROOT_ID", "type": "ROOT", "children": ["GRID_ID"]},
           "GRID_ID": {"id": "GRID_ID", "type": "GRID", "children": ["ROW-a4"],
                       "parents": ["ROOT_ID"]},
           "ROW-a4": {"id": "ROW-a4", "type": "ROW", "children": [],
                      "parents": ["ROOT_ID", "GRID_ID"], "meta": {"background": "BACKGROUND_TRANSPARENT"}}}
    for cid, name in chart_ids:
        key = f"CHART-a4-{cid}"
        pos["ROW-a4"]["children"].append(key)
        pos[key] = {"id": key, "type": "CHART", "children": [],
                    "parents": ["ROOT_ID", "GRID_ID", "ROW-a4"],
                    "meta": {"chartId": cid, "width": 6, "height": 50, "sliceName": name}}
    return json.dumps(pos)


def main():
    schema = tk.user_schema()
    ensure_table(schema)
    ss = Superset()
    uid = ss.my_id()
    ds_id = ensure_dataset(ss, uid, schema)
    dash = ss.owned("dashboard", "dashboard_title", DASHBOARD, uid)
    dash_id = dash[0]["id"] if dash else ss.api(
        "POST", "/dashboard/", {"dashboard_title": DASHBOARD, "published": True})["id"]
    charts = []
    for name, body in ((BAR, bar(ds_id)), (LINE, line(ds_id))):
        body["dashboards"] = [dash_id]
        mine = ss.owned("chart", "slice_name", name, uid)
        if mine:
            cid = mine[0]["id"]
            ss.api("PUT", f"/chart/{cid}", body)
        else:
            cid = ss.api("POST", "/chart/", body)["id"]
        charts.append((cid, name))
    ss.api("PUT", f"/dashboard/{dash_id}", {"position_json": position(charts)})
    print(f"dataset {ds_id}, charts {charts}, dashboard {dash_id}")
    for cid, name in charts:
        print(name, ss.chart_data(cid)[:3])


if __name__ == "__main__":
    main()
