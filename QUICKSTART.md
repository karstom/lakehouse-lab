# 🚀 Lakehouse Lab - 15-Minute Quickstart Guide

Get your complete data analytics environment running in 15 minutes!

## ⚡ 1. Quick Setup

### **Standard Setup (Laptops/Small Servers)**
```bash
git clone <your-repo>
cd lakehouse-lab
docker compose up -d
```

### **Fat Server Setup (32+ cores, 64GB+ RAM)**
```bash
git clone <your-repo>
cd lakehouse-lab
cp .env.fat-server .env
docker compose up -d
```

### **Monitor Progress**
```bash
# Watch containers start
docker compose ps

# Monitor initialization
docker compose logs -f lakehouse-init
```

**Initialization takes 3-5 minutes.** You'll see a success message when complete!

---

## 🎯 2. Access Your Services

Once startup completes, access these URLs:

| Service | URL | Purpose | Credentials |
|---------|-----|---------|-------------|
| **Portainer** | http://localhost:9060 | Container Management | Create admin user |
| **Superset** | http://localhost:9030 | BI & Dashboards | admin/admin |
| **JupyterLab** | http://localhost:9040 | Data Science | token: lakehouse |
| **Airflow** | http://localhost:9020 | Orchestration | admin/admin |
| **MinIO** | http://localhost:9001 | File Storage | minio/minio123 |
| **Spark** | http://localhost:8080 | Processing Engine | N/A |

---

## 📊 3. Your First Analytics Query - FIXED!

### **Step 1: Open Superset**
1. Visit http://localhost:9030
2. Login: **admin** / **admin**
3. Go to **SQL Lab**

### **Step 2: Use Pre-configured DuckDB Database**
✅ **FIXED**: The DuckDB connection is now pre-configured with the correct URI and S3 settings!

The database connection "DuckDB Lakehouse" should appear automatically with:
- **URI**: `duckdb:////app/superset_home/lakehouse.duckdb` (fixed persistent file)
- **S3 Config**: Pre-configured for MinIO access

### **Step 3: Query Your Data (No Configuration Needed!)**
✅ **FIXED**: S3 configuration is now persistent - no need to run setup commands every time!

Simply run your analytics queries:

```sql
-- Query sample orders data directly
SELECT * FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')
LIMIT 10;

-- Analytics query
SELECT 
    product_category,
    COUNT(*) as total_orders,
    ROUND(SUM(total_amount), 2) as total_revenue,
    ROUND(AVG(total_amount), 2) as avg_order_value
FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')
GROUP BY product_category
ORDER BY total_revenue DESC;
```

🎉 **You just ran analytics on your data lake without any configuration!**

---

## 📈 4. Create Your First Dataset - FIXED!

### **Step 1: Create a Dataset (Single Query Only)**
✅ **FIXED**: Use single SELECT statements to avoid "Only single queries supported" error

1. In Superset, go to **Data** → **Datasets** → **+ Dataset**
2. **Database**: DuckDB Lakehouse
3. **Dataset Type**: SQL
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

5. **Save** as "Sales Analysis"

### **Step 2: Create Charts**
1. Click **Create Chart** from your dataset
2. **Chart Type**: Bar Chart
3. **Metrics**: revenue
4. **Dimensions**: product_category
5. **Run Query** → **Save**

### **Step 3: Build Dashboard**
1. Go to **Dashboards** → **+ Dashboard**
2. **Edit Dashboard** → **Add Charts**
3. Add your chart and arrange
4. **Save Dashboard**

---

## 🔬 5. Interactive Data Science - FIXED!

### **Step 1: Open JupyterLab**
✅ **FIXED**: DuckDB packages are now pre-installed in Jupyter

1. Visit http://localhost:9040
2. Enter token: **lakehouse**
3. DuckDB 1.3.2 and all dependencies are ready to use!

### **Step 2: Try Your Analysis**
Create a new notebook and run:

```python
import duckdb
import pandas as pd
import matplotlib.pyplot as plt

# Connect to DuckDB with S3 configuration
conn = duckdb.connect()

# Configure S3 access (still needed in Jupyter)
conn.execute("""
    INSTALL httpfs; LOAD httpfs;
    SET s3_endpoint='minio:9000';
    SET s3_access_key_id='minio';
    SET s3_secret_access_key='minio123';
    SET s3_use_ssl=false;
    SET s3_url_style='path';
""")

# Query and visualize
df = conn.execute("""
    SELECT 
        product_category,
        SUM(total_amount) as revenue
    FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')
    GROUP BY product_category
    ORDER BY revenue DESC
""").fetchdf()

# Create visualization
df.plot(x='product_category', y='revenue', kind='bar', figsize=(10, 6))
plt.title('Revenue by Product Category')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()

# Check versions
print(f"DuckDB version: {duckdb.__version__}")  # Should show 1.3.2
```

---

## ⚙️ 6. Workflow Orchestration - FIXED!

### **Step 1: Open Airflow**
✅ **FIXED**: DuckDB import errors resolved - DAGs now work!

1. Visit http://localhost:9020
2. Login: **admin** / **admin**

### **Step 2: Explore Sample DAGs**
- `sample_duckdb_pipeline` - Now works without import errors!
- `data_quality_checks` - Data validation pipeline

### **Step 3: Run Your First DAG**
1. Find `sample_duckdb_pipeline`
2. Toggle **ON**
3. Click **Trigger DAG**
4. Watch execution in **Graph View** - should complete successfully!

---

## 💾 7. Manage Your Data

### **Step 1: Access MinIO Console**
1. Visit http://localhost:9001
2. Login: **minio** / **minio123**

### **Step 2: Explore Data Structure**
- **Bucket**: `lakehouse`
- **Folders**: 
  - `raw-data/` - Input CSV files (sample_orders.csv included)
  - `warehouse/` - Processed data
  - `processed-data/` - Analytics results

### **Step 3: Upload Your Own Data**
1. Click **Upload** → **Upload File**
2. Choose CSV files
3. Upload to `raw-data/` folder
4. Query immediately with DuckDB!

---

## 🐳 8. Monitor Everything

### **Step 1: Container Management**
1. Visit http://localhost:9060 (Portainer)
2. Create admin user
3. View all containers, logs, and stats

### **Step 2: Check Resource Usage**
```bash
# Command line monitoring
docker stats --no-stream

# Or use Portainer web interface for visual monitoring
```

### **Step 3: View Service Logs**
```bash
# Check specific service
docker compose logs superset

# Follow logs in real-time
docker compose logs -f jupyter
```

---

## 🔧 9. Advanced Patterns

### **Multi-File Analytics (Now Works Perfectly!)**
```sql
-- Query multiple files with same schema
SELECT * FROM read_csv_auto('s3://lakehouse/raw-data/orders_*.csv');

-- Handle different schemas
SELECT * FROM read_csv_auto('s3://lakehouse/raw-data/*.csv', union_by_name=true);

-- Cross-format queries
SELECT * FROM read_parquet('s3://lakehouse/warehouse/*.parquet')
UNION ALL
SELECT * FROM read_csv_auto('s3://lakehouse/raw-data/*.csv');
```

### **Time-Series Analysis**
```sql
SELECT 
    DATE_TRUNC('month', order_date::DATE) as month,
    COUNT(*) as orders,
    SUM(total_amount) as revenue
FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')
GROUP BY month
ORDER BY month;
```

---

## 🚨 10. Troubleshooting

### **Fixed Issues:**
✅ **Issue #1**: Superset S3 configuration now persists  
✅ **Issue #2**: Airflow DuckDB import errors resolved  
✅ **Dataset Creation**: Single query requirement documented  
✅ **Latest Packages**: DuckDB 1.3.2 + duckdb-engine 0.17.0  

### **Common Issues:**
```bash
# Services not starting
docker compose ps
docker compose logs [service-name]

# Memory issues - check usage
docker stats

# Complete reset if needed
docker compose down -v
sudo rm -rf lakehouse-data/
docker compose up -d
```

### **Superset Database Connection Issues**
If you need to manually update the Superset DuckDB connection:

1. Go to **Settings** → **Database Connections**
2. Edit "DuckDB Lakehouse" 
3. Ensure **SQLAlchemy URI**: `duckdb:////app/superset_home/lakehouse.duckdb`
4. **Test Connection** should work immediately

---

## 🎓 What You've Accomplished

After completing this quickstart with the fixes:

✅ **Complete Data Stack** - Storage, processing, analytics, visualization  
✅ **Fixed S3 Integration** - Persistent DuckDB S3 configuration  
✅ **Working Airflow DAGs** - No more import errors  
✅ **Latest Technology** - DuckDB 1.3.2 with all modern features  
✅ **Reliable Datasets** - Single-query dataset creation  
✅ **Production Patterns** - Modern lakehouse architecture  

## 🚀 Next Steps

- **Add Your Data**: Upload CSV/Parquet files to MinIO
- **Build Pipelines**: Create custom Airflow DAGs
- **Advanced Analytics**: Use DuckDB 1.3.2's latest features
- **Scale Up**: Use fat-server configuration for larger workloads

---

**Happy Data Engineering!** 🚀

The lakehouse is now fully functional with all issues resolved!
