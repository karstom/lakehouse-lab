#!/usr/bin/env python3
"""
Superset Database Setup Script for Lakehouse Lab
Configures DuckDB with S3 integration for analytics
"""

import duckdb
import os

print("🔧 Setting up DuckDB for Superset BI platform...")
print("📦 DuckDB Version:", duckdb.__version__)

try:
    # Connect to DuckDB database
    db_path = "/app/superset_home/lakehouse.duckdb"
    conn = duckdb.connect(db_path)
    print(f"✅ Connected to DuckDB: {db_path}")
    
    # Install and load S3 extension
    conn.execute("INSTALL httpfs")
    conn.execute("LOAD httpfs")
    print("✅ Loaded httpfs extension for S3 access")
    
    # Configure S3/MinIO settings with environment variables
    minio_user = os.environ.get('MINIO_ROOT_USER', 'minio')
    minio_password = os.environ.get('MINIO_ROOT_PASSWORD', 'minio123')
    
    # Create S3 configuration function
    conn.execute(f"""
        CREATE OR REPLACE FUNCTION configure_s3() RETURNS VARCHAR AS $$
        BEGIN
            SET s3_endpoint='minio:9000';
            SET s3_access_key_id='{minio_user}';
            SET s3_secret_access_key='{minio_password}';
            SET s3_use_ssl=false;
            SET s3_url_style='path';
            RETURN 'S3 configured successfully';
        END;
    """)
    print("✅ Created S3 configuration function")
    
    # Configure S3 settings immediately
    conn.execute("SELECT configure_s3()")
    print("✅ S3 settings configured for current session")
    
    # Test S3 connection and create a view for easy access
    try:
        conn.execute("""
            CREATE OR REPLACE VIEW sample_orders AS 
            SELECT * FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')
        """)
        print("✅ Successfully created sample_orders view")
    except Exception as e:
        print(f"ℹ️ Note: Could not create sample_orders view (sample data may not exist yet): {e}")
    
    # Create utility functions for Superset users
    try:
        conn.execute("""
            CREATE OR REPLACE FUNCTION list_s3_files(bucket_path VARCHAR DEFAULT 'lakehouse/raw-data/*') 
            RETURNS TABLE(file_path VARCHAR) AS (
                SELECT unnest(glob('s3://' || bucket_path)) as file_path
            )
        """)
        print("✅ Created S3 utility functions")
    except Exception as e:
        print(f"ℹ️ Note: Could not create utility functions: {e}")
    
    # Create other useful views for different data sources
    try:
        conn.execute("""
            CREATE OR REPLACE VIEW list_s3_files AS 
            SELECT * FROM glob('s3://lakehouse/**/*')
        """)
        print("✅ Created S3 file listing view")
    except Exception as e:
        print(f"ℹ️ Note: Could not create file listing view: {e}")
    
    conn.commit()
    print("✅ DuckDB configuration completed successfully")
    print("📝 Connection URI for Superset: duckdb:////app/superset_home/lakehouse.duckdb")
    print("💡 To use S3 in queries, run: SELECT configure_s3(); first")
    
except Exception as e:
    print(f"❌ DuckDB configuration error: {e}")
finally:
    conn.close()