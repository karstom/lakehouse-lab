#!/usr/bin/env python3
"""Reference solution for A3 (test-only; never copied into homes). Runs inside the user's
workspace, as the user: exactly the lesson's steps.

  1. copy the starter dbt project into the module folder as dbt_project/ (step 1);
  2. add models/marts/segment_revenue.sql and its .yml with tests and docs (steps 3-6);
  3. `dbt build --select +segment_revenue` (the model, everything it needs, and the tests).
Safe to run twice.

  python solve.py [<module dir>]
"""
import os
import shutil
import subprocess
import sys

MODULE_DIR = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.getcwd())
PROJECT = os.path.join(MODULE_DIR, "dbt_project")
STARTER = "/opt/lakehouse/starter/dbt_lakehouse"

MODEL_SQL = """\
-- segment_revenue: net revenue per customer market segment and order year.
select
    c.market_segment,
    year(o.order_date)            as order_year,
    count(*)                      as orders,
    count(distinct o.customer_id) as customers,
    round(sum(o.net_revenue), 2)  as net_revenue
from {{ ref('fct_orders') }} o
join {{ ref('dim_customers') }} c on o.customer_id = c.customer_id
group by 1, 2
"""

MODEL_YML = """\
version: 2

models:
  - name: segment_revenue
    description: One row per customer market segment and order year, with the number of orders and customers and their net revenue.
    config:
      persist_docs:
        relation: true
        columns: true
    columns:
      - name: market_segment
        description: The customer's market segment, from lakehouse.samples.customer.
        data_tests:
          - not_null
          - accepted_values:
              arguments:
                values: [AUTOMOBILE, BUILDING, FURNITURE, HOUSEHOLD, MACHINERY]
      - name: order_year
        description: The year the order was placed.
        data_tests:
          - not_null
      - name: net_revenue
        description: Sum of the orders' net revenue (price minus discount), rounded to cents.
"""


def main():
    if not os.path.isfile(os.path.join(PROJECT, "dbt_project.yml")):
        shutil.copytree(STARTER, PROJECT, dirs_exist_ok=True)
    marts = os.path.join(PROJECT, "models", "marts")
    for name, text in (("segment_revenue.sql", MODEL_SQL), ("segment_revenue.yml", MODEL_YML)):
        with open(os.path.join(marts, name), "w", encoding="utf-8") as f:
            f.write(text)
    r = subprocess.run(["dbt", "build", "--select", "+segment_revenue", "--no-use-colors"],
                       cwd=PROJECT, capture_output=True, text=True, timeout=900)
    print(r.stdout[-3000:], r.stderr[-2000:])
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
