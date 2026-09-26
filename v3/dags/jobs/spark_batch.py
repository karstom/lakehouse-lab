"""lab_spark_batch job (ADR-017): a Spark job as the batch service identity `lab-batch`, on the
shared Spark Connect server, that may run far longer than one access token lives.

How it outlives its tokens: the session is given the client CREDENTIAL, not a token
(spark.sql.catalog.lakehouse.credential = lab-batch:<secret>, token refresh on, RFC 8693
token exchange off). The Iceberg REST client then fetches and renews its own tokens by client
credentials, on the driver for catalog calls and commits, and in the S3 remote signer on the
executors for every signed S3 request. Nothing renews a token for it.
(Interactive workspace sessions carry the user's token instead, which cannot be renewed:
that is why long work belongs here.)

The job reads lakehouse.samples.orders, then writes rows into TARGET (in lakehouse.analytics)
with a deliberate per-row delay so the write takes at least MIN_RUNTIME_S, and commits once
at the end. With lab-batch tokens cut to 120 s and MIN_RUNTIME_S >= 300, the data files are
signed and the commit is made with tokens fetched long after the first one expired.

Usage: spark_batch.py RUN_ID MIN_RUNTIME_S TARGET [--auth credential|static-token]
  --auth static-token is the negative control only (a fixed token, as a workspace session has
  it); the DAG always uses the credential.
"""
import argparse
import os
import re
import signal
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lab_batch import batch_token, client_id  # noqa: E402

TABLE_RE = re.compile(r"^lakehouse\.analytics\.[A-Za-z_][A-Za-z0-9_]*$")
RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.:+-]+$")
PARTITIONS = 2           # the worker offers 2 cores: both tasks run in parallel
MS_PER_ROW = 1000


def log(msg):
    print(f"[spark-batch {datetime.now(timezone.utc):%H:%M:%S}] {msg}", flush=True)


def session(auth):
    from pyspark.sql import SparkSession
    remote = os.environ.get("LAB_SPARK_REMOTE", "sc://spark-connect:15002").rstrip("/")
    b = SparkSession.builder.remote(f"{remote}/;user_id={client_id()}").appName("lab_spark_batch")
    if auth == "credential":
        b = (b.config("spark.sql.catalog.lakehouse.credential",
                      f"{client_id()}:{os.environ['OIDC_CLIENT_SECRET_BATCH']}")
              .config("spark.sql.catalog.lakehouse.scope", "openid")
              .config("spark.sql.catalog.lakehouse.token-refresh-enabled", "true")
              .config("spark.sql.catalog.lakehouse.token-exchange-enabled", "false"))
    else:  # negative control: a fixed token that nothing renews
        tok, _ = batch_token()
        b = b.config("spark.sql.catalog.lakehouse.token", tok)
    return b.create()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("min_runtime_s", type=int)
    ap.add_argument("target")
    ap.add_argument("--auth", choices=("credential", "static-token"), default="credential")
    a = ap.parse_args()
    if not TABLE_RE.match(a.target):
        raise SystemExit(f"target must be lakehouse.analytics.<name>, got {a.target!r}")
    if not RUN_ID_RE.match(a.run_id):  # it becomes a SQL string literal
        raise SystemExit(f"unexpected run id {a.run_id!r}")
    run_lit = a.run_id
    runtime = max(a.min_runtime_s, 1)
    rows_per_task = -(-runtime * 1000 // MS_PER_ROW)
    _, c = batch_token()  # evidence only: the lifetime of the tokens lab-batch gets now
    lifespan = c["exp"] - c["iat"]
    log(f"acting as {c.get('preferred_username')}; lab-batch access tokens live {lifespan}s; "
        f"auth mode {a.auth}; target {a.target}; min runtime {runtime}s")

    t0 = time.time()
    spark = session(a.auth)

    def stop(signum, _frame):  # the task was stopped: cancel the job on the shared server
        log(f"signal {signum}: interrupting the Spark job")
        spark.interruptAll()
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, stop)
    try:
        orders = spark.sql("SELECT count(*) AS n FROM lakehouse.samples.orders").collect()[0]["n"]
        log(f"read lakehouse.samples.orders: {orders} rows")
        spark.sql(f"""CREATE TABLE IF NOT EXISTS {a.target} (
            run_id STRING, task_row BIGINT, sample_orders BIGINT, slept STRING,
            written_at TIMESTAMP) USING iceberg""")
        log(f"writing {rows_per_task * PARTITIONS} rows in {PARTITIONS} tasks, "
            f"{MS_PER_ROW} ms per row (>= {runtime}s); one commit at the end")
        spark.sql(f"""
            INSERT INTO {a.target}
            SELECT '{run_lit}', id, {orders},
                   reflect('java.lang.Thread', 'sleep', CAST({MS_PER_ROW} AS BIGINT)),
                   current_timestamp()
            FROM range(0, {rows_per_task * PARTITIONS}, 1, {PARTITIONS})""")
        took = time.time() - t0
        snap = spark.sql(f"""SELECT committed_at, snapshot_id, operation
                              FROM {a.target}.snapshots ORDER BY committed_at DESC LIMIT 1""").collect()[0]
        n = spark.sql(f"SELECT count(*) AS n FROM {a.target} WHERE run_id = '{run_lit}'").collect()[0]["n"]
        log(f"committed snapshot {snap['snapshot_id']} ({snap['operation']}) at {snap['committed_at']}; "
            f"{n} rows for this run; job took {took:.0f}s = {took / lifespan:.1f} token lifetimes")
        if n != rows_per_task * PARTITIONS:
            raise SystemExit(f"expected {rows_per_task * PARTITIONS} rows, found {n}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
