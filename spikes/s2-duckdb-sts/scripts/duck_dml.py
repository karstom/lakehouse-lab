"""Informational (beyond C3): can DuckDB also UPDATE / DELETE the Iceberg table with vended creds?
Run in the duckdb container:  python /opt/s2/duck_dml.py   (removes the row DuckDB inserted, id=100)
"""
import duckdb

con = duckdb.connect()
for ext in ("httpfs", "avro", "iceberg"):
    con.load_extension(ext)
con.sql("ATTACH 'lakehouse' AS lk (TYPE iceberg, ENDPOINT 'http://lakekeeper:8181/catalog', AUTHORIZATION_TYPE 'none')")
for label, stmt in (("UPDATE", "UPDATE lk.s2.events SET amount = amount + 1 WHERE id = 100"),
                    ("DELETE", "DELETE FROM lk.s2.events WHERE id = 100")):
    try:
        con.sql(stmt)
        print(f"DUCK_DML {label} ok ->", con.sql("SELECT count(*), sum(amount) FROM lk.s2.events").fetchone())
    except Exception as e:  # noqa: BLE001
        print(f"DUCK_DML {label} ERROR", type(e).__name__, str(e).replace("\n", " ")[:400])
