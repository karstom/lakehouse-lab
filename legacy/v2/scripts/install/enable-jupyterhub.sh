#!/bin/bash

# Enable JupyterHub (Multi-User Jupyter) for Lakehouse Lab
# Replaces single-user Jupyter with team-ready JupyterHub

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
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

echo -e "${BOLD}${BLUE}👥 Lakehouse Lab - Enable JupyterHub${NC}"
echo -e "${BLUE}====================================${NC}"
echo ""

# Check if we're in the right directory
if [[ ! -f "docker-compose.yml" ]] || [[ ! -f "docker-compose.jupyterhub.yml" ]]; then
    log_error "Please run this script from your Lakehouse Lab directory"
    log_info "Make sure docker-compose.yml and docker-compose.jupyterhub.yml files exist"
    exit 1
fi

# Check if JupyterHub is already running
if docker compose ps | grep -q "jupyterhub"; then
    log_warning "JupyterHub appears to already be running"
    echo -n "Do you want to restart JupyterHub? [y/N]: "
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        log_info "Operation cancelled"
        exit 0
    fi
fi

log_info "Stopping current Jupyter service..."
docker compose stop jupyter 2>/dev/null || true

log_info "Starting JupyterHub with multi-user support..."
docker compose -f docker-compose.yml -f docker-compose.jupyterhub.yml up -d jupyterhub

log_info "Waiting for JupyterHub to start..."
sleep 10

# Check if JupyterHub is responding
log_info "Checking JupyterHub health..."
for i in {1..30}; do
    if curl -s http://localhost:9041/hub/health >/dev/null 2>&1; then
        log_success "JupyterHub is running!"
        break
    elif [[ $i -eq 30 ]]; then
        log_warning "JupyterHub may still be starting up"
        break
    else
        sleep 2
    fi
done

echo ""
log_success "🎉 JupyterHub (Multi-User Jupyter) is now enabled!"
echo ""
echo -e "${CYAN}📋 JupyterHub Access Information:${NC}"
echo -e "${YELLOW}─────────────────────────────────${NC}"
echo -e "🌐 ${BOLD}JupyterHub URL:${NC} http://localhost:9041"
echo -e "👤 ${BOLD}Default Admin:${NC} admin (any password)"
echo -e "🔐 ${BOLD}Authentication:${NC} PAM-based (system users)"
echo ""
echo -e "${BLUE}👥 Multi-User Features:${NC}"
echo -e "✅ Containerized user isolation"
echo -e "✅ Individual user workspaces"
echo -e "✅ Shared notebook access"
echo -e "✅ Resource management per user"
echo -e "✅ Admin control panel"
echo ""
echo -e "${YELLOW}🚀 Next Steps:${NC}"
echo -e "1. Visit http://localhost:9041 to access JupyterHub"
echo -e "2. Login with 'admin' username (any password)"
echo -e "3. Create user accounts from the admin panel"
echo -e "4. Use ${CYAN}./scripts/provision-user.sh${NC} to add team members"
echo ""
echo -e "${GREEN}🔗 User Management:${NC}"
echo -e "• Add users: ${CYAN}./scripts/provision-user.sh username password analyst${NC}"
echo -e "• Monitor usage: Check JupyterHub admin panel"
echo -e "• Scale resources: Edit docker-compose.jupyterhub.yml"
echo ""
echo -e "${BLUE}💡 Note: Single-user Jupyter (port 9040) is now replaced by JupyterHub${NC}"
echo -e "${BLUE}    All users will access notebooks through the multi-user environment${NC}"