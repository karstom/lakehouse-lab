"""Build-time only: bake DuckDB extensions into /opt/duckdb/extensions so nothing is
downloaded when a container starts. iceberg depends on avro + httpfs, so all three ship."""
import os
import duckdb

ext_dir = os.environ["DUCKDB_EXT_DIR"]
con = duckdb.connect(config={"extension_directory": ext_dir})
for ext in ("httpfs", "avro", "iceberg"):
    con.install_extension(ext)
    con.load_extension(ext)
print(con.sql(
    "select extension_name, extension_version, install_path from duckdb_extensions() "
    "where installed").fetchall())
