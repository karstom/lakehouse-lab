"""
PostgreSQL Analytics DAG
Demonstrates PostgreSQL integration for Lakehouse Lab
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
    'postgres_analytics_dag',
    default_args=default_args,
    description='PostgreSQL analytics and data processing',
    schedule_interval=timedelta(hours=8),
    catchup=False,
    tags=['postgresql', 'analytics', 'sql']
)

def test_postgres_connection(**context):
    """Test PostgreSQL connection"""
    try:
        import psycopg2
        
        # Connection parameters
        conn_params = {
            'host': 'postgres',
            'port': 5432,
            'database': 'lakehouse',
            'user': 'postgres',
            'password': 'postgres'
        }
        
        # Test connection
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        
        # Test query
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        logging.info(f"✅ PostgreSQL connected: {version}")
        
        cursor.close()
        conn.close()
        
        return "postgres_connected"
        
    except Exception as e:
        logging.error(f"❌ PostgreSQL connection failed: {e}")
        logging.info("💡 This is normal if PostgreSQL is not fully initialized yet")
        return "postgres_not_ready"

def run_sample_analytics(**context):
    """Run sample PostgreSQL analytics"""
    try:
        import psycopg2
        
        conn_params = {
            'host': 'postgres',
            'port': 5432,
            'database': 'lakehouse',
            'user': 'postgres',
            'password': 'postgres'
        }
        
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        
        # Create a sample table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sample_analytics (
                id SERIAL PRIMARY KEY,
                metric_name VARCHAR(100),
                metric_value DECIMAL(10,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert sample data
        cursor.execute("""
            INSERT INTO sample_analytics (metric_name, metric_value) 
            VALUES ('pipeline_runs', 1.0), ('data_quality_score', 98.5)
            ON CONFLICT DO NOTHING
        """)
        
        # Run analytics query
        cursor.execute("SELECT COUNT(*) FROM sample_analytics")
        count = cursor.fetchone()[0]
        
        logging.info(f"📊 Sample analytics table has {count} records")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return "analytics_completed"
        
    except Exception as e:
        logging.error(f"❌ PostgreSQL analytics failed: {e}")
        return "analytics_failed"

# Define tasks
postgres_test_task = PythonOperator(
    task_id='test_postgres_connection',
    python_callable=test_postgres_connection,
    dag=dag
)

analytics_task = PythonOperator(
    task_id='run_sample_analytics',
    python_callable=run_sample_analytics,
    dag=dag
)

# Set dependencies
postgres_test_task >> analytics_task