"""Criterion 3c: DuckDB loads the baked iceberg extension with auto-install disabled and no
network, and reads an Iceberg table that PyIceberg wrote (local SQL catalog, local files)."""
import os
import shutil
import tempfile

import duckdb
import pyarrow as pa
from pyiceberg.catalog.sql import SqlCatalog

con = duckdb.connect(config={"autoinstall_known_extensions": False})
con.sql("LOAD iceberg")
rows = con.sql(
    "select extension_name, loaded, installed, install_path from duckdb_extensions() "
    "where extension_name in ('iceberg','avro','httpfs') order by 1").fetchall()
for r in rows:
    print("  ", r)
assert all(r[1] and r[2] for r in rows if r[0] == "iceberg"), "iceberg not loaded"

wh = tempfile.mkdtemp(prefix="s4-ice-")
try:
    cat = SqlCatalog("s4", uri=f"sqlite:///{wh}/cat.db", warehouse=f"file://{wh}")
    cat.create_namespace("demo")
    data = pa.table({"id": pa.array(range(1000), pa.int64()),
                     "k": pa.array([i % 7 for i in range(1000)], pa.int64())})
    t = cat.create_table("demo.t", schema=data.schema)
    t.append(data)
    meta = t.metadata_location.removeprefix("file://")
    n, s = con.sql(f"select count(*), sum(k) from iceberg_scan('{meta}')").fetchone()
    print(f"   iceberg_scan({os.path.basename(meta)}) -> count={n} sum(k)={s}")
    assert (n, s) == (1000, sum(i % 7 for i in range(1000)))
finally:
    shutil.rmtree(wh, ignore_errors=True)
print("PASS  duckdb iceberg offline")
