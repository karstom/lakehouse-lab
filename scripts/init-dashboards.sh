#!/bin/bash
# ==============================================================================
# init-dashboards.sh - Dashboard and BI Setup Module
# ==============================================================================
# Sets up Homer dashboard and Superset BI configuration

set -e

# Get script directory and source shared utilities
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
source "$SCRIPT_DIR/lib/init-core.sh"

# ==============================================================================
# HOMER DASHBOARD DEPLOYMENT
# ==============================================================================

deploy_homer_config() {
    log_info "Deploying Homer dashboard configuration..."
    
    local template_dir="$(dirname "$SCRIPT_DIR")/templates/homer"
    local target_dir="$LAKEHOUSE_ROOT/homer"
    
    # Ensure target directories exist
    ensure_directory "$target_dir" "Homer directory"
    ensure_directory "$target_dir/assets" "Homer assets directory"
    
    # Check if template file exists
    local template_file="$template_dir/config.yml"
    if [ ! -f "$template_file" ]; then
        log_error "Homer template not found: $template_file"
        return 1
    fi
    
    # Copy configuration file
    local target_file="$target_dir/assets/config.yml"
    
    if cp "$template_file" "$target_file"; then
        log_success "Deployed Homer configuration: config.yml"
        
        # Set appropriate permissions
        chmod 644 "$target_file"
        
        # Also copy to root homer directory for compatibility
        if cp "$target_file" "$target_dir/config.yml"; then
            log_success "Homer config copied to root location"
        else
            log_warning "Failed to copy Homer config to root location"
        fi
    else
        log_error "Failed to copy Homer configuration"
        return 1
    fi
    
    log_success "Homer dashboard configuration deployed"
}

# ==============================================================================
# SUPERSET DATABASE SETUP
# ==============================================================================

deploy_superset_config() {
    log_info "Deploying Superset database configuration..."
    
    local template_dir="$(dirname "$SCRIPT_DIR")/templates/superset"
    local target_dir="$LAKEHOUSE_ROOT/superset"
    
    # Ensure target directory exists
    ensure_directory "$target_dir" "Superset directory"
    
    # Check if template file exists
    local template_file="$template_dir/database_setup.py"
    if [ ! -f "$template_file" ]; then
        log_error "Superset template not found: $template_file"
        return 1
    fi
    
    # Copy setup script
    local target_file="$target_dir/setup_duckdb.py"
    
    if cp "$template_file" "$target_file"; then
        log_success "Deployed Superset database setup: setup_duckdb.py"
        
        # Set appropriate permissions
        chmod 755 "$target_file"
    else
        log_error "Failed to copy Superset database setup"
        return 1
    fi
    
    # Create additional Superset configuration script
    cat > "$target_dir/add_duckdb_connection.py" << 'EOF'
#!/usr/bin/env python3
"""
Superset DuckDB Connection Setup
Adds DuckDB database connection to Superset with S3 configuration
"""

import os
import sys

# Add Superset to path
sys.path.append('/app')
os.environ.setdefault('SUPERSET_CONFIG_PATH', '/app/superset_config.py')

try:
    from superset import app
    from superset.models.core import Database
    from superset.extensions import db
    
    def add_duckdb_connection():
        """Add DuckDB connection to Superset"""
        
        with app.app_context():
            # Database configuration
            database_config = {
                "database_name": "DuckDB-S3",
                "sqlalchemy_uri": "duckdb:///tmp/lakehouse.duckdb",
                "extra": f"""{{
                    "engine_params": {{
                        "connect_args": {{
                            "config": {{
                                "s3_endpoint": "minio:9000",
                                "s3_access_key_id": "{os.environ.get('MINIO_ROOT_USER', 'minio')}", 
                                "s3_secret_access_key": "{os.environ.get('MINIO_ROOT_PASSWORD', 'minio123')}",
                                "s3_use_ssl": "false",
                                "s3_url_style": "path"
                            }}
                        }}
                    }}
                }}"""
            }
            
            # Check if database already exists
            existing_db = db.session.query(Database).filter(
                Database.database_name == database_config["database_name"]
            ).first()
            
            if existing_db:
                # Update existing database
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
            
            print("✅ Superset DuckDB connection configured successfully!")
            print("📝 Connection name: DuckDB-S3")
            print("🔗 S3 queries can now be run in Superset SQL Lab")
            
    if __name__ == "__main__":
        add_duckdb_connection()
        
except Exception as e:
    print(f"❌ Failed to configure Superset database connection: {e}")
    print("ℹ️ You can manually create the connection in Superset UI")
    sys.exit(1)
EOF
    
    chmod +x "$target_dir/add_duckdb_connection.py"
    log_success "Created Superset DuckDB connection script"
}

# ==============================================================================
# DASHBOARD CONFIGURATION
# ==============================================================================

setup_dashboard_config() {
    log_info "Setting up dashboard configuration..."
    
    # Create general dashboard configuration
    cat > "$LAKEHOUSE_ROOT/dashboard_config.json" << 'EOF'
{
    "lakehouse_lab_dashboards": {
        "version": "2.0",
        "updated": "2024-01-01",
        "services": {
            "homer": {
                "url": "http://localhost:9061",
                "config_path": "homer/assets/config.yml",
                "description": "Service dashboard and navigation"
            },
            "superset": {
                "url": "http://localhost:9030", 
                "config_path": "superset/setup_duckdb.py",
                "description": "Business Intelligence and analytics dashboards",
                "default_login": "admin/admin"
            }
        },
        "data_sources": {
            "minio_s3": "s3://lakehouse/raw-data/",
            "postgres": "postgresql://postgres:postgres@postgres:5432/lakehouse",
            "duckdb": "/tmp/lakehouse.duckdb"
        },
        "sample_queries": [
            "SELECT * FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv') LIMIT 10;",
            "SELECT product_category, COUNT(*) as orders FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv') GROUP BY product_category;",
            "SELECT DATE_TRUNC('month', CAST(order_date AS DATE)) as month, SUM(total_amount) as revenue FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv') GROUP BY month ORDER BY month;"
        ]
    }
}
EOF
    
    log_success "Created dashboard configuration file"
    
    # Create dashboard utilities script
    cat > "$LAKEHOUSE_ROOT/dashboard_utils.sh" << 'EOF'
#!/bin/bash
# Dashboard Utilities for Lakehouse Lab

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

show_dashboard_info() {
    echo -e "${BLUE}🏠 Lakehouse Lab Dashboard Information${NC}"
    echo "=================================="
    echo ""
    echo -e "${GREEN}Service Dashboards:${NC}"
    echo "  🏠 Homer (Service Navigation): http://localhost:9061"
    echo "  📊 Superset (BI Analytics):    http://localhost:9030"
    echo "  🐳 Portainer (Containers):     http://localhost:9060"
    echo ""
    echo -e "${GREEN}Application Interfaces:${NC}"  
    echo "  📋 Airflow (Workflows):        http://localhost:9020"
    echo "  📓 JupyterLab (Notebooks):     http://localhost:9040"
    echo "  ☁️  MinIO (Object Storage):     http://localhost:9001"
    echo "  ⚡ Spark Master (Processing):  http://localhost:8080"
    echo ""
    echo -e "${GREEN}Generated Credentials:${NC}"
    echo "  All services: use ./scripts/show-credentials.sh for login credentials"
    echo ""
}

check_dashboard_health() {
    echo -e "${BLUE}🔍 Checking Dashboard Health${NC}"
    echo "=========================="
    echo ""
    
    services=(
        "Homer:http://localhost:9061"
        "Superset:http://localhost:9030/health"
        "Portainer:http://localhost:9060"
        "Airflow:http://localhost:9020/health"
        "Jupyter:http://localhost:9040"
        "MinIO:http://localhost:9001"
        "Spark:http://localhost:8080"
    )
    
    for service_info in "${services[@]}"; do
        IFS=':' read -r name url <<< "$service_info"
        if curl -sf "$url" >/dev/null 2>&1; then
            echo -e "  ✅ $name is healthy"
        else
            echo -e "  ❌ $name is not responding"
        fi
    done
    echo ""
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    case "${1:-info}" in
        "info"|"show")
            show_dashboard_info
            ;;
        "health"|"check")
            check_dashboard_health
            ;;
        "all")
            show_dashboard_info
            check_dashboard_health
            ;;
        *)
            echo "Usage: $0 [info|health|all]"
            echo "  info   - Show dashboard URLs and credentials"
            echo "  health - Check dashboard service health"
            echo "  all    - Show both info and health"
            ;;
    esac
fi
EOF
    
    chmod +x "$LAKEHOUSE_ROOT/dashboard_utils.sh"
    log_success "Created dashboard utilities script"
}

# ==============================================================================
# DASHBOARD VERIFICATION
# ==============================================================================

verify_dashboards_setup() {
    log_info "Verifying dashboards setup..."
    
    # Check Homer configuration
    local homer_config="$LAKEHOUSE_ROOT/homer/assets/config.yml"
    if [ -f "$homer_config" ] && [ -s "$homer_config" ]; then
        log_success "Homer configuration file exists and is not empty"
    else
        log_error "Homer configuration file missing or empty"
        return 1
    fi
    
    # Check Superset scripts
    local superset_setup="$LAKEHOUSE_ROOT/superset/setup_duckdb.py"
    if [ -f "$superset_setup" ] && [ -s "$superset_setup" ]; then
        log_success "Superset database setup script exists"
        
        # Check Python syntax
        if python3 -m py_compile "$superset_setup" 2>/dev/null; then
            log_success "Superset setup script syntax is valid"
        else
            log_warning "Superset setup script has syntax issues"
        fi
    else
        log_error "Superset setup script missing or empty"
        return 1
    fi
    
    # Check configuration files
    local dashboard_config="$LAKEHOUSE_ROOT/dashboard_config.json"
    if [ -f "$dashboard_config" ]; then
        # Validate JSON syntax
        if python3 -c "import json; json.load(open('$dashboard_config'))" 2>/dev/null; then
            log_success "Dashboard configuration JSON is valid"
        else
            log_warning "Dashboard configuration JSON has syntax issues"
        fi
    else
        log_warning "Dashboard configuration file not found"
    fi
    
    # Check if dashboard services are running (if Docker CLI is available)
    if check_docker_cli_available; then
        if docker compose ps | grep -q "superset.*Up"; then
            log_success "Superset service is running"
        else
            log_info "Superset service is not running (this is normal if not started yet)"
        fi
        
        if docker compose ps | grep -q "homer.*Up"; then
            log_success "Homer service is running"
        else
            log_info "Homer service is not running (this is normal if not started yet)"
        fi
    fi
    
    return 0
}

# ==============================================================================
# MAIN DASHBOARDS SETUP
# ==============================================================================

main() {
    print_separator "📊 DASHBOARDS SETUP"
    
    # Check if analytics are ready
    if ! check_already_initialized "analytics"; then
        log_error "Analytics must be initialized first"
        log_info "Run: ./scripts/init-analytics.sh"
        exit 1
    fi
    
    # Deploy Homer configuration
    if ! deploy_homer_config; then
        handle_error "Homer deployment failed" "Dashboards"
        exit 1
    fi
    
    # Deploy Superset configuration
    if ! deploy_superset_config; then
        handle_error "Superset deployment failed" "Dashboards"
        exit 1
    fi
    
    # Setup dashboard configuration
    if ! setup_dashboard_config; then
        handle_error "Dashboard configuration failed" "Dashboards"
        exit 1
    fi
    
    # Verify setup
    if ! verify_dashboards_setup; then
        handle_error "Dashboards verification failed" "Dashboards"
        exit 1
    fi
    
    # Mark dashboards as initialized
    create_init_marker "dashboards"
    
    print_separator "✅ DASHBOARDS SETUP COMPLETE"
    log_success "Dashboards setup completed successfully"
    
    echo "📊 Dashboard Layer Ready:"
    echo "   • Homer dashboard: $LAKEHOUSE_ROOT/homer/"
    echo "   • Superset BI config: $LAKEHOUSE_ROOT/superset/"
    echo "   • Dashboard utilities: $LAKEHOUSE_ROOT/dashboard_utils.sh"
    echo ""
    echo "🌐 Access URLs (when services are running):"
    echo "   • Homer: http://localhost:9061"
    echo "   • Superset: http://localhost:9030 (admin/admin)"
    echo "   • Portainer: http://localhost:9060"
    echo ""
}

# Only run main if script is executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi