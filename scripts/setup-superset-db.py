#!/usr/bin/env python3
"""
Setup DuckDB-S3 database connection in Superset
"""
import os
import sys
import json

# Add Superset to Python path
sys.path.append('/app/superset')
os.environ.setdefault('SUPERSET_CONFIG_PATH', '/app/superset/superset_config.py')

try:
    print("🔧 Setting up DuckDB-S3 database connection...")
    
    # Import and create app first
    from superset import create_app
    app = create_app()
    
    # Import models inside application context
    with app.app_context():
        from superset import db
        from superset.models.core import Database
        
        # Database connection configuration
        database_config = {
            "database_name": "DuckDB-S3",
            "sqlalchemy_uri": "duckdb:////app/superset_home/lakehouse.duckdb",
            "allow_dml": True,  # Enable Data Manipulation Language
            "allow_file_upload": True,  # Enable CSV file uploads
            "allow_ctas": True,  # Enable CREATE TABLE AS SELECT
            "allow_cvas": True,  # Enable CREATE VIEW AS SELECT  
            "allow_run_async": True,  # Enable async query execution
            "extra": json.dumps({
                "allows_virtual_table_explore": True,
                "disable_data_preview": False,
                "engine_params": {
                    "connect_args": {
                        "preload_extensions": ["httpfs"],
                        "config": {
                            "s3_endpoint": "minio:9000",
                            "s3_access_key_id": os.environ.get('MINIO_ROOT_USER', 'admin'),
                            "s3_secret_access_key": os.environ.get('MINIO_ROOT_PASSWORD', 'changeme'),
                            "s3_url_style": "path",
                            "s3_use_ssl": "false"
                        }
                    }
                }
            })
        }
        
        # Check if database connection already exists
        existing_db = db.session.query(Database).filter_by(
            database_name=database_config["database_name"]
        ).first()
        
        if existing_db:
            # Update existing connection
            existing_db.sqlalchemy_uri = database_config["sqlalchemy_uri"]
            existing_db.extra = database_config["extra"]
            existing_db.allow_dml = database_config["allow_dml"]
            existing_db.allow_file_upload = database_config["allow_file_upload"]
            existing_db.allow_ctas = database_config["allow_ctas"]
            existing_db.allow_cvas = database_config["allow_cvas"]
            existing_db.allow_run_async = database_config["allow_run_async"]
            db.session.commit()
            print(f"✅ Updated existing database connection: {database_config['database_name']}")
        else:
            # Create new database connection
            new_db = Database(
                database_name=database_config["database_name"],
                sqlalchemy_uri=database_config["sqlalchemy_uri"],
                extra=database_config["extra"],
                allow_dml=database_config["allow_dml"],
                allow_file_upload=database_config["allow_file_upload"],
                allow_ctas=database_config["allow_ctas"],
                allow_cvas=database_config["allow_cvas"],
                allow_run_async=database_config["allow_run_async"]
            )
            db.session.add(new_db)
            db.session.commit()
            print(f"✅ Created new database connection: {database_config['database_name']}")
        
        print("✅ DuckDB-S3 connection configured with S3 settings and DML/DDL permissions")
        
except Exception as e:
    print(f"❌ Database connection setup failed: {e}")
    print("ℹ️ Manual setup may be required - check Superset UI")
    import traceback
    traceback.print_exc()
    sys.exit(1)