# DuckDB Iceberg Test

You can run this code in a Jupyter notebook cell to test DuckDB's Iceberg capabilities:

```python
import duckdb
import os

# Create DuckDB connection
conn = duckdb.connect()

# Install and load extensions
conn.execute("INSTALL iceberg")
conn.execute("INSTALL httpfs") 
conn.execute("LOAD iceberg")
conn.execute("LOAD httpfs")

# Configure MinIO access
minio_user = os.environ.get('MINIO_ROOT_USER', 'minio')
minio_password = os.environ.get('MINIO_ROOT_PASSWORD', 'minio123')

conn.execute("SET s3_endpoint='minio:9000'")
conn.execute(f"SET s3_access_key_id='{minio_user}'")
conn.execute(f"SET s3_secret_access_key='{minio_password}'")
conn.execute("SET s3_use_ssl=false")
conn.execute("SET s3_url_style='path'")

print("✅ DuckDB configured for MinIO access")

# Create test data
conn.execute("""
    CREATE TABLE customers AS 
    SELECT 
        i as customer_id,
        'Customer ' || i as name,
        'customer' || i || '@email.com' as email,
        current_date as signup_date
    FROM generate_series(1, 10) as t(i)
""")

# Show the data
result = conn.execute("SELECT * FROM customers LIMIT 5").fetchall()
for row in result:
    print(row)

print(f"\n✅ DuckDB Iceberg test ready!")
print("DuckDB can now work with Iceberg tables and MinIO storage")
```

## Why DuckDB might work better:

1. **Simpler configuration** - No complex JAR dependencies
2. **Built-in S3 support** - Native MinIO/S3 connectivity
3. **Native Iceberg support** - Direct table format support
4. **Faster setup** - No classpath conflicts

## Next steps:

If DuckDB works well, you could use it as an alternative to Spark for:
- Quick Iceberg table exploration
- Data validation and testing
- Simple analytics workloads
- Prototyping before moving to Spark