"""Generate the E1 input files: three daily CSV files of parcel shipments.

Pretend a delivery partner drops one file per day into a folder. Each row is one parcel sent
for an order in `lakehouse.samples.orders` (the order keys are real TPC-H keys, so you can
join the shipments to the orders later).

    python make_data.py            writes data/shipments_2026-03-0{1,2,3}.csv (400 rows each)

Nothing is downloaded: the rows come from a fixed random seed, so everybody gets the same
files, and running it again rewrites the same bytes.
"""
import csv
import os
import random
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
DAYS = [date(2026, 3, 1), date(2026, 3, 2), date(2026, 3, 3)]
ROWS_PER_DAY = 400
CARRIERS = ["DHL", "DPD", "FedEx", "PostNL", "UPS"]
STATUSES = ["delivered", "delivered", "delivered", "in_transit", "returned"]
COLUMNS = ["shipment_id", "orderkey", "carrier", "shipped_at", "weight_kg", "status"]


def tpch_orderkey(i):
    """The i-th order key of TPC-H (1-based). TPC-H keys are sparse: 1-7, 32-39, 64-71, ..."""
    i -= 1
    return (i // 8) * 32 + (i % 8) + 1


def rows_for(day_no):
    """The rows of one day's file (day_no 0, 1 or 2), as strings like in the CSV."""
    rnd = random.Random(20260301 + day_no)
    day = DAYS[day_no]
    out = []
    for n in range(ROWS_PER_DAY):
        shipped = datetime(day.year, day.month, day.day, 6, 0) + timedelta(
            seconds=rnd.randint(0, 14 * 3600))
        out.append({
            "shipment_id": str((day_no + 1) * 100000 + n + 1),
            "orderkey": str(tpch_orderkey(rnd.randint(1, 15000))),
            "carrier": rnd.choice(CARRIERS),
            "shipped_at": shipped.strftime("%Y-%m-%d %H:%M:%S"),
            "weight_kg": f"{rnd.uniform(0.2, 35.0):.2f}",
            "status": rnd.choice(STATUSES),
        })
    return out


def file_name(day_no):
    return os.path.join(DATA_DIR, f"shipments_{DAYS[day_no].isoformat()}.csv")


def expected():
    """What a correct load of all three files contains (used by the checkpoint)."""
    rows = [r for d in range(len(DAYS)) for r in rows_for(d)]
    return {
        "rows": len(rows),
        "weight_kg": round(sum(float(r["weight_kg"]) for r in rows), 2),
        "days": len(DAYS),
    }


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    for d in range(len(DAYS)):
        path = file_name(d)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows(rows_for(d))
        print(f"wrote {os.path.relpath(path, HERE)} ({ROWS_PER_DAY} rows)")


if __name__ == "__main__":
    main()
