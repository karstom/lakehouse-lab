#!/bin/bash

# Stack Health Test Runner for Lakehouse Lab
# This script runs comprehensive tests on a functioning lakehouse stack

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="$SCRIPT_DIR"
VENV_DIR="$TEST_DIR/venv"
RESULTS_DIR="$TEST_DIR/results"

# Parse command line arguments
QUICK_MODE=false
WAIT_TIMEOUT=300

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --wait-timeout)
            WAIT_TIMEOUT="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "OPTIONS:"
            echo "  --quick              Run only service health tests"
            echo "  --wait-timeout N     Wait N seconds for stack readiness (default: 300)"
            echo "  --help               Show this help message"
            echo ""
            echo "This script runs comprehensive tests on a functioning lakehouse stack."
            echo "Make sure to start the stack first with: docker-compose up -d"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Logging functions
log() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')] $1${NC}"
}

log_success() {
    echo -e "${GREEN}[$(date '+%H:%M:%S')] ✅ $1${NC}"
}

log_error() {
    echo -e "${RED}[$(date '+%H:%M:%S')] ❌ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}[$(date '+%H:%M:%S')] ⚠️ $1${NC}"
}

# Check if Docker is available
check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    if ! docker ps &> /dev/null; then
        log_error "Docker daemon is not running or not accessible"
        exit 1
    fi
    
    log_success "Docker is available"
}

# Check if lakehouse stack is running
check_stack_running() {
    log "Checking if lakehouse stack is running..."
    
    # Check for lakehouse containers
    LAKEHOUSE_CONTAINERS=$(docker ps --format '{{.Names}}' | grep -E '(lakehouse|postgres|minio|spark|airflow|jupyter|superset|portainer)' | wc -l)
    
    if [ "$LAKEHOUSE_CONTAINERS" -lt 5 ]; then
        log_error "Lakehouse stack is not running or insufficient containers found"
        log_error "Please start the stack first with: docker-compose up -d"
        exit 1
    fi
    
    log_success "Found $LAKEHOUSE_CONTAINERS lakehouse containers running"
}

# Setup Python virtual environment
setup_venv() {
    log "Setting up Python virtual environment..."
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR"
        log_success "Created virtual environment"
    fi
    
    # Activate virtual environment
    source "$VENV_DIR/bin/activate"
    
    # Upgrade pip
    python -m pip install --upgrade pip > /dev/null 2>&1
    
    # Install dependencies
    log "Installing test dependencies..."
    pip install -r "$TEST_DIR/tests/requirements.txt" > /dev/null 2>&1
    
    log_success "Virtual environment ready"
}

# Run the stack health tests
run_tests() {
    log "Running lakehouse stack health tests..."
    
    # Ensure we're in the virtual environment
    source "$VENV_DIR/bin/activate"
    
    # Create results directory
    mkdir -p "$RESULTS_DIR"
    
    # Change to test directory
    cd "$TEST_DIR"
    
    # Run the comprehensive test suite
    if [ "$QUICK_MODE" = true ]; then
        log "Running quick health check..."
        python test_stack_health.py --quick --wait-timeout "$WAIT_TIMEOUT"
    else
        log "Running comprehensive stack health tests..."
        python test_stack_health.py --wait-timeout "$WAIT_TIMEOUT"
    fi
    
    TEST_EXIT_CODE=$?
    
    return $TEST_EXIT_CODE
}

# Main execution
main() {
    log "Starting Lakehouse Stack Health Tests"
    log "====================================="
    
    # Pre-flight checks
    check_docker
    check_stack_running
    
    # Setup environment
    setup_venv
    
    # Run tests
    if run_tests; then
        log_success "All tests completed successfully!"
        echo ""
        echo "🎉 Your lakehouse stack is healthy and ready to use!"
        echo ""
        echo "Access your services at:"
        echo "  • MinIO Console: http://localhost:9001 (use ./scripts/show-credentials.sh)"
        echo "  • Spark Master: http://localhost:8080"
        echo "  • Airflow: http://localhost:9020 (use ./scripts/show-credentials.sh)"
        echo "  • Jupyter: http://localhost:9040 (use ./scripts/show-credentials.sh for token)"
        echo "  • Superset: http://localhost:9030 (use ./scripts/show-credentials.sh)"
        echo "  • Portainer: http://localhost:9060"
        echo ""
        exit 0
    else
        log_error "Some tests failed. Please check the output above."
        echo ""
        echo "🔍 Troubleshooting tips:"
        echo "  • Make sure all containers are running: docker-compose ps"
        echo "  • Check container logs: docker-compose logs <service-name>"
        echo "  • Restart the stack: docker-compose down && docker-compose up -d"
        echo ""
        exit 1
    fi
}

# Cleanup function
cleanup() {
    if [ -d "$VENV_DIR" ]; then
        deactivate 2>/dev/null || true
    fi
}

# Set up cleanup on exit
trap cleanup EXIT

# Run main function
main "$@"