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
        return "s3_configured"
    except Exception as e:
        logging.error(f"❌ DuckDB S3 configuration failed: {e}")
        raise
    finally:
        conn.close()

def extract_data(**context):
    """Extract sample data from MinIO using DuckDB"""
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
        
        try:
            # Query data from MinIO
            result = conn.execute("""
                SELECT COUNT(*) as record_count
                FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')
            """).fetchone()
            
            record_count = result[0] if result else 0
            logging.info(f"✅ Found {record_count} records in sample data")
            
            # Store result for next task
            context['task_instance'].xcom_push(key='record_count', value=record_count)
            return record_count
            
        except Exception as e:
            logging.warning(f"⚠️ Could not read sample data: {e}")
            logging.info("This is expected if sample data hasn't been created yet")
            context['task_instance'].xcom_push(key='record_count', value=0)
            return 0
            
    finally:
        conn.close()

def transform_data(**context):
    """Transform data using DuckDB"""
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
        
        try:
            # Get record count from previous task
