#!/usr/bin/env python3
"""A4 checkpoint: your Superset dashboard over your A3 model shows the right numbers.

Checks OUTCOMES in Superset, through its API AS YOU (your own login token; Superset sees
the same user as your browser, so it finds YOUR objects and runs the charts' queries in
Trino as you):
  * a dataset on lakehouse.dbt_<you>.segment_revenue that you own;
  * your chart "A4 Revenue by segment" on it, whose saved query returns one row per
    market segment with the right net revenue (the reference is computed from
    lakehouse.samples now);
  * your chart "A4 Revenue by year" on it, with rows;
  * your dashboard "A4 Segment revenue" with both charts on it.

  python3 checkpoint.py [--json]    check        python3 checkpoint.py --reset    start over

`--reset` deletes only these objects that YOU own in Superset (both charts, the dashboard
and your dataset on segment_revenue). Your table segment_revenue is A3's and stays.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_shared"))
import trackkit as tk  # noqa: E402
from superset_api import NotLoggedIn, Superset, SupersetError  # noqa: E402

TABLE = "segment_revenue"
DASHBOARD = "A4 Segment revenue"
BAR = "A4 Revenue by segment"
LINE = "A4 Revenue by year"
REFERENCE = """
WITH lines AS (
    SELECT orderkey, sum(extendedprice * (1 - discount)) AS net
    FROM lakehouse.samples.lineitem GROUP BY orderkey)
SELECT c.mktsegment, sum(l.net)
FROM lakehouse.samples.orders o
JOIN lines l ON o.orderkey = l.orderkey
JOIN lakehouse.samples.customer c ON o.custkey = c.custkey
GROUP BY 1
"""


def _numbers(row, skip):
    return [v for k, v in row.items() if k not in skip and isinstance(v, (int, float))
            and not isinstance(v, bool)]


def checks(ck):
    schema = tk.user_schema()
    if not ck.check(f"your A3 table lakehouse.{schema}.{TABLE} exists",
                    tk.table_type(schema, TABLE) is not None,
                    f"no {TABLE} in {schema}",
                    "A4 builds on A3: finish A3 first (lab-tracks check A3)"):
        return
    ss = Superset()
    try:
        uid = ss.my_id()
    except NotLoggedIn as e:
        ck.check("Superset knows you", False, str(e),
                 f"open {ss.base}/ in your browser, log in once, then run the check again")
        return
    datasets = ss.my_datasets(schema, TABLE, uid)
    if not ck.check(f"you have a dataset on {schema}.{TABLE}", bool(datasets),
                    "none of your Superset datasets points at that table",
                    f"step 2: Datasets > + Dataset > database Lakehouse (Trino), schema "
                    f"{schema}, table {TABLE}"):
        return
    ds_ids = {d["id"] for d in datasets}

    def my_chart(name, step):
        mine = ss.owned("chart", "slice_name", name, uid)
        if not ck.check(f'your chart "{name}" exists', bool(mine),
                        "no chart of yours has exactly that name",
                        f"step {step}: save the chart with the name {name} (spelling and "
                        "capitals count)"):
            return None
        on_ds = [c for c in mine if c.get("datasource_id") in ds_ids]
        if not ck.check(f'"{name}" uses your {TABLE} dataset', bool(on_ds),
                        f"it uses another dataset ({mine[0].get('datasource_name_text') or '?'})",
                        f"in the chart, change the dataset to {schema}.{TABLE}"):
            return None
        return on_ds[0]

    bar = my_chart(BAR, 3)
    if bar:
        rows = ss.chart_data(bar["id"])
        _, ref = tk.query(REFERENCE)
        want = {r[0]: float(r[1]) for r in ref}
        got = {}
        for r in rows:
            seg = r.get("market_segment")
            nums = _numbers(r, {"market_segment"})
            if seg is not None and len(nums) == 1:
                got[seg] = float(nums[0])
        if ck.check(f'"{BAR}" shows one bar per market segment ({len(want)})',
                    set(got) == set(want) and len(rows) == len(want),
                    f"its query returned {len(rows)} rows: "
                    f"{[{k: v for k, v in r.items()} for r in rows[:3]]}",
                    "X-axis: market_segment; one metric: SUM(net_revenue); no filters, "
                    "no dimensions, row limit 10 or more"):
            wrong = [s for s in want if not tk.close_enough(got[s], want[s], 0.005)]
            ck.check(f'"{BAR}" shows the total net revenue per segment', not wrong,
                     f"values differ for {', '.join(wrong)}",
                     "the metric must be SUM of net_revenue (not COUNT, not AVG), with no "
                     "filter on order_year")
    line = my_chart(LINE, 4)
    if line:
        rows = ss.chart_data(line["id"])
        ck.check(f'"{LINE}" returns data', len(rows) > 0, "its query returned no rows",
                 "X-axis: order_year; metric SUM(net_revenue); Dimensions: market_segment")
    dash = ss.owned("dashboard", "dashboard_title", DASHBOARD, uid)
    if not ck.check(f'your dashboard "{DASHBOARD}" exists', bool(dash),
                    "no dashboard of yours has exactly that title",
                    f"step 5: Dashboards > + Dashboard, title {DASHBOARD}"):
        return
    on_dash = {c.get("id") for d in dash for c in ss.dashboard_charts(d["id"])}
    missing = [n for n, c in ((BAR, bar), (LINE, line)) if not c or c["id"] not in on_dash]
    ck.check(f'both charts are on "{DASHBOARD}"', not missing,
             f"not on it: {', '.join(missing)}",
             "edit the dashboard, drag the charts from the right-hand list onto it, then Save")


def reset():
    """Delete this module's Superset objects that YOU own (charts first: a dataset that
    still has charts cannot be deleted)."""
    schema = tk.user_schema()
    ss = Superset()
    try:
        uid = ss.my_id()
    except NotLoggedIn:
        return []                     # Superset never saw you: you own nothing there
    removed = []
    for d in ss.owned("dashboard", "dashboard_title", DASHBOARD, uid):
        ss.delete("dashboard", d["id"])
        removed.append(f"dashboard {DASHBOARD!r}")
    for name in (BAR, LINE):
        for c in ss.owned("chart", "slice_name", name, uid):
            ss.delete("chart", c["id"])
            removed.append(f"chart {name!r}")
    for d in ss.my_datasets(schema, TABLE, uid):
        try:
            ss.delete("dataset", d["id"])
            removed.append(f"dataset {schema}.{TABLE}")
        except SupersetError:         # other charts of yours still use it: keep it
            print(f"  kept your dataset {schema}.{TABLE}: other charts of yours use it")
    return removed


if __name__ == "__main__":
    sys.exit(tk.Checkpoint("A4", "a chart and a dashboard in Superset").run(checks, reset))
