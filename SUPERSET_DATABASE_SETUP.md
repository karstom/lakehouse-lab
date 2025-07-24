# Superset DuckDB Database Setup Guide

## 📝 Manual DuckDB S3 Configuration

This guide explains how to manually configure Superset DuckDB to work with MinIO S3 storage. Manual configuration is the recommended approach for reliability and transparency.

## Why Manual Setup?

**Manual setup is more reliable than automatic configuration because:**
- ✅ **Predictable**: No timing dependencies or startup failures
- ✅ **Transparent**: You see exactly what's being configured
- ✅ **Debuggable**: Easy to troubleshoot when issues arise
- ✅ **Flexible**: Customize settings for your specific use case

## Setup Steps

### 1. Access Superset

1. Open Superset: http://localhost:9030
2. **Get credentials**: Run `./scripts/show-credentials.sh` to see your Superset login
3. Login with your generated credentials (format: admin / memorable-passphrase)

### 2. Create DuckDB Database Connection

1. Go to **Settings** → **Database Connections** → **+ Database**
2. Choose **DuckDB** from the database list
3. Configure the connection:
   - **Database Name**: `DuckDB-S3`
   - **SQLAlchemy URI**: `duckdb:////app/superset_home/lakehouse.duckdb`
4. **Advanced Options**:
   - ✅ Enable **Allow DDL** (CREATE, DROP statements)
   - ✅ Enable **Allow DML** (INSERT, UPDATE, DELETE statements)
   - ✅ Enable **Allow file uploads**
5. Click **Test Connection** → **Connect** to save

### 3. 🔑 Create Persistent S3 Secret (One-Time Setup)

**Run this ONCE to permanently configure S3/MinIO access**. Go to **SQL Lab**, select your **DuckDB-S3** database, and run:

```sql
-- Get your credentials by running: ./scripts/show-credentials.sh
-- Replace YOUR_MINIO_PASSWORD with your actual generated password

CREATE PERSISTENT SECRET minio_secret (
    TYPE S3,
    KEY_ID 'admin',
    SECRET 'YOUR_MINIO_PASSWORD',  -- Paste your actual MinIO password here
    ENDPOINT 'minio:9000',
    USE_SSL false,
    URL_STYLE 'path',
    SCOPE 's3://lakehouse'
);
```

✅ **That's it!** The secret persists across sessions, logins, and container restarts.

### 4. Test S3 Data Access

Now you can query S3 data with **clean, simple queries** - no setup blocks needed:

```sql
-- Test reading CSV data
SELECT * FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv') LIMIT 5;

-- Check DuckDB version  
SELECT version();
```

Expected results:
- CSV query returns sample data immediately
- DuckDB version shows `v1.3.2`

### 5. Example Queries

**All queries now work without any setup commands:**

**Basic data exploration:**
```sql
SELECT 
    product_category,
    COUNT(*) as order_count,
    SUM(total_amount) as revenue,
    AVG(total_amount) as avg_order_value
FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')
GROUP BY product_category
ORDER BY revenue DESC;
```

**Date-based analysis:**
```sql
SELECT 
    DATE_TRUNC('month', order_date::DATE) as month,
    COUNT(*) as monthly_orders,
    SUM(total_amount) as monthly_revenue
FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')
GROUP BY DATE_TRUNC('month', order_date::DATE)
ORDER BY month;
```

**Multi-file queries:**
```sql
SELECT 
    COUNT(*) as total_records,
    COUNT(DISTINCT product_category) as categories,
    SUM(total_amount) as total_revenue
FROM read_csv_auto('s3://lakehouse/raw-data/*.csv', union_by_name=true);
```

### 6. Create Datasets (Now Works Perfectly!)

1. Go to **SQL Lab**, run any query above
2. Click **Save** → **Save as Dataset** 
3. **Dataset creation works!** No more "Only single queries supported" errors

## Why DuckDB Persistent Secrets are Amazing

This approach is **vastly superior** to session-based configuration because:
- ✅ **One-time setup**: Create the secret once, use forever
- ✅ **Clean queries**: No more copying setup blocks for every query
- ✅ **Dataset creation works**: Single SELECT statements work perfectly
- ✅ **Session persistence**: Survives logins, restarts, and new tabs
- ✅ **Professional experience**: Just like any production database

**What changed:** DuckDB 1.3.2+ includes a powerful Secrets Manager that can store persistent S3 credentials in the database file itself.

## Troubleshooting

### If Database Connection Fails

If the database connection test fails:

1. **Check DuckDB installation**: The lakehouse includes DuckDB v1.3.2
2. **Verify file path**: Ensure `/app/superset_home/` directory exists in container
3. **Check permissions**: The Superset container should have write access to create the database file

### If S3 Queries Fail

**Common issues and solutions:**

1. **Invalid credentials**: Run `./scripts/show-credentials.sh` to get current MinIO password
2. **Extension not loaded**: Re-run the S3 configuration commands above
3. **Network connectivity**: Ensure MinIO container is running (`docker-compose ps`)
4. **Wrong endpoint**: Use `s3_endpoint='minio:9000'` (internal Docker network)

**To reconfigure S3 access:**
```sql
-- Clear and reconfigure S3 settings
RESET s3_endpoint;
RESET s3_access_key_id;
RESET s3_secret_access_key;

-- Apply new configuration
SET s3_endpoint='minio:9000';
SET s3_access_key_id='admin';
SET s3_secret_access_key='YOUR_CURRENT_PASSWORD';
SET s3_use_ssl=false;
SET s3_url_style='path';
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

After following this manual setup, you should be able to:
- ✅ Connect to DuckDB in Superset with proper S3 configuration
- ✅ Query MinIO S3 data using DuckDB functions
- ✅ Create datasets using single SELECT statements
- ✅ Build charts and dashboards from your data lake
- ✅ Understand and troubleshoot your DuckDB configuration
- ✅ Quickly reconnect using your setup dataset or view

If all these work, your manual DuckDB integration is successful! 🎉

---

# PostgreSQL Analytics Database Setup

## Overview

In addition to DuckDB for data lake queries, the lakehouse includes a PostgreSQL database perfect for:
- **Structured analytics**: Traditional OLAP queries on relational data
- **Data warehousing**: Store aggregated, cleaned datasets
- **Performance**: Fast queries on indexed, normalized data
- **Airflow integration**: Store workflow results and intermediate data

## PostgreSQL Database Connection Setup

### 1. Add PostgreSQL Connection to Superset

1. Go to **Settings** → **Database Connections** → **+ Database**
2. Choose **PostgreSQL** from the database list
3. Configure the connection:
   - **Database Name**: `PostgreSQL Analytics`
   - **SQLAlchemy URI**: `postgresql://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-lakehouse}`
   - **Replace credentials**: Run `./scripts/show-credentials.sh` to get your actual PostgreSQL password
4. **Advanced Options**:
   - ✅ Enable **Allow DDL** (CREATE, DROP statements)
   - ✅ Enable **Allow DML** (INSERT, UPDATE, DELETE statements)
   - ✅ Enable **Allow file uploads**
5. Click **Test Connection** → **Connect** to save

### 2. Test PostgreSQL Connection

Go to **SQL Lab**, select your **PostgreSQL Analytics** database, and run:

```sql
-- Check PostgreSQL version and connection
SELECT version() as postgres_version;

-- List available schemas
SELECT schema_name FROM information_schema.schemata 
WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast');

-- Check available tables
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public';
```

Expected results:
- PostgreSQL version shows `PostgreSQL 16.x`
- Shows available schemas (likely just `public` initially)
- Lists any existing tables

### 3. Create Analytics Schema

Set up a dedicated schema for analytics:

```sql
-- Create analytics schema
CREATE SCHEMA IF NOT EXISTS analytics;

-- Create a sample fact table for orders
CREATE TABLE IF NOT EXISTS analytics.order_facts (
    id SERIAL PRIMARY KEY,
    order_date DATE NOT NULL,
    product_category VARCHAR(100),
    customer_region VARCHAR(100),
    order_count INTEGER DEFAULT 0,
    total_revenue DECIMAL(12,2) DEFAULT 0.00,
    avg_order_value DECIMAL(10,2) DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_order_facts_date ON analytics.order_facts(order_date);
CREATE INDEX IF NOT EXISTS idx_order_facts_category ON analytics.order_facts(product_category);

-- Verify tables created
SELECT table_name, table_schema 
FROM information_schema.tables 
WHERE table_schema = 'analytics';
```

## Sample Analytics Queries

### Basic Analytics Queries

```sql
-- Daily sales summary
SELECT 
    order_date,
    SUM(order_count) as total_orders,
    SUM(total_revenue) as daily_revenue,
    AVG(avg_order_value) as avg_value
FROM analytics.order_facts
GROUP BY order_date
ORDER BY order_date DESC;

-- Product category performance
SELECT 
    product_category,
    COUNT(*) as days_with_data,
    SUM(order_count) as total_orders,
    SUM(total_revenue) as category_revenue,
    AVG(avg_order_value) as avg_order_value
FROM analytics.order_facts
GROUP BY product_category
ORDER BY category_revenue DESC;

-- Monthly trends
SELECT 
    DATE_TRUNC('month', order_date) as month,
    SUM(total_revenue) as monthly_revenue,
    AVG(avg_order_value) as avg_monthly_order_value
FROM analytics.order_facts
GROUP BY DATE_TRUNC('month', order_date)
ORDER BY month;
```

### Advanced Analytics with Window Functions

```sql
-- Revenue trends with moving averages
SELECT 
    order_date,
    total_revenue,
    AVG(total_revenue) OVER (
        ORDER BY order_date 
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) as revenue_7day_avg,
    LAG(total_revenue, 7) OVER (ORDER BY order_date) as revenue_week_ago,
    (total_revenue - LAG(total_revenue, 7) OVER (ORDER BY order_date)) / 
    LAG(total_revenue, 7) OVER (ORDER BY order_date) * 100 as week_over_week_pct
FROM analytics.order_facts
ORDER BY order_date;

-- Category ranking by month
SELECT 
    DATE_TRUNC('month', order_date) as month,
    product_category,
    SUM(total_revenue) as monthly_revenue,
    RANK() OVER (
        PARTITION BY DATE_TRUNC('month', order_date) 
        ORDER BY SUM(total_revenue) DESC
    ) as category_rank
FROM analytics.order_facts
GROUP BY DATE_TRUNC('month', order_date), product_category
ORDER BY month DESC, category_rank;
```

## Creating Datasets for Superset Dashboards

### 1. Create Summary Dataset

```sql
-- Create a view for dashboard use
CREATE OR REPLACE VIEW analytics.daily_sales_summary AS
SELECT 
    order_date,
    product_category,
    customer_region,
    SUM(order_count) as total_orders,
    SUM(total_revenue) as total_revenue,
    AVG(avg_order_value) as avg_order_value,
    COUNT(*) as record_count
FROM analytics.order_facts
GROUP BY order_date, product_category, customer_region;
```

### 2. Add Dataset to Superset

1. Go to **Data** → **Datasets** → **+ Dataset**
2. Choose **PostgreSQL Analytics** database
3. **Dataset Type**: Virtual or select the `analytics.daily_sales_summary` view
4. **SQL** (if Virtual):

```sql
SELECT * FROM analytics.daily_sales_summary
```

5. **Save** as `Daily Sales Summary`

## PostgreSQL vs DuckDB: When to Use Which

| Use Case | PostgreSQL | DuckDB |
|----------|------------|---------|
| **Structured analytics** | ✅ Excellent | ⚠️ Good |
| **Large data lake queries** | ❌ Limited | ✅ Excellent |
| **Real-time dashboards** | ✅ Excellent | ⚠️ Good |
| **Complex JOINs** | ✅ Excellent | ✅ Excellent |
| **Data warehousing** | ✅ Perfect | ❌ Not ideal |
| **File format support** | ❌ Limited | ✅ Extensive |
| **Performance on aggregations** | ✅ Fast with indexes | ✅ Fast columnar |
| **ACID transactions** | ✅ Full support | ✅ Limited |

**Best Practice**: Use PostgreSQL for cleaned, structured data and DuckDB for raw data lake exploration.

## Example Superset Queries for PostgreSQL

### Dashboard Query Examples

These queries are designed to work well with Superset's visualization components:

#### 1. Sales Performance Dashboard Queries

**Daily Revenue Trend (Line Chart)**
```sql
-- Perfect for Time Series charts
SELECT 
    order_date,
    SUM(total_revenue) as daily_revenue,
    COUNT(DISTINCT product_category) as categories_sold
FROM analytics.order_facts
WHERE order_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY order_date
ORDER BY order_date
```

**Category Performance (Bar Chart)**
```sql
-- Great for horizontal/vertical bar charts
SELECT 
    product_category,
    SUM(total_revenue) as category_revenue,
    SUM(order_count) as total_orders,
    AVG(avg_order_value) as avg_order_value
FROM analytics.order_facts
WHERE order_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY product_category
ORDER BY category_revenue DESC
LIMIT 10
```

**Geographic Sales Distribution (Map Chart)**
```sql
-- Works with Superset's country/region maps
SELECT 
    customer_region as region,
    SUM(total_revenue) as revenue,
    COUNT(*) as order_count,
    AVG(avg_order_value) as avg_order_value
FROM analytics.order_facts
WHERE order_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY customer_region
ORDER BY revenue DESC
```

#### 2. Real-time Analytics Dashboard Queries

**Current Day Performance (Big Number)**
```sql
-- Perfect for Big Number visualization
SELECT 
    SUM(new_revenue) as today_revenue,
    SUM(new_orders) as today_orders,
    AVG(avg_new_order_value) as today_avg_order
FROM analytics.realtime_sales
WHERE batch_date = CURRENT_DATE
```

**Hourly Sales Trend (Time Series)**
```sql
-- Shows intraday patterns
SELECT 
    DATE_TRUNC('hour', processed_at) as hour,
    SUM(new_revenue) as hourly_revenue,
    SUM(new_orders) as hourly_orders
FROM analytics.realtime_sales
WHERE batch_date = CURRENT_DATE
GROUP BY DATE_TRUNC('hour', processed_at)
ORDER BY hour
```

**Category Performance Comparison (Comparison Chart)**
```sql
-- Compare today vs yesterday
SELECT 
    product_category,
    SUM(CASE WHEN batch_date = CURRENT_DATE THEN new_revenue ELSE 0 END) as today_revenue,
    SUM(CASE WHEN batch_date = CURRENT_DATE - 1 THEN new_revenue ELSE 0 END) as yesterday_revenue,
    ROUND(
        (SUM(CASE WHEN batch_date = CURRENT_DATE THEN new_revenue ELSE 0 END) - 
         SUM(CASE WHEN batch_date = CURRENT_DATE - 1 THEN new_revenue ELSE 0 END)) /
        NULLIF(SUM(CASE WHEN batch_date = CURRENT_DATE - 1 THEN new_revenue ELSE 0 END), 0) * 100,
        2
    ) as pct_change
FROM analytics.realtime_sales
WHERE batch_date IN (CURRENT_DATE, CURRENT_DATE - 1)
GROUP BY product_category
HAVING SUM(CASE WHEN batch_date = CURRENT_DATE - 1 THEN new_revenue ELSE 0 END) > 0
ORDER BY pct_change DESC
```

#### 3. Advanced Analytics Queries

**Customer Cohort Analysis**
```sql
-- Monthly cohort revenue analysis
WITH monthly_cohorts AS (
    SELECT 
        DATE_TRUNC('month', order_date) as cohort_month,
        customer_region,
        SUM(total_revenue) as cohort_revenue,
        COUNT(DISTINCT order_date) as active_days
    FROM analytics.order_facts
    WHERE order_date >= CURRENT_DATE - INTERVAL '12 months'
    GROUP BY DATE_TRUNC('month', order_date), customer_region
)
SELECT 
    cohort_month,
    customer_region,
    cohort_revenue,
    LAG(cohort_revenue, 1) OVER (
        PARTITION BY customer_region 
        ORDER BY cohort_month
    ) as prev_month_revenue,
    ROUND(
        (cohort_revenue - LAG(cohort_revenue, 1) OVER (
            PARTITION BY customer_region ORDER BY cohort_month
        )) / NULLIF(LAG(cohort_revenue, 1) OVER (
            PARTITION BY customer_region ORDER BY cohort_month
        ), 0) * 100, 2
    ) as mom_growth_pct
FROM monthly_cohorts
ORDER BY cohort_month DESC, cohort_revenue DESC
```

**Moving Averages and Seasonality**
```sql
-- 7-day and 30-day moving averages
SELECT 
    order_date,
    SUM(total_revenue) as daily_revenue,
    AVG(SUM(total_revenue)) OVER (
        ORDER BY order_date 
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) as revenue_7day_ma,
    AVG(SUM(total_revenue)) OVER (
        ORDER BY order_date 
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    ) as revenue_30day_ma,
    EXTRACT(DOW FROM order_date) as day_of_week,
    EXTRACT(WEEK FROM order_date) as week_of_year
FROM analytics.order_facts
WHERE order_date >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY order_date
ORDER BY order_date
```

**Anomaly Detection Query**
```sql
-- Identify days with unusual sales patterns
WITH daily_stats AS (
    SELECT 
        order_date,
        SUM(total_revenue) as daily_revenue,
        AVG(SUM(total_revenue)) OVER () as avg_daily_revenue,
        STDDEV(SUM(total_revenue)) OVER () as stddev_daily_revenue
    FROM analytics.order_facts
    WHERE order_date >= CURRENT_DATE - INTERVAL '60 days'
    GROUP BY order_date
)
SELECT 
    order_date,
    daily_revenue,
    avg_daily_revenue,
    ROUND(
        ABS(daily_revenue - avg_daily_revenue) / NULLIF(stddev_daily_revenue, 0),
        2
    ) as z_score,
    CASE 
        WHEN ABS(daily_revenue - avg_daily_revenue) > 2 * stddev_daily_revenue 
        THEN 'ANOMALY'
        WHEN ABS(daily_revenue - avg_daily_revenue) > 1.5 * stddev_daily_revenue 
        THEN 'UNUSUAL'
        ELSE 'NORMAL'
    END as status
FROM daily_stats
WHERE ABS(daily_revenue - avg_daily_revenue) > 1.5 * stddev_daily_revenue
ORDER BY z_score DESC
```

### Creating Parameterized Queries

Superset supports Jinja templating for dynamic queries:

**Date Range Filter**
```sql
SELECT 
    order_date,
    product_category,
    SUM(total_revenue) as revenue
FROM analytics.order_facts
WHERE order_date >= '{{ from_dttm }}'
  AND order_date <= '{{ to_dttm }}'
GROUP BY order_date, product_category
ORDER BY order_date, revenue DESC
```

**Category Filter**
```sql
SELECT 
    order_date,
    SUM(total_revenue) as revenue,
    SUM(order_count) as orders
FROM analytics.order_facts
WHERE product_category = '{{ filter_values('product_category')[0] }}'
  AND order_date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY order_date
ORDER BY order_date
```

### Query Performance Tips

1. **Use indexes**: Ensure your queries use the indexes created on `order_date` and `product_category`
2. **Limit data ranges**: Always include date filters to avoid full table scans
3. **Aggregate wisely**: Pre-aggregate data in views for frequently used queries
4. **Cache results**: Enable Superset's query caching for expensive queries

## Success Criteria - PostgreSQL

After following this setup, you should be able to:
- ✅ Connect to PostgreSQL in Superset
- ✅ Create and query analytics schemas and tables
- ✅ Run complex analytical queries with window functions
- ✅ Create datasets and dashboards from PostgreSQL data
- ✅ Use the example queries above to build powerful visualizations
- ✅ Understand when to use PostgreSQL vs DuckDB for different analytics needs