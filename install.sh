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
        read -p "Continue with Docker installation? [Y/n]: " -n 1 -r
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
    
    # Remove existing directory if it exists
    if [[ -d "$INSTALL_DIR" ]]; then
        print_warning "Directory $INSTALL_DIR already exists. Removing..."
        rm -rf "$INSTALL_DIR"
    fi
    
    # Clone repository
    git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    
    print_success "Lakehouse Lab downloaded successfully"
}

configure_environment() {
    print_step "Configuring environment for $PROFILE profile..."
    
    if [[ $PROFILE == "fat-server" ]]; then
        cp .env.fat-server .env
        print_success "Fat server configuration applied"
    else
        cp .env.default .env
        print_success "Standard configuration applied"
    fi
    
    # Make scripts executable
    chmod +x init-all-in-one.sh
    chmod +x start-lakehouse.sh
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
        echo -e "  📈 Superset BI:       ${GREEN}http://localhost:9030${NC} (admin/admin)"
        echo -e "  📋 Airflow:           ${GREEN}http://localhost:9020${NC} (admin/admin)"
        echo -e "  📓 JupyterLab:        ${GREEN}http://localhost:9040${NC} (token: lakehouse)"
        echo -e "  ☁️  MinIO Console:     ${GREEN}http://localhost:9001${NC} (minio/minio123)"
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
    echo -e "${GREEN}${BOLD}🎉 Installation Complete!${NC}"
    echo ""
    echo -e "${BLUE}${BOLD}What's Next:${NC}"
    echo -e "  1. ${CYAN}Wait 3-5 minutes${NC} for all services to initialize"
    echo -e "  2. ${CYAN}Visit Portainer${NC} at http://localhost:9060 for container management"
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
    
    echo -e "${BLUE}Installing Lakehouse Lab with the following settings:${NC}"
    echo -e "  Profile: ${YELLOW}$PROFILE${NC}"
    echo -e "  Directory: ${YELLOW}$INSTALL_DIR${NC}"
    echo -e "  Auto-start: ${YELLOW}$AUTO_START${NC}"
    echo -e "  Iceberg: ${YELLOW}$ENABLE_ICEBERG${NC}"
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
    
    # Confirm installation
    if [[ -t 0 && $UNATTENDED != "true" ]]; then  # Only prompt if interactive and not unattended
        read -p "Continue with installation? [Y/n]: " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Nn]$ ]]; then
            echo "Installation cancelled."
            exit 0
        fi
    elif [[ $UNATTENDED == "true" ]]; then
        echo -e "${GREEN}Running in unattended mode - proceeding automatically${NC}"
    fi
    
    # Run installation steps
    check_system_resources
    check_dependencies
    download_lakehouse_lab
    configure_environment
    start_services
    show_completion_message
}

# Handle script interruption
trap 'echo -e "\n${RED}Installation interrupted.${NC}"; exit 1' INT TERM

# Check if we're being piped to bash
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
