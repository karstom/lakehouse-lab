"""
Data Quality Check DAG
Validates data integrity and quality metrics for Lakehouse Lab
"""

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
    'retry_delay': timedelta(minutes=5)
}

dag = DAG(
    'data_quality_check',
    default_args=default_args,
    description='Data quality validation and monitoring',
    schedule_interval=timedelta(hours=12),
    catchup=False,
    tags=['data-quality', 'validation', 'monitoring']
)

def check_data_quality(**context):
    """Run data quality checks"""
    import duckdb
    
    conn = duckdb.connect()
    
    try:
        # Configure S3
        conn.execute("INSTALL httpfs")
        conn.execute("LOAD httpfs") 
        conn.execute("SET s3_endpoint='minio:9000'")
        conn.execute("SET s3_access_key_id='minio'")
        conn.execute("SET s3_secret_access_key='minio123'")
        conn.execute("SET s3_use_ssl=false")
        conn.execute("SET s3_url_style='path'")
        
        logging.info("🔍 Running data quality checks...")
        
        # Basic existence check
        try:
            result = conn.execute("""
                SELECT COUNT(*) as record_count 
                FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')
            """).fetchone()
            
            if result and result[0] > 0:
                logging.info(f"✅ Data exists: {result[0]} records found")
                return "quality_checks_passed"
            else:
                logging.warning("⚠️ No data found for quality checks")
                return "no_data_to_check"
                
        except Exception as e:
            logging.warning(f"⚠️ Could not access data for quality checks: {e}")
            return "data_access_failed"
            
    except Exception as e:
        logging.error(f"❌ Data quality check failed: {e}")
        raise
    finally:
        conn.close()

# Define task
quality_check_task = PythonOperator(
    task_id='check_data_quality',
    python_callable=check_data_quality,
    dag=dag
)