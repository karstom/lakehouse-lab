"""Synthetic "V2 MinIO" content for the migration test (tests/migration/run.sh seed).

Writes one directory per bucket under OUT (argv[1]); run.sh uploads each directory into the
throwaway MinIO with rclone. Deterministic (fixed seeds) except the large random object.
Runs in the workspace image (pandas + pyarrow), never on the host Python.

Layout (bucket/key):
  lakehouse/raw-data/sample_orders.csv                  5,000 rows (loaded with Trino + PyIceberg)
  lakehouse/raw-data/trips/year=2025/month=0N/part-0.parquet  3 files, 100,000 rows each (Spark)
  lakehouse/raw-data/weird names/...                    keys with spaces, unicode and S3-awkward
                                                        characters (# % & + = ; , ' ( ) ? * @ !)
  analytics-exports/reports/<yyyy>/<mm>/<dd>/...        60 small files, 4 levels of prefixes
  big-files/backups/blob-300MiB.bin                     300 MiB of random bytes (multipart upload)
"""
import datetime as dt
import json
import os
import sys

import numpy as np
import pandas as pd

OUT = sys.argv[1]
BIG_MIB = int(os.environ.get("MIG_BIG_MIB", "300"))


def path(bucket, key):
    p = os.path.join(OUT, bucket, *key.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def orders():
    rng = np.random.default_rng(7)
    n = 5000
    df = pd.DataFrame({
        "order_id": np.arange(1, n + 1),
        "customer": [f"customer-{i:04d}" for i in rng.integers(1, 800, n)],
        "order_date": [(dt.date(2025, 1, 1) + dt.timedelta(days=int(d))).isoformat()
                       for d in rng.integers(0, 90, n)],
        "amount": np.round(rng.gamma(2.0, 40.0, n), 2),
        "status": rng.choice(["new", "shipped", "delivered", "returned"], n),
    })
    df.to_csv(path("lakehouse", "raw-data/sample_orders.csv"), index=False)
    return {"rows": n, "amount_sum": round(float(df["amount"].sum()), 2)}


def trips():
    rng = np.random.default_rng(11)
    total, fare_sum, next_id = 0, 0.0, 1
    for month in (1, 2, 3):
        n = 100_000
        start = pd.Timestamp(2025, month, 1)
        pickup = start + pd.to_timedelta(rng.integers(0, 28 * 86400, n), unit="s")
        dur = pd.to_timedelta(rng.integers(120, 3600, n), unit="s")
        df = pd.DataFrame({
            "trip_id": np.arange(next_id, next_id + n, dtype="int64"),
            "vendor": rng.choice(["acme", "blue cab", "zoom"], n),
            "pickup_at": pickup.astype("datetime64[us]"),
            "dropoff_at": (pickup + dur).astype("datetime64[us]"),
            "distance_km": np.round(rng.gamma(2.0, 3.0, n), 3),
            "fare": np.round(rng.gamma(2.0, 9.0, n), 2),
        })
        df.to_parquet(path("lakehouse", f"raw-data/trips/year=2025/month={month:02d}/part-0.parquet"),
                      index=False)
        total += n
        fare_sum += float(df["fare"].sum())
        next_id += n
    return {"rows": total, "fare_sum": round(fare_sum, 2)}


WEIRD = [
    "raw-data/weird names/café ☕ #1 (copy).csv",
    "raw-data/weird names/100% & more+plus=eq.txt",
    "raw-data/weird names/semi;colon,comma'quote.json",
    "raw-data/weird names/question?mark*star@at!bang.txt",
    "raw-data/weird names/deep/er/est/ümlaut ñ 日本語.txt",
    "raw-data/weird names/tab\there and  double  spaces.txt",
]


def weird():
    for i, key in enumerate(WEIRD):
        with open(path("lakehouse", key), "w", encoding="utf-8") as f:
            f.write(json.dumps({"n": i, "key": key}) + "\n")
    return len(WEIRD)


def reports():
    n = 0
    for day in range(60):
        d = dt.date(2025, 1, 1) + dt.timedelta(days=day)
        key = f"reports/{d:%Y}/{d:%m}/{d:%d}/daily-{d.isoformat()}.json"
        with open(path("analytics-exports", key), "w", encoding="utf-8") as f:
            json.dump({"day": d.isoformat(), "orders": day * 3 + 1}, f)
        n += 1
    return n


def big():
    p = path("big-files", f"backups/blob-{BIG_MIB}MiB.bin")
    with open(p, "wb") as f:
        for _ in range(BIG_MIB):
            f.write(os.urandom(1 << 20))
    return os.path.getsize(p)


if __name__ == "__main__":
    summary = {"orders": orders(), "trips": trips(), "weird_keys": weird(),
               "report_files": reports(), "big_bytes": big()}
    with open(os.path.join(OUT, "expected.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps(summary))
