# Superset DuckDB Database Setup Guide

## ✅ Superset S3 Configuration

This guide explainshow to configure the Superset DuckDB S3 and how to verify everything is working correctly.

## What Was Fixed

### **Before (Broken)**
- ❌ Database URI: `duckdb:///:memory:` (incorrect format)
- ❌ S3 configuration required per session
- ❌ "Only single queries supported" error when creating datasets
- ❌ Manual setup needed every time

### **After (Fixed)**
- ✅ Database URI: `duckdb:////app/superset_home/lakehouse.duckdb` (persistent file)
- ✅ S3 configuration pre-loaded and persistent
- ✅ Single-query dataset creation documented
- ✅ Ready to use out of the box

## Verification Steps

### 1. Check Database Connection

1. Open Superset: http://localhost:9030
2. Login: `admin` / `admin`
3. Go to **Settings** → **Database Connections**
4. You should see "DuckDB Lakehouse" connection
5. Click **Edit** to verify:
   - **SQLAlchemy URI**: `duckdb:////app/superset_home/lakehouse.duckdb`
   - **Test Connection** should work immediately

### 2. Test S3 Queries

Go to **SQL Lab** and run:

```sql
-- This should work immediately without any configuration:
SELECT * FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv') LIMIT 5;

-- Check DuckDB version
SELECT duckdb_version();
```

Expected results:
- Query returns sample data
- DuckDB version shows `v1.3.2`

### 3. Create a Dataset (Fixed Process)

1. Go to **Data** → **Datasets** → **+ Dataset**
2. Choose **DuckDB Lakehouse** database
3. **Dataset Type**: Virtual
4. **SQL**: Use ONLY a single SELECT statement:

```sql
SELECT 
    product_category,
    COUNT(*) as order_count,
    SUM(total_amount) as revenue,
    AVG(total_amount) as avg_order_value
FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')
GROUP BY product_category
```

5. **Save** - This should work without errors!

## Troubleshooting

### If Database Connection Doesn't Exist

The connection should be auto-created, but if it's missing:

1. Go to **Settings** → **Database Connections** → **+ Database**
2. Choose **DuckDB**
3. **SQLAlchemy URI**: `duckdb:////app/superset_home/lakehouse.duckdb`
4. **Advanced** → Enable **Allow DDL** and **Allow DML**
5. **Test Connection** → **Connect**

### If S3 Queries Fail

Check if the S3 configuration was properly applied:

```sql
-- Run this to reconfigure S3 (shouldn't be needed):
INSTALL httpfs;
LOAD httpfs;
SET s3_endpoint='minio:9000';
SET s3_access_key_id='minio';
SET s3_secret_access_key='minio123';
SET s3_use_ssl=false;
SET s3_url_style='path';

-- Then test:
SELECT 1 as test;
```

### If Dataset Creation Fails

Remember the fix for "Only single queries supported":

**❌ Don't do this:**
```sql
-- This causes errors:
INSTALL httpfs;
LOAD httpfs;
SET s3_endpoint='minio:9000';
SELECT * FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv');
```

**✅ Do this instead:**
```sql
-- Use only the SELECT statement for datasets:
SELECT * FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')
```

## Advanced Usage

### Multi-File Queries
```sql
-- Query multiple CSV files
SELECT * FROM read_csv_auto('s3://lakehouse/raw-data/*.csv', union_by_name=true);

-- Cross-format queries
SELECT * FROM read_parquet('s3://lakehouse/warehouse/*.parquet')
UNION ALL
SELECT * FROM read_csv_auto('s3://lakehouse/raw-data/*.csv');
```

### Creating Views for Complex Queries

If you need multi-statement logic, create views in SQL Lab first:

```sql
-- Create a view with complex logic
CREATE OR REPLACE VIEW sales_summary AS 
SELECT 
    product_category,
    DATE_TRUNC('month', order_date::DATE) as month,
    COUNT(*) as orders,
    SUM(total_amount) as revenue
FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')
GROUP BY product_category, month;
```

Then create datasets from the view:
```sql
SELECT * FROM sales_summary
```

## What's Different in DuckDB 1.3.2

The latest version includes:
- **Enhanced S3 performance** - Faster data loading
- **Better error messages** - Clearer debugging
- **UUID v7 support** - Modern unique identifiers
- **Improved SQL features** - More analytical functions

## Success Criteria

After following this guide, you should be able to:
- ✅ Connect to DuckDB in Superset without manual configuration
- ✅ Query S3 data directly without setup commands
- ✅ Create datasets using single SELECT statements
- ✅ Build charts and dashboards from your data lake
- ✅ See DuckDB version 1.3.2 in queries

If all these work, your DuckDB integration is successful! 🎉
