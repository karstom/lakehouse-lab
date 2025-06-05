#!/bin/sh
set -e

# ------------------------------------------------------------------------------
# init-all-in-one.sh (clean version for DuckDB + Spark lakehouse)
#  • Checks if already initialized to avoid re-running
#  • Installs MinIO Client (mc) from MinIO's official release
#  • Creates all required host directories
#  • Waits for MinIO to be healthy, then creates "lakehouse" bucket
#  • Creates sample Airflow DAGs
#  • Optionally uploads sample CSV to MinIO
#  • Writes a custom Homer config.yml into homer/assets
#  • Sets up Jupyter notebook examples
#  • NO TRINO REFERENCES AT ALL
# ------------------------------------------------------------------------------
LAKEHOUSE_ROOT="${LAKEHOUSE_ROOT:-/mnt/lakehouse}"
INIT_MARKER="$LAKEHOUSE_ROOT/.lakehouse-initialized"

echo "[lakehouse-init] LAKEHOUSE_ROOT = $LAKEHOUSE_ROOT"

# Check if already initialized (skip if marker file exists)
if [ -f "$INIT_MARKER" ]; then
    echo "[lakehouse-init] ✅ Already initialized (found $INIT_MARKER)"
    echo "[lakehouse-init] Skipping initialization. Delete $INIT_MARKER to force re-init."
    exit 0
fi

echo "[lakehouse-init] 🚀 First-time initialization starting..."

# 1) Ensure required tools are available
apk update >/dev/null 2>&1
apk add --no-cache curl python3 py3-pip >/dev/null 2>&1

# 2) Download and install MinIO Client (mc) from MinIO releases
echo "[lakehouse-init] Downloading MinIO Client (mc)..."
curl -sSL https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc
chmod +x /usr/local/bin/mc

# 3) Verify mc installation (optional)
echo "[lakehouse-init] Installed mc → $(/usr/local/bin/mc --version | head -n 1)"

# 4) Export a minimal TERM so mc does not complain
export TERM=xterm

# 5) Create all required host‐side directories under $LAKEHOUSE_ROOT
echo "[lakehouse-init] Creating required directories under $LAKEHOUSE_ROOT..."
mkdir -p \
  "$LAKEHOUSE_ROOT/airflow/dags" \
  "$LAKEHOUSE_ROOT/airflow/logs" \
  "$LAKEHOUSE_ROOT/minio" \
  "$LAKEHOUSE_ROOT/postgres" \
  "$LAKEHOUSE_ROOT/notebooks" \
  "$LAKEHOUSE_ROOT/spark/jobs" \
  "$LAKEHOUSE_ROOT/homer/assets" \
  "$LAKEHOUSE_ROOT/superset"

# 6) Fix permissions on folders so services can write
echo "[lakehouse-init] Setting permissions on service folders..."
# Airflow runs as UID 50000 in the container
chown -R 50000:0 "$LAKEHOUSE_ROOT/airflow" || true
chmod -R 775 "$LAKEHOUSE_ROOT/airflow"
chmod -R g+s "$LAKEHOUSE_ROOT/airflow"

# Create scheduler logs directory with proper permissions
mkdir -p "$LAKEHOUSE_ROOT/airflow/logs/scheduler"
chown -R 50000:0 "$LAKEHOUSE_ROOT/airflow/logs" || true
chmod -R 777 "$LAKEHOUSE_ROOT/airflow/logs"

# Jupyter runs as UID 1000 (jovyan) in the container
chown -R 1000:100 "$LAKEHOUSE_ROOT/notebooks" || true
chmod -R 755 "$LAKEHOUSE_ROOT/notebooks"

# Superset permissions
mkdir -p "$LAKEHOUSE_ROOT/superset"
chown -R 1000:0 "$LAKEHOUSE_ROOT/superset" || true
chmod -R 755 "$LAKEHOUSE_ROOT/superset"

# 7) Make homer/assets world‐writable (Homer only needs to read from it)
echo "[lakehouse-init] Making homer/assets world-writable (chmod 777)..."
chmod -R 777 "$LAKEHOUSE_ROOT/homer/assets"

# 8) Wait until MinIO's health endpoint returns HTTP 200
MINIO_URL="http://minio:9000/minio/health/live"
echo "[lakehouse-init] Waiting for MinIO to become healthy at $MINIO_URL ..."
until curl -sf "$MINIO_URL" >/dev/null 2>&1; do
  echo "  … MinIO not ready, retrying in 3 s"
  sleep 3
done
echo "  ✓ MinIO is healthy"

# 9) Wait for Spark to be ready (with timeout)
SPARK_URL="http://spark-master:8080"
echo "[lakehouse-init] Waiting for Spark Master to become healthy at $SPARK_URL ..."
for i in $(seq 1 10); do
  if curl -sf "$SPARK_URL" >/dev/null 2>&1; then
    echo "  ✓ Spark Master is healthy"
    break
  fi
  echo "  … Spark Master not ready, attempt $i/10, retrying in 5 s"
  sleep 5
  if [ $i -eq 10 ]; then
    echo "  ⚠ Warning: Spark Master not ready after 50s, continuing anyway..."
    echo "  ⚠ Services may start without full coordination"
  fi
done

# 10) Configure mc alias so that we can talk to MinIO
echo "[lakehouse-init] Setting up mc alias to talk to MinIO..."
mc alias set local http://minio:9000 minio minio123 >/dev/null 2>&1 || true

# 11) Ensure that the "lakehouse" bucket exists (retry until success)
echo "[lakehouse-init] Ensuring 'lakehouse' bucket exists…"
until mc ls local/lakehouse >/dev/null 2>&1; do
  mc mb local/lakehouse >/dev/null 2>&1 || true
  sleep 2
done
echo "  ✓ 'lakehouse' bucket ready"

# 12) Create warehouse directory structure in MinIO
echo "[lakehouse-init] Creating warehouse directory structure..."
mc mb local/lakehouse/warehouse >/dev/null 2>&1 || true
mc mb local/lakehouse/raw-data >/dev/null 2>&1 || true
mc mb local/lakehouse/processed-data >/dev/null 2>&1 || true

# 13) Create sample Airflow DAGs
echo "[lakehouse-init] Creating sample Airflow DAGs..."

cat <<'EOF' > "$LAKEHOUSE_ROOT/airflow/dags/sample_duckdb_pipeline.py"
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
import pandas as pd

default_args = {
    'owner': 'lakehouse-lab',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'sample_duckdb_pipeline',
    default_args=default_args,
    description='Sample ETL pipeline using DuckDB and MinIO',
    schedule_interval=timedelta(hours=6),
    catchup=False,
    tags=['example', 'etl', 'duckdb'],
)

def extract_data(**context):
    """Extract sample data from MinIO using DuckDB"""
    import duckdb
    
    # Connect to DuckDB
    conn = duckdb.connect()
    
    # Query data from MinIO (S3-compatible)
    result = conn.execute("""
        SELECT COUNT(*) as record_count
        FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')
    """).fetchone()
    
    print(f"Found {result[0]} records in sample data")
    return result[0]

def transform_data(**context):
    """Transform data using DuckDB"""
    import duckdb
    
    conn = duckdb.connect()
    
    # Example transformation
    result = conn.execute("""
        SELECT 
            product_category,
            COUNT(*) as order_count,
            SUM(total_amount) as total_revenue
        FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')
        GROUP BY product_category
        ORDER BY total_revenue DESC
    """).fetchall()
    
    print("Product category analysis:")
    for row in result:
        print(f"  {row[0]}: {row[1]} orders, ${row[2]:.2f} revenue")
    
    return len(result)

# Define tasks
extract_task = PythonOperator(
    task_id='extract_data',
    python_callable=extract_data,
    dag=dag,
)

transform_task = PythonOperator(
    task_id='transform_data',
    python_callable=transform_data,
    dag=dag,
)

# Set dependencies
extract_task >> transform_task
EOF

cat <<'EOF' > "$LAKEHOUSE_ROOT/airflow/dags/data_quality_check.py"
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator

default_args = {
    'owner': 'lakehouse-lab',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'data_quality_checks',
    default_args=default_args,
    description='Data quality monitoring using DuckDB',
    schedule_interval=timedelta(hours=12),
    catchup=False,
    tags=['data-quality', 'monitoring', 'duckdb'],
)

def check_data_quality(**context):
    """Run data quality checks using DuckDB"""
    import duckdb
    
    conn = duckdb.connect()
    
    # Check for data freshness, completeness, etc.
    checks = [
        ("Record Count", "SELECT COUNT(*) FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')"),
        ("Null Check", "SELECT COUNT(*) FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv') WHERE order_id IS NULL"),
        ("Date Range", "SELECT MIN(order_date), MAX(order_date) FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')"),
    ]
    
    results = {}
    for check_name, query in checks:
        try:
            result = conn.execute(query).fetchone()
            results[check_name] = result
            print(f"✓ {check_name}: {result}")
        except Exception as e:
            print(f"✗ {check_name}: ERROR - {e}")
            results[check_name] = f"ERROR: {e}"
    
    return results

quality_check_task = PythonOperator(
    task_id='run_quality_checks',
    python_callable=check_data_quality,
    dag=dag,
)
EOF

# 14) Create Jupyter notebook examples
echo "[lakehouse-init] Creating sample Jupyter notebooks..."

cat <<'EOF' > "$LAKEHOUSE_ROOT/notebooks/01_Getting_Started.ipynb"
{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# Lakehouse Lab - Getting Started\n",
    "\n",
    "Welcome to your lakehouse environment! This notebook will guide you through the basics of working with your data stack.\n",
    "\n",
    "## What's Available\n",
    "\n",
    "- **MinIO**: S3-compatible object storage\n",
    "- **Apache Spark**: Distributed data processing\n",
    "- **DuckDB**: Fast analytics database\n",
    "- **Apache Airflow**: Workflow orchestration\n",
    "- **Apache Superset**: Business intelligence and visualization\n",
    "- **Portainer**: Container management\n"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Import necessary libraries\n",
    "import pandas as pd\n",
    "import duckdb\n",
    "import boto3\n",
    "from pyspark.sql import SparkSession\n",
    "import os\n",
    "\n",
    "print(\"Lakehouse Lab Environment Ready!\")\n",
    "print(f\"Python version: {os.sys.version}\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Connect to MinIO (S3-Compatible Storage)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Configure MinIO connection\n",
    "s3_client = boto3.client(\n",
    "    's3',\n",
    "    endpoint_url='http://minio:9000',\n",
    "    aws_access_key_id='minio',\n",
    "    aws_secret_access_key='minio123'\n",
    ")\n",
    "\n",
    "# List buckets\n",
    "buckets = s3_client.list_buckets()\n",
    "print(\"Available buckets:\")\n",
    "for bucket in buckets['Buckets']:\n",
    "    print(f\"  - {bucket['Name']}\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Query Data with DuckDB"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Connect to DuckDB\n",
    "conn = duckdb.connect()\n",
    "\n",
    "# Configure S3 access for DuckDB\n",
    "conn.execute(\"\"\"\n",
    "    INSTALL httpfs;\n",
    "    LOAD httpfs;\n",
    "    SET s3_endpoint='minio:9000';\n",
    "    SET s3_access_key_id='minio';\n",
    "    SET s3_secret_access_key='minio123';\n",
    "    SET s3_use_ssl=false;\n",
    "    SET s3_url_style='path';\n",
    "\"\"\")\n",
    "\n",
    "print(\"DuckDB configured for S3 access!\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Query sample data\n",
    "result = conn.execute(\"\"\"\n",
    "    SELECT * FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')\n",
    "    LIMIT 10\n",
    "\"\"\").fetchdf()\n",
    "\n",
    "print(\"Sample data from MinIO:\")\n",
    "display(result)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Analytics with DuckDB"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Run analytics query\n",
    "analytics = conn.execute(\"\"\"\n",
    "    SELECT \n",
    "        product_category,\n",
    "        COUNT(*) as order_count,\n",
    "        SUM(total_amount) as total_revenue,\n",
    "        AVG(total_amount) as avg_order_value\n",
    "    FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')\n",
    "    GROUP BY product_category\n",
    "    ORDER BY total_revenue DESC\n",
    "\"\"\").fetchdf()\n",
    "\n",
    "print(\"Sales by Product Category:\")\n",
    "display(analytics)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Initialize Spark Session"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Create Spark session\n",
    "spark = SparkSession.builder \\\n",
    "    .appName(\"Lakehouse Lab\") \\\n",
    "    .config(\"spark.hadoop.fs.s3a.endpoint\", \"http://minio:9000\") \\\n",
    "    .config(\"spark.hadoop.fs.s3a.access.key\", \"minio\") \\\n",
    "    .config(\"spark.hadoop.fs.s3a.secret.key\", \"minio123\") \\\n",
    "    .config(\"spark.hadoop.fs.s3a.path.style.access\", \"true\") \\\n",
    "    .config(\"spark.hadoop.fs.s3a.connection.ssl.enabled\", \"false\") \\\n",
    "    .getOrCreate()\n",
    "\n",
    "print(f\"Spark version: {spark.version}\")\n",
    "print(\"Spark session created successfully!\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Next Steps\n",
    "\n",
    "1. **Explore Superset**: Open http://localhost:9030 to create dashboards\n",
    "2. **Check Airflow**: Visit http://localhost:9020 to see workflow orchestration\n",
    "3. **Monitor with Portainer**: Use http://localhost:9060 for container management\n",
    "4. **Access MinIO Console**: Visit http://localhost:9001 for file management\n",
    "\n",
    "Happy data engineering!"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.8.10"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}
EOF

cat <<'EOF' > "$LAKEHOUSE_ROOT/notebooks/02_Advanced_Analytics.ipynb"
{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# Advanced Analytics with DuckDB and Spark\n",
    "\n",
    "This notebook demonstrates advanced analytics capabilities using DuckDB for fast queries and Spark for distributed processing."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import duckdb\n",
    "import pandas as pd\n",
    "import matplotlib.pyplot as plt\n",
    "import seaborn as sns\n",
    "from pyspark.sql import SparkSession\n",
    "from pyspark.sql.functions import *\n",
    "\n",
    "# Configure plotting\n",
    "plt.style.use('seaborn-v0_8')\n",
    "%matplotlib inline"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Time Series Analysis with DuckDB"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Connect to DuckDB and configure S3\n",
    "conn = duckdb.connect()\n",
    "conn.execute(\"\"\"\n",
    "    INSTALL httpfs;\n",
    "    LOAD httpfs;\n",
    "    SET s3_endpoint='minio:9000';\n",
    "    SET s3_access_key_id='minio';\n",
    "    SET s3_secret_access_key='minio123';\n",
    "    SET s3_use_ssl=false;\n",
    "    SET s3_url_style='path';\n",
    "\"\"\")\n",
    "\n",
    "# Time series analysis\n",
    "time_series = conn.execute(\"\"\"\n",
    "    SELECT \n",
    "        DATE_TRUNC('month', order_date::DATE) as month,\n",
    "        COUNT(*) as orders,\n",
    "        SUM(total_amount) as revenue\n",
    "    FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')\n",
    "    GROUP BY DATE_TRUNC('month', order_date::DATE)\n",
    "    ORDER BY month\n",
    "\"\"\").fetchdf()\n",
    "\n",
    "# Plot time series\n",
    "fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))\n",
    "\n",
    "ax1.plot(time_series['month'], time_series['orders'], marker='o')\n",
    "ax1.set_title('Orders Over Time')\n",
    "ax1.set_ylabel('Number of Orders')\n",
    "\n",
    "ax2.plot(time_series['month'], time_series['revenue'], marker='o', color='green')\n",
    "ax2.set_title('Revenue Over Time')\n",
    "ax2.set_ylabel('Revenue ($)')\n",
    "ax2.set_xlabel('Month')\n",
    "\n",
    "plt.tight_layout()\n",
    "plt.show()\n",
    "\n",
    "display(time_series)"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "name": "python",
   "version": "3.8.10"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}
EOF

# 15) If INSTALL_SAMPLES=true, upload the sample CSV into MinIO
if [ "$INSTALL_SAMPLES" = "true" ]; then
  echo "[lakehouse-init] Uploading sample CSV to MinIO…"
  SAMPLE_CSV="$LAKEHOUSE_ROOT/notebooks/customers-10000.csv"
  # If the sample is not already in /notebooks, download it from GitHub
  if [ ! -f "$SAMPLE_CSV" ]; then
    curl -sSL \
      https://raw.githubusercontent.com/datablist/sample-csv-files/main/files/customers/customers-10000.csv \
      -o "$SAMPLE_CSV"
  fi
  mc cp "$SAMPLE_CSV" local/lakehouse/raw-data/ >/dev/null 2>&1 || true
  
  # Also create a sample dataset in MinIO
  echo "[lakehouse-init] Creating additional sample datasets..."
  
  # Create sample data generation script inline (no external file needed)
  cat <<'PYTHON_SCRIPT' > /tmp/generate_sample_data.py
import csv
import random
from datetime import datetime, timedelta

# Generate orders data
orders = []
base_date = datetime(2023, 1, 1)

for i in range(5000):
    order_date = base_date + timedelta(days=random.randint(0, 400))
    quantity = random.randint(1, 5)
    unit_price = round(random.uniform(10, 500), 2)
    discount = round(random.uniform(0, 0.3), 2)
    shipping_cost = round(random.uniform(5, 25), 2)
    
    orders.append({
        'order_id': f'ORD-{i+1:06d}',
        'customer_id': f'CUST-{random.randint(1, 1000):06d}',
        'order_date': order_date.strftime('%Y-%m-%d'),
        'product_category': random.choice(['Electronics', 'Clothing', 'Books', 'Home', 'Sports']),
        'product_name': f'Product-{random.randint(1, 100)}',
        'quantity': quantity,
        'unit_price': unit_price,
        'discount': discount,
        'shipping_cost': shipping_cost,
        'total_amount': round(quantity * unit_price * (1 - discount) + shipping_cost, 2),
        'region': random.choice(['North', 'South', 'East', 'West']),
        'sales_channel': random.choice(['Online', 'Store', 'Mobile App'])
    })

# Write to CSV
with open('/tmp/sample_orders.csv', 'w', newline='') as csvfile:
    fieldnames = orders[0].keys()
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(orders)

print(f"Created sample orders dataset with {len(orders)} records")
PYTHON_SCRIPT

  # Run the Python script
  python3 /tmp/generate_sample_data.py
  
  # Copy generated file to notebooks and MinIO
  if [ -f "/tmp/sample_orders.csv" ]; then
    cp "/tmp/sample_orders.csv" "$LAKEHOUSE_ROOT/notebooks/"
    mc cp "/tmp/sample_orders.csv" local/lakehouse/raw-data/ >/dev/null 2>&1 || true
    echo "[lakehouse-init] Sample orders dataset created and uploaded"
  fi
fi

# 16) Write the custom Homer config.yml into homer/assets
echo "[lakehouse-init] Writing custom Homer config into $LAKEHOUSE_ROOT/homer/assets/config.yml..."
cat <<EOF > "$LAKEHOUSE_ROOT/homer/assets/config.yml"
title: "Lakehouse Lab Dashboard"
subtitle: "Open Source Data Analytics Stack"
logo: "/logo.png"
icon: "fas fa-database"
header: true

theme: default
colors:
  light:
    highlight-primary: "#3367d6"
    highlight-secondary: "#4285f4"
    background: "#f5f5f5"
    text: "#363636"
  dark:
    highlight-primary: "#3367d6"
    highlight-secondary: "#4285f4"
    background: "#2b2b2b"
    text: "#eaeaea"

footer: '<p>Lakehouse Lab - Open Source Analytics Stack</p>'

message:
  style: "is-dark"
  title: "Welcome to Lakehouse Lab!"
  icon: "fa fa-grin"
  content: "Your complete open source data analytics environment is ready. All services are configured and connected.<br />Default credentials: <strong>admin/admin</strong> for most services."

services:
  - name: "Analytics & BI"
    icon: "fas fa-chart-line"
    items:
      - name: "Superset"
        icon: "fas fa-chart-bar"
        subtitle: "Business Intelligence & Data Visualization"
        tag: "analytics"
        url: "http://localhost:9030"
        target: "_blank"

      - name: "JupyterLab"
        icon: "fas fa-book"
        subtitle: "Data Science Notebooks with Spark & DuckDB"
        tag: "notebook"
        url: "http://localhost:9040"
        target: "_blank"

  - name: "Orchestration"
    icon: "fas fa-cogs"
    items:
      - name: "Airflow"
        icon: "fas fa-tachometer-alt"
        subtitle: "Workflow Orchestration & Data Pipelines"
        tag: "workflow"
        url: "http://localhost:9020"
        target: "_blank"

  - name: "Storage & Infrastructure"
    icon: "fas fa-server"
    items:
      - name: "MinIO Console"
        icon: "fas fa-cloud"
        subtitle: "S3-Compatible Object Storage"
        tag: "storage"
        url: "http://localhost:9001"
        target: "_blank"

      - name: "Spark Master"
        icon: "fas fa-fire"
        subtitle: "Distributed Data Processing Engine"
        tag: "compute"
        url: "http://localhost:8080"
        target: "_blank"

      - name: "Portainer"
        icon: "fas fa-docker"
        subtitle: "Container Management & Monitoring"
        tag: "monitoring"
        url: "http://localhost:9060"
        target: "_blank"

links:
  - name: "Documentation"
    icon: "fas fa-book"
    url: "https://github.com/your-repo/lakehouse-lab"
    target: "_blank"
EOF

# Create simple placeholders for service logos
echo "[lakehouse-init] Creating placeholder assets..."
mkdir -p "$LAKEHOUSE_ROOT/homer/assets/tools"

echo "[lakehouse-init] Custom Homer config written."

echo "[lakehouse-init] Initialization complete."

# Create marker file to indicate successful initialization
echo "Lakehouse Lab initialized on $(date)" > "$INIT_MARKER"
echo "[lakehouse-init] ✅ Created initialization marker: $INIT_MARKER"

# Verify notebooks were created successfully
if [ -f "$LAKEHOUSE_ROOT/notebooks/01_Getting_Started.ipynb" ]; then
    echo "[lakehouse-init] ✅ Jupyter notebooks created successfully"
else
    echo "[lakehouse-init] ⚠️ Warning: Notebook creation may have failed"
fi

# Verify sample data was uploaded
if mc ls local/lakehouse/raw-data/sample_orders.csv >/dev/null 2>&1; then
    echo "[lakehouse-init] ✅ Sample data uploaded successfully"
else
    echo "[lakehouse-init] ⚠️ Warning: Sample data upload may have failed"
fi

echo ""
echo "==================================================================="
echo "🎉 LAKEHOUSE LAB SETUP COMPLETE! 🎉"
echo "==================================================================="
echo ""
echo "Your lakehouse environment is ready! Access points:"
echo ""
echo "🐳 Portainer:         http://localhost:9060 (container management)"
echo "📈 Superset BI:       http://localhost:9030 (admin/admin)"
echo "📋 Airflow:           http://localhost:9020 (admin/admin)"
echo "📓 JupyterLab:        http://localhost:9040 (token: lakehouse)"
echo "☁️  MinIO Console:     http://localhost:9001 (minio/minio123)"
echo "⚡ Spark Master:      http://localhost:8080"
echo "🏠 Service Links:     http://localhost:9061 (optional Homer)"
echo ""
echo "🐳 CONTAINER MANAGEMENT: Portainer at :9060 provides:"
echo "   • Real-time container stats (CPU, memory, network)"
echo "   • Log viewing and container management"
