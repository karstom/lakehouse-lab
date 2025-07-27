#!/bin/bash
# ==============================================================================
# init-core.sh - Shared Utilities for Lakehouse Lab Initialization
# ==============================================================================
# Provides common logging, waiting, and cleanup functions for all init modules

set -e

# Configuration from main script
LAKEHOUSE_ROOT="${LAKEHOUSE_ROOT:-./lakehouse-data}"
INIT_MARKER="$LAKEHOUSE_ROOT/.initialized"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ==============================================================================
# LOGGING FUNCTIONS
# ==============================================================================

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LAKEHOUSE_ROOT/init.log"
}

log_error() {
    echo -e "${RED}$(date '+%Y-%m-%d %H:%M:%S') ERROR: $1${NC}" | tee -a "$LAKEHOUSE_ROOT/init.log"
}

log_success() {
    echo -e "${GREEN}$(date '+%Y-%m-%d %H:%M:%S') ✅ $1${NC}" | tee -a "$LAKEHOUSE_ROOT/init.log"
}

log_warning() {
    echo -e "${YELLOW}$(date '+%Y-%m-%d %H:%M:%S') ⚠️  $1${NC}" | tee -a "$LAKEHOUSE_ROOT/init.log"
}

log_info() {
    echo -e "${BLUE}$(date '+%Y-%m-%d %H:%M:%S') ℹ️  $1${NC}" | tee -a "$LAKEHOUSE_ROOT/init.log"
}

# ==============================================================================
# CLEANUP FUNCTION
# ==============================================================================

cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Initialization failed with exit code $exit_code"
        echo ""
        echo "=============================================================="
        echo "❌ LAKEHOUSE LAB INITIALIZATION FAILED"
        echo "=============================================================="
        echo ""
        echo "Please check the logs above for specific error details."
        echo "Common issues and solutions:"
        echo ""
        echo "🔧 Container Issues:"
        echo "   • Run: docker compose ps (check container status)"
        echo "   • Run: docker compose logs <service> (check specific service logs)"
        echo "   • Try: docker compose down && docker compose up -d"
        echo ""
        echo "🔧 Permission Issues:"
        echo "   • Run: chown -R \$USER:\$USER $LAKEHOUSE_ROOT"
        echo "   • Check: ls -la $LAKEHOUSE_ROOT"
        echo ""
        echo "🔧 Network Issues:"
        echo "   • Wait 2-3 minutes for all services to fully start"
        echo "   • Check: curl -f http://localhost:9000/minio/health/live"
        echo ""
        echo "📋 For support: https://github.com/karstom/lakehouse-lab/issues"
        echo ""
    else
        log_success "Cleanup completed successfully"
    fi
}

# ==============================================================================
# SERVICE WAITING FUNCTIONS
# ==============================================================================

wait_for_service() {
    local service_name="$1"
    local health_url="$2"
    local max_attempts="${3:-30}"
    local attempt=1
    
    log_info "Waiting for $service_name to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -sf "$health_url" >/dev/null 2>&1; then
            log_success "$service_name is ready (attempt $attempt/$max_attempts)"
            return 0
        fi
        
        echo "   Attempt $attempt/$max_attempts - waiting 10s..."
        sleep 10
        attempt=$((attempt + 1))
    done
    
    log_error "$service_name failed to become ready after $max_attempts attempts"
    return 1
}

wait_for_minio_api() {
    local max_attempts="${1:-30}"
    local attempt=1
    
    log_info "Waiting for MinIO API to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -sf "http://localhost:9000/minio/health/live" >/dev/null 2>&1; then
            log_success "MinIO API is ready (attempt $attempt/$max_attempts)"
            return 0
        fi
        
        # Try alternative health check
        if curl -sf "http://localhost:9000/minio/health/ready" >/dev/null 2>&1; then
            log_success "MinIO API is ready via /ready endpoint (attempt $attempt/$max_attempts)"
            return 0
        fi
        
        echo "   Attempt $attempt/$max_attempts - waiting 10s..."
        sleep 10
        attempt=$((attempt + 1))
    done
    
    log_error "MinIO API failed to become ready after $max_attempts attempts"
    log_warning "This may cause S3 operations to fail"
    return 1
}

# ==============================================================================
# VALIDATION FUNCTIONS
# ==============================================================================

check_docker_services() {
    log_info "Checking Docker services status..."
    
    # Check if we're running inside a container (skip Docker checks)
    if [ -f /.dockerenv ] || grep -q docker /proc/1/cgroup 2>/dev/null || [ "$container" = "docker" ] || [ -n "$DOCKER_CONTAINER" ]; then
        log_info "Running inside container - skipping Docker service checks"
        return 0
    fi
    
    # Check if docker compose is available
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        return 1
    fi
    
    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not available"
        return 1
    fi
    
    # Check if any containers are running
    if ! docker compose ps | grep -q "Up"; then
        log_warning "No Docker Compose services appear to be running"
        log_warning "Make sure to start services with: docker compose up -d"
        return 1
    fi
    
    log_success "Docker services check passed"
    return 0
}

validate_environment() {
    log_info "Validating environment requirements..."
    
    # Check if we're in Alpine and install dependencies
    if [ -f /etc/alpine-release ]; then
        log_info "Detected Alpine Linux - installing required packages..."
        apk add --no-cache curl python3 py3-pip >/dev/null 2>&1 || {
            log_error "Failed to install required packages in Alpine"
            return 1
        }
        log_success "Required packages installed in Alpine"
    fi
    
    # Check required commands
    local required_commands=("curl" "python3")
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            log_error "Required command '$cmd' is not installed"
            return 1
        fi
    done
    
    # Check Python modules
    if ! python3 -c "import csv, random, datetime" 2>/dev/null; then
        log_error "Required Python modules are not available"
        return 1
    fi
    
    log_success "Environment validation passed"
    return 0
}

# ==============================================================================
# DIRECTORY MANAGEMENT
# ==============================================================================

ensure_directory() {
    local dir_path="$1"
    local description="${2:-directory}"
    
    if [ ! -d "$dir_path" ]; then
        log_info "Creating $description: $dir_path"
        if mkdir -p "$dir_path"; then
            log_success "Created $description successfully"
        else
            log_error "Failed to create $description: $dir_path"
            return 1
        fi
    else
        log_info "$description already exists: $dir_path"
    fi
    
    return 0
}

# ==============================================================================
# INITIALIZATION MARKER
# ==============================================================================

create_init_marker() {
    local component="$1"
    
    # Create marker file to track completed components
    echo "$(date): $component initialized" >> "$INIT_MARKER"
    log_success "Marked $component as initialized"
}

check_already_initialized() {
    local component="$1"
    
    if [ -f "$INIT_MARKER" ] && grep -q "$component initialized" "$INIT_MARKER"; then
        log_info "$component already initialized (found in $INIT_MARKER)"
        return 0
    fi
    
    return 1
}

# ==============================================================================
# ERROR HANDLING
# ==============================================================================

handle_error() {
    local error_message="$1"
    local component="${2:-Unknown component}"
    
    log_error "$component failed: $error_message"
    
    # Add component-specific troubleshooting
    case "$component" in
        "MinIO")
            echo ""
            log_warning "MinIO troubleshooting:"
            log_warning "  1. Check if MinIO container is running: docker compose ps"
            log_warning "  2. Check MinIO logs: docker compose logs minio"
            log_warning "  3. Verify port 9000 is available: netstat -tlnp | grep 9000"
            ;;
        "Airflow")
            echo ""
            log_warning "Airflow troubleshooting:"
            log_warning "  1. Check Airflow containers: docker compose ps | grep airflow"
            log_warning "  2. Check initialization: docker compose logs airflow-init"
            log_warning "  3. Verify database setup: docker compose logs postgres"
            ;;
        "Jupyter")
            echo ""
            log_warning "Jupyter troubleshooting:"
            log_warning "  1. Check Jupyter container: docker compose ps | grep jupyter"
            log_warning "  2. Check Jupyter logs: docker compose logs jupyter"
            log_warning "  3. Verify port 9040 is available: netstat -tlnp | grep 9040"
            ;;
    esac
    
    return 1
}

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

print_separator() {
    echo ""
    echo "=============================================================="
    echo "$1"
    echo "=============================================================="
    echo ""
}

# Export functions so they can be used by sourcing scripts
export -f log log_error log_success log_warning log_info
export -f cleanup wait_for_service wait_for_minio_api
export -f check_docker_services validate_environment
export -f ensure_directory create_init_marker check_already_initialized
export -f handle_error print_separator

# Export variables
export LAKEHOUSE_ROOT INIT_MARKER RED GREEN YELLOW BLUE NC