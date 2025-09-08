# 🚀 Lakehouse Lab - 15-Minute Educational Quickstart Guide

**Version 2.1.0** - Get your complete modern data engineering learning environment running in 15 minutes! Perfect for data engineering students, CS labs, educational institutions, and learning enterprise-grade technologies in a classroom-friendly environment.

## ⚡ 1. Quick Setup

> ⚠️ **Critical**: Always use `./install.sh` for new installations. Direct `docker compose up -d` will fail without proper credentials and initialization!

### 🎓 **Individual Learning Setup (Simple & Fast)**

**One-Command Install - Perfect for Students & Educators:**
```bash
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
```

### 🏫 **Educational Institution Setup (Multi-User & Collaborative)**

**Multi-User Installation for Classrooms & Labs:**
```bash
# Standard installation with multi-user capabilities
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
```

### **Alternative: Git Clone Method**
```bash
git clone https://github.com/karstom/lakehouse-lab.git
cd lakehouse-lab

# Individual/educational setup
./install.sh

# OR High-performance setup for CS labs (32+ cores, 64GB+ RAM)
./install.sh --fat-server
```

### 🎯 **Interactive Setup Wizard (Recommended)**
```bash
# Configure services and choose your deployment mode
./scripts/setup-wizard.sh

# Or use presets
./scripts/setup-wizard.sh --minimal    # 8GB RAM - Basic learning environment
./scripts/setup-wizard.sh --analytics  # 14GB RAM - BI/Dashboard focus
./scripts/setup-wizard.sh --ml         # 16GB RAM - AI/ML coursework
./scripts/setup-wizard.sh --full       # 20GB RAM - Complete curriculum
```

### 👥 **Multi-User JupyterHub Setup (Classroom Collaboration)**

**For educational environments, enable multi-user JupyterHub for student collaboration:**

```bash
# After installation, enable multi-user JupyterHub
docker compose -f docker-compose.yml -f docker-compose.jupyterhub.yml up -d

# Provision team members
./scripts/provision-user.sh john.doe john.doe@company.com SecurePass123 analyst
./scripts/provision-user.sh jane.smith jane.smith@company.com AnotherPass456 admin
```

**JupyterHub Features for Education:**
- 👥 **Multi-user environment** with containerized isolation per student
- 🔗 **Spark integration** automatically configured for all students
- 📁 **Shared notebooks** (readonly course materials + collaborative workspace)
- 🔐 **Student authentication** with role-based access control
- 📊 **Resource management** with per-student CPU and memory limits

**Access JupyterHub:** http://localhost:9041

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
| **JupyterLab** | http://localhost:9040 | Single-User Notebooks | 🔐 Generated |
| **JupyterHub** | http://localhost:9041 | Multi-User Notebooks | User accounts |
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


## 🔒 Getting Your Login Credentials

**Lakehouse Lab now generates unique, secure credentials for every installation!** No more default passwords.

### View Your Credentials
```bash
./scripts/show-credentials.sh
```

This shows all your service URLs and login credentials in a clean, copy-paste ready format with memorable passphrases like `swift-river-bright-847`.

---

## 📊 3. Your First Analytics Query

### **Step 1: Open Superset**
1. Visit http://localhost:9030
2. **Get credentials**: Run `./scripts/show-credentials.sh` to see your Superset login
3. Login with your generated credentials (format: admin / memorable-passphrase)
4. Go to **SQL Lab**

### **Step 2: Use Pre-configured DuckDB Database**
✅ **Ready for Learning**: The DuckDB connection is pre-configured for immediate educational use!

The database connection **"DuckDB-S3"** should appear automatically with:
- **URI**: `duckdb:////app/superset_home/lakehouse.duckdb` (fixed persistent file)
- **S3 Config**: Pre-configured for MinIO access
- **DML/DDL**: Enabled (CREATE TABLE, INSERT, UPDATE, DELETE allowed)
- **File Uploads**: Enabled for CSV import
- **Async Queries**: Enabled for better performance

**🔧 If you don't see "DuckDB-S3":**
1. Refresh the page or try **Data** → **Database Connections**
2. If still not there, see the [Superset Database Setup Guide](SUPERSET_DATABASE_SETUP.md) for manual creation steps

### **Step 3: Query Your Data (Ready to Go!)**
✅ **Educational Ready**: S3 configuration is persistent - perfect for learning sessions!

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

🎓 **You just learned lakehouse analytics with zero configuration complexity!**

---

## 📈 4. Learn Dataset Creation

### **Step 1: Create a Dataset (Educational Best Practice)**
✅ **Learning**: Use single SELECT statements following data engineering best practices

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


## 📊 5. Learn Modern Interactive Dashboards

### **Step 1: Access Vizro Dashboards**
✨ **Educational**: Learn modern, responsive dashboard development!

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

## 🔍 6. Vector Database & Semantic Search (Educational AI/ML)

### **Step 1: Access LanceDB**
✨ **Educational**: Learn high-performance vector operations for AI/ML!

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

## 🔬 7. Interactive Data Science Learning

### **Step 1: Open JupyterLab**
✅ **Ready for Learning**: DuckDB packages are pre-installed for immediate use

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

# Configure S3 access for learning environment
conn.execute("""
    INSTALL httpfs; LOAD httpfs;
    SET s3_endpoint='minio:9000';
    SET s3_access_key_id='admin';  -- Default username for educational setup
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

### **Step 3: Educational Example Notebooks**
✨ **NEW**: Comprehensive tutorial notebooks designed for learning!

**Available Learning Notebooks:**
- `01_Getting_Started.ipynb` - Introduction to the lakehouse environment
- `02_PostgreSQL_Analytics.ipynb` - Database analytics and SQL integration
- `04_Vizro_Interactive_Dashboards.ipynb` - Modern dashboard creation
- `05_LanceDB_Vector_Search.ipynb` - Vector database and semantic search
- `06_Advanced_Analytics_Vizro_LanceDB.ipynb` - Combined AI-powered analytics
- `simple_working_dashboard.py` - Interactive dashboard development

**Educational Features:**
- 🎨 **Interactive Learning**: Step-by-step tutorials with hands-on examples
- 🤖 **AI/ML Concepts**: Learn semantic clustering, UMAP visualization, and TF-IDF analysis
- 📊 **Data Engineering**: Revenue trends, customer analysis, and business metrics
- 🎓 **Learning-Focused**: Clear explanations with educational best practices

**Quick Start:**
```python
# In any Jupyter notebook, run the dashboard demo:
# Path will be available after initialization
exec(open('/home/jovyan/notebooks/simple_working_dashboard.py').read())
display_dashboard()
```

---

## 🔐 8. User Management & Access Control

### **Step 1: Single-User Access (Default)**
By default, Lakehouse Lab provides secure single-user access perfect for individual learning:

1. All services use generated credentials (run `./scripts/show-credentials.sh` to view)
2. Each service has its own authentication system
3. Perfect for individual students and small learning groups

### **Step 2: Multi-User Setup (Educational Environments)**
For classroom and lab environments, use JupyterHub for multi-user collaboration:

```bash
# Enable multi-user JupyterHub
docker compose -f docker-compose.yml -f docker-compose.jupyterhub.yml up -d

# Add students/users
./scripts/provision-user.sh student1 student1@university.edu SecurePass123 student
./scripts/provision-user.sh professor professor@university.edu AdminPass456 admin
```

### **Step 3: Educational User Roles**
- **student**: Access to JupyterHub, shared notebooks, course materials
- **instructor**: Full notebook access, can create/modify course content
- **admin**: System administration, user management, all services

---

## ⚙️ 9. Workflow Orchestration Learning

### **Step 1: Open Airflow**
✅ **Educational**: Pre-configured DAGs ready for learning workflow orchestration

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

## 💾 10. Learn Data Management

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

## 🐳 11. Learn System Monitoring

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

## 🔧 12. Advanced Learning Patterns

### **Multi-File Analytics (Educational Examples)**
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

## 🚨 13. Learning Environment Troubleshooting

### **Educational Environment Features:**
✅ **Persistent Configuration**: Superset S3 settings maintained across sessions  
✅ **Working Examples**: All Airflow DAGs configured and functional  
✅ **Best Practices**: Single query patterns for dataset creation  
✅ **Modern Stack**: DuckDB 1.3.2 + duckdb-engine 0.17.0 for current industry practices  

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

### **Educational Environment Connection Issues**
If you need to manually update the Superset DuckDB connection for learning purposes:

1. Go to **Settings** → **Database Connections**
2. Edit "DuckDB-S3" 
3. Ensure **SQLAlchemy URI**: `duckdb:////app/superset_home/lakehouse.duckdb`
4. **Test Connection** should work immediately - perfect for educational demos

---

## 🎓 What You've Learned

After completing this Version 2.1.0 quickstart, you've gained hands-on experience with:

✅ **Modern Data Engineering Platform** - Complete analytics stack for learning  
  
✅ **Interactive Dashboard Development** - Vizro framework with live data  
✅ **Vector Database Concepts** - LanceDB for semantic search and AI/ML applications  
✅ **Cloud-Native Storage** - S3-compatible object storage with DuckDB integration  
✅ **Workflow Orchestration** - Airflow DAGs for data pipeline automation  
✅ **Modern Analytics Stack** - DuckDB 1.3.2 + Vector database + AI integration  
✅ **Multi-User Collaboration** - JupyterHub for team-based data science  
✅ **Lakehouse Architecture** - Modern data lake + warehouse + vector database patterns  
✅ **Educational Best Practices** - Comprehensive learning environment for data engineering  

## 🚀 Next Steps

### **Individual Students & Self-Learners**
- **Add Your Data**: Upload CSV/Parquet files to MinIO
- **Build ML Models**: Use LanceDB for vector embeddings and semantic search
- **Create Dashboards**: Build interactive Vizro dashboards
- **Experiment & Learn**: Safe environment for data engineering practice

### **Educational Institutions & Instructors** 
- **Setup Multi-User**: Configure JupyterHub for classroom collaboration
- **Manage Students**: Assign roles and control access to course materials
- **Monitor Progress**: Track student usage and learning activities
- **Scale Resources**: Use high-performance configuration for computer labs

### **Advanced Learning Topics**
- **Vector Search**: Build recommendation systems and semantic search applications
- **Real-time Analytics**: Create streaming dashboards and live data visualization
- **Distributed Computing**: Explore Spark for large-scale data processing
- **Data Pipeline Design**: Learn ETL/ELT patterns with Airflow orchestration

---

**Happy Learning and Data Engineering!** 🚀🎓

Your educational lakehouse environment is now ready for comprehensive data engineering learning and experimentation!
