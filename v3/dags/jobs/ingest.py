"""lab_ingest job: append a small generated batch of orders to lakehouse.analytics.landing_orders
through Trino, as lab-batch. No internet: the rows are generated here, deterministically from
the run id, so a re-run of the same run id lands the same rows (and is skipped).

Usage: ingest.py RUN_ID [ROWS]
"""
import hashlib
import random
import sys
from datetime import datetime, timedelta, timezone

from labjob import query, trino

TABLE = "lakehouse.analytics.landing_orders"
REGIONS = ("AFRICA", "AMERICA", "ASIA", "EUROPE", "MIDDLE EAST")


def rows(run_id, n):
    rnd = random.Random(int(hashlib.sha256(run_id.encode()).hexdigest()[:16], 16))
    base = datetime.now(timezone.utc).replace(microsecond=0)
    for i in range(n):
        yield (run_id, i, rnd.choice(REGIONS), round(rnd.uniform(10, 5000), 2),
               (base - timedelta(minutes=rnd.randint(0, 1440))).replace(tzinfo=None))


def main():
    run_id = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 25
    conn = trino()
    cur = conn.cursor()
    query(cur, f"""CREATE TABLE IF NOT EXISTS {TABLE} (
        batch_id varchar, line integer, region varchar, amount double,
        order_ts timestamp(6), ingested_at timestamp(6) with time zone)""")
    done = query(cur, f"SELECT count(*) FROM {TABLE} WHERE batch_id = ?", [run_id])[0][0]
    if done:
        print(f"[ingest] batch {run_id} already landed ({done} rows); nothing to do")
    else:
        batch = list(rows(run_id, n))
        values = ", ".join(["(?, ?, ?, ?, ?, current_timestamp(6))"] * len(batch))
        params = [v for r in batch for v in r]
        query(cur, f"INSERT INTO {TABLE} (batch_id, line, region, amount, order_ts, ingested_at) "
                   f"VALUES {values}", params)
        print(f"[ingest] landed {len(batch)} rows as batch {run_id}")
    who = query(cur, "SELECT current_user")[0][0]
    total, batches = query(cur, f"SELECT count(*), count(DISTINCT batch_id) FROM {TABLE}")[0]
    print(f"[ingest] {TABLE}: {total} rows in {batches} batch(es); Trino user {who}")


if __name__ == "__main__":
    main()
