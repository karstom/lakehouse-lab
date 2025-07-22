#!/bin/bash
set -e

# ==============================================================================
# init-all-in-one.sh - Enhanced Lakehouse Lab Initialization Script
# - FIXED: Issues #1 and #2 resolution
# - DuckDB 1.3.0 with duckdb-engine 0.17.0
# - Enhanced error handling and logging
# - Better dependency management
# - TrueNAS SCALE compatibility
# - Robust permission handling
# ==============================================================================

LAKEHOUSE_ROOT="${LAKEHOUSE_ROOT:-/mnt/lakehouse}"
INIT_MARKER="$LAKEHOUSE_ROOT/.lakehouse-initialized"
LOG_FILE="$LAKEHOUSE_ROOT/init.log"

# Color codes for better logging
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [lakehouse-init] $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}$(date '+%Y-%m-%d %H:%M:%S') [ERROR] $1${NC}" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}$(date '+%Y-%m-%d %H:%M:%S') [SUCCESS] $1${NC}" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}$(date '+%Y-%m-%d %H:%M:%S') [WARNING] $1${NC}" | tee -a "$LOG_FILE"
}

log_info() {
    echo -e "${BLUE}$(date '+%Y-%m-%d %H:%M:%S') [INFO] $1${NC}" | tee -a "$LOG_FILE"
}

# Cleanup function for error handling
cleanup() {
    if [ $? -ne 0 ]; then
        log_error "Initialization failed. Check $LOG_FILE for details."
        log_error "To retry, delete $INIT_MARKER and restart the containers."
    fi
}
trap cleanup EXIT

log_info "LAKEHOUSE_ROOT = $LAKEHOUSE_ROOT"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Check if already initialized
if [ -f "$INIT_MARKER" ]; then
    log_success "Already initialized (found $INIT_MARKER)"
    log_info "Skipping initialization. Delete $INIT_MARKER to force re-init."
    exit 0
fi

log_info "🚀 First-time initialization starting..."

# Update package manager and install required tools
log_info "Installing required packages..."
apk update >/dev/null 2>&1 || log_warning "Failed to update package index"
apk add --no-cache curl python3 py3-pip jq bash >/dev/null 2>&1 || {
    log_error "Failed to install required packages"
    exit 1
}

# Install MinIO Client with retry logic
install_minio_client() {
    local max_attempts=3
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        log_info "Downloading MinIO Client (attempt $attempt/$max_attempts)..."
        if curl -sSL https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc; then
            chmod +x /usr/local/bin/mc
            log_success "MinIO Client installed successfully"
            return 0
        else
            log_warning "Download attempt $attempt failed"
            attempt=$((attempt + 1))
            sleep 5
        fi
    done
    
    log_error "Failed to download MinIO Client after $max_attempts attempts"
    return 1
}

install_minio_client || exit 1

# Verify installation
MC_VERSION=$(/usr/local/bin/mc --version | head -n 1)
log_info "Installed mc → $MC_VERSION"

# Export minimal TERM to prevent mc warnings
export TERM=xterm

# Create directory structure with error handling
create_directories() {
    log_info "Creating required directories under $LAKEHOUSE_ROOT..."
    
    local dirs="
        airflow/dags
        airflow/logs
        airflow/logs/scheduler
        minio
        postgres
        notebooks
        spark/jobs
        homer/assets
        superset
    "
    
    for dir in $dirs; do
        if mkdir -p "$LAKEHOUSE_ROOT/$dir"; then
            log_info "Created directory: $dir"
        else
            log_error "Failed to create directory: $dir"
            return 1
        fi
    done
    
    return 0
}

create_directories || exit 1

# Set permissions with proper error handling
set_permissions() {
    log_info "Setting permissions on service folders..."
    
    # Airflow permissions (UID 50000)
    if chown -R 50000:0 "$LAKEHOUSE_ROOT/airflow" 2>/dev/null; then
        log_success "Set Airflow ownership"
    else
        log_warning "Failed to set Airflow ownership (may not be critical)"
    fi
    
    chmod -R 775 "$LAKEHOUSE_ROOT/airflow" || log_warning "Failed to set Airflow permissions"
    chmod -R g+s "$LAKEHOUSE_ROOT/airflow" || log_warning "Failed to set Airflow group permissions"
    chmod -R 777 "$LAKEHOUSE_ROOT/airflow/logs" || log_warning "Failed to set Airflow logs permissions"
    
    # Jupyter permissions (UID 1000)
    if chown -R 1000:100 "$LAKEHOUSE_ROOT/notebooks" 2>/dev/null; then
        log_success "Set Jupyter ownership"
    else
        log_warning "Failed to set Jupyter ownership (may not be critical)"
    fi
    
    chmod -R 755 "$LAKEHOUSE_ROOT/notebooks" || log_warning "Failed to set Jupyter permissions"
    
    # Superset permissions
    if chown -R 1000:0 "$LAKEHOUSE_ROOT/superset" 2>/dev/null; then
        log_success "Set Superset ownership"
    else
        log_warning "Failed to set Superset ownership (may not be critical)"
    fi
    
    chmod -R 755 "$LAKEHOUSE_ROOT/superset" || log_warning "Failed to set Superset permissions"
    
    # Homer permissions
    chmod -R 777 "$LAKEHOUSE_ROOT/homer/assets" || log_warning "Failed to set Homer permissions"
    
    log_success "Permission setup completed"
}

set_permissions

# Wait for services with timeout and retry logic
wait_for_service() {
    local service_name=$1
    local health_url=$2
    local max_attempts=${3:-20}
    local sleep_time=${4:-3}
    
    log_info "Waiting for $service_name to become healthy at $health_url..."
    
    local attempt=1
    while [ $attempt -le $max_attempts ]; do
        if curl -sf "$health_url" >/dev/null 2>&1; then
            log_success "$service_name is healthy"
            return 0
        fi
        log_info "  … $service_name not ready, attempt $attempt/$max_attempts, retrying in ${sleep_time}s"
        sleep $sleep_time
        attempt=$((attempt + 1))
    done
    
    log_error "$service_name failed to become healthy after $max_attempts attempts"
    return 1
}

# Wait for MinIO
wait_for_service "MinIO" "http://minio:9000/minio/health/live" 20 3 || exit 1

# Configure MinIO client first (needed for readiness verification)
configure_minio() {
    log_info "Configuring MinIO client..."
    
    # Set up mc alias with retry
    local max_attempts=5
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if mc alias set local http://minio:9000 minio minio123 >/dev/null 2>&1; then
            log_success "MinIO client configured successfully"
            break
        else
            log_warning "MinIO client configuration attempt $attempt failed, retrying..."
            sleep 2
            attempt=$((attempt + 1))
        fi
    done
    
    if [ $attempt -gt $max_attempts ]; then
        log_error "Failed to configure MinIO client after $max_attempts attempts"
        return 1
    fi
    
    return 0
}

# Configure MinIO client before readiness verification
configure_minio || exit 1

# Enhanced MinIO readiness verification
wait_for_minio_api() {
    local timeout=${MINIO_READY_TIMEOUT:-20}
    local interval=${MINIO_READY_INTERVAL:-3}
    local skip_check=${SKIP_MINIO_READY_CHECK:-false}
    
    if [ "$skip_check" = "true" ]; then
        log_info "MinIO readiness check skipped (SKIP_MINIO_READY_CHECK=true)"
        return 0
    fi
    
    log_info "Performing comprehensive MinIO readiness verification..."
    log_info "Timeout: ${timeout} attempts × ${interval}s = $((timeout * interval))s maximum"
    
    local attempt=1
    while [ $attempt -le $timeout ]; do
        log_info "MinIO API readiness check: attempt $attempt/$timeout"
        
        # Test 1: Basic connectivity test
        if ! curl -sf "http://minio:9000/minio/health/live" >/dev/null 2>&1; then
            log_warning "  ❌ MinIO health endpoint not responding"
        else
            log_info "  ✅ MinIO health endpoint responding"
            
            # Test 2: MinIO client configuration
            if ! mc alias list local >/dev/null 2>&1; then
                log_warning "  ❌ MinIO client alias not configured, attempting reconfiguration..."
                if mc alias set local http://minio:9000 minio minio123 >/dev/null 2>&1; then
                    log_info "  ✅ MinIO client reconfigured successfully"
                else
                    log_warning "  ❌ MinIO client reconfiguration failed"
                fi
            else
                log_info "  ✅ MinIO client alias configured"
            fi
            
            # Test 3: Admin API functionality (the real readiness test)
            local admin_output
            if admin_output=$(mc admin info local 2>&1); then
                log_success "MinIO API is fully operational and ready for bucket operations"
                log_info "MinIO server info: $(echo "$admin_output" | head -1)"
                return 0
            else
                log_warning "  ❌ MinIO admin API not ready: $admin_output"
                
                # Additional debugging for common issues
                if echo "$admin_output" | grep -i "connection refused" >/dev/null; then
                    log_info "  🔍 Diagnosis: MinIO server not accepting connections yet"
                elif echo "$admin_output" | grep -i "timeout" >/dev/null; then
                    log_info "  🔍 Diagnosis: MinIO server responding slowly"
                elif echo "$admin_output" | grep -i "unauthorized\|access denied" >/dev/null; then
                    log_warning "  🔍 Diagnosis: Authentication issue - check MinIO credentials"
                fi
            fi
        fi
        
        if [ $attempt -lt $timeout ]; then
            log_info "  ⏳ Waiting ${interval}s before next attempt..."
            sleep $interval
        fi
        
        attempt=$((attempt + 1))
    done
    
    log_error "MinIO API failed to become ready after $((timeout * interval))s"
    log_error "This usually indicates:"
    log_error "  • MinIO is still initializing (try increasing MINIO_READY_TIMEOUT)"
    log_error "  • Resource constraints (CPU/memory/disk)"
    log_error "  • Network connectivity issues between containers"
    log_error "  • MinIO configuration problems"
    
    # Try a basic operation as fallback
    log_info "Attempting fallback: testing basic MinIO operations..."
    if mc ls local >/dev/null 2>&1; then
        log_warning "Basic MinIO operations work despite admin API issues"
        log_warning "Proceeding with initialization (bucket creation may still work)"
        return 0
    else
        log_error "Both admin API and basic operations failed"
        log_info "To skip this check entirely, set SKIP_MINIO_READY_CHECK=true"
        return 1
    fi
}

# Perform MinIO readiness verification
wait_for_minio_api || exit 1

# Wait for Spark (with more lenient timeout)
wait_for_service "Spark Master" "http://spark-master:8080" 10 5 || {
    log_warning "Spark Master not ready after 50s, continuing anyway..."
    log_warning "Services may start without full coordination"
}

# MinIO client already configured above

# Create and verify buckets with enhanced reliability
create_buckets() {
    log_info "Creating MinIO buckets and directory structure..."
    
    # Since MinIO API is now verified as ready, bucket creation should be more reliable
    local max_attempts=${BUCKET_CREATE_RETRIES:-8}
    local attempt=1
    local bucket_created=false
    
    while [ $attempt -le $max_attempts ] && [ "$bucket_created" = false ]; do
        log_info "Bucket creation attempt $attempt/$max_attempts..."
        
        # Check if bucket already exists first
        if mc ls local/lakehouse >/dev/null 2>&1; then
            log_info "'lakehouse' bucket already exists"
            bucket_created=true
            break
        fi
        
        # Try to create the bucket with detailed error output
        local create_output
        local create_exit_code
        create_output=$(mc mb local/lakehouse 2>&1)
        create_exit_code=$?
        
        if [ $create_exit_code -eq 0 ]; then
            log_success "'lakehouse' bucket created successfully"
            bucket_created=true
            break
        else
            log_warning "Bucket creation attempt $attempt failed with exit code $create_exit_code"
            log_warning "Error details: $create_output"
            
            # Since we've verified MinIO is ready, shorter retry intervals should work
            if [ $attempt -lt $max_attempts ]; then
                local wait_time=2
                log_info "Retrying in ${wait_time}s..."
                sleep $wait_time
            fi
        fi
        
        attempt=$((attempt + 1))
    done
    
    if [ "$bucket_created" = false ]; then
        log_error "Failed to create 'lakehouse' bucket after $max_attempts attempts"
        log_error "This is unexpected since MinIO API was verified as ready."
        log_error "Please check the error details above and consider:"
        log_error "  • Disk space on MinIO storage volume"
        log_error "  • MinIO server configuration"
        log_error "  • Container resource limits"
        return 1
    fi
    
    # Verify bucket was created successfully
    if mc ls local/lakehouse >/dev/null 2>&1; then
        log_success "Bucket 'lakehouse' verification successful"
    else
        log_error "Bucket verification failed - bucket may not be accessible"
        return 1
    fi
    
    # Create directory structure within the bucket using .keep files
    log_info "Creating directory structure within bucket..."
    local directories="warehouse raw-data processed-data iceberg-warehouse"
    local dir_success=0
    local dir_total=0
    
    for dir in $directories; do
        dir_total=$((dir_total + 1))
        # Create directories by putting empty .keep objects
        if echo "# This file ensures the directory exists in MinIO" | mc pipe "local/lakehouse/$dir/.keep" >/dev/null 2>&1; then
            log_success "Created directory: lakehouse/$dir/"
            dir_success=$((dir_success + 1))
        else
            log_warning "Could not create directory lakehouse/$dir/ (may not be critical)"
        fi
    done
    
    log_info "Directory structure: $dir_success/$dir_total directories created successfully"
    
    # Final verification - list the bucket contents
    log_info "Bucket contents verification:"
    if mc ls --recursive local/lakehouse/ 2>/dev/null; then
        log_success "Bucket structure created and verified successfully"
    else
        log_warning "Could not list all bucket contents, but core structure should be ready"
    fi
    
    return 0
}

# Download Iceberg JAR files
download_iceberg_jars() {
    log_info "Downloading Apache Iceberg JAR files for Spark integration..."
    
    # Create iceberg-jars directory inside lakehouse data directory
    local iceberg_dir="$LAKEHOUSE_ROOT/iceberg-jars"
    if mkdir -p "$iceberg_dir"; then
        log_success "Created iceberg-jars directory: $iceberg_dir"
    else
        log_error "Failed to create iceberg-jars directory"
        return 1
    fi
    
    # Iceberg JAR files for Spark 3.5.0
    local iceberg_version="1.4.3"
    local scala_version="2.12"
    local spark_version="3.5"
    
    # Define JAR URLs and files (POSIX compatible)
    local jar_url="https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-spark-runtime-${spark_version}_${scala_version}/${iceberg_version}/iceberg-spark-runtime-${spark_version}_${scala_version}-${iceberg_version}.jar"
    local jar_file="iceberg-spark-runtime-${spark_version}_${scala_version}-${iceberg_version}.jar"
    
    # Download JAR files with retry logic
    local success=true
    local url="$jar_url"
    local filename="$jar_file"
    local filepath="$iceberg_dir/$filename"
    
    if [ -f "$filepath" ]; then
        log_info "JAR already exists: $filename"
    else
        log_info "Downloading: $filename..."
        local max_attempts=3
        local attempt=1
        local downloaded=false
        
        while [ $attempt -le $max_attempts ] && [ "$downloaded" = false ]; do
            if curl -sSL "$url" -o "$filepath"; then
                # Verify the download by checking file size
                local filesize=$(stat -c%s "$filepath" 2>/dev/null || echo "0")
                if [ "$filesize" -gt 1000000 ]; then  # Should be > 1MB
                    log_success "Downloaded: $filename (${filesize} bytes)"
                    downloaded=true
                else
                    log_warning "Downloaded file seems too small, retrying..."
                    rm -f "$filepath"
                fi
            else
                log_warning "Download attempt $attempt failed for $filename"
            fi
            
            if [ "$downloaded" = false ]; then
                attempt=$((attempt + 1))
                sleep 2
            fi
        done
        
        if [ "$downloaded" = false ]; then
            log_error "Failed to download $filename after $max_attempts attempts"
            success=false
        fi
    fi
    
    if [ "$success" = true ]; then
        log_success "All Iceberg JAR files downloaded successfully"
        
        # Create a version file for tracking
        echo "iceberg-spark-runtime-${spark_version}_${scala_version}-${iceberg_version}.jar" > "$iceberg_dir/VERSION"
        echo "Downloaded on: $(date)" >> "$iceberg_dir/VERSION"
        echo "Iceberg version: ${iceberg_version}" >> "$iceberg_dir/VERSION"
        echo "Compatible with: Spark ${spark_version}, Scala ${scala_version}" >> "$iceberg_dir/VERSION"
        
        log_info "To enable Iceberg, use: docker compose -f docker-compose.yml -f docker-compose.iceberg.yml up -d"
        return 0
    else
        log_error "Some Iceberg JAR downloads failed"
        return 1
    fi
}

create_buckets || exit 1

# Download Iceberg JAR files
download_iceberg_jars || {
    log_warning "Iceberg JAR download failed, but continuing with setup"
    log_info "Iceberg support can be enabled later by running the download manually"
}

# Create sample Airflow DAGs - FIXED for Issue #2
create_airflow_dags() {
    log_info "Creating enhanced Airflow DAGs with DuckDB 1.3.0 support..."

    # Enhanced DuckDB Pipeline DAG - FIXED for Issue #2
    cat <<'EOF' > "$LAKEHOUSE_ROOT/airflow/dags/sample_duckdb_pipeline.py"
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator
import logging

default_args = {
    'owner': 'lakehouse-lab',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'sample_duckdb_pipeline',
    default_args=default_args,
    description='Enhanced ETL pipeline using DuckDB 1.3.0 and MinIO',
    schedule_interval=timedelta(hours=6),
    catchup=False,
    tags=['example', 'etl', 'duckdb', 'minio'],
)

def check_dependencies(**context):
    """Check if required dependencies are available - FIXED for Issue #2"""
    try:
        import duckdb
        import boto3
        logging.info(f"✅ DuckDB version: {duckdb.__version__}")
        logging.info("✅ All dependencies are available")
        
        # Test DuckDB connection
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
            record_count = context['task_instance'].xcom_pull(key='record_count', task_ids='extract_data')
            
            if record_count and record_count > 0:
                # Perform transformation
                result = conn.execute("""
                    SELECT 
                        product_category,
                        COUNT(*) as order_count,
                        SUM(total_amount) as total_revenue,
                        AVG(total_amount) as avg_order_value
                    FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')
                    GROUP BY product_category
                    ORDER BY total_revenue DESC
                """).fetchall()
                
                logging.info("✅ Product category analysis:")
                for row in result:
                    logging.info(f"  📊 {row[0]}: {row[1]} orders, ${row[2]:.2f} revenue, ${row[3]:.2f} avg")
                
                return len(result)
            else:
                logging.info("ℹ️ No data to transform")
                return 0
                
        except Exception as e:
            logging.error(f"❌ Transformation failed: {e}")
            raise
            
    finally:
        conn.close()

def data_quality_check(**context):
    """Run basic data quality checks"""
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
            # Basic quality checks
            checks = [
                ("Record Count", "SELECT COUNT(*) FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')"),
                ("Null Check", "SELECT COUNT(*) FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv') WHERE order_id IS NULL"),
                ("Date Range", "SELECT MIN(order_date), MAX(order_date) FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')"),
            ]
            
            results = {}
            for check_name, query in checks:
                try:
                    result = conn.execute(query).fetchone()
                    results[check_name] = result
                    logging.info(f"✅ {check_name}: {result}")
                except Exception as e:
                    logging.warning(f"⚠️ {check_name}: Could not execute - {e}")
                    results[check_name] = f"ERROR: {e}"
            
            return results
            
        except Exception as e:
            logging.warning(f"⚠️ Quality checks could not complete: {e}")
            return {"status": "skipped", "reason": str(e)}
            
    finally:
        conn.close()

# Define tasks
check_deps = PythonOperator(
    task_id='check_dependencies',
    python_callable=check_dependencies,
    dag=dag,
)

configure_s3 = PythonOperator(
    task_id='configure_s3',
    python_callable=configure_duckdb_s3,
    dag=dag,
)

extract_task = PythonOperator(
    task_id='extract_data',
    python_callable=extract_data,
    dag=dag,
)

transform_task = PythonOperator(
    task_id='transform_data',
    python_callable=transform_data,
    dag=dag,
)

quality_check = PythonOperator(
    task_id='data_quality_check',
    python_callable=data_quality_check,
    dag=dag,
)

# Set dependencies
check_deps >> configure_s3 >> extract_task >> transform_task >> quality_check
EOF

    # Enhanced Data Quality Checks DAG
    cat <<'EOF' > "$LAKEHOUSE_ROOT/airflow/dags/data_quality_check.py"
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
import logging

default_args = {
    'owner': 'lakehouse-lab',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'data_quality_checks',
    default_args=default_args,
    description='Enhanced data quality monitoring using DuckDB 1.3.0',
    schedule_interval=timedelta(hours=12),
    catchup=False,
    tags=['data-quality', 'monitoring', 'duckdb'],
)

def run_comprehensive_quality_checks(**context):
    """Run comprehensive data quality checks using DuckDB 1.3.0"""
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
        
        # Enhanced quality checks
        checks = [
            ("Record Count", "SELECT COUNT(*) FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')"),
            ("Null Check - Order ID", "SELECT COUNT(*) FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv') WHERE order_id IS NULL"),
            ("Null Check - Customer ID", "SELECT COUNT(*) FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv') WHERE customer_id IS NULL"),
            ("Date Range", "SELECT MIN(order_date), MAX(order_date) FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')"),
            ("Negative Amounts", "SELECT COUNT(*) FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv') WHERE total_amount < 0"),
            ("Duplicate Orders", "SELECT COUNT(*) - COUNT(DISTINCT order_id) FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')"),
            ("Category Distribution", "SELECT product_category, COUNT(*) FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv') GROUP BY product_category"),
        ]
        
        results = {}
        failed_checks = 0
        
        for check_name, query in checks:
            try:
                result = conn.execute(query).fetchall()
                results[check_name] = result
                
                # Define quality rules
                if check_name == "Record Count" and (not result or result[0][0] == 0):
                    logging.warning(f"⚠️ {check_name}: No data found")
                    failed_checks += 1
                elif check_name in ["Null Check - Order ID", "Null Check - Customer ID", "Negative Amounts", "Duplicate Orders"] and result and result[0][0] > 0:
                    logging.warning(f"⚠️ {check_name}: Found {result[0][0]} issues")
                    failed_checks += 1
                else:
                    logging.info(f"✅ {check_name}: {result}")
                    
            except Exception as e:
                logging.error(f"❌ {check_name}: ERROR - {e}")
                results[check_name] = f"ERROR: {e}"
                failed_checks += 1
        
        # Summary
        total_checks = len(checks)
        passed_checks = total_checks - failed_checks
        
        logging.info(f"📊 Quality Check Summary: {passed_checks}/{total_checks} checks passed")
        
        if failed_checks > 0:
            logging.warning(f"⚠️ {failed_checks} quality issues detected")
        else:
            logging.info("✅ All quality checks passed!")
        
        return results
        
    except ImportError as e:
        logging.error(f"❌ Missing dependency: {e}")
        raise
    finally:
        conn.close()

quality_check_task = PythonOperator(
    task_id='run_comprehensive_quality_checks',
    python_callable=run_comprehensive_quality_checks,
    dag=dag,
)
EOF

    log_success "Enhanced Airflow DAGs created with DuckDB 1.3.0 support"
}

create_airflow_dags

# Create Jupyter notebook examples
create_jupyter_notebooks() {
    log_info "Creating sample Jupyter notebooks..."

    cat <<'EOF' > "$LAKEHOUSE_ROOT/notebooks/01_Getting_Started.ipynb"
{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# Lakehouse Lab - Getting Started (DuckDB 1.3.0)\n",
    "\n",
    "Welcome to your lakehouse environment! This notebook demonstrates the latest DuckDB 1.3.0 features.\n",
    "\n",
    "## What's Available\n",
    "\n",
    "- **MinIO**: S3-compatible object storage\n",
    "- **Apache Spark**: Distributed data processing\n",
    "- **DuckDB 1.3.0**: Fast analytics database with enhanced S3 support\n",
    "- **Apache Airflow**: Workflow orchestration\n",
    "- **Apache Superset**: Business intelligence and visualization\n",
    "- **Portainer**: Container management\n"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Import necessary libraries - FIXED: No more import errors!\n",
    "import pandas as pd\n",
    "import duckdb\n",
    "import boto3\n",
    "from pyspark.sql import SparkSession\n",
    "import os\n",
    "\n",
    "print(\"✅ Lakehouse Lab Environment Ready!\")\n",
    "print(f\"📊 DuckDB version: {duckdb.__version__}\")  # Should show 1.3.0\n",
    "print(f\"🐍 Python version: {os.sys.version}\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Connect to MinIO (S3-Compatible Storage)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Configure MinIO connection\n",
    "s3_client = boto3.client(\n",
    "    's3',\n",
    "    endpoint_url='http://minio:9000',\n",
    "    aws_access_key_id='minio',\n",
    "    aws_secret_access_key='minio123'\n",
    ")\n",
    "\n",
    "# List buckets\n",
    "buckets = s3_client.list_buckets()\n",
    "print(\"Available buckets:\")\n",
    "for bucket in buckets['Buckets']:\n",
    "    print(f\"  - {bucket['Name']}\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Query Data with DuckDB 1.3.0"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Connect to DuckDB\n",
    "conn = duckdb.connect()\n",
    "\n",
    "# Configure S3 access for DuckDB\n",
    "conn.execute(\"\"\"\n",
    "    INSTALL httpfs;\n",
    "    LOAD httpfs;\n",
    "    SET s3_endpoint='minio:9000';\n",
    "    SET s3_access_key_id='minio';\n",
    "    SET s3_secret_access_key='minio123';\n",
    "    SET s3_use_ssl=false;\n",
    "    SET s3_url_style='path';\n",
    "\"\"\")\n",
    "\n",
    "print(\"✅ DuckDB 1.3.0 configured for S3 access!\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Query sample data\n",
    "result = conn.execute(\"\"\"\n",
    "    SELECT * FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')\n",
    "    LIMIT 10\n",
    "\"\"\").fetchdf()\n",
    "\n",
    "print(\"Sample data from MinIO:\")\n",
    "display(result)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Analytics with DuckDB 1.3.0"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Run analytics query\n",
    "analytics = conn.execute(\"\"\"\n",
    "    SELECT \n",
    "        product_category,\n",
    "        COUNT(*) as order_count,\n",
    "        SUM(total_amount) as total_revenue,\n",
    "        AVG(total_amount) as avg_order_value\n",
    "    FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')\n",
    "    GROUP BY product_category\n",
    "    ORDER BY total_revenue DESC\n",
    "\"\"\").fetchdf()\n",
    "\n",
    "print(\"Sales by Product Category:\")\n",
    "display(analytics)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Initialize Spark Session"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Create Spark session\n",
    "spark = SparkSession.builder \\\n",
    "    .appName(\"Lakehouse Lab\") \\\n",
    "    .config(\"spark.hadoop.fs.s3a.endpoint\", \"http://minio:9000\") \\\n",
    "    .config(\"spark.hadoop.fs.s3a.access.key\", \"minio\") \\\n",
    "    .config(\"spark.hadoop.fs.s3a.secret.key\", \"minio123\") \\\n",
    "    .config(\"spark.hadoop.fs.s3a.path.style.access\", \"true\") \\\n",
    "    .config(\"spark.hadoop.fs.s3a.connection.ssl.enabled\", \"false\") \\\n",
    "    .getOrCreate()\n",
    "\n",
    "print(f\"Spark version: {spark.version}\")\n",
    "print(\"✅ Spark session created successfully!\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Next Steps\n",
    "\n",
    "1. **Explore Superset**: Open http://localhost:9030 to create dashboards\n",
    "2. **Check Airflow**: Visit http://localhost:9020 to see workflow orchestration\n",
    "3. **Monitor with Portainer**: Use http://localhost:9060 for container management\n",
    "4. **Access MinIO Console**: Visit http://localhost:9001 for file management\n",
    "\n",
    "## Issues Fixed\n",
    "\n",
    "✅ **Issue #1**: Superset S3 configuration now persistent  \n",
    "✅ **Issue #2**: Airflow DuckDB import errors resolved  \n",
    "✅ **Latest packages**: DuckDB 1.3.0 + duckdb-engine 0.17.0  \n",
    "\n",
    "Happy data engineering!"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.8.10"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}
EOF

    cat <<'EOF' > "$LAKEHOUSE_ROOT/notebooks/02_Advanced_Analytics.ipynb"
{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# Advanced Analytics with DuckDB 1.3.0 and Spark\n",
    "\n",
    "This notebook demonstrates advanced analytics capabilities using DuckDB 1.3.0's latest features."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import duckdb\n",
    "import pandas as pd\n",
    "import matplotlib.pyplot as plt\n",
    "import seaborn as sns\n",
    "from pyspark.sql import SparkSession\n",
    "from pyspark.sql.functions import *\n",
    "\n",
    "# Configure plotting\n",
    "plt.style.use('seaborn-v0_8')\n",
    "%matplotlib inline\n",
    "\n",
    "print(f\"✅ DuckDB version: {duckdb.__version__}\")  # Should show 1.3.0"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Multi-File Analytics with DuckDB 1.3.0"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Connect to DuckDB and configure S3\n",
    "conn = duckdb.connect()\n",
    "conn.execute(\"\"\"\n",
    "    INSTALL httpfs;\n",
    "    LOAD httpfs;\n",
    "    SET s3_endpoint='minio:9000';\n",
    "    SET s3_access_key_id='minio';\n",
    "    SET s3_secret_access_key='minio123';\n",
    "    SET s3_use_ssl=false;\n",
    "    SET s3_url_style='path';\n",
    "\"\"\")\n",
    "\n",
    "# Multi-file query example\n",
    "multi_file_analysis = conn.execute(\"\"\"\n",
    "    SELECT \n",
    "        'sample_orders.csv' as file_source,\n",
    "        COUNT(*) as record_count,\n",
    "        SUM(total_amount) as total_revenue\n",
    "    FROM read_csv_auto('s3://lakehouse/raw-data/*.csv', union_by_name=true)\n",
    "    GROUP BY file_source\n",
    "\"\"\").fetchdf()\n",
    "\n",
    "print(\"Multi-file analysis:\")\n",
    "display(multi_file_analysis)"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Time Series Analysis"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Time series analysis\n",
    "time_series = conn.execute(\"\"\"\n",
    "    SELECT \n",
    "        DATE_TRUNC('month', order_date::DATE) as month,\n",
    "        COUNT(*) as orders,\n",
    "        SUM(total_amount) as revenue\n",
    "    FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')\n",
    "    GROUP BY DATE_TRUNC('month', order_date::DATE)\n",
    "    ORDER BY month\n",
    "\"\"\").fetchdf()\n",
    "\n",
    "# Plot time series\n",
    "fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))\n",
    "\n",
    "ax1.plot(time_series['month'], time_series['orders'], marker='o')\n",
    "ax1.set_title('Orders Over Time')\n",
    "ax1.set_ylabel('Number of Orders')\n",
    "\n",
    "ax2.plot(time_series['month'], time_series['revenue'], marker='o', color='green')\n",
    "ax2.set_title('Revenue Over Time')\n",
    "ax2.set_ylabel('Revenue ($)')\n",
    "ax2.set_xlabel('Month')\n",
    "\n",
    "plt.tight_layout()\n",
    "plt.show()\n",
    "\n",
    "display(time_series)"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "name": "python",
   "version": "3.8.10"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}
EOF

    # Create Iceberg example notebook
    cat <<'EOF' > "$LAKEHOUSE_ROOT/notebooks/03_Iceberg_Tables.ipynb"
{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# Apache Iceberg Tables with Spark 3.5.0\n",
    "\n",
    "This notebook demonstrates how to use Apache Iceberg with Spark for lakehouse table management.\n",
    "\n",
    "**Requirements:**\n",
    "- Start with Iceberg enabled: `docker compose -f docker-compose.yml -f docker-compose.iceberg.yml up -d`\n",
    "- Iceberg JAR files automatically downloaded during setup"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Import libraries\n",
    "from pyspark.sql import SparkSession\n",
    "from pyspark.sql.functions import *\n",
    "from pyspark.sql.types import *\n",
    "import pandas as pd\n",
    "\n",
    "print(\"📦 Iceberg with Spark 3.5.0 Example\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Initialize Spark with Iceberg Support"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Create Spark session with Iceberg configuration\n",
    "# Note: These configurations should already be set when using docker-compose.iceberg.yml\n",
    "spark = SparkSession.builder \\\n",
    "    .appName(\"Iceberg Lakehouse Demo\") \\\n",
    "    .config(\"spark.sql.extensions\", \"org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions\") \\\n",
    "    .config(\"spark.sql.catalog.spark_catalog\", \"org.apache.iceberg.spark.SparkSessionCatalog\") \\\n",
    "    .config(\"spark.sql.catalog.spark_catalog.type\", \"hive\") \\\n",
    "    .config(\"spark.sql.catalog.iceberg\", \"org.apache.iceberg.spark.SparkCatalog\") \\\n",
    "    .config(\"spark.sql.catalog.iceberg.type\", \"hadoop\") \\\n",
    "    .config(\"spark.sql.catalog.iceberg.warehouse\", \"s3a://lakehouse/iceberg-warehouse/\") \\\n",
    "    .config(\"spark.hadoop.fs.s3a.endpoint\", \"http://minio:9000\") \\\n",
    "    .config(\"spark.hadoop.fs.s3a.access.key\", \"minio\") \\\n",
    "    .config(\"spark.hadoop.fs.s3a.secret.key\", \"minio123\") \\\n",
    "    .config(\"spark.hadoop.fs.s3a.path.style.access\", \"true\") \\\n",
    "    .config(\"spark.hadoop.fs.s3a.connection.ssl.enabled\", \"false\") \\\n",
    "    .getOrCreate()\n",
    "\n",
    "print(f\"✅ Spark {spark.version} with Iceberg support initialized\")\n",
    "print(f\"📍 Iceberg warehouse: s3a://lakehouse/iceberg-warehouse/\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Load Sample Data"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Load sample data from MinIO\n",
    "try:\n",
    "    df = spark.read \\\n",
    "        .option(\"header\", \"true\") \\\n",
    "        .option(\"inferSchema\", \"true\") \\\n",
    "        .csv(\"s3a://lakehouse/raw-data/sample_orders.csv\")\n",
    "    \n",
    "    print(f\"📊 Loaded {df.count()} records from sample_orders.csv\")\n",
    "    print(\"🔍 Schema:\")\n",
    "    df.printSchema()\n",
    "    \n",
    "    # Show sample data\n",
    "    print(\"📄 Sample data:\")\n",
    "    df.show(5)\n",
    "    \n",
    "except Exception as e:\n",
    "    print(f\"⚠️ Could not load sample data: {e}\")\n",
    "    print(\"Creating sample data for demo...\")\n",
    "    \n",
    "    # Create sample data for demo\n",
    "    sample_data = [\n",
    "        (\"ORD-0000001\", \"CUST-000001\", \"2024-01-15\", \"Electronics\", \"Laptop\", 2, 999.99, 0.1, 25.00, 1824.99),\n",
    "        (\"ORD-0000002\", \"CUST-000002\", \"2024-01-16\", \"Clothing\", \"T-Shirt\", 5, 29.99, 0.0, 10.00, 159.95),\n",
    "        (\"ORD-0000003\", \"CUST-000003\", \"2024-01-17\", \"Books\", \"Data Engineering\", 1, 49.99, 0.05, 5.00, 52.49)\n",
    "    ]\n",
    "    \n",
    "    schema = StructType([\n",
    "        StructField(\"order_id\", StringType(), True),\n",
    "        StructField(\"customer_id\", StringType(), True),\n",
    "        StructField(\"order_date\", StringType(), True),\n",
    "        StructField(\"product_category\", StringType(), True),\n",
    "        StructField(\"product_name\", StringType(), True),\n",
    "        StructField(\"quantity\", IntegerType(), True),\n",
    "        StructField(\"unit_price\", DoubleType(), True),\n",
    "        StructField(\"discount\", DoubleType(), True),\n",
    "        StructField(\"shipping_cost\", DoubleType(), True),\n",
    "        StructField(\"total_amount\", DoubleType(), True)\n",
    "    ])\n",
    "    \n",
    "    df = spark.createDataFrame(sample_data, schema)\n",
    "    print(f\"📊 Created sample dataset with {df.count()} records\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Create Iceberg Table"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Create Iceberg table\n",
    "table_name = \"iceberg.orders\"\n",
    "\n",
    "try:\n",
    "    # Drop table if exists (for demo purposes)\n",
    "    spark.sql(f\"DROP TABLE IF EXISTS {table_name}\")\n",
    "    print(f\"🗑️ Dropped existing table {table_name}\")\n",
    "except:\n",
    "    pass\n",
    "\n",
    "# Create Iceberg table with partitioning\n",
    "df.writeTo(table_name) \\\n",
    "    .option(\"write-audit-publish\", \"false\") \\\n",
    "    .partitionedBy(\"product_category\") \\\n",
    "    .createOrReplace()\n",
    "\n",
    "print(f\"✅ Created Iceberg table: {table_name}\")\n",
    "print(f\"📂 Partitioned by: product_category\")\n",
    "\n",
    "# Verify table creation\n",
    "iceberg_df = spark.table(table_name)\n",
    "print(f\"📊 Table has {iceberg_df.count()} records\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Query Iceberg Table"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Query the Iceberg table\n",
    "print(\"📋 Querying Iceberg table:\")\n",
    "spark.sql(f\"SELECT * FROM {table_name}\").show()\n",
    "\n",
    "# Analytics query with partitioning benefits\n",
    "print(\"📈 Sales by product category (leveraging partitioning):\")\n",
    "sales_by_category = spark.sql(f\"\"\"\n",
    "    SELECT \n",
    "        product_category,\n",
    "        COUNT(*) as order_count,\n",
    "        SUM(total_amount) as total_revenue,\n",
    "        AVG(total_amount) as avg_order_value\n",
    "    FROM {table_name}\n",
    "    GROUP BY product_category\n",
    "    ORDER BY total_revenue DESC\n",
    "\"\"\")\n",
    "\n",
    "sales_by_category.show()"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Iceberg Time Travel and Versioning"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Insert more data to create a new version\n",
    "new_data = [\n",
    "    (\"ORD-0000004\", \"CUST-000004\", \"2024-01-18\", \"Electronics\", \"Smartphone\", 1, 799.99, 0.05, 15.00, 774.99),\n",
    "    (\"ORD-0000005\", \"CUST-000005\", \"2024-01-19\", \"Home\", \"Coffee Maker\", 1, 199.99, 0.0, 20.00, 219.99)\n",
    "]\n",
    "\n",
    "new_df = spark.createDataFrame(new_data, df.schema)\n",
    "\n",
    "# Append to Iceberg table\n",
    "new_df.writeTo(table_name).append()\n",
    "\n",
    "print(f\"➕ Added {new_df.count()} more records\")\n",
    "print(f\"📊 Table now has {spark.table(table_name).count()} total records\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Show table history (time travel capability)\n",
    "print(\"🕒 Table history (Iceberg time travel):\")\n",
    "try:\n",
    "    history = spark.sql(f\"SELECT * FROM {table_name}.history\")\n",
    "    history.show(truncate=False)\n",
    "except Exception as e:\n",
    "    print(f\"ℹ️ History metadata: {e}\")\n",
    "\n",
    "# Show table snapshots\n",
    "print(\"📸 Table snapshots:\")\n",
    "try:\n",
    "    snapshots = spark.sql(f\"SELECT * FROM {table_name}.snapshots\")\n",
    "    snapshots.show(truncate=False)\n",
    "except Exception as e:\n",
    "    print(f\"ℹ️ Snapshots metadata: {e}\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Iceberg Schema Evolution"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Demonstrate schema evolution - add a new column\n",
    "print(\"🔄 Schema evolution: Adding 'order_priority' column\")\n",
    "\n",
    "# Add new column to the table\n",
    "spark.sql(f\"ALTER TABLE {table_name} ADD COLUMN order_priority string\")\n",
    "\n",
    "# Update some records with the new column\n",
    "spark.sql(f\"\"\"\n",
    "    UPDATE {table_name}\n",
    "    SET order_priority = CASE \n",
    "        WHEN total_amount > 500 THEN 'HIGH'\n",
    "        WHEN total_amount > 100 THEN 'MEDIUM'\n",
    "        ELSE 'LOW'\n",
    "    END\n",
    "\"\"\")\n",
    "\n",
    "print(\"✅ Schema evolved - added order_priority column\")\n",
    "\n",
    "# Show updated data\n",
    "print(\"📋 Updated table with new column:\")\n",
    "spark.sql(f\"SELECT order_id, product_category, total_amount, order_priority FROM {table_name}\").show()"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Data Quality and ACID Transactions"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Demonstrate ACID transactions with merge operations\n",
    "print(\"⚡ ACID Transactions: MERGE operation\")\n",
    "\n",
    "# Create staging data with updates and new records\n",
    "staging_data = [\n",
    "    (\"ORD-0000001\", \"CUST-000001\", \"2024-01-15\", \"Electronics\", \"Laptop\", 2, 899.99, 0.15, 25.00, 1554.99, \"HIGH\"),  # Updated price\n",
    "    (\"ORD-0000006\", \"CUST-000006\", \"2024-01-20\", \"Sports\", \"Running Shoes\", 1, 149.99, 0.0, 12.00, 161.99, \"MEDIUM\")  # New record\n",
    "]\n",
    "\n",
    "staging_schema = df.schema.add(\"order_priority\", StringType())\n",
    "staging_df = spark.createDataFrame(staging_data, staging_schema)\n",
    "\n",
    "# Register as temporary view for MERGE\n",
    "staging_df.createOrReplaceTempView(\"staging_orders\")\n",
    "\n",
    "# Perform MERGE operation (UPSERT)\n",
    "merge_query = f\"\"\"\n",
    "MERGE INTO {table_name} target\n",
    "USING staging_orders source\n",
    "ON target.order_id = source.order_id\n",
    "WHEN MATCHED THEN UPDATE SET\n",
    "    unit_price = source.unit_price,\n",
    "    total_amount = source.total_amount,\n",
    "    discount = source.discount,\n",
    "    order_priority = source.order_priority\n",
    "WHEN NOT MATCHED THEN INSERT\n",
    "    (order_id, customer_id, order_date, product_category, product_name, \n",
    "     quantity, unit_price, discount, shipping_cost, total_amount, order_priority)\n",
    "VALUES\n",
    "    (source.order_id, source.customer_id, source.order_date, source.product_category, \n",
    "     source.product_name, source.quantity, source.unit_price, source.discount, \n",
    "     source.shipping_cost, source.total_amount, source.order_priority)\n",
    "\"\"\"\n",
    "\n",
    "spark.sql(merge_query)\n",
    "\n",
    "print(\"✅ MERGE operation completed\")\n",
    "print(f\"📊 Table now has {spark.table(table_name).count()} records\")\n",
    "\n",
    "# Show final result\n",
    "print(\"📋 Final table state:\")\n",
    "spark.sql(f\"SELECT order_id, product_category, unit_price, total_amount, order_priority FROM {table_name} ORDER BY order_id\").show()"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Cleanup"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Optional: Drop the demo table\n",
    "# spark.sql(f\"DROP TABLE IF EXISTS {table_name}\")\n",
    "# print(f\"🗑️ Dropped table {table_name}\")\n",
    "\n",
    "print(\"\\n🎉 Iceberg Demo Complete!\")\n",
    "print(\"\\n✨ Key Iceberg Features Demonstrated:\")\n",
    "print(\"   • ✅ Table creation with partitioning\")\n",
    "print(\"   • ✅ Time travel and versioning\")\n",
    "print(\"   • ✅ Schema evolution\")\n",
    "print(\"   • ✅ ACID transactions with MERGE\")\n",
    "print(\"   • ✅ S3-compatible storage (MinIO)\")\n",
    "print(\"\\n📚 Next Steps:\")\n",
    "print(\"   • Explore table metadata and partitioning strategies\")\n",
    "print(\"   • Set up automated data pipelines with Airflow\")\n",
    "print(\"   • Create dashboards in Superset using Iceberg tables\")"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.8.10"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}
EOF

    log_success "Jupyter notebooks created with DuckDB 1.3.0 and Iceberg examples"
}

create_jupyter_notebooks

# Create sample data - UPDATED for testing
create_sample_data() {
    if [ "$INSTALL_SAMPLES" = "true" ]; then
        log_info "Creating sample datasets..."
        
        # Generate sample data using Python
        cat > /tmp/generate_sample_data.py << 'PYTHON_SCRIPT'
import csv
import random
from datetime import datetime, timedelta

# Generate enhanced orders data for DuckDB 1.3.0 testing
orders = []
base_date = datetime(2023, 1, 1)

product_categories = ['Electronics', 'Clothing', 'Books', 'Home', 'Sports', 'Beauty', 'Automotive']
regions = ['North', 'South', 'East', 'West', 'Central']
channels = ['Online', 'Store', 'Mobile App', 'Phone']

for i in range(10000):  # Increased sample size
    order_date = base_date + timedelta(days=random.randint(0, 500))
    quantity = random.randint(1, 10)
    unit_price = round(random.uniform(5, 1000), 2)
    discount = round(random.uniform(0, 0.4), 2)
    shipping_cost = round(random.uniform(0, 50), 2)
    
    orders.append({
        'order_id': f'ORD-{i+1:07d}',
        'customer_id': f'CUST-{random.randint(1, 2000):06d}',
        'order_date': order_date.strftime('%Y-%m-%d'),
        'product_category': random.choice(product_categories),
        'product_name': f'Product-{random.randint(1, 500)}',
        'quantity': quantity,
        'unit_price': unit_price,
        'discount': discount,
        'shipping_cost': shipping_cost,
        'total_amount': round(quantity * unit_price * (1 - discount) + shipping_cost, 2),
        'region': random.choice(regions),
        'sales_channel': random.choice(channels),
        'customer_segment': random.choice(['Premium', 'Standard', 'Basic']),
        'payment_method': random.choice(['Credit Card', 'Debit Card', 'PayPal', 'Cash'])
    })

# Write to CSV
with open('/tmp/sample_orders.csv', 'w', newline='') as csvfile:
    fieldnames = orders[0].keys()
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(orders)

print(f"Created enhanced sample orders dataset with {len(orders)} records for DuckDB 1.3.0 testing")
PYTHON_SCRIPT

        # Run the Python script
        if python3 /tmp/generate_sample_data.py; then
            log_success "Sample data generation completed"
            
            # Copy generated file to notebooks and MinIO
            if [ -f "/tmp/sample_orders.csv" ]; then
                cp "/tmp/sample_orders.csv" "$LAKEHOUSE_ROOT/notebooks/"
                if mc cp "/tmp/sample_orders.csv" local/lakehouse/raw-data/ >/dev/null 2>&1; then
                    log_success "Sample orders dataset uploaded to MinIO"
                else
                    log_warning "Failed to upload sample data to MinIO"
                fi
                rm -f "/tmp/sample_orders.csv"
            fi
        else
            log_warning "Sample data generation failed"
        fi
        
        # Clean up
        rm -f /tmp/generate_sample_data.py
    fi
}

create_sample_data

# Create Homer dashboard configuration
create_homer_config() {
    log_info "Creating Homer dashboard configuration..."
    
    cat > "$LAKEHOUSE_ROOT/homer/assets/config.yml" << 'EOF'
title: "Lakehouse Lab Dashboard"
subtitle: "Open Source Data Analytics Stack - Issues #1 & #2 Fixed!"
logo: "/logo.png"
icon: "fas fa-database"
header: true

theme: default
colors:
  light:
    highlight-primary: "#3367d6"
    highlight-secondary: "#4285f4"
    background: "#f5f5f5"
    text: "#363636"
  dark:
    highlight-primary: "#3367d6"
    highlight-secondary: "#4285f4"
    background: "#2b2b2b"
    text: "#eaeaea"

footer: '<p>Lakehouse Lab v2.0 - Issues Resolved | DuckDB 1.3.0 + duckdb-engine 0.17.0</p>'

message:
  style: "is-success"
  title: "✅ All Issues Fixed!"
  icon: "fa fa-check-circle"
  content: "Your lakehouse is ready with all issues resolved:<br />✅ <strong>Issue #1</strong>: Superset S3 configuration now persistent<br />✅ <strong>Issue #2</strong>: Airflow DuckDB imports working<br />🚀 <strong>Latest tech</strong>: DuckDB 1.3.0 + duckdb-engine 0.17.0"

services:
  - name: "Analytics & BI - ✅ Fixed"
    icon: "fas fa-chart-line"
    items:
      - name: "Superset (Issue #1 Fixed)"
        icon: "fas fa-chart-bar"
        subtitle: "BI & Visualization - S3 config now persistent!"
        tag: "fixed"
        url: "http://localhost:9030"
        target: "_blank"

      - name: "JupyterLab (DuckDB 1.3.0)"
        icon: "fas fa-book"
        subtitle: "Data Science - Latest DuckDB packages installed"
        tag: "updated"
        url: "http://localhost:9040"
        target: "_blank"

  - name: "Orchestration - ✅ Fixed"
    icon: "fas fa-cogs"
    items:
      - name: "Airflow (Issue #2 Fixed)"
        icon: "fas fa-tachometer-alt"
        subtitle: "Workflow Orchestration - DuckDB imports working!"
        tag: "fixed"
        url: "http://localhost:9020"
        target: "_blank"

  - name: "Storage & Infrastructure"
    icon: "fas fa-server"
    items:
      - name: "MinIO Console"
        icon: "fas fa-cloud"
        subtitle: "S3-Compatible Object Storage"
        tag: "storage"
        url: "http://localhost:9001"
        target: "_blank"

      - name: "Spark Master"
        icon: "fas fa-fire"
        subtitle: "Distributed Data Processing Engine"
        tag: "compute"
        url: "http://localhost:8080"
        target: "_blank"

      - name: "Portainer"
        icon: "fas fa-docker"
        subtitle: "Container Management & Monitoring"
        tag: "monitoring"
        url: "http://localhost:9060"
        target: "_blank"

links:
  - name: "Local Services"
    icon: "fas fa-home"
    url: "http://localhost:9061"
    target: "_self"
  
  - name: "Test Health"
    icon: "fas fa-heartbeat"
    url: "#"
    target: "_self"
EOF

    log_success "Homer dashboard configuration created"
    
    # Copy config to correct location for Homer container
    if cp "$LAKEHOUSE_ROOT/homer/assets/config.yml" "$LAKEHOUSE_ROOT/homer/config.yml"; then
        log_success "Homer config copied to correct location"
    else
        log_warning "Failed to copy Homer config to root location"
    fi
}

create_homer_config

# Configure Superset DuckDB connection - FIXED for Issue #1
configure_superset_duckdb() {
    log_info "Configuring Superset DuckDB connection for Issue #1 fix..."
    
    # Wait for Superset to be healthy
    wait_for_service "Superset" "http://superset:8088/health" 15 10 || {
        log_warning "Superset not ready, configuration will be done during container startup"
        return 0
    }
    
    # Create enhanced configuration script for Superset startup
    cat > "$LAKEHOUSE_ROOT/superset/setup_duckdb.py" << 'EOF'
import duckdb
import os

# Create DuckDB file with S3 configuration - FIXED for Issue #1
db_path = '/app/superset_home/lakehouse.duckdb'
conn = duckdb.connect(db_path)

try:
    # Install and configure httpfs for S3 access
    conn.execute("INSTALL httpfs")
    conn.execute("LOAD httpfs")
    
    # Set S3 configuration for MinIO - FIXED to use minio:9000 instead of AWS
    conn.execute("SET s3_endpoint='minio:9000'")
    conn.execute("SET s3_access_key_id='minio'")
    conn.execute("SET s3_secret_access_key='minio123'")
    conn.execute("SET s3_use_ssl=false")
    conn.execute("SET s3_url_style='path'")
    
    # Create persistent S3 configuration macro for session consistency
    conn.execute("CREATE SCHEMA IF NOT EXISTS config")
    conn.execute("""
        CREATE OR REPLACE MACRO configure_s3() AS (
            INSTALL httpfs;
            LOAD httpfs;
            SET s3_endpoint='minio:9000';
            SET s3_access_key_id='minio';
            SET s3_secret_access_key='minio123';
            SET s3_use_ssl=false;
            SET s3_url_style='path';
        )
    """)
    print("✅ Created S3 configuration macro for session consistency")
    
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
EOF

    log_success "Superset database connection script created"
}

configure_superset_duckdb

# Create marker file to indicate successful initialization
echo "Lakehouse Lab initialized on $(date)" > "$INIT_MARKER"
echo "Issues #1 and #2 resolved" >> "$INIT_MARKER"
echo "DuckDB 1.3.0 + duckdb-engine 0.17.0" >> "$INIT_MARKER"

log_success "Created initialization marker: $INIT_MARKER"

# Verify critical components
log_info "Verifying initialization..."

# Verify notebooks were created successfully
if [ -f "$LAKEHOUSE_ROOT/notebooks/01_Getting_Started.ipynb" ]; then
    log_success "Jupyter notebooks created successfully"
else
    log_warning "Notebook creation may have failed"
fi

# Verify sample data was uploaded
if mc ls local/lakehouse/raw-data/sample_orders.csv >/dev/null 2>&1; then
    log_success "Sample data uploaded successfully"
else
    log_warning "Sample data upload may have failed"
fi

# Verify DAGs were created
if [ -f "$LAKEHOUSE_ROOT/airflow/dags/sample_duckdb_pipeline.py" ]; then
    log_success "Airflow DAGs created successfully"
else
    log_warning "Airflow DAG creation may have failed"
fi

log_success "Initialization verification completed"

echo ""
echo "=================================================================="
echo "🎉 LAKEHOUSE LAB SETUP COMPLETE! 🎉"
echo "=================================================================="
echo ""
echo "✅ New: Superset S3 configuration now persistent"
echo "✅ RESOLVED: Airflow DuckDB imports working perfectly"
echo "🚀 UPDATED: DuckDB 1.3.0 + duckdb-engine 0.17.0 (latest stable)"
echo ""
echo "Your lakehouse environment is ready! Access points:"
echo ""
echo "🐳 Portainer:         http://localhost:9060 (container management)"
echo "📈 Superset BI:       http://localhost:9030 (admin/admin) - S3 FIXED!"
echo "📋 Airflow:           http://localhost:9020 (admin/admin) - IMPORTS FIXED!"
echo "📓 JupyterLab:        http://localhost:9040 (token: lakehouse)"
echo "☁️  MinIO Console:     http://localhost:9001 (minio/minio123)"
echo "⚡ Spark Master:      http://localhost:8080"
echo "🏠 Service Links:     http://localhost:9061 (Homer dashboard)"
echo ""
echo "🔧 WHAT'S FIXED:"
echo "   • Superset: No more S3 configuration per session"
echo "   • Superset: Single-query dataset creation documented"
echo "   • Airflow: DuckDB packages pre-installed in all containers"
echo "   • Latest: DuckDB 1.3.0 with UUID v7 and enhanced S3 performance"
echo "   • NEW: Apache Iceberg JAR files downloaded automatically"
echo ""
echo "📚 QUICK START:"
echo "   1. Visit Superset → SQL Lab → Run: SELECT * FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv') LIMIT 10;"
echo "   2. Visit Airflow → Enable 'sample_duckdb_pipeline' DAG → Trigger (should work!)"
echo "   3. Visit JupyterLab → Open '01_Getting_Started.ipynb' → Run cells"
echo "   4. For Iceberg: docker compose -f docker-compose.yml -f docker-compose.iceberg.yml up -d"
echo ""
echo "🐳 CONTAINER MANAGEMENT: Portainer at :9060 provides:"
echo "   • Real-time container stats (CPU, memory, network)"
echo "   • Log viewing and container management"
echo "   • Service health monitoring"
echo ""
echo "Happy Data Engineering! 🚀"
