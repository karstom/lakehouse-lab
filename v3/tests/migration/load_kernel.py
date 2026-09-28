"""Runs INSIDE a lab admin's workspace kernel (sent by load_driver.py): the notebook cells of
docs/MIGRATION.md step 5, as written there, plus the checks. The only difference from the
guide: the landing-reader key comes from PARAMS instead of input()/getpass().

Prints one line "MIGRATION_RESULT <json>" at the end.
"""
import json
import traceback

PARAMS = json.loads(PARAMS_JSON)  # noqa: F821 - set by load_driver.py before this code
RESULT = {"steps": {}}


def step(name, fn):
    try:
        RESULT["steps"][name] = {"ok": True, **(fn() or {})}
    except Exception as e:  # noqa: BLE001 - every step reports, the driver decides
        RESULT["steps"][name] = {"ok": False, "error": f"{type(e).__name__}: {e}"[:600],
                                 "trace": traceback.format_exc()[-1500:]}


# ---------------------------------------------------------------- guide, cell 1: open landing
def cell_open_landing():
    global landing
    from pyarrow import fs

    landing = fs.S3FileSystem(
        access_key=PARAMS["landing_access_key"],   # guide: input("landing-reader access key: ")
        secret_key=PARAMS["landing_secret_key"],   # guide: getpass.getpass("... secret key: ")
        endpoint_override="http://seaweedfs:8333",
        region="us-east-1")
    listing = landing.get_file_info(fs.FileSelector("landing/v2/lakehouse/raw-data", recursive=True))
    files = sorted(i.path for i in listing if i.type == fs.FileType.File)
    return {"files_under_raw_data": len(files), "sample": files[:4]}


# ---------------------------------------------------------------- guide, cells 2-3: Spark (E1)
def cell_spark_trips():
    global s
    import pandas as pd
    from pyarrow import fs
    from lakehouse import spark

    s = spark("migrate trips")
    s.sql("CREATE NAMESPACE IF NOT EXISTS lakehouse.v2")
    table = "lakehouse.v2.trips"
    s.sql(f"""
    CREATE TABLE IF NOT EXISTS {table} (
        trip_id     BIGINT,
        vendor      STRING,
        pickup_at   TIMESTAMP_NTZ,
        dropoff_at  TIMESTAMP_NTZ,
        distance_km DOUBLE,
        fare        DOUBLE)
    USING iceberg
    PARTITIONED BY (days(pickup_at))
    """)

    def load_file(path):
        """Read one Parquet file from landing, keep the table's columns, append it."""
        with landing.open_input_file(path) as f:
            pdf = pd.read_parquet(f, columns=s.table(table).columns)
        df = s.createDataFrame(pdf, schema=s.table(table).schema)
        df.writeTo(table).append()
        return len(pdf)

    files = sorted(i.path for i in landing.get_file_info(
        fs.FileSelector("landing/v2/lakehouse/raw-data/trips", recursive=True))
        if i.path.endswith(".parquet"))
    loaded = {}
    for path in files:
        loaded[path] = load_file(path)
        print(f"{path}: {loaded[path]} rows")
    count = s.table(table).count()
    print("the table now has", count, "rows")
    parts = [r[0] for r in s.sql(f"SELECT partition FROM {table}.partitions").collect()]
    return {"files": loaded, "spark_count": count, "partitions": len(parts)}


# ---------------------------------------------------------------- guide, cell 4: Trino + PyIceberg
def cell_trino_pyiceberg_orders():
    import pyarrow as pa
    import pyarrow.csv as pacsv
    from lakehouse import catalog, trino_connection

    cur = trino_connection().cursor()
    cur.execute("CREATE SCHEMA IF NOT EXISTS lakehouse.v2")
    cur.fetchall()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS lakehouse.v2.orders (
        order_id   BIGINT,
        customer   VARCHAR,
        order_date DATE,
        amount     DECIMAL(12, 2),
        status     VARCHAR)""")
    cur.fetchall()

    tbl = catalog().load_table("v2.orders")
    schema = tbl.schema().as_arrow()
    with landing.open_input_stream("landing/v2/lakehouse/raw-data/sample_orders.csv") as f:
        data = pacsv.read_csv(f, convert_options=pacsv.ConvertOptions(column_types=schema))
    tbl.append(data.select(schema.names).cast(schema))
    print("appended", data.num_rows, "rows")
    return {"appended": data.num_rows, "arrow_schema": str(pa.schema(schema))[:300]}


# ---------------------------------------------------------------- guide, cell 5: check in Trino
def cell_trino_verify():
    from lakehouse import trino_connection

    cur = trino_connection().cursor()
    exp = PARAMS["expected"]
    cur.execute("SELECT count(*), sum(amount) FROM lakehouse.v2.orders")
    orders_count, amount_sum = cur.fetchall()[0]
    res = {"orders_count": orders_count, "amount_sum": float(amount_sum)}
    ok = (orders_count == exp["orders"]["rows"]
          and abs(float(amount_sum) - exp["orders"]["amount_sum"]) < 0.01)
    if PARAMS["spark"]:
        cur.execute("SELECT count(*), round(sum(fare), 2) FROM lakehouse.v2.trips")
        trips_count, fare_sum = cur.fetchall()[0]
        cur.execute('SELECT count(*) FROM lakehouse.v2."trips$partitions"')
        res.update(trips_count=trips_count, fare_sum=float(fare_sum),
                   trips_partitions=cur.fetchall()[0][0])
        ok = ok and trips_count == exp["trips"]["rows"] and abs(float(fare_sum) - exp["trips"]["fare_sum"]) < 0.01
    res["matches_source"] = ok
    if not ok:
        raise AssertionError(json.dumps(res))
    return res


# ---------------------------------------------------------------- the landing key's limits
def check_landing_key_scope():
    """The landing-reader key reads landing only: no write there, no read of the warehouse."""
    from pyarrow import fs

    res = {}
    try:
        with landing.open_output_stream("landing/v2/should-not-exist.txt") as f:
            f.write(b"x")
        res["write_landing"] = "ALLOWED"
    except OSError as e:
        res["write_landing"] = f"denied ({str(e)[:120]})"
    try:
        info = landing.get_file_info(fs.FileSelector("warehouse", recursive=True))
        res["list_warehouse"] = f"ALLOWED ({len(info)} entries)"
    except OSError as e:
        res["list_warehouse"] = f"denied ({str(e)[:120]})"
    try:
        landing.open_input_stream(PARAMS["warehouse_probe_key"]).read(16)
        res["read_warehouse_object"] = "ALLOWED"
    except OSError as e:
        res["read_warehouse_object"] = f"denied ({str(e)[:120]})"
    if any(v.startswith("ALLOWED") for v in res.values()):
        raise AssertionError(json.dumps(res))
    return res


# ---------------------------------------------------------------- test only: start clean
def drop_previous_run():
    """Not in the guide: a re-run of this test starts from no tables (the guide's appends
    are not idempotent). Trino DROP TABLE (never Spark DROP ... PURGE, see anti-patterns)."""
    from lakehouse import trino_connection

    cur = trino_connection().cursor()
    dropped = []
    for t in ("trips", "orders"):
        cur.execute(f"DROP TABLE IF EXISTS lakehouse.v2.{t}")
        cur.fetchall()
        dropped.append(t)
    return {"dropped_if_existed": dropped}


step("drop_previous_run", drop_previous_run)
step("open_landing", cell_open_landing)
if RESULT["steps"]["open_landing"]["ok"]:
    if PARAMS["spark"]:                       # profiles engineer/full
        step("spark_trips", cell_spark_trips)
    step("trino_pyiceberg_orders", cell_trino_pyiceberg_orders)
    step("trino_verify", cell_trino_verify)
    step("landing_key_scope", check_landing_key_scope)
try:
    s.stop()  # noqa: F821
except Exception:  # noqa: BLE001
    pass
print("MIGRATION_RESULT " + json.dumps(RESULT, default=str), flush=True)
