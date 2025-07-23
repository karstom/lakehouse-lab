#!/bin/bash

# Lakehouse Lab - Credential Rotation
# Generates new credentials while preserving service configuration

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

# Check if services are running
check_services_running() {
    if docker compose ps --services --filter "status=running" | grep -q .; then
        return 0  # Services are running
    else
        return 1  # No services running
    fi
}

# Main rotation process
main() {
    echo -e "${BLUE}🔄 Lakehouse Lab - Credential Rotation${NC}"
    echo
    
    # Check if .env exists
    if [[ ! -f ".env" ]]; then
        log_error "No .env file found!"
        log_info "Run './scripts/generate-credentials.sh' first to create initial credentials"
        exit 1
    fi
    
    # Warning about credential rotation
    log_warning "CREDENTIAL ROTATION WARNING:"
    echo "   • This will generate new passwords for all services"
    echo "   • You will need to log in again to all web interfaces"
    echo "   • Running services may need to be restarted"
    echo "   • A backup of current credentials will be created"
    echo
    
    # Check if services are running
    if check_services_running; then
        log_warning "Detected running services. They may need restart after rotation."
        echo -n "Continue with credential rotation? [y/N]: "
    else
        echo -n "Generate new credentials? [y/N]: "
    fi
    
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        log_info "Credential rotation cancelled"
        exit 0
    fi
    
    # Create backup
    backup_file=".env.backup.$(date +%Y%m%d_%H%M%S)"
    cp ".env" "$backup_file"
    log_success "Backed up current credentials to: $backup_file"
    
    # Generate new credentials
    log_info "Generating new credentials..."
    ./scripts/generate-credentials.sh
    
    # Check if services need restart
    if check_services_running; then
        echo
        log_warning "Services are currently running with old credentials"
        echo -n "Restart services with new credentials? [Y/n]: "
        read -r restart_response
        
        if [[ ! "$restart_response" =~ ^[Nn]$ ]]; then
            log_info "Restarting services with new credentials..."
            docker compose down
            sleep 2
            docker compose up -d
            log_success "Services restarted with new credentials"
        else
            log_warning "Services are still running with old credentials"
            log_info "Run 'docker compose restart' to apply new credentials"
        fi
    fi
    
    echo
    log_success "🎉 Credential rotation complete!"
    log_info "Use './scripts/show-credentials.sh' to view new credentials"
    
    # Offer to show new credentials
    echo -n "Show new credentials now? [Y/n]: "
    read -r show_response
    if [[ ! "$show_response" =~ ^[Nn]$ ]]; then
        echo
        ./scripts/show-credentials.sh
    fi
}

# Run main function
main "$@"