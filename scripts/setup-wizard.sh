#!/bin/bash

# Lakehouse Lab Setup Wizard
# Interactive installer with service configuration options

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo -e "${PURPLE}"
    cat << 'EOF'
╔════════════════════════════════════════════════╗
║                                                ║
║           🏠 LAKEHOUSE LAB SETUP WIZARD        ║
║                                                ║
║    Welcome to the interactive installation     ║
║         and configuration wizard               ║
║                                                ║
╚════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

# Function to check system requirements
check_system_requirements() {
    log_info "Checking system requirements..."
    
    local errors=0
    local warnings=0
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found. Please install Docker first."
        errors=$((errors + 1))
    else
        local docker_version=$(docker --version | grep -oE '[0-9]+\.[0-9]+' | head -1)
        log_success "Docker found (version $docker_version)"
    fi
    
    # Check Docker Compose
    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose not found. Please install Docker Compose first."
        errors=$((errors + 1))
    else
        local compose_version=$(docker compose version | grep -oE 'v[0-9]+\.[0-9]+' | head -1)
        log_success "Docker Compose found ($compose_version)"
    fi
    
    # Check available memory
    if command -v free &> /dev/null; then
        local mem_gb=$(free -g | awk '/^Mem:/{print $2}')
        if [[ $mem_gb -lt 8 ]]; then
            log_warning "Only ${mem_gb}GB RAM detected. Recommended: 16GB+ for full setup"
            warnings=$((warnings + 1))
        elif [[ $mem_gb -lt 16 ]]; then
            log_warning "${mem_gb}GB RAM detected. Consider minimal configuration"
            warnings=$((warnings + 1))
        else
            log_success "${mem_gb}GB RAM detected - sufficient for full setup"
        fi
    fi
    
    # Check disk space
    if command -v df &> /dev/null; then
        local disk_gb=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
        if [[ $disk_gb -lt 10 ]]; then
            log_warning "Only ${disk_gb}GB disk space available. Recommended: 20GB+"
            warnings=$((warnings + 1))
        else
            log_success "${disk_gb}GB disk space available"
        fi
    fi
    
    echo ""
    if [[ $errors -gt 0 ]]; then
        log_error "System check failed with $errors critical errors"
        log_info "Please resolve these issues before continuing"
        return 1
    elif [[ $warnings -gt 0 ]]; then
        log_warning "System check completed with $warnings warnings"
        echo -n "Continue with installation? [y/N]: "
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            log_info "Installation cancelled by user"
            exit 0
        fi
    else
        log_success "System check passed - ready for installation"
    fi
    
    return 0
}

# Function to show installation modes
show_installation_modes() {
    echo -e "${BLUE}📦 Installation Modes${NC}"
    echo -e "${BLUE}===================${NC}"
    echo ""
    echo -e "${GREEN}1. Quick Setup (Recommended)${NC}"
    echo -e "   • All services enabled"
    echo -e "   • Automated configuration"
    echo -e "   • Best for new users"
    echo -e "   • RAM requirement: ~20GB"
    echo ""
    echo -e "${YELLOW}2. Minimal Setup${NC}"
    echo -e "   • Core services + Jupyter only"
    echo -e "   • Lightweight configuration"  
    echo -e "   • Best for resource-constrained systems"
    echo -e "   • RAM requirement: ~8GB"
    echo ""
    echo -e "${PURPLE}3. Analytics Focus${NC}"
    echo -e "   • Jupyter + Superset + Vizro"
    echo -e "   • Business intelligence emphasis"
    echo -e "   • No workflow orchestration"
    echo -e "   • RAM requirement: ~14GB"
    echo ""
    echo -e "${BLUE}4. ML/AI Focus${NC}"
    echo -e "   • Jupyter + LanceDB + Airflow"
    echo -e "   • Machine learning workflows"
    echo -e "   • Vector database included"
    echo -e "   • RAM requirement: ~16GB"
    echo ""
    echo -e "${RED}5. Custom Configuration${NC}"
    echo -e "   • Choose specific services"
    echo -e "   • Advanced users only"
    echo -e "   • Interactive service selection"
    echo ""
}

# Function to handle installation mode selection
select_installation_mode() {
    while true; do
        show_installation_modes
        echo -n "Select installation mode [1-5]: "
        read -r mode
        
        case "$mode" in
            1)
                log_info "Selected: Quick Setup (All services)"
                export SETUP_MODE="full"
                return 0
                ;;
            2)
                log_info "Selected: Minimal Setup"
                export SETUP_MODE="minimal"
                return 0
                ;;
            3)
                log_info "Selected: Analytics Focus"
                export SETUP_MODE="analytics"
                return 0
                ;;
            4)
                log_info "Selected: ML/AI Focus"
                export SETUP_MODE="ml"
                return 0
                ;;
            5)
                log_info "Selected: Custom Configuration"
                export SETUP_MODE="custom"
                return 0
                ;;
            *)
                log_error "Invalid selection. Please choose 1-5."
                echo ""
                ;;
        esac
    done
}

# Function to show what will be installed
show_installation_plan() {
    local mode="$1"
    
    echo -e "${BLUE}📋 Installation Plan${NC}"
    echo -e "${BLUE}===================${NC}"
    echo ""
    
    # Always installed services
    echo -e "${GREEN}✅ Core Services (always installed):${NC}"
    echo -e "   • PostgreSQL Database (data storage)"
    echo -e "   • MinIO Object Storage (S3-compatible)"
    echo -e "   • Apache Spark (distributed processing)"
    echo -e "   • Portainer (container management)"
    echo ""
    
    case "$mode" in
        "full")
            echo -e "${GREEN}✅ Optional Services (will be installed):${NC}"
            echo -e "   • Apache Airflow (workflow orchestration)"
            echo -e "   • Apache Superset (business intelligence)"
            echo -e "   • JupyterLab (data science notebooks)"
            echo -e "   • Vizro (interactive dashboards)"
            echo -e "   • LanceDB (vector database)"
            ;;
        "minimal")
            echo -e "${GREEN}✅ Optional Services (will be installed):${NC}"
            echo -e "   • JupyterLab (data science notebooks)"
            echo ""
            echo -e "${RED}❌ Services that will NOT be installed:${NC}"
            echo -e "   • Apache Airflow, Superset, Vizro, LanceDB"
            ;;
        "analytics")
            echo -e "${GREEN}✅ Optional Services (will be installed):${NC}"
            echo -e "   • JupyterLab (data science notebooks)"
            echo -e "   • Apache Superset (business intelligence)"
            echo -e "   • Vizro (interactive dashboards)"
            echo ""
            echo -e "${RED}❌ Services that will NOT be installed:${NC}"
            echo -e "   • Apache Airflow, LanceDB"
            ;;
        "ml")
            echo -e "${GREEN}✅ Optional Services (will be installed):${NC}"
            echo -e "   • JupyterLab (data science notebooks)"
            echo -e "   • Apache Airflow (workflow orchestration)"
            echo -e "   • LanceDB (vector database)"
            echo ""
            echo -e "${RED}❌ Services that will NOT be installed:${NC}"
            echo -e "   • Apache Superset, Vizro"
            ;;
    esac
    
    echo ""
    echo -e "${YELLOW}📊 Estimated Resource Usage:${NC}"
    case "$mode" in
        "full")
            echo -e "   • RAM: ~20GB"
            echo -e "   • Storage: ~5GB (initial)"
            echo -e "   • Ports: 8080, 9001, 9020, 9030, 9040, 9050, 9060, 9080"
            ;;
        "minimal")
            echo -e "   • RAM: ~8GB" 
            echo -e "   • Storage: ~2GB (initial)"
            echo -e "   • Ports: 8080, 9001, 9040, 9060"
            ;;
        "analytics")
            echo -e "   • RAM: ~14GB"
            echo -e "   • Storage: ~3GB (initial)"
            echo -e "   • Ports: 8080, 9001, 9030, 9040, 9050, 9060"
            ;;
        "ml")
            echo -e "   • RAM: ~16GB"
            echo -e "   • Storage: ~4GB (initial)"
            echo -e "   • Ports: 8080, 9001, 9020, 9040, 9060, 9080"
            ;;
    esac
    echo ""
}

# Function to run the installation
run_installation() {
    local mode="$1"
    
    log_info "Starting installation process..."
    
    # Step 1: Configure services based on selected mode
    if [[ "$mode" != "custom" ]]; then
        log_info "Configuring services for '$mode' mode..."
        if ! ./scripts/configure-services.sh preset "$mode"; then
            log_error "Service configuration failed"
            return 1
        fi
    else
        log_info "Starting interactive service configuration..."
        if ! ./scripts/configure-services.sh interactive; then
            log_error "Interactive configuration cancelled or failed"
            return 1
        fi
    fi
    
    # Step 2: Generate credentials
    log_info "Generating secure credentials..."
    if ! ./scripts/generate-credentials.sh; then
        log_error "Credential generation failed"
        return 1
    fi
    
    # Step 3: Start services
    log_info "Starting Lakehouse Lab services..."
    if ! ./start-lakehouse.sh; then
        log_error "Service startup failed"
        return 1
    fi
    
    log_success "Installation completed successfully!"
    return 0
}

# Function to show post-installation information
show_post_install_info() {
    echo ""
    echo -e "${GREEN}🎉 Installation Complete!${NC}"
    echo -e "${GREEN}=========================${NC}"
    echo ""
    
    log_info "Your Lakehouse Lab is now running!"
    echo ""
    echo -e "${BLUE}📋 Next Steps:${NC}"
    echo -e "1. View service credentials: ${YELLOW}./scripts/show-credentials.sh${NC}"
    echo -e "2. Access Portainer UI: ${YELLOW}http://localhost:9060${NC} (container management)"  
    echo -e "3. Try the example notebooks in JupyterLab"
    echo -e "4. Explore the getting started guide: ${YELLOW}QUICKSTART.md${NC}"
    echo ""
    echo -e "${BLUE}🔧 Management Commands:${NC}"
    echo -e "• Configure services:     ${YELLOW}./scripts/configure-services.sh${NC}"
    echo -e "• Start/stop services:    ${YELLOW}./start-lakehouse.sh [start|stop|status]${NC}"
    echo -e "• Rotate credentials:     ${YELLOW}./scripts/rotate-credentials.sh${NC}"
    echo -e "• View logs:             ${YELLOW}docker compose logs${NC}"
    echo ""
    
    # Offer to show credentials
    echo -n "Would you like to see your service credentials now? [Y/n]: "
    read -r show_creds
    if [[ ! "$show_creds" =~ ^[Nn]$ ]]; then
        echo ""
        ./scripts/show-credentials.sh
    fi
}

# Function to handle installation errors
handle_installation_error() {
    echo ""
    log_error "Installation failed!"
    echo ""
    log_info "Troubleshooting suggestions:"
    echo -e "• Check system resources: ${YELLOW}./start-lakehouse.sh resources${NC}"
    echo -e "• View service logs:      ${YELLOW}./start-lakehouse.sh logs${NC}"
    echo -e "• Try minimal setup:      ${YELLOW}$0 --minimal${NC}"
    echo -e "• Reset and retry:        ${YELLOW}./start-lakehouse.sh reset${NC}"
    echo ""
    log_info "For help, check the troubleshooting guide in README.md"
}

# Function to handle command line arguments
handle_args() {
    case "${1:-}" in
        "--minimal")
            export SETUP_MODE="minimal"
            return 0
            ;;
        "--analytics")
            export SETUP_MODE="analytics"
            return 0
            ;;
        "--ml"|"--ai")
            export SETUP_MODE="ml"
            return 0
            ;;
        "--full")
            export SETUP_MODE="full"
            return 0
            ;;
        "--help"|"-h")
            echo "Lakehouse Lab Setup Wizard"
            echo ""
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --minimal     Quick minimal installation"
            echo "  --analytics   Quick analytics-focused installation"
            echo "  --ml, --ai    Quick ML/AI-focused installation"
            echo "  --full        Quick full installation"
            echo "  --help, -h    Show this help"
            echo ""
            echo "Without options, runs interactive wizard"
            exit 0
            ;;
        "")
            return 1  # Interactive mode
            ;;
        *)
            log_error "Unknown option: $1"
            log_info "Use --help for usage information"
            exit 1
            ;;
    esac
}

# Main installation function
main() {
    print_header
    
    # Handle command line arguments
    local interactive=true
    if handle_args "$@"; then
        interactive=false
        log_info "Running in non-interactive mode: $SETUP_MODE"
    fi
    
    # Check system requirements
    if ! check_system_requirements; then
        exit 1
    fi
    
    # Select installation mode (interactive or from args)
    if [[ "$interactive" == "true" ]]; then
        select_installation_mode
    fi
    
    # Show installation plan and confirm
    show_installation_plan "$SETUP_MODE"
    
    if [[ "$interactive" == "true" ]]; then
        echo -n "Proceed with this installation? [Y/n]: "
        read -r confirm
        if [[ "$confirm" =~ ^[Nn]$ ]]; then
            log_info "Installation cancelled by user"
            exit 0
        fi
    fi
    
    # Run the installation
    if run_installation "$SETUP_MODE"; then
        show_post_install_info
    else
        handle_installation_error
        exit 1
    fi
}

# Run main function with all arguments
main "$@"