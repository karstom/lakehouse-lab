#!/bin/bash
# ==============================================================================
# init-all-in-one-modular.sh - Modular Lakehouse Lab Initialization
# ==============================================================================
# Main orchestrator for modular lakehouse initialization
# Replaces the monolithic init-all-in-one.sh with a clean, maintainable approach

set -e

# Get script directory
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"

# Source shared utilities
source "$SCRIPT_DIR/scripts/lib/init-core.sh"

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Module execution order (critical for dependency management)
MODULES=(
    "infrastructure"
    "storage" 
    "compute"
    "workflows"
    "analytics"
    "dashboards"
)

# Module script mapping
declare -A MODULE_SCRIPTS=(
    ["infrastructure"]="$SCRIPT_DIR/scripts/init-infrastructure.sh"
    ["storage"]="$SCRIPT_DIR/scripts/init-storage.sh"
    ["compute"]="$SCRIPT_DIR/scripts/init-compute.sh"
    ["workflows"]="$SCRIPT_DIR/scripts/init-workflows.sh"
    ["analytics"]="$SCRIPT_DIR/scripts/init-analytics.sh"
    ["dashboards"]="$SCRIPT_DIR/scripts/init-dashboards.sh"
)

# ==============================================================================
# MODULE EXECUTION
# ==============================================================================

execute_module() {
    local module_name="$1"
    local script_path="${MODULE_SCRIPTS[$module_name]}"
    
    print_separator "🚀 INITIALIZING: ${module_name^^}"
    
    # Check if script exists
    if [ ! -f "$script_path" ]; then
        log_error "Module script not found: $script_path"
        return 1
    fi
    
    # Check if script is executable
    if [ ! -x "$script_path" ]; then
        log_error "Module script is not executable: $script_path"
        log_info "Run: chmod +x $script_path"
        return 1
    fi
    
    # Execute the module
    log_info "Executing module: $module_name"
    log_info "Script: $script_path"
    
    if "$script_path"; then
        log_success "Module '$module_name' completed successfully"
        return 0
    else
        log_error "Module '$module_name' failed"
        return 1
    fi
}

# ==============================================================================
# MAIN INITIALIZATION FLOW
# ==============================================================================

main() {
    # Print header
    print_separator "🏠 LAKEHOUSE LAB MODULAR INITIALIZATION"
    
    log_info "Starting modular lakehouse initialization..."
    log_info "Modules to initialize: ${MODULES[*]}"
    echo ""
    
    # Set trap for cleanup
    trap cleanup EXIT
    
    # Initialize start time
    local start_time=$(date +%s)
    
    # Execute each module in order
    local completed_modules=0
    local total_modules=${#MODULES[@]}
    
    for module in "${MODULES[@]}"; do
        log_info "Progress: $completed_modules/$total_modules modules completed"
        echo ""
        
        # Execute module
        if execute_module "$module"; then
            completed_modules=$((completed_modules + 1))
            log_success "✅ Module '$module' completed ($completed_modules/$total_modules)"
        else
            log_error "❌ Module '$module' failed"
            log_error "Initialization stopped due to module failure"
            
            echo ""
            echo "=============================================================="
            echo "❌ LAKEHOUSE LAB INITIALIZATION FAILED"
            echo "=============================================================="
            echo ""
            echo "Failed module: $module"
            echo "Completed modules: $completed_modules/$total_modules"
            echo ""
            echo "🔧 Troubleshooting:"
            echo "   1. Check the logs above for specific error details"
            echo "   2. Verify Docker services are running: docker compose ps"
            echo "   3. Check individual module: ${MODULE_SCRIPTS[$module]}"
            echo "   4. Review initialization log: $LAKEHOUSE_ROOT/init.log"
            echo ""
            echo "🔄 To retry after fixing issues:"
            echo "   ./init-all-in-one-modular.sh"
            echo ""
            
            exit 1
        fi
        
        echo ""
    done
    
    # Calculate execution time
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local minutes=$((duration / 60))
    local seconds=$((duration % 60))
    
    # Create final initialization marker
    echo "Lakehouse Lab modular initialization completed on $(date)" > "$INIT_MARKER"
    echo "All modules completed successfully" >> "$INIT_MARKER"
    echo "Total execution time: ${minutes}m ${seconds}s" >> "$INIT_MARKER"
    
    # Print success message
    print_separator "🎉 LAKEHOUSE LAB INITIALIZATION COMPLETE!"
    
    log_success "All $total_modules modules completed successfully"
    log_success "Total execution time: ${minutes}m ${seconds}s"
    
    echo ""
    echo "✅ Lakehouse Lab is ready for use!"
    echo ""
    echo "🌐 Access Points:"
    echo "   • Portainer:         http://localhost:9060 (container management)"
    echo "   • Superset BI:       http://localhost:9030 (admin/admin)"
    echo "   • Airflow:           http://localhost:9020 (admin/admin)"
    echo "   • JupyterLab:        http://localhost:9040 (token: lakehouse)"
    echo "   • MinIO Console:     http://localhost:9001 (minio/minio123)"
    echo "   • Spark Master:      http://localhost:8080"
    echo "   • Homer Dashboard:   http://localhost:9061"
    echo ""
    echo "📊 What's Ready:"
    echo "   ✅ Complete directory structure in: $LAKEHOUSE_ROOT/"
    echo "   ✅ MinIO object storage with sample data"
    echo "   ✅ Airflow DAGs for data processing workflows"
    echo "   ✅ Jupyter notebooks for interactive analysis"
    echo "   ✅ Superset dashboards for business intelligence"
    echo "   ✅ Apache Iceberg support for advanced table formats"
    echo ""
    echo "🚀 Quick Start:"
    echo "   1. Visit Superset → SQL Lab → Run sample queries"
    echo "   2. Visit Airflow → Enable 'sample_duckdb_pipeline' DAG"
    echo "   3. Visit JupyterLab → Open '01_Getting_Started.ipynb'"
    echo "   4. For Iceberg: docker compose -f docker-compose.yml -f docker-compose.iceberg.yml up -d"
    echo ""
    echo "📖 Documentation:"
    echo "   • README.md - Complete setup guide"
    echo "   • QUICKSTART.md - Step-by-step tutorials"
    echo "   • ICEBERG.md - Advanced table format features"
    echo ""
    echo "🔧 Utilities:"
    echo "   • Dashboard info: $LAKEHOUSE_ROOT/dashboard_utils.sh"
    echo "   • Initialization log: $LAKEHOUSE_ROOT/init.log"
    echo ""
    echo "Happy Data Engineering! 🚀📊"
    echo ""
}

# ==============================================================================
# COMMAND LINE OPTIONS
# ==============================================================================

show_usage() {
    echo "Lakehouse Lab Modular Initialization"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  --module NAME  Run only a specific module"
    echo "  --list         List available modules"
    echo "  --status       Show initialization status"
    echo "  --clean        Clean initialization markers (force re-run)"
    echo ""
    echo "Modules: ${MODULES[*]}"
    echo ""
    echo "Examples:"
    echo "  $0                    # Run full initialization"
    echo "  $0 --module storage   # Run only storage module"
    echo "  $0 --status           # Check what's been initialized"
    echo "  $0 --clean            # Reset and run full initialization"
    echo ""
}

run_single_module() {
    local module_name="$1"
    
    # Validate module name
    if [[ ! " ${MODULES[*]} " =~ " $module_name " ]]; then
        log_error "Invalid module name: $module_name"
        log_info "Available modules: ${MODULES[*]}"
        exit 1
    fi
    
    print_separator "🎯 SINGLE MODULE EXECUTION: ${module_name^^}"
    
    # Set trap for cleanup
    trap cleanup EXIT
    
    if execute_module "$module_name"; then
        log_success "Module '$module_name' completed successfully"
    else
        log_error "Module '$module_name' failed"
        exit 1
    fi
}

show_module_list() {
    echo "Available Lakehouse Lab Modules:"
    echo "================================"
    echo ""
    
    for i in "${!MODULES[@]}"; do
        local module="${MODULES[$i]}"
        local script="${MODULE_SCRIPTS[$module]}"
        local order=$((i + 1))
        
        echo "$order. $module"
        echo "   Script: $script"
        
        if [ -f "$script" ] && [ -x "$script" ]; then
            echo "   Status: ✅ Ready"
        else
            echo "   Status: ❌ Not available"
        fi
        echo ""
    done
}

show_status() {
    print_separator "📊 INITIALIZATION STATUS"
    
    if [ -f "$INIT_MARKER" ]; then
        echo "Initialization marker found:"
        echo ""
        cat "$INIT_MARKER"
        echo ""
        
        # Check individual modules
        echo "Module Status:"
        for module in "${MODULES[@]}"; do
            if grep -q "$module initialized" "$INIT_MARKER" 2>/dev/null; then
                echo "  ✅ $module"
            else
                echo "  ❌ $module"
            fi
        done
    else
        echo "❌ No initialization marker found"
        echo "Lakehouse Lab has not been initialized yet"
        echo ""
        echo "Run: $0"
    fi
    echo ""
}

clean_initialization() {
    print_separator "🧹 CLEANING INITIALIZATION"
    
    log_warning "This will remove initialization markers and force re-initialization"
    
    if [ -f "$INIT_MARKER" ]; then
        rm -f "$INIT_MARKER"
        log_success "Removed initialization marker"
    else
        log_info "No initialization marker found"
    fi
    
    # Ask if user wants to clean data directory
    read -p "Do you want to remove the entire data directory? [y/N]: " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [ -d "$LAKEHOUSE_ROOT" ]; then
            log_warning "Removing data directory: $LAKEHOUSE_ROOT"
            rm -rf "$LAKEHOUSE_ROOT"
            log_success "Data directory removed"
        fi
    fi
    
    log_success "Initialization cleaned - ready for fresh start"
}

# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

# Parse command line arguments
case "${1:-}" in
    "-h"|"--help")
        show_usage
        exit 0
        ;;
    "--module")
        if [ -z "${2:-}" ]; then
            log_error "Module name required"
            show_usage
            exit 1
        fi
        run_single_module "$2"
        exit $?
        ;;
    "--list")
        show_module_list
        exit 0
        ;;
    "--status")
        show_status
        exit 0
        ;;
    "--clean")
        clean_initialization
        exit 0
        ;;
    "")
        # No arguments - run full initialization
        main
        ;;
    *)
        log_error "Unknown option: $1"
        show_usage
        exit 1
        ;;
esac