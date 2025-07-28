#!/bin/bash
# ==============================================================================
# init-storage.sh - Storage Layer Setup Module
# ==============================================================================
# Configures MinIO object storage and creates required buckets

set -e

# Get script directory and source shared utilities
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
source "$SCRIPT_DIR/lib/init-core.sh"

# ==============================================================================
# MINIO CONFIGURATION
# ==============================================================================

configure_minio() {
    log_info "Configuring MinIO client for lakehouse access..."
    
    # Wait for MinIO to be ready first
    if ! wait_for_minio_api 30; then
        log_error "MinIO API is not ready, cannot configure client"
        return 1
    fi
    
    # Configure MinIO client alias
    log_info "Setting up MinIO client alias 'lakehouse'..."
    
    if mc alias set lakehouse http://minio:9000 minio minio123 >/dev/null 2>&1; then
        log_success "MinIO client configured successfully"
    else
        log_error "Failed to configure MinIO client"
        return 1
    fi
    
    # Test connection
    if mc admin info lakehouse >/dev/null 2>&1; then
        log_success "MinIO connection test successful"
    else
        log_warning "MinIO connection test failed, but configuration appears correct"
    fi
    
    return 0
}

# ==============================================================================
# BUCKET CREATION
# ==============================================================================

create_buckets() {
    log_info "Creating required S3 buckets..."
    
    # List of buckets to create
    local buckets=(
        "lakehouse"
        "lakehouse-data" 
        "raw-data"
        "processed-data"
        "backup-data"
        "lakehouse-warehouse"
    )
    
    # Create each bucket
    for bucket in "${buckets[@]}"; do
        log_info "Creating bucket: $bucket"
        
        # Check if bucket already exists
        if mc ls "lakehouse/$bucket" >/dev/null 2>&1; then
            log_info "Bucket $bucket already exists"
        else
            # Create bucket
            if mc mb "lakehouse/$bucket" >/dev/null 2>&1; then
                log_success "Created bucket: $bucket"
            else
                log_error "Failed to create bucket: $bucket"
                return 1
            fi
        fi
        
        # Set bucket policy for read access (for development)
        if mc anonymous set download "lakehouse/$bucket" >/dev/null 2>&1; then
            log_info "Set download policy for bucket: $bucket"
        else
            log_warning "Could not set download policy for bucket: $bucket"
        fi
    done
    
    # Create directory structure within main bucket
    log_info "Creating directory structure in lakehouse bucket..."
    
    local directories=(
        "raw-data"
        "processed-data" 
        "backup-data"
        "iceberg-warehouse"
        "temp"
    )
    
    for dir in "${directories[@]}"; do
        # Create a placeholder file to establish the directory
        echo "# Placeholder file for $dir directory" | mc pipe "lakehouse/lakehouse/$dir/.gitkeep" 2>/dev/null || {
            log_warning "Could not create directory structure for: $dir"
        }
    done
    
    log_success "Bucket creation completed"
}

# ==============================================================================
# SAMPLE DATA UPLOAD
# ==============================================================================

upload_sample_data() {
    log_info "Setting up sample data upload..."
    
    # Check if sample data exists locally
    local sample_file="/tmp/sample_orders.csv"
    
    if [ -f "$sample_file" ]; then
        log_info "Found local sample data, uploading to MinIO..."
        
        if mc cp "$sample_file" "lakehouse/lakehouse/raw-data/sample_orders.csv" >/dev/null 2>&1; then
            log_success "Sample data uploaded successfully"
            
            # Verify upload
            if mc stat "lakehouse/lakehouse/raw-data/sample_orders.csv" >/dev/null 2>&1; then
                log_success "Sample data upload verified"
            else
                log_warning "Sample data upload verification failed"
            fi
        else
            log_warning "Failed to upload sample data (this is not critical)"
        fi
    else
        log_info "No local sample data found (will be created in analytics module)"
    fi
}

# ==============================================================================
# STORAGE VERIFICATION
# ==============================================================================

verify_storage_setup() {
    log_info "Verifying storage setup..."
    
    # Test MinIO connection
    if ! mc admin info lakehouse >/dev/null 2>&1; then
        log_error "MinIO connection verification failed"
        return 1
    fi
    
    # List buckets to verify creation
    log_info "Available buckets:"
    if mc ls lakehouse/ 2>/dev/null | while read -r line; do
        bucket_name=$(echo "$line" | awk '{print $5}' | sed 's|/$||')
        if [ -n "$bucket_name" ]; then
            echo "   ✓ $bucket_name"
        fi
    done; then
        log_success "Bucket verification completed"
    else
        log_warning "Could not list buckets (this may be a permissions issue)"
    fi
    
    # Test file operations
    local test_file="/tmp/storage_test.txt"
    echo "Storage test - $(date)" > "$test_file"
    
    if mc cp "$test_file" "lakehouse/lakehouse/temp/test.txt" >/dev/null 2>&1; then
        log_success "Storage write test passed"
        
        # Clean up test file
        mc rm "lakehouse/lakehouse/temp/test.txt" >/dev/null 2>&1 || true
        rm -f "$test_file"
    else
        log_warning "Storage write test failed"
    fi
    
    return 0
}

# ==============================================================================
# MAIN STORAGE SETUP
# ==============================================================================

main() {
    print_separator "🗄️  STORAGE SETUP"
    
    # Check if infrastructure is ready
    if ! check_already_initialized "infrastructure"; then
        log_error "Infrastructure must be initialized first"
        log_info "Run: ./scripts/init-infrastructure.sh"
        exit 1
    fi
    
    # Check Docker services
    if ! check_docker_services; then
        handle_error "Docker services not ready" "Storage"
        exit 1
    fi
    
    # Configure MinIO client
    if ! configure_minio; then
        handle_error "MinIO configuration failed" "Storage"
        exit 1
    fi
    
    # Create buckets
    if ! create_buckets; then
        handle_error "Bucket creation failed" "Storage"
        exit 1
    fi
    
    # Upload any available sample data
    upload_sample_data
    
    # Verify setup
    if ! verify_storage_setup; then
        handle_error "Storage verification failed" "Storage"
        exit 1
    fi
    
    # Mark storage as initialized
    create_init_marker "storage"
    
    print_separator "✅ STORAGE SETUP COMPLETE"
    log_success "Storage setup completed successfully"
    
    echo "🗄️  MinIO Storage Ready:"
    echo "   • MinIO Console: http://localhost:9001 (minio/minio123)"
    echo "   • S3 Endpoint: http://minio:9000"
    echo "   • Buckets created: lakehouse, raw-data, processed-data, backup-data"
    echo "   • Directory structure established"
    echo ""
}

# Only run main if script is executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi