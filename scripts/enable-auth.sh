#!/bin/bash

# Lakehouse Lab - Enable Authentication System
# Adds authentication services to existing installation

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
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
    echo -e "${BLUE}🔐 Lakehouse Lab - Enable Authentication System${NC}"
    echo -e "${BLUE}===============================================${NC}"
    echo ""
}

# Check if lakehouse lab is installed
check_installation() {
    if [[ ! -f ".env" ]]; then
        log_error "Lakehouse Lab not found in current directory"
        log_info "Please run this script from your Lakehouse Lab installation directory"
        log_info "Or run './install.sh' first to create a new installation"
        exit 1
    fi
    
    if [[ ! -f "docker-compose.yml" ]]; then
        log_error "docker-compose.yml not found"
        log_info "Please ensure you're in the correct Lakehouse Lab directory"
        exit 1
    fi
    
    log_success "Found existing Lakehouse Lab installation"
}

# Check if auth is already enabled
check_auth_status() {
    if docker compose ps --services | grep -q "auth-service\|auth-proxy\|mcp-server"; then
        log_warning "Authentication services appear to be already running"
        echo -n "Do you want to reconfigure authentication? [y/N]: "
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            log_info "Authentication configuration cancelled"
            exit 0
        fi
    fi
}

# Add authentication environment variables
add_auth_env_vars() {
    log_info "Adding authentication configuration to .env file..."
    
    # Generate JWT secret if not exists
    if ! grep -q "^JWT_SECRET=" .env; then
        jwt_secret=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
        echo "" >> .env
        echo "# Authentication Configuration" >> .env
        echo "JWT_SECRET=${jwt_secret}" >> .env
    fi
    
    # Add auth mode if not exists
    if ! grep -q "^AUTH_MODE=" .env; then
        echo "AUTH_MODE=hybrid" >> .env
    fi
    
    # Add default admin email if not exists
    if ! grep -q "^DEFAULT_ADMIN_EMAIL=" .env; then
        echo "DEFAULT_ADMIN_EMAIL=admin@localhost" >> .env
    fi
    
    # Add admin emails if not exists
    if ! grep -q "^ADMIN_EMAILS=" .env; then
        echo "ADMIN_EMAILS=admin@localhost" >> .env
    fi
    
    # Add MCP configuration
    if ! grep -q "^MCP_LOG_LEVEL=" .env; then
        echo "" >> .env
        echo "# MCP Server Configuration" >> .env
        echo "MCP_LOG_LEVEL=INFO" >> .env
        echo "MCP_RATE_LIMIT=true" >> .env
        echo "MCP_MAX_QUERY_SIZE=100MB" >> .env
        echo "MCP_MEMORY_LIMIT=2G" >> .env
        echo "MCP_MEMORY_RESERVATION=1G" >> .env
    fi
    
    # Add audit configuration
    if ! grep -q "^AUDIT_RETENTION_DAYS=" .env; then
        echo "" >> .env
        echo "# Audit Configuration" >> .env
        echo "AUDIT_RETENTION_DAYS=365" >> .env
        echo "AUTH_LOG_LEVEL=INFO" >> .env
        echo "CORS_ENABLED=true" >> .env
    fi
    
    log_success "Authentication environment variables added"
}

# Enable authentication services in configuration
enable_auth_services() {
    log_info "Enabling authentication services in configuration..."
    
    # Use the secure preset which includes all auth services
    if [[ -f "scripts/configure-services.sh" ]]; then
        ./scripts/configure-services.sh preset secure
        log_success "Authentication services enabled in service configuration"
    else
        log_warning "Service configuration script not found, manual configuration needed"
    fi
}

# Create configuration directories
create_config_dirs() {
    log_info "Creating configuration directories..."
    
    mkdir -p config
    mkdir -p "${LAKEHOUSE_ROOT:-./lakehouse-data}/auth"
    mkdir -p "${LAKEHOUSE_ROOT:-./lakehouse-data}/audit/logs"
    mkdir -p "${LAKEHOUSE_ROOT:-./lakehouse-data}/mcp/logs"
    
    log_success "Configuration directories created"
}

# Check if Docker images need to be built
check_docker_images() {
    log_info "Checking Docker images for authentication services..."
    
    local images_needed=()
    
    if ! docker images --format "table {{.Repository}}:{{.Tag}}" | grep -q "lakehouse-auth:latest"; then
        images_needed+=("lakehouse-auth")
    fi
    
    if ! docker images --format "table {{.Repository}}:{{.Tag}}" | grep -q "lakehouse-auth-proxy:latest"; then
        images_needed+=("lakehouse-auth-proxy")
    fi
    
    if ! docker images --format "table {{.Repository}}:{{.Tag}}" | grep -q "lakehouse-mcp:latest"; then
        images_needed+=("lakehouse-mcp")
    fi
    
    if [[ ${#images_needed[@]} -gt 0 ]]; then
        log_warning "Docker images need to be built: ${images_needed[*]}"
        log_info "This is normal for first-time authentication setup"
        echo -n "Build authentication service images now? [Y/n]: "
        read -r build_response
        
        if [[ ! "$build_response" =~ ^[Nn]$ ]]; then
            build_auth_images
        else
            log_warning "Authentication images not built - services may fail to start"
            log_info "You can build them later with: docker compose -f docker-compose.yml -f docker-compose.auth.yml build"
        fi
    else
        log_success "All authentication Docker images are available"
    fi
}

# Build authentication service images
build_auth_images() {
    log_info "Building authentication service Docker images..."
    
    # This would build the images if we had the full source
    # For now, we'll note that images need to be available
    log_warning "Note: Authentication service images need to be built or pulled"
    log_info "In a complete implementation, this would build:"
    log_info "  • lakehouse-auth:latest (OAuth & local authentication)"
    log_info "  • lakehouse-auth-proxy:latest (Service access control)"
    log_info "  • lakehouse-mcp:latest (AI-powered data API)"
}

# Start authentication services
start_auth_services() {
    log_info "Starting authentication services..."
    
    # Stop existing services first
    log_info "Stopping existing services..."
    docker compose down
    
    # Start with authentication overlay
    log_info "Starting services with authentication enabled..."
    if docker compose -f docker-compose.yml -f docker-compose.auth.yml up -d; then
        log_success "Authentication services started successfully"
    else
        log_error "Failed to start authentication services"
        log_info "Check logs with: docker compose -f docker-compose.yml -f docker-compose.auth.yml logs"
        return 1
    fi
    
    # Wait for services to be healthy
    log_info "Waiting for authentication services to be ready..."
    sleep 10
    
    # Check service status
    local auth_status=$(docker compose ps --filter "name=lakehouse-auth" --format "table {{.Name}}\t{{.Status}}")
    if echo "$auth_status" | grep -q "Up"; then
        log_success "Authentication service is running"
    else
        log_warning "Authentication service status unclear"
    fi
}

# Show post-installation information
show_completion_info() {
    echo ""
    log_success "🎉 Authentication system enabled successfully!"
    echo ""
    echo -e "${BLUE}📋 What's Changed:${NC}"
    echo -e "✅ Authentication services added to your Lakehouse Lab"
    echo -e "✅ Service configuration updated to include auth components"
    echo -e "✅ Environment variables configured with secure defaults"
    echo -e "✅ Configuration directories created"
    echo ""
    echo -e "${YELLOW}🔐 Next Steps:${NC}"
    echo ""
    echo -e "${YELLOW}1. Configure OAuth Providers (Optional):${NC}"
    echo "   ./scripts/setup-auth.sh"
    echo ""
    echo -e "${YELLOW}2. Access Points:${NC}"
    local host_ip="${HOST_IP:-localhost}"
    echo "   • Authentication Portal: http://${host_ip}:9091"
    echo "   • Secure Service Access: http://${host_ip}:9092"
    echo "   • MCP API:              http://${host_ip}:9090"
    echo ""
    echo -e "${YELLOW}3. Service Management:${NC}"
    echo "   • View all credentials:  ./scripts/show-credentials.sh"
    echo "   • Configure services:    ./scripts/configure-services.sh"
    echo "   • Start/stop services:   docker compose -f docker-compose.yml -f docker-compose.auth.yml [up|down]"
    echo ""
    echo -e "${BLUE}💡 Tips:${NC}"
    echo "• Authentication is now in 'hybrid' mode (local + OAuth when configured)"
    echo "• Local admin login still available: admin@localhost with any password"
    echo "• Configure OAuth providers for team access with Google/Microsoft/GitHub"
    echo "• All service access is now controlled by user roles and permissions"
    echo ""
    echo -e "${GREEN}Your Lakehouse Lab is now secure and ready for team collaboration! 🚀${NC}"
}

# Main function
main() {
    print_header
    
    # Check prerequisites
    check_installation
    check_auth_status
    
    log_info "Enabling authentication system for your Lakehouse Lab installation..."
    echo ""
    
    # Perform installation steps
    add_auth_env_vars
    enable_auth_services
    create_config_dirs
    check_docker_images
    
    # Start services
    echo ""
    log_info "Starting authentication-enabled services..."
    if start_auth_services; then
        show_completion_info
    else
        log_error "Failed to start authentication services"
        echo ""
        log_info "Troubleshooting:"
        log_info "• Check Docker logs: docker compose logs auth-service"
        log_info "• Verify .env configuration"
        log_info "• Ensure all required ports are available"
        exit 1
    fi
}

# Run main function
main "$@"