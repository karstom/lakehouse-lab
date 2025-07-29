#!/bin/bash
# ==============================================================================
# init-workflows.sh - Workflow Orchestration Setup Module
# ==============================================================================
# Sets up Airflow DAGs and workflow orchestration

set -e

# Get script directory and source shared utilities
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
source "$SCRIPT_DIR/lib/init-core.sh"

# ==============================================================================
# AIRFLOW DAG DEPLOYMENT
# ==============================================================================

deploy_airflow_dags() {
    log_info "Deploying Airflow DAGs from templates..."
    
    local template_dir="$(dirname "$SCRIPT_DIR")/templates/airflow/dags"
    local target_dir="$LAKEHOUSE_ROOT/airflow/dags"
    
    # Ensure target directory exists
    ensure_directory "$target_dir" "Airflow DAGs directory"
    
    # Check if template directory exists
    if [ ! -d "$template_dir" ]; then
        log_error "Template directory not found: $template_dir"
        return 1
    fi
    
    # Copy DAG files
    log_info "Copying DAG files from $template_dir to $target_dir"
    
    local dag_files=(
        "sample_duckdb_pipeline.py"
        "postgres_analytics_dag.py"
        "data_quality_check.py"
        "postgres_streaming_dag.py"
    )
    
    local copied_count=0
    
    for dag_file in "${dag_files[@]}"; do
        local source_file="$template_dir/$dag_file"
        local target_file="$target_dir/$dag_file"
        
        if [ -f "$source_file" ]; then
            if cp "$source_file" "$target_file"; then
                log_success "Deployed DAG: $dag_file"
                copied_count=$((copied_count + 1))
                
                # Set appropriate permissions
                chmod 644 "$target_file"
            else
                log_error "Failed to copy DAG: $dag_file"
                return 1
            fi
        else
            log_warning "Template file not found: $dag_file"
        fi
    done
    
    if [ $copied_count -gt 0 ]; then
        log_success "Deployed $copied_count Airflow DAG(s)"
    else
        log_error "No DAG files were deployed"
        return 1
    fi
}

# ==============================================================================
# AIRFLOW CONFIGURATION
# ==============================================================================

setup_airflow_config() {
    log_info "Setting up Airflow configuration..."
    
    local airflow_dir="$LAKEHOUSE_ROOT/airflow"
    
    # Create additional Airflow directories if needed
    ensure_directory "$airflow_dir/logs" "Airflow logs directory"
    ensure_directory "$airflow_dir/plugins" "Airflow plugins directory"
    ensure_directory "$airflow_dir/config" "Airflow config directory"
    
    # Create requirements file for additional Python packages
    cat > "$airflow_dir/requirements.txt" << 'EOF'
# Additional Python packages for Lakehouse Lab Airflow
# Install these in Airflow containers for enhanced functionality

# Data processing
duckdb==1.3.0
duckdb-engine==0.17.0
boto3==1.35.5
pyarrow==14.0.2

# Additional utilities
sqlalchemy>=1.4.0
pandas>=1.5.0
requests>=2.28.0

# Monitoring and logging
psutil>=5.9.0
EOF
    
    log_success "Created Airflow requirements.txt"
    
    # Create Airflow connections configuration script
    cat > "$airflow_dir/config/setup_connections.py" << 'EOF'
#!/usr/bin/env python3
"""
Airflow Connections Setup Script
Creates necessary connections for Lakehouse Lab
"""

import os
import sys
from airflow.models import Connection
from airflow.utils.db import create_session

def create_connection(conn_id, conn_type, host=None, login=None, password=None, 
                     port=None, schema=None, extra=None):
    """Create an Airflow connection"""
    
    with create_session() as session:
        # Check if connection already exists
        existing = session.query(Connection).filter(Connection.conn_id == conn_id).first()
        
        if existing:
            print(f"Connection '{conn_id}' already exists, updating...")
            existing.conn_type = conn_type
            existing.host = host
            existing.login = login
            existing.password = password
            existing.port = port
            existing.schema = schema
            existing.extra = extra
        else:
            print(f"Creating connection '{conn_id}'...")
            new_conn = Connection(
                conn_id=conn_id,
                conn_type=conn_type,
                host=host,
                login=login,
                password=password,
                port=port,
                schema=schema,
                extra=extra
            )
            session.add(new_conn)
        
        session.commit()
        print(f"✅ Connection '{conn_id}' configured successfully")

def main():
    """Set up all required connections"""
    print("Setting up Airflow connections for Lakehouse Lab...")
    
    # MinIO S3 Connection
    create_connection(
        conn_id='minio_s3',
        conn_type='aws',
        extra=f'{{"aws_access_key_id": "{os.environ.get(\"MINIO_ROOT_USER\", \"minio\")}", "aws_secret_access_key": "{os.environ.get(\"MINIO_ROOT_PASSWORD\", \"minio123\")}", "endpoint_url": "http://minio:9000"}}'
    )
    
    # PostgreSQL Connection
    create_connection(
        conn_id='postgres_default',
        conn_type='postgres',
        host='postgres',
        login=os.environ.get('POSTGRES_USER', 'postgres'),
        password=os.environ.get('POSTGRES_PASSWORD', 'postgres'),
        port=5432,
        schema=os.environ.get('POSTGRES_DB', 'lakehouse')
    )
    
    # DuckDB Connection (for local processing)
    create_connection(
        conn_id='duckdb_default',
        conn_type='sqlite',  # DuckDB uses SQLite connection type in Airflow
        host='/tmp/lakehouse.duckdb'
    )
    
    print("✅ All connections configured successfully!")

if __name__ == "__main__":
    main()
EOF
    
    chmod +x "$airflow_dir/config/setup_connections.py"
    log_success "Created Airflow connections setup script"
}

# ==============================================================================
# WORKFLOW VERIFICATION
# ==============================================================================

verify_workflows_setup() {
    log_info "Verifying workflows setup..."
    
    local target_dir="$LAKEHOUSE_ROOT/airflow/dags"
    
    # Check if DAG files exist
    local dag_count=$(find "$target_dir" -name "*.py" -type f | wc -l)
    
    if [ "$dag_count" -gt 0 ]; then
        log_success "Found $dag_count DAG file(s)"
        
        # List the DAGs
        log_info "Available DAGs:"
        find "$target_dir" -name "*.py" -type f -exec basename {} \; | while read -r dag_name; do
            echo "   ✓ $dag_name"
        done
    else
        log_error "No DAG files found in $target_dir"
        return 1
    fi
    
    # Check Python syntax of DAG files
    log_info "Checking DAG file syntax..."
    local syntax_errors=0
    
    for dag_file in "$target_dir"/*.py; do
        if [ -f "$dag_file" ]; then
            if python3 -m py_compile "$dag_file" 2>/dev/null; then
                log_info "✓ $(basename "$dag_file") - syntax OK"
            else
                log_error "✗ $(basename "$dag_file") - syntax error"
                syntax_errors=$((syntax_errors + 1))
            fi
        fi
    done
    
    if [ $syntax_errors -eq 0 ]; then
        log_success "All DAG files passed syntax check"
    else
        log_error "$syntax_errors DAG file(s) have syntax errors"
        return 1
    fi
    
    # Check if Airflow services are running (if Docker CLI is available)
    if check_docker_cli_available; then
        if docker compose ps | grep -q "airflow-webserver.*Up"; then
            log_success "Airflow webserver is running"
        else
            log_info "Airflow webserver is not running (this is normal if not started yet)"
        fi
        
        if docker compose ps | grep -q "airflow-scheduler.*Up"; then
            log_success "Airflow scheduler is running"
        else
            log_info "Airflow scheduler is not running (this is normal if not started yet)"
        fi
    fi
    
    return 0
}

# ==============================================================================
# MAIN WORKFLOWS SETUP
# ==============================================================================

main() {
    print_separator "🔄 WORKFLOWS SETUP"
    
    # Check if compute is ready
    if ! check_already_initialized "compute"; then
        log_error "Compute must be initialized first"
        log_info "Run: ./scripts/init-compute.sh"
        exit 1
    fi
    
    # Deploy Airflow DAGs
    if ! deploy_airflow_dags; then
        handle_error "DAG deployment failed" "Workflows"
        exit 1
    fi
    
    # Setup Airflow configuration
    if ! setup_airflow_config; then
        handle_error "Airflow configuration failed" "Workflows"
        exit 1
    fi
    
    # Verify setup
    if ! verify_workflows_setup; then
        handle_error "Workflows verification failed" "Workflows"
        exit 1
    fi
    
    # Mark workflows as initialized
    create_init_marker "workflows"
    
    print_separator "✅ WORKFLOWS SETUP COMPLETE"
    log_success "Workflows setup completed successfully"
    
    echo "🔄 Workflow Orchestration Ready:"
    echo "   • Airflow DAGs deployed to: $LAKEHOUSE_ROOT/airflow/dags/"
    echo "   • Configuration files created: $LAKEHOUSE_ROOT/airflow/config/"
    echo "   • Requirements defined: $LAKEHOUSE_ROOT/airflow/requirements.txt"
    echo "   • Airflow UI: http://localhost:9020 (when services are running)"
    echo "   • Default login: admin/admin"
    echo ""
}

# Only run main if script is executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi