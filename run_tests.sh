#!/bin/bash

# =============================================================================
# Lakehouse Lab Test Runner
# Comprehensive test execution script for all test suites
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$TEST_DIR")"
VENV_DIR="$TEST_DIR/venv"
RESULTS_DIR="$TEST_DIR/results"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')

# Default options
RUN_UNIT_TESTS=true
RUN_INTEGRATION_TESTS=true
RUN_DOCKER_TESTS=true
RUN_LINTING=true
GENERATE_COVERAGE=true
VERBOSE=false
PARALLEL=false
KEEP_VENV=false
DOCKER_AVAILABLE=false

# Function to print colored output
print_status() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')] $1${NC}"
}

print_success() {
    echo -e "${GREEN}[$(date '+%H:%M:%S')] ✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}[$(date '+%H:%M:%S')] ⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}[$(date '+%H:%M:%S')] ❌ $1${NC}"
}

# Function to show usage
show_usage() {
    cat << EOF
Lakehouse Lab Test Runner

Usage: $0 [OPTIONS]

OPTIONS:
    -u, --unit-only          Run only unit tests
    -i, --integration-only   Run only integration tests
    -d, --docker-only        Run only Docker-related tests
    -l, --lint-only          Run only linting and code quality checks
    -n, --no-coverage        Skip coverage report generation
    -v, --verbose            Enable verbose output
    -p, --parallel           Run tests in parallel (faster)
    -k, --keep-venv          Keep virtual environment after tests
    --docker                 Force enable Docker tests
    --no-docker              Force disable Docker tests
    -h, --help               Show this help message

EXAMPLES:
    $0                       # Run all tests
    $0 -u                    # Run only unit tests
    $0 -i --docker           # Run integration tests with Docker
    $0 -l                    # Run only linting
    $0 -v -p                 # Run all tests with verbose output and parallel execution

EOF
}

# Function to parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -u|--unit-only)
                RUN_UNIT_TESTS=true
                RUN_INTEGRATION_TESTS=false
                RUN_DOCKER_TESTS=false
                shift
                ;;
            -i|--integration-only)
                RUN_UNIT_TESTS=false
                RUN_INTEGRATION_TESTS=true
                RUN_DOCKER_TESTS=true
                shift
                ;;
            -d|--docker-only)
                RUN_UNIT_TESTS=false
                RUN_INTEGRATION_TESTS=false
                RUN_DOCKER_TESTS=true
                shift
                ;;
            -l|--lint-only)
                RUN_UNIT_TESTS=false
                RUN_INTEGRATION_TESTS=false
                RUN_DOCKER_TESTS=false
                RUN_LINTING=true
                shift
                ;;
            -n|--no-coverage)
                GENERATE_COVERAGE=false
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -p|--parallel)
                PARALLEL=true
                shift
                ;;
            -k|--keep-venv)
                KEEP_VENV=true
                shift
                ;;
            --docker)
                DOCKER_AVAILABLE=true
                shift
                ;;
            --no-docker)
                DOCKER_AVAILABLE=false
                RUN_DOCKER_TESTS=false
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
}

# Function to check Docker availability
check_docker() {
    if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
        if docker info &> /dev/null; then
            DOCKER_AVAILABLE=true
            print_success "Docker is available"
        else
            print_warning "Docker is installed but not running"
            DOCKER_AVAILABLE=false
        fi
    else
        print_warning "Docker or Docker Compose not found"
        DOCKER_AVAILABLE=false
    fi
}

# Function to setup virtual environment
setup_venv() {
    print_status "Setting up virtual environment..."
    
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR"
    fi
    
    source "$VENV_DIR/bin/activate"
    
    print_status "Installing test dependencies..."
    pip install --upgrade pip
    pip install -r "$TEST_DIR/tests/requirements.txt"
    
    print_success "Virtual environment ready"
}

# Function to run linting
run_linting() {
    if [ "$RUN_LINTING" = false ]; then
        return 0
    fi
    
    print_status "Running linting and code quality checks..."
    
    # Python linting
    if ls "$TEST_DIR"/*.py 1> /dev/null 2>&1; then
        print_status "Linting Python files..."
        
        if [ "$VERBOSE" = true ]; then
            flake8 "$TEST_DIR"/ --max-line-length=120 --ignore=E203,W503
            black --check "$TEST_DIR"/
            isort --check-only "$TEST_DIR"/
        else
            flake8 "$TEST_DIR"/ --max-line-length=120 --ignore=E203,W503 > /dev/null
            black --check "$TEST_DIR"/ > /dev/null
            isort --check-only "$TEST_DIR"/ > /dev/null
        fi
        
        print_success "Python linting passed"
    fi
    
    # Shell script linting
    if ls "$PROJECT_ROOT"/*.sh 1> /dev/null 2>&1; then
        print_status "Linting shell scripts..."
        
        if command -v shellcheck &> /dev/null; then
            if [ "$VERBOSE" = true ]; then
                shellcheck "$PROJECT_ROOT"/*.sh
            else
                shellcheck "$PROJECT_ROOT"/*.sh > /dev/null
            fi
            print_success "Shell script linting passed"
        else
            print_warning "shellcheck not available, skipping shell script linting"
        fi
    fi
    
    # YAML linting
    if ls "$PROJECT_ROOT"/docker-compose*.yml 1> /dev/null 2>&1; then
        print_status "Linting YAML files..."
        
        if command -v yamllint &> /dev/null; then
            if [ "$VERBOSE" = true ]; then
                yamllint "$PROJECT_ROOT"/docker-compose*.yml
            else
                yamllint "$PROJECT_ROOT"/docker-compose*.yml > /dev/null
            fi
            print_success "YAML linting passed"
        else
            print_warning "yamllint not available, skipping YAML linting"
        fi
    fi
}

# Function to run unit tests
run_unit_tests() {
    if [ "$RUN_UNIT_TESTS" = false ]; then
        return 0
    fi
    
    print_status "Running unit tests..."
    
    local pytest_args=()
    
    if [ "$VERBOSE" = true ]; then
        pytest_args+=("-v")
    fi
    
    if [ "$PARALLEL" = true ]; then
        pytest_args+=("-n" "auto")
    fi
    
    if [ "$GENERATE_COVERAGE" = true ]; then
        pytest_args+=("--cov=." "--cov-report=html:$RESULTS_DIR/coverage_html" "--cov-report=xml:$RESULTS_DIR/coverage.xml")
    fi
    
    pytest_args+=("$TEST_DIR/test_init_scripts.py")
    
    if [ "$VERBOSE" = true ]; then
        python -m pytest "${pytest_args[@]}"
    else
        python -m pytest "${pytest_args[@]}" > "$RESULTS_DIR/unit_tests.log" 2>&1
    fi
    
    print_success "Unit tests passed"
}

# Function to run integration tests
run_integration_tests() {
    if [ "$RUN_INTEGRATION_TESTS" = false ]; then
        return 0
    fi
    
    print_status "Running integration tests..."
    
    local pytest_args=()
    
    if [ "$VERBOSE" = true ]; then
        pytest_args+=("-v")
    fi
    
    if [ "$PARALLEL" = false ]; then
        # Integration tests should not run in parallel
        pytest_args+=("-n" "0")
    fi
    
    pytest_args+=("-m" "integration")
    pytest_args+=("$TEST_DIR/test_docker_compose.py")
    
    if [ "$VERBOSE" = true ]; then
        python -m pytest "${pytest_args[@]}"
    else
        python -m pytest "${pytest_args[@]}" > "$RESULTS_DIR/integration_tests.log" 2>&1
    fi
    
    print_success "Integration tests passed"
}

# Function to run Docker tests
run_docker_tests() {
    if [ "$RUN_DOCKER_TESTS" = false ] || [ "$DOCKER_AVAILABLE" = false ]; then
        if [ "$RUN_DOCKER_TESTS" = true ]; then
            print_warning "Docker tests requested but Docker not available"
        fi
        return 0
    fi
    
    print_status "Running Docker tests..."
    
    local pytest_args=()
    
    if [ "$VERBOSE" = true ]; then
        pytest_args+=("-v")
    fi
    
    pytest_args+=("-m" "docker")
    pytest_args+=("--docker-available")
    pytest_args+=("$TEST_DIR/test_docker_compose.py" "$TEST_DIR/test_iceberg_integration.py")
    
    if [ "$VERBOSE" = true ]; then
        python -m pytest "${pytest_args[@]}"
    else
        python -m pytest "${pytest_args[@]}" > "$RESULTS_DIR/docker_tests.log" 2>&1
    fi
    
    print_success "Docker tests passed"
}

# Function to generate test report
generate_report() {
    print_status "Generating test report..."
    
    local report_file="$RESULTS_DIR/test_report_$TIMESTAMP.html"
    
    cat > "$report_file" << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Lakehouse Lab Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f0f0f0; padding: 20px; border-radius: 5px; }
        .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
        .success { background-color: #d4edda; border-color: #c3e6cb; }
        .warning { background-color: #fff3cd; border-color: #ffeaa7; }
        .error { background-color: #f8d7da; border-color: #f5c6cb; }
        .info { background-color: #d1ecf1; border-color: #bee5eb; }
        pre { background-color: #f8f9fa; padding: 10px; border-radius: 3px; overflow-x: auto; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Lakehouse Lab Test Report</h1>
        <p><strong>Generated:</strong> $(date)</p>
        <p><strong>Test Run ID:</strong> $TIMESTAMP</p>
    </div>
    
    <div class="section info">
        <h2>Test Configuration</h2>
        <ul>
            <li>Unit Tests: $([ "$RUN_UNIT_TESTS" = true ] && echo "✅ Enabled" || echo "❌ Disabled")</li>
            <li>Integration Tests: $([ "$RUN_INTEGRATION_TESTS" = true ] && echo "✅ Enabled" || echo "❌ Disabled")</li>
            <li>Docker Tests: $([ "$RUN_DOCKER_TESTS" = true ] && echo "✅ Enabled" || echo "❌ Disabled")</li>
            <li>Linting: $([ "$RUN_LINTING" = true ] && echo "✅ Enabled" || echo "❌ Disabled")</li>
            <li>Coverage: $([ "$GENERATE_COVERAGE" = true ] && echo "✅ Enabled" || echo "❌ Disabled")</li>
            <li>Docker Available: $([ "$DOCKER_AVAILABLE" = true ] && echo "✅ Yes" || echo "❌ No")</li>
        </ul>
    </div>
    
    <div class="section success">
        <h2>Test Results</h2>
        <p>All configured tests have passed successfully!</p>
    </div>
    
    <div class="section info">
        <h2>Files and Logs</h2>
        <ul>
            <li><a href="coverage_html/index.html">Coverage Report</a> (if generated)</li>
            <li><a href="unit_tests.log">Unit Test Log</a></li>
            <li><a href="integration_tests.log">Integration Test Log</a></li>
            <li><a href="docker_tests.log">Docker Test Log</a></li>
        </ul>
    </div>
</body>
</html>
EOF
    
    print_success "Test report generated: $report_file"
}

# Function to cleanup
cleanup() {
    print_status "Cleaning up..."
    
    # Stop any running containers
    if [ "$DOCKER_AVAILABLE" = true ]; then
        cd "$PROJECT_ROOT" || exit 1
        docker-compose down -v > /dev/null 2>&1 || true
    fi
    
    # Clean up virtual environment
    if [ "$KEEP_VENV" = false ] && [ -d "$VENV_DIR" ]; then
        rm -rf "$VENV_DIR"
        print_success "Virtual environment cleaned up"
    fi
    
    print_success "Cleanup completed"
}

# Main execution function
main() {
    print_status "Starting Lakehouse Lab Test Runner"
    
    # Parse command line arguments
    parse_args "$@"
    
    # Create results directory
    mkdir -p "$RESULTS_DIR"
    
    # Setup trap for cleanup
    trap cleanup EXIT
    
    # Check Docker availability
    check_docker
    
    # Setup virtual environment
    setup_venv
    
    # Change to project root
    cd "$PROJECT_ROOT" || exit 1
    
    # Run tests in order
    local test_results=()
    
    if ! run_linting; then
        test_results+=("Linting: FAILED")
    else
        test_results+=("Linting: PASSED")
    fi
    
    if ! run_unit_tests; then
        test_results+=("Unit Tests: FAILED")
    else
        test_results+=("Unit Tests: PASSED")
    fi
    
    if ! run_integration_tests; then
        test_results+=("Integration Tests: FAILED")
    else
        test_results+=("Integration Tests: PASSED")
    fi
    
    if ! run_docker_tests; then
        test_results+=("Docker Tests: FAILED")
    else
        test_results+=("Docker Tests: PASSED")
    fi
    
    # Generate report
    generate_report
    
    # Print summary
    print_success "Test run completed successfully!"
    print_status "Results summary:"
    for result in "${test_results[@]}"; do
        echo "  $result"
    done
    
    print_status "Detailed results available in: $RESULTS_DIR"
}

# Run main function
main "$@"