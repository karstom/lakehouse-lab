#!/bin/bash

# =============================================================================
# Lakehouse Lab Bootstrap Installer
# =============================================================================
# One-command setup for complete data analytics stack
# 
# Usage:
#   curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
#   
# Or with options:
#   curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --fat-server
#
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration
REPO_URL="https://github.com/karstom/lakehouse-lab.git"
INSTALL_DIR="lakehouse-lab"
BRANCH="main"
PROFILE="standard"
AUTO_START="true"
SKIP_DEPS="false"
UNATTENDED="false"
ENABLE_ICEBERG="false"
UPGRADE_MODE="false"
REPLACE_MODE="false"
UPGRADE_CHOICE=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --fat-server)
            PROFILE="fat-server"
            shift
            ;;
        --iceberg)
            ENABLE_ICEBERG="true"
            shift
            ;;
        --no-start)
            AUTO_START="false"
            shift
            ;;
        --skip-deps)
            SKIP_DEPS="true"
            shift
            ;;
        --unattended)
            UNATTENDED="true"
            shift
            ;;
        --dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        --branch)
            BRANCH="$2"
            shift 2
            ;;
        --upgrade)
            UPGRADE_MODE="true"
            shift
            ;;
        --replace)
            REPLACE_MODE="true"
            shift
            ;;
        -h|--help)
            cat << EOF
Lakehouse Lab Bootstrap Installer

Usage: $0 [OPTIONS]

Options:
    --fat-server    Use high-performance configuration (64GB+ RAM)
    --iceberg       Enable Apache Iceberg table format support
    --no-start      Download only, don't start services
    --skip-deps     Skip dependency checks (Docker, git, curl)
    --unattended    Run without prompts (assumes yes to all)
    --dir DIR       Install to specific directory (default: lakehouse-lab)
    --branch BRANCH Use specific git branch (default: main)
    --upgrade       Upgrade existing installation (preserve data)
    --replace       Replace existing installation (clean slate)
    -h, --help      Show this help message

Examples:
    # Standard installation
    curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash

    # Fat server installation
    curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --fat-server

    # Installation with Iceberg support
    curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --iceberg

    # Fat server with Iceberg
    curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --fat-server --iceberg

    # Unattended installation (no prompts)
    curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --unattended

    # Download only, manual start
    curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --no-start

    # Upgrade existing installation
    curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --upgrade

    # Fresh installation (replaces existing)
    curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --replace

EOF
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Helper functions
print_header() {
    echo ""
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo -e "${BLUE}${BOLD} 🏠 Lakehouse Lab Bootstrap Installer${NC}"
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo ""
}

print_step() {
    echo -e "${CYAN}${BOLD}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

detect_existing_installation() {
    local existing_dir=""
    local has_docker_services=""
    local data_directory=""
    
    # Check for directory
    if [[ -d "$INSTALL_DIR" ]]; then
        existing_dir="true"
    fi
    
    # Check for running Docker services
    if check_command docker; then
        if docker ps --format "table {{.Names}}" 2>/dev/null | grep -q "lakehouse-lab"; then
            has_docker_services="true"
        fi
    fi
    
    # Check for data directory
    if [[ -d "$INSTALL_DIR/lakehouse-data" ]] || [[ -d "./lakehouse-data" ]]; then
        data_directory="true"
    fi
    
    # Return detection results
    if [[ "$existing_dir" == "true" ]] || [[ "$has_docker_services" == "true" ]] || [[ "$data_directory" == "true" ]]; then
        return 0  # Existing installation found
    else
        return 1  # No existing installation
    fi
}

show_upgrade_options() {
    echo ""
    echo -e "${YELLOW}🔍 Existing Lakehouse Lab installation detected!${NC}"
    echo ""
    
    # Show what we found
    if [[ -d "$INSTALL_DIR" ]]; then
        echo -e "${BLUE}📁 Found installation directory: ${CYAN}$INSTALL_DIR${NC}"
    fi
    
    if check_command docker && docker ps --format "table {{.Names}}" 2>/dev/null | grep -q "lakehouse-lab"; then
        echo -e "${BLUE}🐳 Found running services:${NC}"
        docker ps --format "table {{.Names}}\t{{.Status}}" | grep "lakehouse-lab" | sed 's/^/     /'
    fi
    
    if [[ -d "$INSTALL_DIR/lakehouse-data" ]] || [[ -d "./lakehouse-data" ]]; then
        echo -e "${BLUE}💾 Found data directory with your analytics data${NC}"
    fi
    
    echo ""
    echo -e "${BLUE}${BOLD}What would you like to do?${NC}"
    echo ""
    echo -e "${GREEN}1) Upgrade${NC} - Update to latest version (keeps your data and settings)"
    echo -e "${YELLOW}2) Replace${NC} - Fresh installation (⚠️  removes all data and starts over)"
    echo -e "${CYAN}3) Cancel${NC} - Exit without making changes"
    echo ""
    
    if [[ $UNATTENDED == "true" ]]; then
        echo -e "${GREEN}Unattended mode: defaulting to upgrade${NC}"
        UPGRADE_CHOICE="upgrade"
        return 0
    fi
    
    while true; do
        read -p "Please choose (1/2/3): " choice </dev/tty
        case $choice in
            1|upgrade|Upgrade|UPGRADE)
                UPGRADE_CHOICE="upgrade"
                return 0
                ;;
            2|replace|Replace|REPLACE)
                UPGRADE_CHOICE="replace"
                return 0
                ;;
            3|cancel|Cancel|CANCEL|q|quit)
                UPGRADE_CHOICE="cancel"
                return 0
                ;;
            *)
                echo -e "${RED}Invalid choice. Please enter 1, 2, or 3.${NC}"
                ;;
        esac
    done
}

perform_upgrade() {
    print_step "Upgrading existing Lakehouse Lab installation..."
    
    # Stop running services gracefully
    if check_command docker && docker ps --format "table {{.Names}}" 2>/dev/null | grep -q "lakehouse-lab"; then
        print_step "Stopping running services..."
        cd "$INSTALL_DIR" 2>/dev/null || true
        docker compose down || print_warning "Could not stop some services"
        cd - >/dev/null
    fi
    
    # Backup current installation
    local backup_dir="${INSTALL_DIR}_backup_$(date +%Y%m%d_%H%M%S)"
    if [[ -d "$INSTALL_DIR" ]]; then
        print_step "Creating backup of current installation..."
        mv "$INSTALL_DIR" "$backup_dir"
        print_success "Backup created: $backup_dir"
    fi
    
    # Download latest version
    download_lakehouse_lab
    
    # Restore data directory if it exists in backup
    if [[ -d "$backup_dir/lakehouse-data" ]]; then
        print_step "Restoring your data and settings..."
        cp -r "$backup_dir/lakehouse-data" "$INSTALL_DIR/"
        print_success "Data restored successfully"
    fi
    
    # Restore custom .env if it exists
    if [[ -f "$backup_dir/.env" ]] && [[ ! "$backup_dir/.env" -ef "$backup_dir/.env.default" ]]; then
        print_step "Restoring your custom configuration..."
        cp "$backup_dir/.env" "$INSTALL_DIR/.env"
        print_success "Configuration restored"
    else
        configure_environment
    fi
    
    print_success "Upgrade completed successfully!"
    print_warning "Backup available at: $backup_dir"
}

perform_replace() {
    print_step "Performing fresh installation (replacing existing)..."
    
    # Stop and remove all services
    if check_command docker && docker ps --format "table {{.Names}}" 2>/dev/null | grep -q "lakehouse-lab"; then
        print_step "Stopping and removing all services..."
        cd "$INSTALL_DIR" 2>/dev/null || true
        docker compose down -v || print_warning "Could not stop some services"
        cd - >/dev/null
    fi
    
    # Remove existing directory
    if [[ -d "$INSTALL_DIR" ]]; then
        print_step "Removing existing installation..."
        rm -rf "$INSTALL_DIR"
        print_success "Existing installation removed"
    fi
    
    # Remove any lakehouse-data directories
    if [[ -d "./lakehouse-data" ]]; then
        print_warning "Removing existing data directory..."
        rm -rf "./lakehouse-data"
    fi
    
    # Remove any partial initialization markers
    rm -f "./.lakehouse-initialized" 2>/dev/null || true
    
    # Proceed with fresh installation
    download_lakehouse_lab
    configure_environment
    
    print_success "Fresh installation ready!"
}

install_docker_ubuntu() {
    print_step "Installing Docker on Ubuntu/Debian..."
    print_warning "This requires sudo access and will add Docker's official GPG key"
    
    # Update package index
    sudo apt-get update -qq
    sudo apt-get install -y ca-certificates curl gnupg lsb-release
    
    # Add Docker's official GPG key (with better error handling)
    print_step "Adding Docker's official GPG key..."
    sudo mkdir -p /etc/apt/keyrings
    
    # Download and add GPG key with better error handling
    if curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null; then
        print_success "Docker GPG key added successfully"
    else
        print_error "Failed to add Docker GPG key. Please check your internet connection."
        exit 1
    fi
    
    # Set up Docker repository
    print_step "Setting up Docker repository..."
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Install Docker
    print_step "Installing Docker Engine..."
    sudo apt-get update -qq
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    
    # Start Docker service
    print_step "Starting Docker service..."
    sudo systemctl start docker
    sudo systemctl enable docker
    
    # Add user to docker group
    sudo usermod -aG docker $USER
    
    # Test Docker installation
    if sudo docker run --rm hello-world >/dev/null 2>&1; then
        print_success "Docker installed and working correctly"
    else
        print_warning "Docker installed but may need system restart"
    fi
    
    print_warning "Note: You may need to log out and back in for Docker permissions to take effect"
}

install_docker_centos() {
    print_step "Installing Docker on CentOS/RHEL/Fedora..."
    sudo yum install -y yum-utils
    sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
    sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker $USER
    print_warning "You may need to log out and back in for Docker permissions to take effect"
}

install_docker_macos() {
    print_step "Installing Docker on macOS..."
    if check_command brew; then
        brew install --cask docker
        print_warning "Please start Docker Desktop manually before continuing"
    else
        print_error "Homebrew not found. Please install Docker Desktop manually from https://docker.com/products/docker-desktop"
        exit 1
    fi
}

# Function to check Docker Compose functionality
check_docker_compose() {
    if docker compose version &> /dev/null; then
        return 0
    else
        return 1
    fi
}

detect_and_install_docker() {
    if check_command docker && check_docker_compose; then
        print_success "Docker and Docker Compose already installed"
        return
    fi
    
    print_step "Docker not found. Setting up automatic installation..."
    
    # Show what we're about to do
    echo ""
    echo -e "${YELLOW}The installer will now:${NC}"
    echo -e "  • Install Docker and Docker Compose"
    echo -e "  • Add Docker's official GPG signing key"
    echo -e "  • Add you to the docker group for permissions"
    echo -e "  • This requires sudo access"
    echo ""
    
    # Give user a chance to cancel if running interactively
    if [[ -t 0 && $UNATTENDED != "true" ]]; then  # Only prompt if interactive and not unattended
        read -p "Continue with Docker installation? [Y/n]: " -n 1 -r </dev/tty
        echo
        if [[ $REPLY =~ ^[Nn]$ ]]; then
            echo ""
            echo -e "${YELLOW}Docker installation cancelled.${NC}"
            echo -e "${BLUE}To install Docker manually, visit: https://docs.docker.com/engine/install/${NC}"
            echo -e "${BLUE}Then re-run this installer.${NC}"
            exit 0
        fi
    elif [[ $UNATTENDED == "true" ]]; then
        echo -e "${GREEN}Unattended mode: proceeding with Docker installation${NC}"
    fi
    
    # Detect OS and install
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if check_command apt-get; then
            install_docker_ubuntu
        elif check_command yum; then
            install_docker_centos
        else
            print_error "Unsupported Linux distribution. Please install Docker manually."
            echo "Visit: https://docs.docker.com/engine/install/"
            exit 1
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        install_docker_macos
    else
        print_error "Unsupported operating system. Please install Docker manually."
        echo "Visit: https://docs.docker.com/engine/install/"
        exit 1
    fi
}

check_system_resources() {
    print_step "Checking system resources..."
    
    # Check available memory
    if command -v free &> /dev/null; then
        TOTAL_MEM=$(free -g | awk '/^Mem:/{print $2}')
        if [[ $TOTAL_MEM -lt 8 ]]; then
            print_warning "Only ${TOTAL_MEM}GB RAM detected. 16GB+ recommended for best performance."
        elif [[ $TOTAL_MEM -ge 64 && $PROFILE == "standard" ]]; then
            print_warning "64GB+ RAM detected. Consider using --fat-server for optimal performance."
        fi
    fi
    
    # Check available disk space
    if command -v df &> /dev/null; then
        AVAILABLE_SPACE=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
        if [[ $AVAILABLE_SPACE -lt 20 ]]; then
            print_warning "Only ${AVAILABLE_SPACE}GB disk space available. 50GB+ recommended."
        fi
    fi
    
    # Check CPU cores
    if command -v nproc &> /dev/null; then
        CPU_CORES=$(nproc)
        if [[ $CPU_CORES -lt 4 ]]; then
            print_warning "Only ${CPU_CORES} CPU cores detected. 4+ cores recommended."
        elif [[ $CPU_CORES -ge 16 && $PROFILE == "standard" ]]; then
            print_warning "16+ CPU cores detected. Consider using --fat-server for optimal performance."
        fi
    fi
}

check_dependencies() {
    if [[ $SKIP_DEPS == "true" ]]; then
        print_warning "Skipping dependency checks as requested"
        return
    fi
    
    print_step "Checking dependencies..."
    
    # Check git
    if ! check_command git; then
        print_step "Installing git..."
        if command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y git
        elif command -v yum &> /dev/null; then
            sudo yum install -y git
        elif command -v brew &> /dev/null; then
            brew install git
        else
            print_error "Cannot install git automatically. Please install git manually."
            exit 1
        fi
    fi
    
    # Check curl
    if ! check_command curl; then
        print_step "Installing curl..."
        if command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y curl
        elif command -v yum &> /dev/null; then
            sudo yum install -y curl
        elif command -v brew &> /dev/null; then
            brew install curl
        else
            print_error "Cannot install curl automatically. Please install curl manually."
            exit 1
        fi
    fi
    
    # Check Docker - but be smarter about detection
    if check_command docker; then
        if check_docker_compose; then
            print_success "Docker and Docker Compose already available"
        else
            print_warning "Docker found but Docker Compose not working. Checking installation..."
            detect_and_install_docker
        fi
    else
        detect_and_install_docker
    fi
    
    print_success "All dependencies satisfied"
}

download_lakehouse_lab() {
    print_step "Downloading Lakehouse Lab..."
    
    # Only remove directory if not in upgrade/replace mode (those handle it)
    if [[ -d "$INSTALL_DIR" ]] && [[ $UPGRADE_MODE != "true" ]] && [[ $REPLACE_MODE != "true" ]]; then
        print_warning "Directory $INSTALL_DIR already exists. Removing..."
        rm -rf "$INSTALL_DIR"
    fi
    
    # Clone repository
    git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    
    print_success "Lakehouse Lab downloaded successfully"
}

configure_environment() {
    print_step "Configuring secure environment for $PROFILE profile..."
    
    # Make scripts executable first
    chmod +x init-all-in-one.sh
    chmod +x start-lakehouse.sh
    chmod +x scripts/*.sh 2>/dev/null || true
    
    # Step 1: Generate secure credentials
    print_step "🔐 Generating secure credentials..."
    if [[ -f "scripts/generate-credentials.sh" ]]; then
        ./scripts/generate-credentials.sh
    else
        print_warning "Credential generator not found, creating basic .env"
        cp .env.example .env 2>/dev/null || touch .env
    fi
    
    # Step 2: Apply profile-specific resource configurations  
    print_step "⚙️  Applying $PROFILE profile resource settings..."
    
    # Create backup of generated credentials
    cp .env .env.credentials.backup
    
    if [[ $PROFILE == "fat-server" && -f ".env.fat-server" ]]; then
        # Extract resource settings from profile file (skip credential lines)
        grep -E '^(SPARK_|POSTGRES_|JUPYTER_|AIRFLOW_|SUPERSET_|MINIO_).*_(MEMORY|CORES|INSTANCES|WORKERS|PARALLELISM|THREADS)' .env.fat-server >> .env 2>/dev/null || true
        print_success "Fat server resource configuration merged"
    elif [[ -f ".env.default" ]]; then
        # Extract resource settings from default profile  
        grep -E '^(SPARK_|POSTGRES_|JUPYTER_|AIRFLOW_|SUPERSET_|MINIO_).*_(MEMORY|CORES|INSTANCES|WORKERS|PARALLELISM|THREADS)' .env.default >> .env 2>/dev/null || true
        print_success "Standard resource configuration merged"
    fi
    
    # Clean up backup 
    rm -f .env.credentials.backup
    
    print_success "Environment configured: secure credentials + $PROFILE profile resources"
}

start_services() {
    if [[ $AUTO_START == "false" ]]; then
        print_warning "Auto-start disabled. Use './start-lakehouse.sh' to start services manually."
        if [[ $ENABLE_ICEBERG == "true" ]]; then
            print_warning "To start with Iceberg: docker compose -f docker-compose.yml -f docker-compose.iceberg.yml up -d"
        fi
        return
    fi
    
    print_step "Starting Lakehouse Lab services..."
    if [[ $ENABLE_ICEBERG == "true" ]]; then
        print_step "Iceberg support enabled - starting with enhanced Spark configuration..."
    fi
    print_warning "This may take 5-10 minutes for initial startup..."
    
    # Use the startup script if available, otherwise fall back to docker compose
    if [[ -f "start-lakehouse.sh" ]]; then
        if [[ $ENABLE_ICEBERG == "true" ]]; then
            # Set environment variable for the startup script to use Iceberg
            export ENABLE_ICEBERG_OVERRIDE="true"
        fi
        ./start-lakehouse.sh
    else
        # Direct docker compose startup
        if [[ $ENABLE_ICEBERG == "true" ]]; then
            docker compose -f docker-compose.yml -f docker-compose.iceberg.yml up -d
        else
            docker compose up -d
        fi
        sleep 30
        echo ""
        echo -e "${GREEN}🎉 Lakehouse Lab is starting up!${NC}"
        echo ""
        echo -e "${BLUE}Access points:${NC}"
        echo -e "  🐳 Portainer:         ${GREEN}http://localhost:9060${NC} (container management)"
        echo -e "  📈 Superset BI:       ${GREEN}http://localhost:9030${NC} (use ./scripts/show-credentials.sh for login)"
        echo -e "  📋 Airflow:           ${GREEN}http://localhost:9020${NC} (use ./scripts/show-credentials.sh for login)"
        echo -e "  📓 JupyterLab:        ${GREEN}http://localhost:9040${NC} (use ./scripts/show-credentials.sh for token)"
        echo -e "  ☁️  MinIO Console:     ${GREEN}http://localhost:9001${NC} (use ./scripts/show-credentials.sh for login)"
        echo -e "  ⚡ Spark Master:      ${GREEN}http://localhost:8080${NC}"
        if [[ $ENABLE_ICEBERG == "true" ]]; then
            echo ""
            echo -e "${CYAN}🧊 Iceberg Features:${NC}"
            echo -e "  • Time travel and versioning"
            echo -e "  • Schema evolution"
            echo -e "  • ACID transactions"
            echo -e "  • Try the '03_Iceberg_Tables.ipynb' notebook!"
        fi
    fi
}

show_completion_message() {
    echo ""
    if [[ $UPGRADE_MODE == "true" ]]; then
        echo -e "${GREEN}${BOLD}🎉 Upgrade Complete!${NC}"
        echo -e "${BLUE}Your data and settings have been preserved${NC}"
    elif [[ $REPLACE_MODE == "true" ]]; then
        echo -e "${GREEN}${BOLD}🎉 Fresh Installation Complete!${NC}"
        echo -e "${BLUE}Starting with a clean slate${NC}"
    else
        echo -e "${GREEN}${BOLD}🎉 Installation Complete!${NC}"
    fi
    echo ""
    echo -e "${BLUE}${BOLD}What's Next:${NC}"
    echo -e "  1. ${CYAN}Wait 3-5 minutes${NC} for all services to initialize"
    echo -e "  2. ${CYAN}Visit Portainer${NC} at http://localhost:9060 for container management"
    echo -e "     ${YELLOW}⚠️  IMPORTANT: Set up Portainer admin account within 5 minutes or you'll be locked out!${NC}"
    echo -e "  3. ${CYAN}Check the QUICKSTART.md${NC} guide for step-by-step tutorials"
    echo -e "  4. ${CYAN}Start with Superset${NC} at http://localhost:9030 for instant analytics"
    echo ""
    echo -e "${BLUE}${BOLD}Useful Commands:${NC}"
    echo -e "  ${YELLOW}./start-lakehouse.sh status${NC}    # Check service status"
    echo -e "  ${YELLOW}./start-lakehouse.sh logs${NC}      # View service logs"
    echo -e "  ${YELLOW}./start-lakehouse.sh stop${NC}      # Stop all services"
    echo -e "  ${YELLOW}./start-lakehouse.sh reset${NC}     # Reset environment"
    echo ""
    echo -e "${BLUE}${BOLD}Documentation:${NC}"
    echo -e "  📖 Full guide: ${CYAN}README.md${NC}"
    echo -e "  🚀 Quick start: ${CYAN}QUICKSTART.md${NC}"
    echo -e "  🤝 Contributing: ${CYAN}CONTRIBUTING.md${NC}"
    echo ""
    if [[ $PROFILE == "fat-server" ]]; then
        echo -e "${GREEN}💪 Fat server configuration active - optimized for high performance!${NC}"
    else
        echo -e "${BLUE}💡 Using standard configuration. For high-end servers, try: ${YELLOW}cp .env.fat-server .env && docker compose restart${NC}"
    fi
    
    if [[ $ENABLE_ICEBERG == "true" ]]; then
        echo -e "${CYAN}🧊 Iceberg table format enabled - try the advanced features!${NC}"
        echo -e "${BLUE}   • Time travel queries and versioning${NC}"
        echo -e "${BLUE}   • Schema evolution without data migration${NC}"
        echo -e "${BLUE}   • ACID transactions with MERGE operations${NC}"
        echo -e "${BLUE}   • See ICEBERG.md for detailed usage guide${NC}"
    else
        echo -e "${BLUE}💡 Want Iceberg table format? Restart with: ${YELLOW}docker compose -f docker-compose.yml -f docker-compose.iceberg.yml up -d${NC}"
    fi
    echo ""
    echo -e "${CYAN}Happy Data Engineering! 🚀📊${NC}"
}

# Main installation flow
main() {
    print_header
    
    # Check for existing installation first (unless explicitly told to upgrade/replace)
    if [[ $UPGRADE_MODE != "true" ]] && [[ $REPLACE_MODE != "true" ]]; then
        if detect_existing_installation; then
            show_upgrade_options
            case $UPGRADE_CHOICE in
                upgrade)  # Upgrade
                    UPGRADE_MODE="true"
                    ;;
                replace)  # Replace
                    REPLACE_MODE="true"
                    ;;
                cancel)  # Cancel
                    echo "Installation cancelled."
                    exit 0
                    ;;
            esac
        fi
    fi
    
    echo -e "${BLUE}Installing Lakehouse Lab with the following settings:${NC}"
    echo -e "  Profile: ${YELLOW}$PROFILE${NC}"
    echo -e "  Directory: ${YELLOW}$INSTALL_DIR${NC}"
    echo -e "  Auto-start: ${YELLOW}$AUTO_START${NC}"
    echo -e "  Iceberg: ${YELLOW}$ENABLE_ICEBERG${NC}"
    if [[ $UPGRADE_MODE == "true" ]]; then
        echo -e "  Mode: ${GREEN}Upgrade (preserving data)${NC}"
    elif [[ $REPLACE_MODE == "true" ]]; then
        echo -e "  Mode: ${YELLOW}Replace (fresh install)${NC}"
    else
        echo -e "  Mode: ${CYAN}Fresh installation${NC}"
    fi
    echo ""
    
    # Show system info
    if command -v lsb_release &> /dev/null; then
        echo -e "${BLUE}Detected system: ${YELLOW}$(lsb_release -d | cut -f2)${NC}"
    fi
    
    # Check if Docker installation will be needed
    if ! check_command docker || ! check_command "docker compose"; then
        echo -e "${YELLOW}⚠️  Docker not found - will be installed automatically${NC}"
        echo -e "${BLUE}   This requires sudo access and adds Docker's GPG key${NC}"
    fi
    echo ""
    
    # Confirm installation (only if not already chosen via upgrade options)
    if [[ -t 0 && $UNATTENDED != "true" ]] && [[ $UPGRADE_MODE != "true" ]] && [[ $REPLACE_MODE != "true" ]]; then
        read -p "Continue with installation? [Y/n]: " -n 1 -r </dev/tty
        echo
        if [[ $REPLY =~ ^[Nn]$ ]]; then
            echo "Installation cancelled."
            exit 0
        fi
    elif [[ $UNATTENDED == "true" ]]; then
        echo -e "${GREEN}Running in unattended mode - proceeding automatically${NC}"
    fi
    
    # Run installation steps based on mode
    check_system_resources
    check_dependencies
    
    if [[ $UPGRADE_MODE == "true" ]]; then
        perform_upgrade
    elif [[ $REPLACE_MODE == "true" ]]; then
        perform_replace
    else
        download_lakehouse_lab
        configure_environment
    fi
    
    start_services
    show_completion_message
}

# Handle script interruption
trap 'echo -e "\n${RED}Installation interrupted.${NC}"; exit 1' INT TERM

# Check if we're being piped to bash
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
