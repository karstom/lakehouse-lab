    dag=dag,
)

# Set dependencies
check_deps >> configure_s3 >> extract_task >> transform_task >> quality_check
EOF

    # Enhanced Data Quality Checks DAG
    cat <<'EOF' > "$LAKEHOUSE_ROOT/airflow/dags/data_quality_check.py"
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
import logging

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
    description='Enhanced data quality monitoring using DuckDB 1.3.0',
    schedule_interval=timedelta(hours=12),
    catchup=False,
    tags=['data-quality', 'monitoring', 'duckdb'],
)

def run_comprehensive_quality_checks(**context):
    """Run comprehensive data quality checks using DuckDB 1.3.0"""
    import duckdb
    
    conn = duckdb.connect()
    
    try:
        # Configure S3 access
        conn.execute("INSTALL httpfs")
        conn.execute("LOAD httpfs")
        conn.execute("SET s3_endpoint='minio:9000'")
        conn.execute("SET s3_access_key_id='minio'")
        conn.execute("SET s3_secret_access_key='minio123'")
        conn.execute("SET s3_use_ssl=false")
        conn.execute("SET s3_url_style='path'")
        
        # Enhanced quality checks
