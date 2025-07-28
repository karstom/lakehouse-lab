"""
Sample DuckDB Data Pipeline DAG
Demonstrates DuckDB analytics with S3 integration for Lakehouse Lab
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
import logging

# DAG default arguments
default_args = {
    'owner': 'lakehouse-lab',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
}

# Create the DAG
dag = DAG(
    'sample_duckdb_pipeline',
    default_args=default_args,
    description='Sample DuckDB analytics pipeline with S3 integration',
    schedule_interval=timedelta(hours=6),
    catchup=False,
    tags=['duckdb', 's3', 'analytics', 'sample']
)

def check_dependencies(**context):
    """Check if required dependencies are available"""
    try:
        import duckdb
        import logging
        
        # Test DuckDB connection
        conn = duckdb.connect()
        conn.execute("SELECT 1 as test").fetchone()
        conn.close()
        logging.info("✅ DuckDB connection test successful")
        
        return "dependencies_ok"
    except ImportError as e:
        logging.error(f"❌ Missing dependency: {e}")
        raise
    except Exception as e:
        logging.error(f"❌ DuckDB test failed: {e}")
        raise

def configure_duckdb_s3(**context):
    """Configure DuckDB for S3 access"""
    import duckdb
    
    conn = duckdb.connect()
    
    try:
        # Install and configure httpfs for S3 access
        conn.execute("INSTALL httpfs")
        conn.execute("LOAD httpfs")
        
        # Set S3 configuration for MinIO
        conn.execute("SET s3_endpoint='minio:9000'")
        conn.execute("SET s3_access_key_id='minio'")
        conn.execute("SET s3_secret_access_key='minio123'")
        conn.execute("SET s3_use_ssl=false")
        conn.execute("SET s3_url_style='path'")
        
        logging.info("✅ DuckDB S3 configuration completed")
        conn.close()
        return "s3_configured"
        
    except Exception as e:
        logging.error(f"❌ DuckDB S3 configuration failed: {e}")
        conn.close()
        raise

def analyze_sample_data(**context):
    """Run analytics on sample data"""
    import duckdb
    
    conn = duckdb.connect()
    
    try:
        # Configure S3 first
        conn.execute("INSTALL httpfs")
        conn.execute("LOAD httpfs")
        conn.execute("SET s3_endpoint='minio:9000'")
        conn.execute("SET s3_access_key_id='minio'")
        conn.execute("SET s3_secret_access_key='minio123'")
        conn.execute("SET s3_use_ssl=false")
        conn.execute("SET s3_url_style='path'")
        
        # Try to read sample data from S3
        try:
            result = conn.execute("""
                SELECT COUNT(*) as record_count 
                FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')
            """).fetchone()
            
            if result:
                logging.info(f"✅ Found {result[0]} records in sample data")
                
                # Run some basic analytics
                analytics_results = conn.execute("""
                    SELECT 
                        product_category,
                        COUNT(*) as order_count,
                        ROUND(AVG(total_amount), 2) as avg_amount,
                        ROUND(SUM(total_amount), 2) as total_revenue
                    FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')
                    GROUP BY product_category
                    ORDER BY total_revenue DESC
                """).fetchall()
                
                logging.info("📊 Analytics Results:")
                for row in analytics_results:
                    logging.info(f"   Category: {row[0]}, Orders: {row[1]}, Avg: ${row[2]}, Total: ${row[3]}")
                    
                return "analytics_completed"
            else:
                logging.warning("⚠️ Sample data appears to be empty")
                return "no_data"
                
        except Exception as e:
            logging.warning(f"⚠️ Could not read sample data from S3: {e}")
            logging.info("💡 This is normal if sample data hasn't been generated yet")
            return "no_sample_data"
            
    except Exception as e:
        logging.error(f"❌ Analytics failed: {e}")
        raise
    finally:
        conn.close()

def generate_summary_report(**context):
    """Generate a summary report of the pipeline execution"""
    import duckdb
    from datetime import datetime
    
    logging.info("📋 DuckDB Pipeline Summary Report")
    logging.info("=" * 50)
    logging.info(f"🕐 Execution Time: {datetime.now()}")
    logging.info(f"🏷️  DAG: {context['dag'].dag_id}")
    logging.info(f"📅 Run Date: {context['ds']}")
    
    # Test DuckDB capabilities
    conn = duckdb.connect()
    
    try:
        # Show DuckDB version
        version = conn.execute("SELECT version()").fetchone()[0]
        logging.info(f"🦆 DuckDB Version: {version}")
        
        # Test S3 connectivity
        conn.execute("INSTALL httpfs")
        conn.execute("LOAD httpfs")
        logging.info("✅ S3/HTTP filesystem support available")
        
        # Test basic analytics
        result = conn.execute("SELECT 1+1 as test_calc, 'DuckDB Works!' as message").fetchone()
        logging.info(f"🧮 Test Calculation: {result[0]}")
        logging.info(f"💬 Message: {result[1]}")
        
    except Exception as e:
        logging.error(f"❌ Summary generation failed: {e}")
    finally:
        conn.close()
    
    logging.info("=" * 50)
    logging.info("🎉 Pipeline execution completed!")
    
    return "summary_generated"

# Define tasks
check_deps_task = PythonOperator(
    task_id='check_dependencies',
    python_callable=check_dependencies,
    dag=dag
)

configure_s3_task = PythonOperator(
    task_id='configure_duckdb_s3',
    python_callable=configure_duckdb_s3,
    dag=dag
)

analyze_data_task = PythonOperator(
    task_id='analyze_sample_data',
    python_callable=analyze_sample_data,
    dag=dag
)

summary_task = PythonOperator(
    task_id='generate_summary_report',
    python_callable=generate_summary_report,
    dag=dag
)

# Set task dependencies
check_deps_task >> configure_s3_task >> analyze_data_task >> summary_task