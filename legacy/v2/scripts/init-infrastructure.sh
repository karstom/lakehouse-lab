#!/bin/bash
# ==============================================================================
# init-infrastructure.sh - Infrastructure Setup Module
# ==============================================================================
# Sets up basic infrastructure: directories, permissions, MinIO client

set -e

# Get script directory and source shared utilities
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
source "$SCRIPT_DIR/lib/init-core.sh"

# ==============================================================================
# MINIO CLIENT INSTALLATION
# ==============================================================================

install_minio_client() {
    log_info "Installing MinIO client (mc)..."
    
    # Check if mc is already installed and working
    if command -v mc >/dev/null 2>&1 && mc --version >/dev/null 2>&1; then
        log_success "MinIO client (mc) is already installed"
        return 0
    fi
    
    # Install MinIO client
    local mc_url="https://dl.min.io/client/mc/release/linux-amd64/mc"
    local mc_path="/usr/local/bin/mc"
    
    log_info "Downloading MinIO client from $mc_url"
    
    if curl -fsSL --connect-timeout 30 --max-time 60 "$mc_url" -o /tmp/mc; then
        if mv /tmp/mc "$mc_path" && chmod +x "$mc_path"; then
            log_success "MinIO client installed successfully to $mc_path"
            
            # Verify installation
            if mc --version >/dev/null 2>&1; then
                log_success "MinIO client installation verified"
            else
                log_warning "MinIO client installed but version check failed"
            fi
        else
            log_error "Failed to install MinIO client to $mc_path"
            log_warning "Continuing without MinIO client - some features may be limited"
        fi
    else
        log_warning "Failed to download MinIO client (network issue)"
        log_warning "Continuing without MinIO client - some features may be limited"
        log_info "MinIO client can be installed manually if needed:"
        log_info "  curl -fsSL $mc_url -o /usr/local/bin/mc && chmod +x /usr/local/bin/mc"
    fi
    
    # Always return success - MinIO client is optional
    return 0
}

# ==============================================================================
# DIRECTORY CREATION
# ==============================================================================

create_directories() {
    log_info "Creating lakehouse directory structure..."
    
    # Main data directory
    ensure_directory "$LAKEHOUSE_ROOT" "main lakehouse data directory"
    
    # Airflow directories
    ensure_directory "$LAKEHOUSE_ROOT/airflow" "Airflow directory"
    ensure_directory "$LAKEHOUSE_ROOT/airflow/dags" "Airflow DAGs directory"
    ensure_directory "$LAKEHOUSE_ROOT/airflow/logs" "Airflow logs directory"
    ensure_directory "$LAKEHOUSE_ROOT/airflow/plugins" "Airflow plugins directory"
    
    # Jupyter directories
    ensure_directory "$LAKEHOUSE_ROOT/notebooks" "Jupyter notebooks directory"
    ensure_directory "$LAKEHOUSE_ROOT/notebooks/work" "Jupyter work directory"
    
    # Storage directories
    ensure_directory "$LAKEHOUSE_ROOT/minio-data" "MinIO data directory"
    ensure_directory "$LAKEHOUSE_ROOT/raw-data" "Raw data directory"
    ensure_directory "$LAKEHOUSE_ROOT/processed-data" "Processed data directory"
    
    # Configuration directories
    ensure_directory "$LAKEHOUSE_ROOT/superset" "Superset directory"
    
    # Iceberg directories (for future use)
    ensure_directory "$LAKEHOUSE_ROOT/iceberg-jars" "Iceberg JARs directory"
    ensure_directory "$LAKEHOUSE_ROOT/iceberg-warehouse" "Iceberg warehouse directory"
    
    log_success "Directory structure created successfully"
}

# ==============================================================================
# PERMISSIONS SETUP
# ==============================================================================

set_permissions() {
    log_info "Setting appropriate permissions for lakehouse directories..."
    
    # In container environments, use permissive permissions instead of changing ownership
    # This allows different service users to access the directories
    log_info "Setting permissive permissions for multi-user container access"
    
    # Set directory permissions (777 - rwxrwxrwx for container compatibility)
    find "$LAKEHOUSE_ROOT" -type d -exec chmod 777 {} \; 2>/dev/null || {
        log_warning "Some directory permissions could not be set"
    }
    
    # Set file permissions (666 - rw-rw-rw- for container compatibility)
    find "$LAKEHOUSE_ROOT" -type f -exec chmod 666 {} \; 2>/dev/null || {
        log_warning "Some file permissions could not be set"
    }
    
    # Special permissions for executables
    find "$LAKEHOUSE_ROOT" -name "*.sh" -exec chmod 777 {} \; 2>/dev/null || true
    find "$LAKEHOUSE_ROOT" -name "*.py" -exec chmod 777 {} \; 2>/dev/null || true
    
    # Create log file with proper permissions
    touch "$LAKEHOUSE_ROOT/init.log"
    chmod 666 "$LAKEHOUSE_ROOT/init.log"
    
    log_success "Permissions set successfully"
}

# ==============================================================================
# MAIN INFRASTRUCTURE SETUP
# ==============================================================================

main() {
    print_separator "🏗️  INFRASTRUCTURE SETUP"
    
    # Validate environment first
    if ! validate_environment; then
        handle_error "Environment validation failed" "Infrastructure"
        exit 1
    fi
    
    # Create directory structure
    if ! create_directories; then
        handle_error "Directory creation failed" "Infrastructure"
        exit 1
    fi
    
    # Set permissions
    if ! set_permissions; then
        handle_error "Permission setup failed" "Infrastructure"
        exit 1
    fi
    
    # Install MinIO client (optional - continues even if download fails)
    if ! install_minio_client; then
        log_warning "MinIO client installation completed with warnings"
    fi
    
    # Mark infrastructure as initialized
    create_init_marker "infrastructure"
    
    print_separator "✅ INFRASTRUCTURE SETUP COMPLETE"
    log_success "Infrastructure setup completed successfully"
    
    echo "📁 Directory structure ready:"
    echo "   └── $LAKEHOUSE_ROOT/"
    echo "       ├── airflow/ (DAGs, logs, plugins)"
    echo "       ├── notebooks/ (Jupyter notebooks)"
    echo "       ├── minio-data/ (Object storage)"
    echo "       ├── raw-data/ (Raw datasets)"
    echo "       ├── processed-data/ (Processed datasets)"
    echo "       ├── superset/ (BI configuration)"
    echo ""
}

# Only run main if script is executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi