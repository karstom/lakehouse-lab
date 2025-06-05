# 🚀 Lakehouse Lab - 15-Minute Quickstart Guide

Get your complete data analytics environment running in 15 minutes!

## ⚡ 1. Quick Setup

### **Standard Setup (Laptops/Small Servers)**
```bash
git clone https://github.com/karstom/lakehouse-lab.git
cd lakehouse-lab
docker compose up -d
```

### **Fat Server Setup (32+ cores, 64GB+ RAM)**
```bash
git clone https://github.com/karstom/lakehouse-lab.git
cd lakehouse-lab
cp .env.fat-server .env
docker compose up -d
```

### **Alternative: Use the Startup Script**
```bash
# Standard startup with better error handling
./start-lakehouse.sh

# Debug mode (step-by-step startup)
./start-lakehouse.sh debug

# Check system resources first
./start-lakehouse.sh resources
```

### **Monitor Progress**
```bash
# Watch containers start
docker compose ps

# Monitor initialization
docker compose logs -f lakehouse-init

# Check overall status
./start-lakehouse.sh status
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
| **Homer** | http://localhost:9061 | Service Dashboard | N/A |

**💡 Start with Portainer (localhost:9060)** - it provides real-time monitoring and management for all containers.

---

## 📊 3. Your First Analytics Query

### **Step 1: Open Superset**
1. Visit http://localhost:9030
2. Login: **admin** / **admin**
3. Go to **SQL Lab**

### **Step 2: Add DuckDB Database**
1. Click **Settings** → **Database Connections** → **+ Database**
2. Choose **DuckDB**
3. **SQLAlchemy URI**: `duckdb:///:memory:`
4. Click **Advanced** → Enable **Allow DDL** and **Allow DML**
5. **Test Connection** → **Connect**

### **Step 3: Configure S3 Access**
In SQL Lab, run this configuration (run once per session):

```sql
-- Configure DuckDB for S3/MinIO access
INSTALL httpfs;
LOAD httpfs;
SET s3_endpoint='minio:9000';
SET s3_access_key_id='minio';
SET s3_secret_access_key='minio123';
SET s3_use_ssl=false;
SET s3_url_style='path';
```

### **Step 4: Query Your Data**
```sql
-- Query sample orders data
SELECT * FROM read_csv_auto('s3a://lakehouse/raw-data/sample_orders.csv')
LIMIT 10;

-- Analytics query
SELECT 
    product_category,
    COUNT(*) as total_orders,
    ROUND(SUM(total_amount), 2) as total_revenue,
    ROUND(AVG(total_amount), 2) as avg_order_value
FROM read_csv_auto('s3a://lakehouse/raw-data/sample_orders.csv')
GROUP BY product_category
ORDER BY total_revenue DESC;
```

🎉 **You just ran analytics on your data lake!**

---

## 📈 4. Create Your First Dashboard

### **Step 1: Create a Dataset**
1. In Superset, go to **Data** → **Datasets** → **+ Dataset**
2. **Database**: Your DuckDB connection
3. **Schema**: Leave blank
4. **Table**: Paste this SQL as a "Virtual Table":
```sql
SELECT 
    product_category,
    COUNT(*) as order_count,
    SUM(total_amount) as revenue,
    AVG(total_amount) as avg_order_value
FROM read_csv_auto('s3a://lakehouse/raw-data/sample_orders.csv')
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

## 🔬 5. Interactive Data Science

### **Step 1: Open JupyterLab**
1. Visit http://localhost:9040
2. Enter token: **lakehouse**
3. You should see a `notebooks/` folder with examples
4. Open `01_Getting_Started.ipynb`

### **Step 2: Run Sample Analysis**
The getting started notebook demonstrates:
- ✅ Connecting to MinIO (S3)
- ✅ Using DuckDB for fast analytics
- ✅ Spark integration for distributed processing
- ✅ Creating visualizations

### **Step 3: Try Your Own Analysis**
Create a new notebook and try:

```python
import duckdb
import pandas as pd
import matplotlib.pyplot as plt

# Connect to DuckDB with S3 configuration
conn = duckdb.connect()
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
    FROM read_csv_auto('s3a://lakehouse/raw-data/sample_orders.csv')
    GROUP BY product_category
    ORDER BY revenue DESC
""").fetchdf()

# Create visualization
df.plot(x='product_category', y='revenue', kind='bar', figsize=(10, 6))
plt.title('Revenue by Product Category')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
```

---

## ⚙️ 6. Workflow Orchestration

### **Step 1: Open Airflow**
1. Visit http://localhost:9020
2. Login: **admin** / **admin**

### **Step 2: Explore Sample DAGs**
- `sample_duckdb_pipeline` - Analytics pipeline using DuckDB
- `data_quality_checks` - Data validation workflow

### **Step 3: Run Your First DAG**
1. Find `sample_duckdb_pipeline`
2. Toggle **ON**
3. Click **Trigger DAG**
4. Watch execution in **Graph View**

---

## 💾 7. Manage Your Data

### **Step 1: Access MinIO Console**
1. Visit http://localhost:9001
2. Login: **minio** / **minio123**

### **Step 2: Explore Data Structure**
- **Bucket**: `lakehouse`
- **Folders**: 
  - `raw-data/` - Input CSV files
  - `warehouse/` - Processed data
  - `processed-data/` - Analytics results

### **Step 3: Upload Your Own Data**
1. Click **Upload** → **Upload File**
2. Choose CSV files
3. Upload to `raw-data/` folder
4. Query with DuckDB using your file names

---

## 🐳 8. Monitor Everything

### **Step 1: Container Management**
1. Visit http://localhost:9060 (Portainer)
2. Create admin user
3. View all containers, logs, and stats in real-time

### **Step 2: Check Resource Usage**
```bash
# Command line monitoring
docker stats --no-stream

# Or use the startup script
./start-lakehouse.sh resources

# Check service status
./start-lakehouse.sh status
```

### **Step 3: View Service Logs**
```bash
# Check specific service
docker compose logs superset

# Follow logs in real-time
docker compose logs -f jupyter

# Or use the startup script
./start-lakehouse.sh logs
```

---

## 🔧 9. Advanced Patterns

### **Multi-File Analytics**
```sql
-- Query multiple files with same schema
SELECT * FROM read_csv_auto('s3a://lakehouse/raw-data/orders_*.csv');

-- Handle different schemas
SELECT * FROM read_csv_auto('s3a://lakehouse/raw-data/*.csv', union_by_name=true);

-- Cross-format queries
SELECT * FROM read_parquet('s3a://lakehouse/warehouse/*.parquet')
UNION ALL
SELECT * FROM read_csv_auto('s3a://lakehouse/raw-data/*.csv');
```

### **Time-Series Analysis**
```sql
SELECT 
    DATE_TRUNC('month', order_date::DATE) as month,
    COUNT(*) as orders,
    SUM(total_amount) as revenue
FROM read_csv_auto('s3a://lakehouse/raw-data/sample_orders.csv')
GROUP BY month
ORDER BY month;
```

### **Data Pipeline Pattern**
1. **Ingest** → Upload raw data to MinIO
2. **Process** → Transform with Spark/DuckDB in Jupyter
3. **Store** → Save results back to MinIO
4. **Analyze** → Query with DuckDB in Superset
5. **Visualize** → Create dashboards in Superset
6. **Orchestrate** → Automate with Airflow DAGs

### **Spark Integration**
```python
# In Jupyter - Using Spark for large-scale processing
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("Large Scale Processing") \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .config("spark.hadoop.fs.s3a.access.key", "minio") \
    .config("spark.hadoop.fs.s3a.secret.key", "minio123") \
    .getOrCreate()

# Read large datasets
df = spark.read.csv("s3a://lakehouse/raw-data/*.csv", header=True, inferSchema=True)

# Process and save
df.groupBy("product_category").sum("total_amount") \
  .write.mode("overwrite") \
  .parquet("s3a://lakehouse/warehouse/category_totals")
```

---

## 🚨 10. Troubleshooting

### **Services Not Starting**
```bash
# Check status
./start-lakehouse.sh status

# Try debug mode
./start-lakehouse.sh debug

# Check logs
./start-lakehouse.sh logs

# Restart specific service
docker compose restart superset
```

### **DuckDB S3 Connection Issues**
```sql
-- Test basic connection in Superset
SELECT 1 as test;

-- Re-run S3 configuration
INSTALL httpfs; LOAD httpfs;
SET s3_endpoint='minio:9000';
SET s3_access_key_id='minio';
SET s3_secret_access_key='minio123';
SET s3_use_ssl=false;
SET s3_url_style='path';

-- Test file access
SELECT COUNT(*) FROM read_csv_auto('s3a://lakehouse/raw-data/sample_orders.csv');
```

### **Memory Issues**
```bash
# Check memory usage
./start-lakehouse.sh resources

# Reduce memory in .env file
cp .env.default .env
# Edit memory limits to smaller values
docker compose restart
```

### **Permission Issues**
```bash
# Fix common permission problems
sudo chown -R $USER:$USER ./lakehouse-data
sudo chmod -R 755 ./lakehouse-data
```

### **Port Conflicts**
Edit `docker-compose.yml` to change port mappings:
```yaml
ports:
  - "9999:8080"  # Change 9030 to 9999
```

### **Complete Reset**
```bash
# Nuclear option - start fresh
./start-lakehouse.sh reset

# Or manually:
docker compose down -v
sudo rm -rf lakehouse-data/
docker compose up -d
```

---

## 🎓 What You've Learned

After completing this quickstart, you now have:

✅ **Complete Data Stack** - Storage, processing, analytics, visualization  
✅ **S3-Native Querying** - Multi-file analytics with DuckDB  
✅ **Real-Time Dashboards** - Interactive BI with Superset  
✅ **Data Science Environment** - Jupyter with Spark integration  
✅ **Workflow Orchestration** - Automated pipelines with Airflow  
✅ **Container Management** - Full observability with Portainer  
✅ **Production Patterns** - Modern lakehouse architecture  

## 🚀 Next Steps

### **Add Your Own Data**
- Upload CSV/Parquet files to MinIO (`raw-data/` folder)
- Create custom Jupyter notebooks for your analysis
- Build Superset dashboards for your datasets
- Set up Airflow workflows for automated processing

### **Scale Your Setup**
- Switch to fat-server configuration for larger datasets
- Add more Spark workers by increasing `SPARK_WORKER_INSTANCES`
- Optimize memory settings based on your workload
- Set up regular backups of your data and configurations

### **Learn Advanced Techniques**
- Explore Iceberg table format for versioned data
- Set up incremental data processing patterns
- Implement data quality monitoring
- Create complex multi-stage analytics pipelines

### **Connect External Data**
- Set up connections to your existing databases
- Configure API data ingestion workflows
- Implement real-time streaming with Kafka (future enhancement)
- Connect to cloud storage providers

### **Production Deployment**
- Set up SSL/TLS certificates
- Configure proper authentication and authorization
- Implement backup and disaster recovery
- Set up monitoring and alerting

## 🤝 Need Help?

- **GitHub Issues**: Report bugs and request features
- **Documentation**: Check the full README.md
- **Community**: Join discussions on GitHub
- **Contributing**: See CONTRIBUTING.md for how to help improve the project

---

**🎉 Congratulations!** You've successfully set up and learned to use a complete, modern data analytics stack. Welcome to the world of open source data engineering!

**Happy Analytics!** 🚀📊
