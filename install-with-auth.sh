#!/bin/bash

# =============================================================================
# Lakehouse Lab Bootstrap Installer with Authentication
# =============================================================================
# One-command setup for complete data analytics stack with federated auth
# 
# Usage:
#   curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install-with-auth.sh | bash
#   
# Or with options:
#   curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install-with-auth.sh | bash -s -- --fat-server
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
BRANCH="dev"  # Use dev branch which has auth features
PROFILE="standard"
AUTO_START="true"
SKIP_DEPS="false"
UNATTENDED="false"
ENABLE_ICEBERG="false"
ENABLE_AUTH="true"  # Always enable auth for this installer
ENABLE_MCP="false"
UPGRADE_MODE="false"
REPLACE_MODE="false"
SETUP_OAUTH="false"

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
        --with-mcp)
            ENABLE_MCP="true"
            shift
            ;;
        --setup-oauth)
            SETUP_OAUTH="true"
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
Lakehouse Lab Bootstrap Installer with Authentication

Usage: $0 [OPTIONS]

Options:
    --fat-server    Use high-performance configuration (64GB+ RAM)
    --iceberg       Enable Apache Iceberg table format support
    --with-mcp      Enable MCP server (AI-powered data API)
    --setup-oauth   Run OAuth setup wizard after installation
    --no-start      Download only, don't start services
    --skip-deps     Skip dependency checks (Docker, git, curl)
    --unattended    Run without prompts (assumes yes to all)
    --dir DIR       Install to specific directory (default: lakehouse-lab)
    --branch BRANCH Use specific git branch (default: dev)
    --upgrade       Upgrade existing installation (preserve data)
    --replace       Replace existing installation (clean slate)
    -h, --help      Show this help message

Features Included:
    ✅ All Lakehouse Lab services (Spark, Superset, Jupyter, etc.)
    ✅ OAuth authentication (Google, Microsoft, GitHub)
    ✅ Local authentication fallback
    ✅ Role-based access control
    ✅ Service access proxy
    ✅ Audit logging
    ✅ Optional MCP server (AI assistant)

Examples:
    # Standard installation with authentication
    curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install-with-auth.sh | bash

    # Fat server with authentication and MCP
    curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install-with-auth.sh | bash -s -- --fat-server --with-mcp

    # Installation with OAuth setup wizard
    curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install-with-auth.sh | bash -s -- --setup-oauth

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

# Print header
print_header() {
    echo -e "${BOLD}${BLUE}"
    cat << 'EOF'
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║               🏠 LAKEHOUSE LAB INSTALLER                     ║
║                    WITH AUTHENTICATION                       ║
║                                                              ║
║  Complete data analytics stack with enterprise security     ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

# Check if running in an existing installation
check_existing_installation() {
    if [[ -d "$INSTALL_DIR" ]]; then
        echo -e "${YELLOW}⚠️  Found existing installation in $INSTALL_DIR${NC}"
        
        if [[ "$UPGRADE_MODE" == "true" ]]; then
            echo -e "${GREEN}Running in upgrade mode - preserving data${NC}"
            return 0
        elif [[ "$REPLACE_MODE" == "true" ]]; then
            echo -e "${RED}Running in replace mode - removing existing installation${NC}"
            rm -rf "$INSTALL_DIR"
            return 0
        fi
        
        if [[ "$UNATTENDED" != "true" ]]; then
            echo ""
            echo "Choose an option:"
            echo "1) Upgrade (preserve your data and settings)"
            echo "2) Replace (clean slate - removes all data)"
            echo "3) Cancel"
            echo ""
            
            while true; do
                read -p "Your choice [1-3]: " choice
                case $choice in
                    1)
                        UPGRADE_MODE="true"
                        echo -e "${GREEN}Upgrading existing installation${NC}"
                        break
                        ;;
                    2)
                        REPLACE_MODE="true"
                        echo -e "${RED}Replacing existing installation${NC}"
                        rm -rf "$INSTALL_DIR"
                        break
                        ;;
                    3)
                        echo -e "${YELLOW}Installation cancelled${NC}"
                        exit 0
                        ;;
                    *)
                        echo "Please choose 1, 2, or 3"
                        ;;
                esac
            done
        else
            echo -e "${GREEN}Unattended mode: upgrading existing installation${NC}"
            UPGRADE_MODE="true"
        fi
        echo ""
    fi
}

# Check system dependencies
check_dependencies() {
    if [[ "$SKIP_DEPS" == "true" ]]; then
        echo -e "${YELLOW}⚠️  Skipping dependency checks${NC}"
        return 0
    fi
    
    echo -e "${BLUE}🔍 Checking system dependencies...${NC}"
    
    local missing_deps=()
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        missing_deps+=("docker")
    elif ! docker --version &> /dev/null; then
        echo -e "${RED}❌ Docker is installed but not running${NC}"
        echo "Please start Docker and try again"
        exit 1
    fi
    
    # Check Docker Compose
    if ! docker compose version &> /dev/null; then
        if ! command -v docker-compose &> /dev/null; then
            missing_deps+=("docker-compose")
        fi
    fi
    
    # Check git
    if ! command -v git &> /dev/null; then
        missing_deps+=("git")
    fi
    
    # Check curl
    if ! command -v curl &> /dev/null; then
        missing_deps+=("curl")
    fi
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        echo -e "${RED}❌ Missing dependencies: ${missing_deps[*]}${NC}"
        echo ""
        echo "Please install the missing dependencies:"
        
        for dep in "${missing_deps[@]}"; do
            case "$dep" in
                "docker")
                    echo "  • Docker: https://docs.docker.com/get-docker/"
                    ;;
                "docker-compose")
                    echo "  • Docker Compose: https://docs.docker.com/compose/install/"
                    ;;
                "git")
                    echo "  • Git: https://git-scm.com/downloads"
                    ;;
                "curl")
                    echo "  • curl: Usually pre-installed or available via package manager"
                    ;;
            esac
        done
        
        exit 1
    fi
    
    echo -e "${GREEN}✅ All dependencies are available${NC}"
}

# Clone or update repository
setup_repository() {
    if [[ "$UPGRADE_MODE" == "true" && -d "$INSTALL_DIR" ]]; then
        echo -e "${BLUE}📥 Updating existing repository...${NC}"
        cd "$INSTALL_DIR"
        
        # Stash any local changes
        if git status --porcelain | grep -q .; then
            echo -e "${YELLOW}⚠️  Local changes detected - stashing them${NC}"
            git stash push -m "Pre-upgrade stash $(date)"
        fi
        
        # Pull latest changes
        git fetch origin
        git checkout "$BRANCH"
        git pull origin "$BRANCH"
        
        cd ..
    else
        echo -e "${BLUE}📥 Cloning repository...${NC}"
        git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$INSTALL_DIR"
    fi
    
    echo -e "${GREEN}✅ Repository ready${NC}"
}

# Configure authentication services
configure_auth_services() {
    echo -e "${BLUE}🔐 Configuring authentication services...${NC}"
    
    cd "$INSTALL_DIR"
    
    # Set up service configuration for secure mode
    if [[ -f "scripts/configure-services.sh" ]]; then
        if [[ "$ENABLE_MCP" == "true" ]]; then
            ./scripts/configure-services.sh preset secure
            echo -e "${GREEN}✅ Configured with all authentication services + MCP${NC}"
        else
            # Create custom config with auth but without MCP
            ./scripts/configure-services.sh preset full
            
            # Add auth services manually
            cat >> .lakehouse-services.conf << EOF

# Authentication Services
auth-service=true
auth-proxy=true
mcp-server=false
EOF
            ./scripts/configure-services.sh validate || true
            echo -e "${GREEN}✅ Configured with authentication services${NC}"
        fi
    fi
    
    cd ..
}

# Run installation
run_installation() {
    echo -e "${BLUE}🚀 Running Lakehouse Lab installation...${NC}"
    
    cd "$INSTALL_DIR"
    
    # Run the main installer
    local install_args=""
    
    if [[ "$PROFILE" == "fat-server" ]]; then
        install_args+=" --fat-server"
    fi
    
    if [[ "$ENABLE_ICEBERG" == "true" ]]; then
        install_args+=" --iceberg"
    fi
    
    if [[ "$UNATTENDED" == "true" ]]; then
        install_args+=" --unattended"
    fi
    
    if [[ "$AUTO_START" == "false" ]]; then
        install_args+=" --no-start"
    fi
    
    # Run the base installation
    ./install.sh $install_args
    
    cd ..
    
    echo -e "${GREEN}✅ Base installation completed${NC}"
}

# Enable authentication
enable_authentication() {
    echo -e "${BLUE}🔐 Enabling authentication system...${NC}"
    
    cd "$INSTALL_DIR"
    
    # Enable authentication services
    ./scripts/enable-auth.sh
    
    cd ..
    
    echo -e "${GREEN}✅ Authentication system enabled${NC}"
}

# Setup OAuth (optional)
setup_oauth_wizard() {
    if [[ "$SETUP_OAUTH" == "true" && "$UNATTENDED" != "true" ]]; then
        echo -e "${BLUE}🔗 Running OAuth setup wizard...${NC}"
        
        cd "$INSTALL_DIR"
        ./scripts/setup-auth.sh
        cd ..
        
        echo -e "${GREEN}✅ OAuth configuration completed${NC}"
    elif [[ "$SETUP_OAUTH" == "true" ]]; then
        echo -e "${YELLOW}⚠️  OAuth setup skipped in unattended mode${NC}"
        echo -e "${BLUE}💡 Run './scripts/setup-auth.sh' later to configure OAuth${NC}"
    fi
}

# Show completion message
show_completion() {
    echo ""
    echo -e "${BOLD}${GREEN}🎉 Lakehouse Lab with Authentication installed successfully!${NC}"
    echo ""
    echo -e "${BLUE}📋 What's Installed:${NC}"
    echo -e "✅ Complete data analytics stack (Spark, Superset, Jupyter, Airflow)"
    echo -e "✅ Modern additions (Vizro dashboards, LanceDB vector database)"
    echo -e "✅ Authentication system (OAuth + local)"
    echo -e "✅ Role-based access control"
    echo -e "✅ Service access proxy"
    echo -e "✅ Audit logging"
    
    if [[ "$ENABLE_MCP" == "true" ]]; then
        echo -e "✅ MCP Server (AI-powered data API)"
    fi
    
    echo ""
    echo -e "${YELLOW}🔗 Access Points:${NC}"
    
    cd "$INSTALL_DIR"
    
    # Get host IP
    local host_ip=$(grep "HOST_IP=" .env 2>/dev/null | cut -d'=' -f2 || echo "localhost")
    
    echo -e "• Authentication Portal:    ${GREEN}http://${host_ip}:9091${NC}"
    echo -e "• Secure Service Access:    ${GREEN}http://${host_ip}:9092${NC}"
    echo -e "• Service Dashboard:        ${GREEN}http://${host_ip}:9061${NC}"
    
    if [[ "$ENABLE_MCP" == "true" ]]; then
        echo -e "• MCP API:                  ${GREEN}http://${host_ip}:9090${NC}"
    fi
    
    cd ..
    
    echo ""
    echo -e "${YELLOW}🔐 Authentication:${NC}"
    echo -e "• Default admin login: admin@localhost (any password)"
    echo -e "• Configure OAuth providers: ${CYAN}cd $INSTALL_DIR && ./scripts/setup-auth.sh${NC}"
    echo -e "• View all credentials: ${CYAN}cd $INSTALL_DIR && ./scripts/show-credentials.sh${NC}"
    
    echo ""
    echo -e "${BLUE}📚 Next Steps:${NC}"
    echo -e "1. ${CYAN}cd $INSTALL_DIR${NC}"
    if [[ "$SETUP_OAUTH" != "true" ]]; then
        echo -e "2. ${CYAN}./scripts/setup-auth.sh${NC} (configure OAuth providers)"
    fi
    echo -e "3. Access the authentication portal and log in"
    echo -e "4. Explore the example notebooks and dashboards"
    echo -e "5. Check the documentation: ${CYAN}README.md${NC} and ${CYAN}CONFIGURATION.md${NC}"
    
    echo ""
    echo -e "${GREEN}Your secure, team-ready data platform is now available! 🚀${NC}"
}

# Main installation flow
main() {
    print_header
    
    echo -e "${BLUE}Installing Lakehouse Lab with Enterprise Authentication${NC}"
    echo -e "${BLUE}Configuration: $PROFILE profile, branch: $BRANCH${NC}"
    if [[ "$ENABLE_MCP" == "true" ]]; then
        echo -e "${BLUE}Features: Authentication + MCP Server (AI Assistant)${NC}"
    else
        echo -e "${BLUE}Features: Authentication System${NC}"
    fi
    echo ""
    
    # Installation steps
    check_existing_installation
    check_dependencies
    setup_repository
    configure_auth_services
    run_installation
    enable_authentication
    setup_oauth_wizard
    
    # Show completion
    show_completion
}

# Run main installation
main "$@"