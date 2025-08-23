# 🚀 Lakehouse Lab - 15-Minute Quickstart Guide

**Version 2.0.0** - Get your complete enterprise-ready data analytics environment running in 15 minutes! Choose between simple individual setup or secure team collaboration.

## ⚡ 1. Quick Setup

> ⚠️ **Critical**: Always use `./install.sh` for new installations. Direct `docker compose up -d` will fail without proper credentials and initialization!

### 🏠 **Individual Developer Setup (Simple & Fast)**

**One-Command Install - Perfect for Learning:**
```bash
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
```

### 🏢 **Enterprise Team Setup (Secure & Collaborative)**

**Secure Installation with Team Authentication:**
```bash
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install-with-auth.sh | bash
```

### **Alternative: Git Clone Method**
```bash
git clone https://github.com/karstom/lakehouse-lab.git
cd lakehouse-lab

# Individual setup
./install.sh

# OR Enterprise setup  
./install-with-auth.sh

# OR Fat server setup (32+ cores, 64GB+ RAM)
./install.sh --fat-server
```

### 🎯 **Interactive Setup Wizard (Recommended)**
```bash
# Configure services and choose your deployment mode
./scripts/setup-wizard.sh

# Or use presets
./scripts/setup-wizard.sh --minimal    # 8GB RAM
./scripts/setup-wizard.sh --analytics  # 14GB RAM  
./scripts/setup-wizard.sh --ml         # 16GB RAM
./scripts/setup-wizard.sh --full       # 20GB RAM
./scripts/setup-wizard.sh --secure     # 22GB RAM (with auth)
```

### **Why install.sh is Required**
The installer handles critical setup that Docker Compose can't do alone:
- 🔐 Generates secure credentials in `.env` file
- 🔧 Sets proper script permissions  
- 📊 Optimizes resources for your system
- 🚀 Performs initialization and health checks

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

### 🏠 **Core Data Services (Always Available)**
| Service | URL | Purpose | Credentials |
|---------|-----|---------|-------------|
| **Portainer** | http://localhost:9060 | Container Management | Create admin user |
| **JupyterLab** | http://localhost:9040 | Data Science Notebooks | 🔐 Generated |
| **MinIO Console** | http://localhost:9001 | Object Storage | 🔐 Generated |
| **Spark Master** | http://localhost:8080 | Processing Engine | N/A |
| **PostgreSQL** | localhost:5432 | Analytics Database | 🔐 Generated |

### 📊 **Optional Analytics Services (If Enabled)**
| Service | URL | Purpose | Credentials |
|---------|-----|---------|-------------|
| **Apache Superset** | http://localhost:9030 | BI & Dashboards | 🔐 Generated |
| **Apache Airflow** | http://localhost:9020 | Workflow Orchestration | 🔐 Generated |
| **Vizro Dashboards** | http://localhost:9050 | Interactive Dashboards | 🔐 Generated |
| **LanceDB API** | http://localhost:9080 | Vector Database | API Access |
| **Homer Dashboard** | http://localhost:9061 | Service Links | N/A |

### 🔐 **Enterprise Authentication Services (If Enabled)**
| Service | URL | Purpose | Credentials |
|---------|-----|---------|-------------|
| **Auth Portal** | http://localhost:9091 | Login & User Management | OAuth/Local |
| **Secure Access** | http://localhost:9092 | Authenticated Service Access | Via Auth Portal |
| **MCP Data API** | http://localhost:9090 | AI-Powered Data Queries | API Key |

## 🔒 Getting Your Login Credentials

**Lakehouse Lab now generates unique, secure credentials for every installation!** No more default passwords.

### View Your Credentials
```bash
./scripts/show-credentials.sh
```

This shows all your service URLs and login credentials in a clean, copy-paste ready format with memorable passphrases like `swift-river-bright-847`.

---

## 📊 3. Your First Analytics Query - FIXED!

### **Step 1: Open Superset**
1. Visit http://localhost:9030
2. **Get credentials**: Run `./scripts/show-credentials.sh` to see your Superset login
3. Login with your generated credentials (format: admin / memorable-passphrase)
4. Go to **SQL Lab**

### **Step 2: Use Pre-configured DuckDB Database**
✅ **FIXED**: The DuckDB connection is now pre-configured with the correct URI and S3 settings!

The database connection **"DuckDB-S3"** should appear automatically with:
- **URI**: `duckdb:////app/superset_home/lakehouse.duckdb` (fixed persistent file)
- **S3 Config**: Pre-configured for MinIO access
- **DML/DDL**: Enabled (CREATE TABLE, INSERT, UPDATE, DELETE allowed)
- **File Uploads**: Enabled for CSV import
- **Async Queries**: Enabled for better performance

**🔧 If you don't see "DuckDB-S3":**
1. Refresh the page or try **Data** → **Database Connections**
2. If still not there, see the [Superset Database Setup Guide](SUPERSET_DATABASE_SETUP.md) for manual creation steps

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
2. **Database**: DuckDB-S3
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

## 🤖 5. AI-Powered Data Queries (NEW!)

### **Step 1: Access the MCP Server**
✨ **NEW**: Natural language data queries with AI assistance!

1. Get MCP API URL: Run `./scripts/show-credentials.sh`
2. The MCP Server provides AI-powered data access at http://localhost:9090

### **Step 2: Query Data with Natural Language**
```python
import requests

# Natural language query
response = requests.post('http://localhost:9090/api/query', json={
    "query": "Show me the top 5 product categories by revenue from the sample data",
    "limit": 5
})
print(response.json())

# Vector similarity search
response = requests.post('http://localhost:9090/api/vector-search', json={
    "text": "find products similar to electronics",
    "limit": 10
})
similar_items = response.json()
```

### **Step 3: Advanced AI Features**
```python
# Semantic data discovery
response = requests.post('http://localhost:9090/api/discover', json={
    "description": "customer purchase patterns during holidays"
})

# Automated insights
response = requests.post('http://localhost:9090/api/insights', json={
    "table": "sample_orders",
    "focus": "anomaly_detection"
})
```

---

## 📊 6. Modern Interactive Dashboards (NEW!)

### **Step 1: Access Vizro Dashboards**
✨ **NEW**: Modern, responsive dashboard framework!

1. Visit http://localhost:9050
2. Get credentials: Run `./scripts/show-credentials.sh`
3. Explore pre-built sample dashboards

### **Step 2: Interactive Features**
- **Sample Dashboard**: `/sample-dashboard` with sales analytics
- **Real-time Updates**: Live data from PostgreSQL and MinIO  
- **Interactive Filtering**: Dynamic filters and drill-down capabilities
- **Responsive Design**: Works on desktop, tablet, and mobile

### **Step 3: Create Custom Dashboards**
```bash
# Edit dashboard configuration
nano config/dashboards/custom-dashboard.yaml
```

```yaml
# Example Vizro dashboard configuration
pages:
  - title: "Sales Analytics"
    components:
      - title: "Revenue Trends"
        type: "graph"
        figure:
          data: "SELECT * FROM analytics.daily_sales"
          x: "date"
          y: "revenue"
```

---

## 🔍 7. Vector Database & Semantic Search (NEW!)

### **Step 1: Access LanceDB**
✨ **NEW**: High-performance vector operations for AI/ML!

1. API available at http://localhost:9080
2. Pre-loaded with sample embeddings and vectors

### **Step 2: Semantic Search Examples**
```python
import requests
import numpy as np

# Store vectors
vectors = np.random.rand(100, 128).tolist()  # Sample embeddings
response = requests.post('http://localhost:9080/api/vectors', json={
    "table": "product_embeddings",
    "vectors": vectors,
    "metadata": [{"product_id": i, "category": "electronics"} for i in range(100)]
})

# Semantic similarity search
query_vector = np.random.rand(128).tolist()
response = requests.post('http://localhost:9080/api/search', json={
    "table": "product_embeddings", 
    "vector": query_vector,
    "limit": 5
})
similar_products = response.json()
```

---

## 🔬 8. Interactive Data Science - Enhanced!

### **Step 1: Open JupyterLab**
✅ **FIXED**: DuckDB packages are now pre-installed in Jupyter

1. Visit http://localhost:9040
2. **Get token**: Run `./scripts/show-credentials.sh` to see your JupyterLab token
3. Enter your generated token (format: memorable-passphrase)
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
    SET s3_access_key_id='admin';  -- Replace with your MinIO username
    SET s3_secret_access_key='YOUR_MINIO_PASSWORD';  -- Get from ./scripts/show-credentials.sh
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

## 🔐 9. Enterprise Authentication & Team Access (NEW!)

### **Step 1: Access Authentication Portal (If Enabled)**
✨ **NEW**: Enterprise-grade authentication with role-based access!

1. Visit http://localhost:9091 (Auth Portal)
2. Choose login method:
   - **Local Login**: admin@localhost (development)
   - **OAuth**: Google, Microsoft, GitHub (production)

### **Step 2: Configure OAuth Providers**
```bash
# Interactive OAuth setup wizard
./scripts/setup-auth.sh

# Add authentication to existing installation
./scripts/enable-auth.sh
```

### **Step 3: User Roles & Permissions**
- **data_viewer**: Read-only dashboard access
- **data_analyst**: Query data, create charts  
- **data_engineer**: ETL pipelines, data modeling
- **admin**: Full system access, user management

### **Step 4: Secure Service Access**
All services are protected via http://localhost:9092 when authentication is enabled:
- Automatic JWT token validation
- Complete audit logging of all actions
- Role-based service access control

---

## ⚙️ 10. Workflow Orchestration - Enhanced!

### **Step 1: Open Airflow**
✅ **FIXED**: DuckDB import errors resolved - DAGs now work!

1. Visit http://localhost:9020
2. **Get credentials**: Run `./scripts/show-credentials.sh` to see your Airflow login
3. Login with your generated credentials (format: admin / memorable-passphrase)

### **Step 2: Explore Sample DAGs**
- `sample_duckdb_pipeline` - Now works without import errors!
- `data_quality_checks` - Data validation pipeline

### **Step 3: Run Your First DAG**
1. Find `sample_duckdb_pipeline`
2. Toggle **ON**
3. Click **Trigger DAG**
4. Watch execution in **Graph View** - should complete successfully!

---

## 💾 11. Manage Your Data

### **Step 1: Access MinIO Console**
1. Visit http://localhost:9001
2. **Get credentials**: Run `./scripts/show-credentials.sh` to see your MinIO login
3. Login with your generated credentials (format: admin / strong-password)

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

## 🐳 12. Monitor Everything

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

## 🔧 13. Advanced Patterns

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

## 🚨 14. Troubleshooting

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
2. Edit "DuckDB-S3" 
3. Ensure **SQLAlchemy URI**: `duckdb:////app/superset_home/lakehouse.duckdb`
4. **Test Connection** should work immediately

---

## 🎓 What You've Accomplished

After completing this Version 2.0.0 quickstart:

✅ **Enterprise-Ready Data Platform** - Complete analytics stack with optional security  
✅ **AI-Powered Data API** - Natural language queries via MCP Server  
✅ **Modern Interactive Dashboards** - Vizro framework with live data  
✅ **Vector Database Integration** - LanceDB for semantic search and AI/ML  
✅ **Fixed S3 Integration** - Persistent DuckDB S3 configuration  
✅ **Working Airflow DAGs** - No more import errors, enhanced capabilities  
✅ **Latest Technology** - DuckDB 1.3.2 + Vector database + AI integration  
✅ **Enterprise Security** - Optional OAuth with role-based access control  
✅ **Triple Analytics Architecture** - Data lake + warehouse + vector database  
✅ **Production Patterns** - Modern lakehouse with team collaboration  

## 🚀 Next Steps

### **Individual Developers**
- **Add Your Data**: Upload CSV/Parquet files to MinIO
- **Build ML Models**: Use LanceDB for vector embeddings and semantic search
- **Create Dashboards**: Build interactive Vizro dashboards
- **AI Integration**: Experiment with natural language data queries

### **Enterprise Teams** 
- **Setup OAuth**: Configure Google/Microsoft/GitHub authentication
- **Manage Users**: Assign roles and permissions for team members
- **Enable Audit**: Monitor all data access and operations
- **Scale Infrastructure**: Use fat-server configuration for production workloads

### **Advanced Use Cases**
- **Custom MCP Tools**: Extend the AI data API with custom functions
- **Vector Search**: Build recommendation systems and semantic search
- **Real-time Analytics**: Create streaming dashboards with live data
- **Multi-tenant**: Configure separate environments for different teams

---

**Happy Data Engineering in the AI Era!** 🚀🤖

Your enterprise-ready lakehouse is now fully functional with cutting-edge AI capabilities!
