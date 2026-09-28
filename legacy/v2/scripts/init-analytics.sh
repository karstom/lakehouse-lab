#!/bin/bash
# ==============================================================================
# init-analytics.sh - Analytics Environment Setup Module
# ==============================================================================
# Sets up Jupyter notebooks and generates sample data

set -e

# Get script directory and source shared utilities
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
source "$SCRIPT_DIR/lib/init-core.sh"

# ==============================================================================
# JUPYTER NOTEBOOK DEPLOYMENT
# ==============================================================================

deploy_jupyter_notebooks() {
    log_info "Deploying Jupyter notebooks from templates..."
    
    local template_dir="$(dirname "$SCRIPT_DIR")/templates/jupyter/notebooks"
    local target_dir="$LAKEHOUSE_ROOT/notebooks"
    
    # Ensure target directory exists
    ensure_directory "$target_dir" "Jupyter notebooks directory"
    
    # Check if template directory exists
    if [ ! -d "$template_dir" ]; then
        log_error "Template directory not found: $template_dir"
        return 1
    fi
    
    # Copy notebook files
    log_info "Copying notebook files from $template_dir to $target_dir"
    
    local notebook_files=(
        "00_Package_Manager.ipynb"
        "01_Getting_Started.ipynb"
        "02_PostgreSQL_Analytics.ipynb"
        "03_Iceberg_Tables.ipynb"
        "04_Vizro_Interactive_Dashboards.ipynb"
        "05_LanceDB_Vector_Search.ipynb"
        "06_Advanced_Analytics_Vizro_LanceDB.ipynb"
        "07_Interactive_Dashboard_Development.ipynb"
    )
    
    local copied_count=0
    
    for notebook_file in "${notebook_files[@]}"; do
        local source_file="$template_dir/$notebook_file"
        local target_file="$target_dir/$notebook_file"
        
        if [ -f "$source_file" ]; then
            if cp "$source_file" "$target_file"; then
                log_success "Deployed notebook: $notebook_file"
                copied_count=$((copied_count + 1))
                
                # Set appropriate permissions
                chmod 644 "$target_file"
            else
                log_error "Failed to copy notebook: $notebook_file"
                return 1
            fi
        else
            log_warning "Template file not found: $notebook_file"
        fi
    done
    
    if [ $copied_count -gt 0 ]; then
        log_success "Deployed $copied_count Jupyter notebook(s)"
    else
        log_error "No notebook files were deployed"
        return 1
    fi
    
    # Copy the notebook package manager
    local package_manager_source="$(dirname "$SCRIPT_DIR")/templates/notebook_package_manager.py"
    local package_manager_target="$target_dir/notebook_package_manager.py"
    
    if [ -f "$package_manager_source" ]; then
        if cp "$package_manager_source" "$package_manager_target"; then
            log_success "Deployed package manager: notebook_package_manager.py"
            chmod 644 "$package_manager_target"
        else
            log_warning "Failed to copy package manager (notebooks will still work)"
        fi
    else
        log_warning "Package manager not found: $package_manager_source"
    fi
    
    # Copy dashboard support files
    local dashboard_source_dir="$(dirname "$SCRIPT_DIR")/templates/jupyter"
    local dashboard_files=(
        "simple_working_dashboard.py"
        "DASHBOARD_DEVELOPMENT_README.md"
    )
    
    for dashboard_file in "${dashboard_files[@]}"; do
        local dashboard_source="$dashboard_source_dir/$dashboard_file"
        local dashboard_target="$LAKEHOUSE_ROOT/shared-notebooks/$dashboard_file"
        
        # Ensure target directory exists
        ensure_directory "$LAKEHOUSE_ROOT/shared-notebooks" "Shared notebooks directory"
        
        if [ -f "$dashboard_source" ]; then
            if cp "$dashboard_source" "$dashboard_target"; then
                log_success "Deployed dashboard support: $dashboard_file"
                chmod 644 "$dashboard_target"
            else
                log_warning "Failed to copy dashboard support: $dashboard_file"
            fi
        else
            log_warning "Dashboard support file not found: $dashboard_file"
        fi
    done
}

# ==============================================================================
# SAMPLE DATA GENERATION
# ==============================================================================

generate_sample_data() {
    log_info "Generating sample data for analytics..."
    
    local template_dir="$(dirname "$SCRIPT_DIR")/templates/sample-data"
    local generator_script="$template_dir/generate_orders.py"
    
    # Check if generator script exists
    if [ ! -f "$generator_script" ]; then
        log_error "Sample data generator not found: $generator_script"
        return 1
    fi
    
    # Copy generator script to temporary location
    local temp_script="/tmp/generate_sample_data.py"
    if ! cp "$generator_script" "$temp_script"; then
        log_error "Failed to copy sample data generator"
        return 1
    fi
    
    # Make script executable
    chmod +x "$temp_script"
    
    # Run the Python script to generate sample data
    log_info "Running sample data generation script..."
    
    if python3 "$temp_script"; then
        log_success "Sample data generation completed"
        
        # Verify the generated file
        local sample_file="/tmp/sample_orders.csv"
        if [ -f "$sample_file" ] && [ -s "$sample_file" ]; then
            local line_count=$(wc -l < "$sample_file")
            log_success "Generated sample CSV with $line_count lines"
            
            # Upload to MinIO if available
            if command -v mc >/dev/null 2>&1 && mc ls lakehouse/ >/dev/null 2>&1; then
                log_info "Uploading sample data to MinIO..."
                
                if mc cp "$sample_file" "lakehouse/lakehouse/raw-data/sample_orders.csv" >/dev/null 2>&1; then
                    log_success "Sample data uploaded to MinIO: s3://lakehouse/raw-data/sample_orders.csv"
                else
                    log_warning "Failed to upload sample data to MinIO"
                fi
            else
                log_info "MinIO not available, sample data saved locally only"
            fi
        else
            log_error "Sample data file was not created or is empty"
            return 1
        fi
    else
        log_error "Sample data generation failed"
        return 1
    fi
    
    # Clean up temporary script
    rm -f "$temp_script"
}

# ==============================================================================
# JUPYTER CONFIGURATION
# ==============================================================================

setup_jupyter_config() {
    log_info "Setting up Jupyter configuration..."
    
    local notebooks_dir="$LAKEHOUSE_ROOT/notebooks"
    
    # Create Jupyter configuration directory
    ensure_directory "$notebooks_dir/config" "Jupyter config directory"
    
    # Create requirements file for Jupyter environment
    cat > "$notebooks_dir/requirements.txt" << 'EOF'
# Python packages for Lakehouse Lab Jupyter environment
# These should be available in the Jupyter container

# Core data science
pandas>=1.5.0
numpy>=1.24.0
matplotlib>=3.6.0
seaborn>=0.12.0
plotly>=5.17.0

# Database connectivity
duckdb==1.3.0
duckdb-engine==0.17.0
psycopg2-binary>=2.9.0
sqlalchemy>=1.4.0

# Object storage
boto3==1.35.5
s3fs>=2023.1.0

# Big data processing
pyarrow==14.0.2
pyspark>=3.5.0

# Additional utilities
requests>=2.28.0
python-dotenv>=1.0.0
openpyxl>=3.0.0
EOF
    
    log_success "Created Jupyter requirements.txt"
    
    # Create Jupyter startup script for environment setup
    cat > "$notebooks_dir/config/jupyter_startup.py" << 'EOF'
"""
Jupyter Startup Configuration for Lakehouse Lab
Automatically configures connections and imports for data analysis
"""

import os
import sys
import warnings
warnings.filterwarnings('ignore')

# Add current directory to Python path
if '/home/jovyan/work' not in sys.path:
    sys.path.append('/home/jovyan/work')

print("🏠 Lakehouse Lab Jupyter Environment")
print("=" * 50)

# Test imports and show versions
try:
    import pandas as pd
    print(f"✅ Pandas {pd.__version__}")
except ImportError:
    print("❌ Pandas not available")

try:
    import duckdb
    print(f"✅ DuckDB {duckdb.__version__}")
except ImportError:
    print("❌ DuckDB not available")

try:
    import boto3
    print(f"✅ Boto3 {boto3.__version__}")
except ImportError:
    print("❌ Boto3 not available")

try:
    from pyspark.sql import SparkSession
    print("✅ PySpark available")
except ImportError:
    print("❌ PySpark not available")

print("=" * 50)
print("🚀 Ready for data analysis!")
print()

# Environment variables for convenience
os.environ.setdefault('MINIO_ENDPOINT', 'http://minio:9000')
os.environ.setdefault('MINIO_ACCESS_KEY', os.environ.get('MINIO_ROOT_USER', 'minio'))
os.environ.setdefault('MINIO_SECRET_KEY', os.environ.get('MINIO_ROOT_PASSWORD', 'minio123'))
os.environ.setdefault('POSTGRES_HOST', 'postgres')
os.environ.setdefault('POSTGRES_USER', os.environ.get('POSTGRES_USER', 'postgres'))
os.environ.setdefault('POSTGRES_PASSWORD', os.environ.get('POSTGRES_PASSWORD', 'postgres'))
os.environ.setdefault('POSTGRES_DB', os.environ.get('POSTGRES_DB', 'lakehouse'))

print("Environment variables configured for lakehouse access")
EOF
    
    log_success "Created Jupyter startup configuration"
    
    # Create useful utility functions file
    cat > "$notebooks_dir/lakehouse_utils.py" << 'EOF'
"""
Lakehouse Lab Utility Functions
Convenient functions for common data operations
"""

import duckdb
import boto3
import pandas as pd
from sqlalchemy import create_engine

def get_duckdb_connection():
    """Get a DuckDB connection with S3 configured"""
    conn = duckdb.connect()
    
    # Configure S3 access
    conn.execute("INSTALL httpfs")
    conn.execute("LOAD httpfs")
    conn.execute("SET s3_endpoint='minio:9000'")
    conn.execute(f"SET s3_access_key_id='{os.environ.get('MINIO_ROOT_USER', 'minio')}'")
    conn.execute(f"SET s3_secret_access_key='{os.environ.get('MINIO_ROOT_PASSWORD', 'minio123')}'")
    conn.execute("SET s3_use_ssl=false")
    conn.execute("SET s3_url_style='path'")
    
    return conn

def get_s3_client():
    """Get a configured S3 client for MinIO"""
    return boto3.client(
        's3',
        endpoint_url='http://minio:9000',
        aws_access_key_id=os.environ.get('MINIO_ROOT_USER', 'minio'),
        aws_secret_access_key=os.environ.get('MINIO_ROOT_PASSWORD', 'minio123')
    )

def get_postgres_engine():
    """Get a SQLAlchemy engine for PostgreSQL"""
    pg_user = os.environ.get('POSTGRES_USER', 'postgres')
    pg_password = os.environ.get('POSTGRES_PASSWORD', 'postgres')
    pg_db = os.environ.get('POSTGRES_DB', 'lakehouse')
    return create_engine(
        f'postgresql://{pg_user}:{pg_password}@postgres:5432/{pg_db}'
    )

def query_s3_csv(s3_path, limit=None):
    """Query a CSV file from S3 using DuckDB"""
    conn = get_duckdb_connection()
    
    query = f"SELECT * FROM read_csv_auto('s3://lakehouse/{s3_path}')"
    if limit:
        query += f" LIMIT {limit}"
    
    return conn.execute(query).df()

def list_s3_objects(bucket='lakehouse', prefix=''):
    """List objects in S3 bucket"""
    s3 = get_s3_client()
    
    try:
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        if 'Contents' in response:
            return [obj['Key'] for obj in response['Contents']]
        else:
            return []
    except Exception as e:
        print(f"Error listing S3 objects: {e}")
        return []

print("✅ Lakehouse utilities loaded")
print("Available functions: get_duckdb_connection(), get_s3_client(), get_postgres_engine()")
print("                    query_s3_csv(), list_s3_objects()")
EOF
    
    log_success "Created lakehouse utility functions"
}

# ==============================================================================
# ANALYTICS VERIFICATION
# ==============================================================================

verify_analytics_setup() {
    log_info "Verifying analytics setup..."
    
    local notebooks_dir="$LAKEHOUSE_ROOT/notebooks"
    
    # Check if notebook files exist
    local notebook_count=$(find "$notebooks_dir" -name "*.ipynb" -type f | wc -l)
    
    if [ "$notebook_count" -gt 0 ]; then
        log_success "Found $notebook_count notebook file(s)"
        
        # List the notebooks
        log_info "Available notebooks:"
        find "$notebooks_dir" -name "*.ipynb" -type f -exec basename {} \; | while read -r notebook_name; do
            echo "   ✓ $notebook_name"
        done
    else
        log_error "No notebook files found in $notebooks_dir"
        return 1
    fi
    
    # Check if sample data was created
    local sample_file="/tmp/sample_orders.csv"
    if [ -f "$sample_file" ] && [ -s "$sample_file" ]; then
        local line_count=$(wc -l < "$sample_file")
        log_success "Sample data file created with $line_count lines"
    else
        log_warning "Sample data file not found or empty"
    fi
    
    # Check if sample data is in MinIO
    if command -v mc >/dev/null 2>&1 && mc ls lakehouse/ >/dev/null 2>&1; then
        if mc ls "lakehouse/lakehouse/raw-data/sample_orders.csv" >/dev/null 2>&1; then
            log_success "Sample data available in MinIO"
        else
            log_warning "Sample data not found in MinIO"
        fi
    fi
    
    # Check if Jupyter service is running (if Docker CLI is available)
    if check_docker_cli_available; then
        if docker compose ps | grep -q "jupyter.*Up"; then
            log_success "Jupyter service is running"
        else
            log_info "Jupyter service is not running (this is normal if not started yet)"
        fi
    fi
    
    return 0
}

# ==============================================================================
# MAIN ANALYTICS SETUP
# ==============================================================================

main() {
    print_separator "📊 ANALYTICS SETUP"
    
    # Check if workflows are ready
    if ! check_already_initialized "workflows"; then
        log_error "Workflows must be initialized first"
        log_info "Run: ./scripts/init-workflows.sh"
        exit 1
    fi
    
    # Deploy Jupyter notebooks
    if ! deploy_jupyter_notebooks; then
        handle_error "Notebook deployment failed" "Analytics"
        exit 1
    fi
    
    # Setup Jupyter configuration
    if ! setup_jupyter_config; then
        handle_error "Jupyter configuration failed" "Analytics"
        exit 1
    fi
    
    # Generate sample data
    if ! generate_sample_data; then
        handle_error "Sample data generation failed" "Analytics"
        exit 1
    fi
    
    # Verify setup
    if ! verify_analytics_setup; then
        handle_error "Analytics verification failed" "Analytics"
        exit 1
    fi
    
    # Mark analytics as initialized
    create_init_marker "analytics"
    
    print_separator "✅ ANALYTICS SETUP COMPLETE"
    log_success "Analytics setup completed successfully"
    
    echo "📊 Analytics Environment Ready:"
    echo "   • Jupyter notebooks deployed to: $LAKEHOUSE_ROOT/notebooks/"
    echo "   • Sample data generated and uploaded to MinIO"
    echo "   • Utility functions available: lakehouse_utils.py"
    echo "   • Jupyter UI: http://localhost:9040 (when services are running)"
    echo "   • Default token: lakehouse"
    echo ""
}

# Only run main if script is executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi