import duckdb
con = duckdb.connect()
for ext in ("httpfs", "avro", "iceberg"):
    con.install_extension(ext)
print(con.sql("SELECT extension_name, extension_version, installed FROM duckdb_extensions() "
              "WHERE extension_name IN ('httpfs','avro','iceberg')").fetchall())
