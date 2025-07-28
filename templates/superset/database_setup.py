    
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
    print("✅ DuckDB 1.3.0 configuration completed successfully for Issue #1 fix")
    print("📝 Connection URI for Superset: duckdb:////app/superset_home/lakehouse.duckdb")
    print("💡 To use S3 in queries, run: SELECT configure_s3(); first")
    
except Exception as e:
    print(f"❌ DuckDB configuration error: {e}")
finally:
    conn.close()
EOF
    
    log_success "Enhanced DuckDB configuration script created for Superset Issue #1 fix"
    
    # Create Superset database connection programmatically
    log_info "Setting up Superset database connection with S3 configuration..."
    
    cat > "$LAKEHOUSE_ROOT/superset/add_duckdb_connection.py" << 'EOF'
import os
import sys
sys.path.append('/app/superset')
os.environ.setdefault('SUPERSET_CONFIG_PATH', '/app/superset/superset_config.py')

from superset import db
from superset.models.core import Database
from superset.utils.database import get_or_create_db
import json

try:
    # Database connection configuration with S3 settings
    database_config = {
        "database_name": "DuckDB-S3",
        "sqlalchemy_uri": "duckdb:////app/superset_home/lakehouse.duckdb",
        "extra": json.dumps({
            "engine_params": {
                "connect_args": {
                    "preload_extensions": ["httpfs"],
                    "config": {
                        "s3_endpoint": "minio:9000",
                        "s3_access_key_id": "minio", 
                        "s3_secret_access_key": "minio123",
                        "s3_url_style": "path",
                        "s3_use_ssl": "false"
                    }
                }
            }
        })
    }
    
    # Check if database already exists
    existing_db = db.session.query(Database).filter_by(
        database_name=database_config["database_name"]
    ).first()
    
    if existing_db:
        # Update existing database with new S3 configuration
        existing_db.sqlalchemy_uri = database_config["sqlalchemy_uri"]
        existing_db.extra = database_config["extra"]
        db.session.commit()
        print(f"✅ Updated existing database connection: {database_config['database_name']}")
    else:
        # Create new database connection
        new_db = Database(
            database_name=database_config["database_name"],
            sqlalchemy_uri=database_config["sqlalchemy_uri"],
            extra=database_config["extra"]
        )
        db.session.add(new_db)
        db.session.commit()
        print(f"✅ Created new database connection: {database_config['database_name']}")
    
    print("✅ Superset database connection configured with S3 settings")
    print("📝 Connection name: DuckDB-S3")
    print("🔗 S3 queries can now be run without manual configuration")
    
except Exception as e:
    print(f"❌ Failed to configure Superset database connection: {e}")
    print("ℹ️ You can manually create the connection in Superset UI")
