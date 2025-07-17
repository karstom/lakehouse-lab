# Apache Iceberg Support

This lakehouse environment includes full support for Apache Iceberg table format, providing advanced features like schema evolution, time travel, and ACID transactions.

## Quick Start

### 1. Enable Iceberg Support

Start the lakehouse with Iceberg enabled:

```bash
docker compose -f docker-compose.yml -f docker-compose.iceberg.yml up -d
```

### 2. Verify Iceberg Components

- **JAR Files**: Automatically downloaded to `./iceberg-jars/` during setup
- **Spark Configuration**: Pre-configured with Iceberg extensions
- **S3 Warehouse**: Located at `s3a://lakehouse/iceberg-warehouse/`

### 3. Try the Examples

Open JupyterLab at http://localhost:9040 and run:
- `03_Iceberg_Tables.ipynb` - Complete Iceberg demo

## Features

### ✅ Table Format Features
- **ACID Transactions**: Full transactional support with rollback capability
- **Schema Evolution**: Add, drop, rename columns without data migration
- **Time Travel**: Query table state at any point in time
- **Partitioning**: Efficient data organization and pruning
- **Snapshot Isolation**: Consistent reads across concurrent operations

### ✅ Storage Features
- **S3 Compatible**: Works with MinIO object storage
- **Columnar Format**: Optimized Parquet storage
- **Metadata Management**: Centralized catalog with version history
- **Data Compaction**: Automatic file optimization

### ✅ Integration Features
- **Spark 3.5.0**: Native Iceberg support with DataFrame API
- **SQL Interface**: Standard SQL commands for DDL and DML
- **Jupyter Notebooks**: Interactive data exploration
- **Airflow Integration**: Automated pipeline support

## Configuration

### Spark Session Configuration

When using Iceberg with Spark, these configurations are automatically applied:

```python
spark = SparkSession.builder \
    .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
    .config("spark.sql.catalog.iceberg", "org.apache.iceberg.spark.SparkCatalog") \
    .config("spark.sql.catalog.iceberg.type", "hadoop") \
    .config("spark.sql.catalog.iceberg.warehouse", "s3a://lakehouse/iceberg-warehouse/") \
    .getOrCreate()
```

### S3 Configuration

MinIO S3 settings are pre-configured:

```python
.config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
.config("spark.hadoop.fs.s3a.access.key", "minio") \
.config("spark.hadoop.fs.s3a.secret.key", "minio123") \
.config("spark.hadoop.fs.s3a.path.style.access", "true") \
.config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
```

## Usage Examples

### Create Iceberg Table

```sql
CREATE TABLE iceberg.orders (
    order_id string,
    customer_id string,
    order_date date,
    product_category string,
    total_amount double
) USING ICEBERG
PARTITIONED BY (product_category)
```

### Time Travel Queries

```sql
-- Query table at specific timestamp
SELECT * FROM iceberg.orders TIMESTAMP AS OF '2024-01-15 10:00:00'

-- Query specific snapshot
SELECT * FROM iceberg.orders VERSION AS OF 12345678901234
```

### Schema Evolution

```sql
-- Add new column
ALTER TABLE iceberg.orders ADD COLUMN order_priority string

-- Rename column
ALTER TABLE iceberg.orders RENAME COLUMN total_amount TO revenue
```

### ACID Transactions

```sql
-- Atomic MERGE operation
MERGE INTO iceberg.orders target
USING staging_orders source
ON target.order_id = source.order_id
WHEN MATCHED THEN UPDATE SET total_amount = source.total_amount
WHEN NOT MATCHED THEN INSERT *
```

## Advanced Features

### Table Maintenance

```sql
-- Optimize table files
CALL iceberg.system.rewrite_data_files('iceberg.orders')

-- Remove old snapshots
CALL iceberg.system.expire_snapshots('iceberg.orders', TIMESTAMP '2024-01-01 00:00:00')
```

### Metadata Queries

```sql
-- View table history
SELECT * FROM iceberg.orders.history

-- View current snapshots
SELECT * FROM iceberg.orders.snapshots

-- View table files
SELECT * FROM iceberg.orders.files
```

## Performance Optimization

### Partitioning Strategy

```sql
-- Time-based partitioning
CREATE TABLE iceberg.events (
    event_id string,
    event_time timestamp,
    user_id string,
    event_type string
) USING ICEBERG
PARTITIONED BY (days(event_time))
```

### Data Types and Bucketing

```sql
-- Bucketed partitioning for even distribution
CREATE TABLE iceberg.users (
    user_id string,
    username string,
    created_at timestamp
) USING ICEBERG
PARTITIONED BY (bucket(16, user_id))
```

## Troubleshooting

### Common Issues

1. **JAR Not Found**
   - Ensure Iceberg is enabled: `docker compose -f docker-compose.yml -f docker-compose.iceberg.yml up -d`
   - Check JAR file exists: `ls -la iceberg-jars/`

2. **S3 Connection Issues**
   - Verify MinIO is running: `curl http://localhost:9000/minio/health/live`
   - Check S3 credentials in Spark configuration

3. **Table Not Found**
   - Verify catalog configuration: `SHOW CATALOGS`
   - Check warehouse location: `s3a://lakehouse/iceberg-warehouse/`

### Logs and Debugging

```bash
# Check Spark logs
docker compose logs spark-master
docker compose logs spark-worker

# Check Jupyter logs for Iceberg operations
docker compose logs jupyter
```

## Version Information

- **Iceberg Version**: 1.4.3
- **Spark Version**: 3.5.0
- **Scala Version**: 2.12
- **JAR File**: `iceberg-spark-runtime-3.5_2.12-1.4.3.jar`

## Next Steps

1. **Explore Examples**: Run the `03_Iceberg_Tables.ipynb` notebook
2. **Build Pipelines**: Create Airflow DAGs with Iceberg operations
3. **Create Dashboards**: Use Superset to visualize Iceberg table data
4. **Performance Tuning**: Optimize partitioning and file sizes for your workload

## Resources

- [Apache Iceberg Documentation](https://iceberg.apache.org/)
- [Iceberg Spark Integration](https://iceberg.apache.org/docs/latest/spark-configuration/)
- [Lakehouse Lab Repository](https://github.com/your-repo/lakehouse-lab)

---

**Note**: This Iceberg integration is automatically configured during lakehouse initialization. JAR files are downloaded and configurations are applied without manual intervention.