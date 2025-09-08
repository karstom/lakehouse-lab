#!/bin/bash
# ==============================================================================
# init-compute.sh - Compute Layer Setup Module
# ==============================================================================
# Downloads Iceberg JARs and sets up compute engine components

set -e

# Get script directory and source shared utilities
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
source "$SCRIPT_DIR/lib/init-core.sh"

# ==============================================================================
# ICEBERG JAR DOWNLOAD
# ==============================================================================

download_iceberg_jars() {
    log_info "Downloading Apache Iceberg JAR files for Spark integration..."
    
    local iceberg_dir="$LAKEHOUSE_ROOT/iceberg-jars"
    local iceberg_version="1.9.2"
    local spark_version="3.5"
    local scala_version="2.12"
    
    # Ensure iceberg directory exists
    ensure_directory "$iceberg_dir" "Iceberg JARs directory"
    
    # Define JAR files to download
    local jar_files=(
        "iceberg-spark-runtime-${spark_version}_${scala_version}-${iceberg_version}.jar"
        "iceberg-aws-${iceberg_version}.jar"
        "hadoop-aws-3.3.4.jar"
        "aws-java-sdk-bundle-1.12.262.jar"
        "bundle-2.17.295.jar"
        "url-connection-client-2.17.295.jar"
    )
    
    local base_maven_url="https://repo1.maven.org/maven2"
    
    for jar_file in "${jar_files[@]}"; do
        local jar_path="$iceberg_dir/$jar_file"
        
        # Skip if JAR already exists and is not empty
        if [ -f "$jar_path" ] && [ -s "$jar_path" ]; then
            log_info "JAR already exists: $jar_file"
            continue
        fi
        
        # Determine the correct Maven path based on JAR name
        local maven_path
        if [[ "$jar_file" == *"spark-runtime"* ]]; then
            maven_path="org/apache/iceberg/iceberg-spark-runtime-${spark_version}_${scala_version}/${iceberg_version}/$jar_file"
        elif [[ "$jar_file" == *"iceberg-aws"* ]]; then
            maven_path="org/apache/iceberg/iceberg-aws/${iceberg_version}/$jar_file"
        elif [[ "$jar_file" == *"hadoop-aws"* ]]; then
            maven_path="org/apache/hadoop/hadoop-aws/3.3.4/$jar_file"
        elif [[ "$jar_file" == *"aws-java-sdk-bundle"* ]]; then
            maven_path="com/amazonaws/aws-java-sdk-bundle/1.12.262/$jar_file"
        elif [[ "$jar_file" == "bundle-"* ]]; then
            maven_path="software/amazon/awssdk/bundle/2.17.295/$jar_file"
        elif [[ "$jar_file" == "url-connection-client-"* ]]; then
            maven_path="software/amazon/awssdk/url-connection-client/2.17.295/$jar_file"
        else
            log_warning "Unknown JAR pattern: $jar_file"
            continue
        fi
        
        local jar_url="$base_maven_url/$maven_path"
        
        log_info "Downloading: $jar_file"
        log_info "From: $jar_url"
        
        # Download with retries
        local max_retries=3
        local retry=1
        local download_success=false
        
        while [ $retry -le $max_retries ] && [ "$download_success" = false ]; do
            if curl -fsSL "$jar_url" -o "$jar_path"; then
                # Verify download
                if [ -f "$jar_path" ] && [ -s "$jar_path" ]; then
                    local file_size=$(stat -c%s "$jar_path" 2>/dev/null || wc -c < "$jar_path")
                    if [ "$file_size" -gt 1000 ]; then  # Should be much larger than 1KB
                        log_success "Downloaded: $jar_file (${file_size} bytes)"
                        download_success=true
                    else
                        log_warning "Downloaded file appears too small: $jar_file (${file_size} bytes)"
                        rm -f "$jar_path"
                    fi
                else
                    log_warning "Download verification failed for: $jar_file"
                fi
            else
                log_warning "Download attempt $retry failed for: $jar_file"
            fi
            
            if [ "$download_success" = false ]; then
                retry=$((retry + 1))
                if [ $retry -le $max_retries ]; then
                    log_info "Retrying download in 5 seconds... (attempt $retry/$max_retries)"
                    sleep 5
                fi
            fi
        done
        
        if [ "$download_success" = false ]; then
            log_error "Failed to download after $max_retries attempts: $jar_file"
            log_warning "Iceberg functionality may be limited without this JAR"
        fi
    done
    
    # List downloaded JARs
    log_info "Downloaded Iceberg JARs:"
    if ls -la "$iceberg_dir"/*.jar 2>/dev/null; then
        log_success "Iceberg JAR download completed"
    else
        log_warning "No Iceberg JARs were downloaded successfully"
        log_info "Iceberg functionality will not be available"
        return 1
    fi
}

# ==============================================================================
# COMPUTE VERIFICATION
# ==============================================================================

verify_compute_setup() {
    log_info "Verifying compute setup..."
    
    local iceberg_dir="$LAKEHOUSE_ROOT/iceberg-jars"
    
    # Check if Iceberg directory exists
    if [ ! -d "$iceberg_dir" ]; then
        log_error "Iceberg directory does not exist: $iceberg_dir"
        return 1
    fi
    
    # Count JAR files
    local jar_count=$(find "$iceberg_dir" -name "*.jar" -type f | wc -l)
    
    if [ "$jar_count" -gt 0 ]; then
        log_success "Found $jar_count Iceberg JAR file(s)"
        
        # List the JARs for verification
        log_info "Available Iceberg JARs:"
        find "$iceberg_dir" -name "*.jar" -type f -exec basename {} \; | while read -r jar_name; do
            echo "   ✓ $jar_name"
        done
    else
        log_warning "No Iceberg JAR files found"
        log_info "Iceberg functionality will not be available"
    fi
    
    # Check if Spark services are running (if Docker CLI is available)
    if check_docker_cli_available; then
        if docker compose ps | grep -q "spark-master.*Up"; then
            log_success "Spark Master service is running"
        else
            log_info "Spark Master service is not running (this is normal if not started yet)"
        fi
        
        if docker compose ps | grep -q "spark-worker.*Up"; then
            log_success "Spark Worker service is running" 
        else
            log_info "Spark Worker service is not running (this is normal if not started yet)"
        fi
    fi
    
    return 0
}

# ==============================================================================
# SPARK CONFIGURATION PREP
# ==============================================================================

prepare_spark_config() {
    log_info "Preparing Spark configuration for Iceberg integration..."
    
    local config_dir="$LAKEHOUSE_ROOT/spark-config"
    ensure_directory "$config_dir" "Spark configuration directory"
    
    # Create Spark defaults configuration with Iceberg settings
    cat > "$config_dir/spark-defaults.conf" << EOF
# Spark Configuration for Lakehouse Lab with Iceberg Support
# ==========================================================

# Iceberg Configuration
spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions
spark.sql.catalog.spark_catalog=org.apache.iceberg.spark.SparkSessionCatalog
spark.sql.catalog.spark_catalog.type=hive
spark.sql.catalog.iceberg=org.apache.iceberg.spark.SparkCatalog
spark.sql.catalog.iceberg.type=hadoop
spark.sql.catalog.iceberg.warehouse=s3a://lakehouse/iceberg-warehouse/

# S3/MinIO Configuration
spark.hadoop.fs.s3a.endpoint=http://minio:9000
spark.hadoop.fs.s3a.access.key=${MINIO_ROOT_USER:-minio}
spark.hadoop.fs.s3a.secret.key=${MINIO_ROOT_PASSWORD:-minio123}
spark.hadoop.fs.s3a.path.style.access=true
spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem

# Performance Settings
spark.sql.adaptive.enabled=true
spark.sql.adaptive.coalescePartitions.enabled=true
spark.serializer=org.apache.spark.serializer.KryoSerializer

# Memory Settings (can be overridden by environment)
spark.executor.memory=2g
spark.driver.memory=1g
spark.executor.cores=2
EOF
    
    log_success "Spark configuration prepared"
    
    # Create environment file for Iceberg
    cat > "$config_dir/iceberg.env" << 'EOF'
# Environment variables for Iceberg integration
SPARK_CLASSPATH=/opt/spark/jars/iceberg-spark-runtime-3.5_2.12-1.4.3.jar
ICEBERG_ENABLED=true
ICEBERG_VERSION=1.4.3
EOF
    
    log_success "Iceberg environment configuration prepared"
}

# ==============================================================================
# MAIN COMPUTE SETUP
# ==============================================================================

main() {
    print_separator "⚡ COMPUTE SETUP"
    
    # Check if storage is ready
    if ! check_already_initialized "storage"; then
        log_error "Storage must be initialized first"
        log_info "Run: ./scripts/init-storage.sh"
        exit 1
    fi
    
    # Download Iceberg JARs
    if ! download_iceberg_jars; then
        log_warning "Iceberg JAR download had issues, but continuing..."
    fi
    
    # Prepare Spark configuration
    if ! prepare_spark_config; then
        handle_error "Spark configuration preparation failed" "Compute"
        exit 1
    fi
    
    # Verify setup
    if ! verify_compute_setup; then
        handle_error "Compute verification failed" "Compute"
        exit 1
    fi
    
    # Mark compute as initialized
    create_init_marker "compute"
    
    print_separator "✅ COMPUTE SETUP COMPLETE"
    log_success "Compute setup completed successfully"
    
    echo "⚡ Compute Layer Ready:"
    echo "   • Iceberg JARs downloaded to: $LAKEHOUSE_ROOT/iceberg-jars/"
    echo "   • Spark configuration prepared: $LAKEHOUSE_ROOT/spark-config/"
    echo "   • Ready for Iceberg table format support"
    echo "   • Spark Master UI: http://localhost:8080 (when services are running)"
    echo ""
}

# Only run main if script is executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi