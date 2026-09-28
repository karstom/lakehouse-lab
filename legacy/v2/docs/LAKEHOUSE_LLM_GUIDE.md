# 🤖 Lakehouse Lab - LLM Development Guide

> **Comprehensive metadata and development guide for Large Language Models working with Lakehouse Lab**

**Version 2.0.0** - This document provides LLMs and AI developers with complete system understanding, code patterns, configuration details, and best practices for working with the modern Lakehouse Lab environment, including the authentication system and AI-powered capabilities.

## 🏗️ System Architecture Overview

### Core Infrastructure
```
┌─────────────────────────────────────────────────────────────────────┐
│                    LAKEHOUSE LAB ECOSYSTEM v2.0                     │
├─────────────────┬─────────────────┬─────────────────┬───────────────┤
│  STORAGE LAYER  │ PROCESSING LAYER│  INTERFACE LAYER│   AI LAYER    │
├─────────────────┼─────────────────┼─────────────────┼───────────────┤
│ • PostgreSQL    │ • Apache Spark  │ • JupyterLab    │ • MinIO (S3)    │ • Apache Airflow│ • Apache Superset│ • LanceDB API │
│ • LanceDB       │ • DuckDB        │ • Vizro Dashboards│ • Vector Search│
│                 │                 │ • Portainer     │               │
│                 │                 │ • Auth Portal   │               │
└─────────────────┴─────────────────┴─────────────────┴───────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    AUTHENTICATION LAYER (OPTIONAL)                  │
├─────────────────┬─────────────────┬─────────────────┬───────────────┤
│  AUTH SERVICES  │   ACCESS CONTROL │   AUDIT & LOG   │   PROVIDERS   │
├─────────────────┼─────────────────┼─────────────────┼───────────────┤
│ • Auth Service  │ • Auth Proxy    │ • Audit Service │ • Google OAuth│
│ • JWT Manager   │ • Role Enforcer │ • Activity Log  │ • Microsoft   │
│ • User Manager  │ • Permission Mgr│ • Compliance    │ • GitHub      │
└─────────────────┴─────────────────┴─────────────────┴───────────────┘
```

### Service Communication Matrix
```
Service         | Internal Port | External Port | Container Name        | Health Check
----------------|---------------|---------------|-----------------------|------------------
PostgreSQL      | 5432          | 5432          | postgres              | pg_isready
MinIO           | 9000          | 9000/9001     | minio                 | /minio/health/live
Spark Master    | 7077          | 8080          | spark-master          | HTTP:8080
Spark Worker    | -             | 8081          | spark-worker-1        | HTTP:8081
JupyterLab      | 8888          | 9040          | jupyter               | HTTP:9040
Airflow Web     | 8080          | 9020          | airflow-webserver     | /health
Superset        | 8088          | 9030          | superset              | /health
Vizro           | 8050          | 9050          | vizro                 | HTTP:8050
LanceDB         | 8000          | 9080          | lancedb               | /health
Portainer       | 9000          | 9060          | portainer             | HTTP:9060

# AI Services
Vector Search   | 8000          | 9080          | lancedb               | /health

# Authentication Services (Optional)
Auth Service    | 8080          | 9091          | auth-service          | /health
Auth Proxy      | 8080          | 9092          | auth-proxy            | /health
Audit Service   | 8080          | -             | audit-service         | /health
```

## 🔐 Environment Configuration

### Primary Environment Variables (.env)
```bash
# Database Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=${SECURE_GENERATED_PASSWORD}
POSTGRES_DB=lakehouse

# Object Storage (S3-Compatible)
MINIO_ROOT_USER=admin
MINIO_ROOT_PASSWORD=${SECURE_GENERATED_PASSWORD}

# Service Authentication
AIRFLOW_ADMIN_USER=admin
AIRFLOW_ADMIN_PASSWORD=${SECURE_PASSPHRASE}
SUPERSET_ADMIN_USER=admin
SUPERSET_ADMIN_PASSWORD=${SECURE_PASSPHRASE}
JUPYTER_TOKEN=${SECURE_PASSPHRASE}

# Security Keys
AIRFLOW_SECRET_KEY=${GENERATED_SECRET_KEY}
AIRFLOW_FERNET_KEY=${GENERATED_FERNET_KEY}
SUPERSET_SECRET_KEY=${GENERATED_SECRET_KEY}

# Resource Allocation
SPARK_MASTER_MEMORY=2g
SPARK_WORKER_MEMORY=8g
SPARK_WORKER_CORES=4
JUPYTER_MEMORY_LIMIT=8G
AIRFLOW_MEMORY_LIMIT=4G
SUPERSET_MEMORY_LIMIT=4G

# Paths and Configuration
LAKEHOUSE_ROOT=./lakehouse-data
HOST_IP=${AUTO_DETECTED_OR_SET}
```

### Service Discovery Patterns
```python
# Internal service communication (within Docker network)
POSTGRES_URL = "postgresql://postgres:${POSTGRES_PASSWORD}@postgres:5432/lakehouse"
MINIO_ENDPOINT = "http://minio:9000"
SPARK_MASTER_URL = "spark://spark-master:7077"
LANCEDB_API_URL = "http://lancedb:8000"

# External access (from host or remote)
POSTGRES_EXTERNAL = "postgresql://postgres:${POSTGRES_PASSWORD}@${HOST_IP}:5432/lakehouse"
MINIO_CONSOLE = "http://${HOST_IP}:9001"
JUPYTER_URL = "http://${HOST_IP}:9040"
SUPERSET_URL = "http://${HOST_IP}:9030"
```

## 📊 Data Connection Patterns

### 1. PostgreSQL Analytics Database

**Connection from JupyterLab/Python:**
```python
import psycopg2
import pandas as pd
import os

# Read credentials from environment
def get_postgres_connection():
    return psycopg2.connect(
        host="postgres",  # Internal Docker network
        database="lakehouse",
        user="postgres",
        password=os.getenv('POSTGRES_PASSWORD')
    )

# Common query patterns
def query_analytics_data(query, params=None):
    """Execute analytical queries against PostgreSQL"""
    with get_postgres_connection() as conn:
        return pd.read_sql(query, conn, params=params)

# Example usage
df = query_analytics_data("""
    SELECT 
        date_trunc('day', created_at) as day,
        product_category,
        COUNT(*) as orders,
        SUM(total_amount) as revenue
    FROM analytics.order_facts 
    WHERE created_at >= %s
    GROUP BY 1, 2
    ORDER BY 1 DESC, 4 DESC
""", params=['2024-01-01'])
```

### 2. MinIO S3-Compatible Storage

**S3 Connection Patterns:**
```python
import boto3
import os
from botocore.exceptions import ClientError

def get_s3_client():
    """Get S3 client for MinIO"""
    return boto3.client(
        's3',
        endpoint_url='http://minio:9000',
        aws_access_key_id=os.getenv('MINIO_ROOT_USER', 'admin'),
        aws_secret_access_key=os.getenv('MINIO_ROOT_PASSWORD'),
        region_name='us-east-1'
    )

def upload_dataframe_to_s3(df, bucket, key):
    """Upload pandas DataFrame to S3 as CSV"""
    s3 = get_s3_client()
    csv_buffer = df.to_csv(index=False)
    s3.put_object(Bucket=bucket, Key=key, Body=csv_buffer)

def download_s3_to_dataframe(bucket, key):
    """Download S3 object to pandas DataFrame"""
    s3 = get_s3_client()
    obj = s3.get_object(Bucket=bucket, Key=key)
    return pd.read_csv(obj['Body'])

# List objects in bucket
def list_s3_objects(bucket, prefix=''):
    """List objects in S3 bucket"""
    s3 = get_s3_client()
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    return [obj['Key'] for obj in response.get('Contents', [])]
```

### 3. DuckDB with S3 Integration

**DuckDB S3 Setup Pattern:**
```python
import duckdb
import os

def setup_duckdb_s3_connection():
    """Setup DuckDB with persistent S3 credentials"""
    conn = duckdb.connect(':memory:')  # Or persistent DB path
    
    # Configure S3 settings
    conn.execute(f"""
        CREATE PERSISTENT SECRET minio_secret (
            TYPE S3,
            KEY_ID '{os.getenv('MINIO_ROOT_USER', 'admin')}',
            SECRET '{os.getenv('MINIO_ROOT_PASSWORD')}',
            ENDPOINT 'minio:9000',
            USE_SSL false,
            URL_STYLE 'path',
            SCOPE 's3://lakehouse'
        );
    """)
    return conn

def query_s3_data(query):
    """Query data directly from S3 using DuckDB"""
    conn = setup_duckdb_s3_connection()
    return conn.execute(query).fetchdf()

# Example multi-file analytics
results = query_s3_data("""
    SELECT 
        product_category,
        COUNT(*) as total_orders,
        SUM(total_amount) as revenue,
        AVG(total_amount) as avg_order_value
    FROM read_csv_auto('s3://lakehouse/raw-data/*.csv', union_by_name=true)
    WHERE order_date >= '2024-01-01'
    GROUP BY product_category
    ORDER BY revenue DESC
""")
```

### 4. LanceDB Vector Database

**LanceDB Integration Patterns:**
```python
import requests
import numpy as np
import pandas as pd

class LanceDBClient:
    def __init__(self, base_url="http://lancedb:8000"):
        self.base_url = base_url
    
    def create_table(self, table_name, schema):
        """Create a new table in LanceDB"""
        response = requests.post(
            f"{self.base_url}/tables/{table_name}",
            json={"schema": schema}
        )
        return response.json()
    
    def insert_vectors(self, table_name, data):
        """Insert vector data into table"""
        response = requests.post(
            f"{self.base_url}/tables/{table_name}/data",
            json=data
        )
        return response.json()
    
    def search_similar(self, table_name, query_vector, limit=10):
        """Search for similar vectors"""
        response = requests.post(
            f"{self.base_url}/tables/{table_name}/search",
            json={
                "query_vector": query_vector,
                "limit": limit
            }
        )
        return response.json()

# Example usage
lance_client = LanceDBClient()

# Create embeddings table
lance_client.create_table("document_embeddings", {
    "id": "string",
    "content": "string", 
    "embedding": "vector(384)",
    "metadata": "struct"
})

# Insert document embeddings
embeddings_data = {
    "data": [
        {
            "id": "doc_1",
            "content": "Machine learning document",
            "embedding": [0.1, 0.2, 0.3, ...],  # 384-dim vector
            "metadata": {"category": "ml", "source": "research"}
        }
    ]
}
lance_client.insert_vectors("document_embeddings", embeddings_data)
```

## 🚀 Spark Integration Patterns

### PySpark Setup in JupyterLab
```python
from pyspark.sql import SparkSession
from pyspark.conf import SparkConf
import os

def create_spark_session():
    """Create Spark session with proper configuration"""
    conf = SparkConf() \
        .setAppName("LakehouseAnalytics") \
        .setMaster("spark://spark-master:7077") \
        .set("spark.sql.adaptive.enabled", "true") \
        .set("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .set("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
        .set("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
        .set("spark.sql.catalog.spark_catalog", "org.apache.iceberg.spark.SparkSessionCatalog") \
        .set("spark.sql.catalog.spark_catalog.type", "hive") \
        .set("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .set("spark.hadoop.fs.s3a.access.key", os.getenv('MINIO_ROOT_USER')) \
        .set("spark.hadoop.fs.s3a.secret.key", os.getenv('MINIO_ROOT_PASSWORD')) \
        .set("spark.hadoop.fs.s3a.path.style.access", "true")
    
    return SparkSession.builder.config(conf=conf).getOrCreate()

# Usage pattern
spark = create_spark_session()

# Read from S3
df = spark.read.option("header", "true").csv("s3a://lakehouse/raw-data/*.csv")

# Process and write back to S3
result = df.groupBy("product_category") \
    .agg({"total_amount": "sum", "*": "count"}) \
    .withColumnRenamed("sum(total_amount)", "total_revenue") \
    .withColumnRenamed("count(1)", "order_count")

result.write.mode("overwrite").parquet("s3a://lakehouse/processed/category_summary")
```

## 📈 Visualization Integration

### Superset Database Connections

**DuckDB Connection String:**
```
duckdb:////app/superset_home/lakehouse.duckdb
```

**PostgreSQL Connection String:**
```
postgresql://postgres:${POSTGRES_PASSWORD}@postgres:5432/lakehouse
```

### Vizro Dashboard Creation

**Vizro Dashboard Pattern:**
```python
import vizro
from vizro import Vizro
from vizro.models import Dashboard, Page, Graph
from vizro.tables import dash_ag_grid
import pandas as pd
import plotly.express as px

# Data loading function
def load_data():
    """Load data from various sources"""
    # From PostgreSQL
    pg_data = pd.read_sql("""
        SELECT * FROM analytics.daily_metrics 
        WHERE date >= CURRENT_DATE - INTERVAL '30 days'
    """, get_postgres_connection())
    
    # From S3 via DuckDB
    duck_conn = setup_duckdb_s3_connection()
    s3_data = duck_conn.execute("""
        SELECT * FROM read_csv_auto('s3://lakehouse/raw-data/recent/*.csv')
    """).fetchdf()
    
    return pg_data, s3_data

# Dashboard configuration
def create_dashboard():
    """Create interactive Vizro dashboard"""
    pg_data, s3_data = load_data()
    
    # Create visualizations
    revenue_chart = Graph(
        figure=px.line(
            pg_data, 
            x='date', 
            y='revenue', 
            color='category',
            title="Daily Revenue Trends"
        )
    )
    
    category_chart = Graph(
        figure=px.bar(
            s3_data.groupby('category').sum().reset_index(),
            x='category',
            y='total_amount',
            title="Revenue by Category"
        )
    )
    
    # Create dashboard
    dashboard = Dashboard(
        pages=[
            Page(
                title="Analytics Overview",
                components=[revenue_chart, category_chart]
            )
        ]
    )
    
    return dashboard

# Run dashboard
app = Vizro().build(create_dashboard())
app.run_server(host="0.0.0.0", port=8050)
```

## 🔄 Airflow DAG Patterns

### ETL Pipeline Template
```python
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.models import Variable
import pandas as pd

default_args = {
    'owner': 'lakehouse-lab',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
}

def extract_data(**context):
    """Extract data from various sources"""
    # From S3
    s3_client = get_s3_client()
    # Implementation here
    
def transform_data(**context):
    """Transform data using pandas/PySpark"""
    # Data transformation logic
    pass

def load_to_postgres(**context):
    """Load transformed data to PostgreSQL"""
    # Loading logic
    pass

def update_vector_embeddings(**context):
    """Update vector embeddings in LanceDB"""
    lance_client = LanceDBClient()
    # Vector update logic
    pass

dag = DAG(
    'lakehouse_etl_pipeline',
    default_args=default_args,
    description='Complete lakehouse ETL pipeline',
    schedule_interval=timedelta(hours=1),
    catchup=False
)

# Define tasks
extract_task = PythonOperator(
    task_id='extract_data',
    python_callable=extract_data,
    dag=dag
)

transform_task = PythonOperator(
    task_id='transform_data',
    python_callable=transform_data,
    dag=dag
)

load_task = PythonOperator(
    task_id='load_to_postgres',
    python_callable=load_to_postgres,
    dag=dag
)

vector_task = PythonOperator(
    task_id='update_vector_embeddings',
    python_callable=update_vector_embeddings,
    dag=dag
)

# Set dependencies
extract_task >> transform_task >> [load_task, vector_task]
```

## 🐍 JupyterLab Package Management

### Package Manager Integration
The Lakehouse Lab includes a built-in package manager for JupyterLab:

```python
# In any Jupyter notebook cell
%run /app/notebook_package_manager.py

# Install packages
install_package("scikit-learn>=1.3.0")
install_package("transformers")
install_package("sentence-transformers")

# Install from requirements
install_from_requirements("requirements.txt")

# List installed packages
list_packages()

# Package management with persistence
def setup_ml_environment():
    """Setup ML environment with common packages"""
    packages = [
        "scikit-learn>=1.3.0",
        "xgboost>=1.7.0", 
        "lightgbm>=4.0.0",
        "transformers>=4.30.0",
        "sentence-transformers>=2.2.0",
        "faiss-cpu>=1.7.0",
        "umap-learn>=0.5.0",
        "plotly>=5.15.0",
        "seaborn>=0.12.0"
    ]
    
    for package in packages:
        install_package(package)

# Usage
setup_ml_environment()
```

### Environment Management
```python
import os
import sys

# Add custom paths
sys.path.append('/app/custom_modules')

# Environment variables access
def get_environment_config():
    """Get all environment configuration"""
    return {
        'postgres_url': f"postgresql://postgres:{os.getenv('POSTGRES_PASSWORD')}@postgres:5432/lakehouse",
        'minio_endpoint': 'http://minio:9000',
        'minio_access_key': os.getenv('MINIO_ROOT_USER'),
        'minio_secret_key': os.getenv('MINIO_ROOT_PASSWORD'),
        'spark_master': 'spark://spark-master:7077',
        'lancedb_url': 'http://lancedb:8000'
    }

config = get_environment_config()
```

## 🔧 Development Best Practices

### 1. Data Pipeline Development
```python
class LakehousePipeline:
    """Template for lakehouse data pipelines"""
    
    def __init__(self):
        self.config = get_environment_config()
        self.pg_conn = get_postgres_connection()
        self.s3_client = get_s3_client()
        self.spark = create_spark_session()
        self.lance_client = LanceDBClient()
    
    def extract(self, source_config):
        """Extract data from sources"""
        if source_config['type'] == 's3':
            return self.extract_from_s3(source_config)
        elif source_config['type'] == 'postgres':
            return self.extract_from_postgres(source_config)
        # Add more source types
    
    def transform(self, data, transformations):
        """Apply transformations"""
        for transform in transformations:
            data = self.apply_transformation(data, transform)
        return data
    
    def load(self, data, destination_config):
        """Load data to destinations"""
        if destination_config['type'] == 'postgres':
            self.load_to_postgres(data, destination_config)
        elif destination_config['type'] == 's3':
            self.load_to_s3(data, destination_config)
        elif destination_config['type'] == 'lancedb':
            self.load_to_lancedb(data, destination_config)
```

### 2. Error Handling and Logging
```python
import logging
from functools import wraps

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('lakehouse-pipeline')

def retry_on_failure(max_retries=3, delay=1):
    """Decorator for retrying failed operations"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1} failed: {e}")
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(delay * (2 ** attempt))  # Exponential backoff
            return wrapper
        return decorator

@retry_on_failure(max_retries=3)
def reliable_s3_upload(data, bucket, key):
    """Upload with retry logic"""
    s3_client = get_s3_client()
    s3_client.put_object(Bucket=bucket, Key=key, Body=data)
```

### 3. Configuration Management
```python
import yaml
from pathlib import Path

class LakehouseConfig:
    """Centralized configuration management"""
    
    def __init__(self, config_path="/app/config.yaml"):
        self.config_path = Path(config_path)
        self.config = self.load_config()
    
    def load_config(self):
        """Load configuration from file and environment"""
        base_config = {
            'databases': {
                'postgres': {
                    'host': 'postgres',
                    'port': 5432,
                    'database': 'lakehouse',
                    'user': 'postgres',
                    'password': os.getenv('POSTGRES_PASSWORD')
                }
            },
            'storage': {
                's3': {
                    'endpoint': 'http://minio:9000',
                    'access_key': os.getenv('MINIO_ROOT_USER'),
                    'secret_key': os.getenv('MINIO_ROOT_PASSWORD'),
                    'bucket': 'lakehouse'
                }
            },
            'processing': {
                'spark': {
                    'master': 'spark://spark-master:7077',
                    'app_name': 'lakehouse-processing'
                }
            },
            'ml': {
                'lancedb': {
                    'url': 'http://lancedb:8000'
                }
            }
        }
        
        # Merge with file-based config if exists
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                file_config = yaml.safe_load(f)
                base_config.update(file_config)
        
        return base_config
    
    def get(self, key_path, default=None):
        """Get configuration value using dot notation"""
        keys = key_path.split('.')
        value = self.config
        for key in keys:
            value = value.get(key, {})
            if not value:
                return default
        return value

# Usage
config = LakehouseConfig()
postgres_config = config.get('databases.postgres')
```

## 🚀 Advanced Integration Patterns

### 1. Real-time Data Processing
```python
import asyncio
import aioredis
from kafka import KafkaConsumer
import json

class RealTimeProcessor:
    """Real-time data processing pipeline"""
    
    def __init__(self):
        self.pg_conn = get_postgres_connection()
        self.lance_client = LanceDBClient()
    
    async def process_stream(self, topic):
        """Process streaming data"""
        consumer = KafkaConsumer(
            topic,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        
        for message in consumer:
            await self.process_message(message.value)
    
    async def process_message(self, data):
        """Process individual message"""
        # Transform data
        processed_data = self.transform_data(data)
        
        # Store in PostgreSQL for immediate queries
        await self.store_in_postgres(processed_data)
        
        # Update vector embeddings if needed
        if self.requires_vector_update(data):
            await self.update_vectors(processed_data)
```

### 2. ML Model Deployment
```python
import mlflow
import joblib
from sklearn.base import BaseEstimator

class LakehouseMLModel:
    """ML Model deployment in lakehouse environment"""
    
    def __init__(self, model_name, version="latest"):
        self.model_name = model_name
        self.version = version
        self.model = self.load_model()
        self.config = LakehouseConfig()
    
    def load_model(self):
        """Load model from MLflow or file system"""
        # Implementation for model loading
        pass
    
    def predict(self, features):
        """Make predictions"""
        return self.model.predict(features)
    
    def batch_predict(self, input_table, output_table):
        """Batch prediction pipeline"""
        # Load data from PostgreSQL
        data = pd.read_sql(f"SELECT * FROM {input_table}", self.pg_conn)
        
        # Make predictions
        predictions = self.predict(data.drop(['id'], axis=1))
        
        # Store results
        results = data[['id']].copy()
        results['prediction'] = predictions
        results['prediction_timestamp'] = datetime.now()
        
        results.to_sql(output_table, self.pg_conn, if_exists='append', index=False)
    
    def update_vector_store(self, embeddings, metadata):
        """Update vector store with model embeddings"""
        self.lance_client.insert_vectors("model_embeddings", {
            "data": [
                {
                    "id": f"prediction_{i}",
                    "embedding": emb.tolist(),
                    "metadata": meta
                }
                for i, (emb, meta) in enumerate(zip(embeddings, metadata))
            ]
        })
```

### 3. Multi-Service Orchestration
```python
import concurrent.futures
import asyncio

class LakehouseOrchestrator:
    """Orchestrate complex multi-service operations"""
    
    def __init__(self):
        self.services = {
            'postgres': get_postgres_connection(),
            's3': get_s3_client(),
            'spark': create_spark_session(),
            'lancedb': LanceDBClient()
        }
    
    async def parallel_processing(self, tasks):
        """Execute tasks in parallel across services"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            loop = asyncio.get_event_loop()
            futures = [
                loop.run_in_executor(executor, self.execute_task, task)
                for task in tasks
            ]
            results = await asyncio.gather(*futures)
        return results
    
    def execute_task(self, task):
        """Execute individual task on appropriate service"""
        service = self.services[task['service']]
        method = getattr(self, f"execute_{task['type']}")
        return method(service, task['params'])
```

## 🔍 Monitoring and Observability

### Health Check Patterns
```python
import requests
from datetime import datetime

class LakehouseHealthChecker:
    """Monitor health of all lakehouse services"""
    
    def __init__(self):
        self.services = {
            'postgres': {'host': 'postgres', 'port': 5432},
            'minio': {'url': 'http://minio:9000/minio/health/live'},
            'spark': {'url': 'http://spark-master:8080'},
            'jupyter': {'url': 'http://jupyter:8888'},
            'superset': {'url': 'http://superset:8088/health'},
            'airflow': {'url': 'http://airflow-webserver:8080/health'},
            'lancedb': {'url': 'http://lancedb:8000/health'},
            'vizro': {'url': 'http://vizro:8050'}
        }
    
    def check_service_health(self, service_name):
        """Check health of individual service"""
        service_config = self.services[service_name]
        
        if service_name == 'postgres':
            return self.check_postgres_health(service_config)
        else:
            return self.check_http_health(service_config['url'])
    
    def check_postgres_health(self, config):
        """Check PostgreSQL health"""
        try:
            conn = psycopg2.connect(
                host=config['host'],
                port=config['port'],
                user='postgres',
                password=os.getenv('POSTGRES_PASSWORD'),
                database='lakehouse',
                connect_timeout=5
            )
            conn.close()
            return {'status': 'healthy', 'timestamp': datetime.now()}
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e), 'timestamp': datetime.now()}
    
    def check_http_health(self, url):
        """Check HTTP service health"""
        try:
            response = requests.get(url, timeout=5)
            return {
                'status': 'healthy' if response.status_code == 200 else 'unhealthy',
                'status_code': response.status_code,
                'timestamp': datetime.now()
            }
        except Exception as e:
            return {'status': 'unhealthy', 'error': str(e), 'timestamp': datetime.now()}
    
    def get_system_health(self):
        """Get overall system health"""
        health_status = {}
        for service_name in self.services:
            health_status[service_name] = self.check_service_health(service_name)
        
        return {
            'overall_status': 'healthy' if all(
                h['status'] == 'healthy' for h in health_status.values()
            ) else 'degraded',
            'services': health_status,
            'timestamp': datetime.now()
        }
```

## 📝 Code Generation Templates

When generating code for Lakehouse Lab, use these patterns:

### Database Query Template
```python
def query_template(table_name, conditions=None, aggregations=None):
    base_query = f"SELECT * FROM {table_name}"
    
    if conditions:
        where_clause = " AND ".join(conditions)
        base_query += f" WHERE {where_clause}"
    
    if aggregations:
        # Add GROUP BY and aggregation logic
        pass
    
    return base_query
```

### Data Pipeline Template
```python
def pipeline_template(source, transformations, destination):
    """Generate data pipeline code"""
    pipeline_code = f"""
def run_pipeline():
    # Extract from {source}
    data = extract_from_{source}()
    
    # Transform
    {chr(10).join(f'    data = {transform}(data)' for transform in transformations)}
    
    # Load to {destination}
    load_to_{destination}(data)
    
    return data
"""
    return pipeline_code
```

This guide provides LLMs with comprehensive system understanding for effective code generation, troubleshooting, and development assistance within the Lakehouse Lab environment.