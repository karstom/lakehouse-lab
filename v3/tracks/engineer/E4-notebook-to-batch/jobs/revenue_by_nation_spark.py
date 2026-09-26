"""Spark batch job for E4: revenue by nation, as the batch identity lab-batch (ADR-017).

Airflow does not parse this file (it is in a `jobs/` folder). Your DAG starts it as a separate
program in the lab's jobs environment:

    revenue_by_nation_spark.py TABLE DAG_ID RUN_ID

Why a batch job gets a CREDENTIAL, not a token: an access token lives for minutes. Your
notebook's Spark session carries YOUR token and stops working when it expires (you open a
new session with spark()). A scheduled job may run for hours with nobody around, so its
session gets the lab-batch client credential instead, and Spark's Iceberg client fetches and
renews its own tokens for as long as the job runs. The credential reaches this program only
through its environment (the DAG passes it), and Spark hides it in its UI and logs.
"""
import os
import re
import sys

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

import lab_batch  # the lab's helpers (on PYTHONPATH for jobs started by lab_batch.job_env)

TABLE_RE = re.compile(r"^lakehouse\.analytics\.u_[a-z0-9_]+$")


def batch_session(app_name):
    """A Spark Connect session as lab-batch, with a self-renewing credential."""
    client = lab_batch.client_id()
    remote = os.environ.get("LAB_SPARK_REMOTE", "sc://spark-connect:15002").rstrip("/")
    return (SparkSession.builder.remote(f"{remote}/;user_id={client}")
            .appName(app_name)
            .config("spark.sql.catalog.lakehouse.credential",
                    f"{client}:{os.environ['OIDC_CLIENT_SECRET_BATCH']}")
            .config("spark.sql.catalog.lakehouse.scope", "openid")
            .config("spark.sql.catalog.lakehouse.token-refresh-enabled", "true")
            .config("spark.sql.catalog.lakehouse.token-exchange-enabled", "false")
            .create())


def revenue_by_nation(s):
    """The notebook's SQL, written with the DataFrame API."""
    orders = s.table("lakehouse.samples.orders").select("custkey", "totalprice")
    customers = s.table("lakehouse.samples.customer").select("custkey", "nationkey")
    nations = s.table("lakehouse.samples.nation").select("nationkey", F.col("name").alias("nation"))
    joined = orders.join(customers, "custkey").join(nations, "nationkey")
    # TODO: group `joined` by nation, with two columns like the notebook's query:
    #   orders  = the number of orders            (F.count("*"))
    #   revenue = the sum of totalprice, rounded to 2 decimals   (F.round(F.sum(...), 2))
    result = joined
    return result


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    table, dag_id, run_id = sys.argv[1:4]
    if not TABLE_RE.match(table):
        sys.exit(f"table must be lakehouse.analytics.u_<you>_<name>, got {table!r}")
    _, claims = lab_batch.batch_token()          # only to record who wrote the rows
    s = batch_session(f"{dag_id} {run_id}")
    try:
        out = (revenue_by_nation(s)
               .withColumn("run_id", F.lit(run_id))
               .withColumn("dag_id", F.lit(dag_id))
               .withColumn("engine", F.lit("spark (batch job)"))
               .withColumn("written_by", F.lit(lab_batch.principal(claims)))
               .withColumn("computed_at", F.current_timestamp()))
        out.writeTo(table).using("iceberg").createOrReplace()   # one atomic commit
        n = s.table(table).count()
        print(f"[spark-job] wrote {table}: {n} rows, run {run_id}", flush=True)
        if n != 25:
            sys.exit(f"expected 25 nations, got {n}")
    finally:
        s.stop()


if __name__ == "__main__":
    main()
