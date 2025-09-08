#!/bin/bash
#
# Lakehouse Lab - Central User Provisioning Script
# 
# This script provisions a user account across all lakehouse services:
# - Superset (BI and dashboards)
# - Airflow (Workflow orchestration)
# - MinIO (Object storage)
# - JupyterHub (Multi-user notebooks)
#
# Usage: ./provision-user.sh <username> <email> <password> [role]
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAKEHOUSE_DIR="$(dirname "$SCRIPT_DIR")"

# Service URLs (using external localhost for host access)
SUPERSET_URL="http://localhost:9030"
AIRFLOW_URL="http://localhost:9020"
MINIO_URL="http://localhost:9001"
JUPYTERHUB_URL="http://localhost:9041"

# Load environment variables
if [ -f "$LAKEHOUSE_DIR/.env" ]; then
    source "$LAKEHOUSE_DIR/.env"
else
    echo -e "${RED}Error: .env file not found in $LAKEHOUSE_DIR${NC}"
    exit 1
fi

# Function definitions
usage() {
    echo "Usage: $0 <username> <email> <password> [role]"
    echo ""
    echo "Parameters:"
    echo "  username    - Username for all services"
    echo "  email       - User email address"
    echo "  password    - User password"
    echo "  role        - User role (admin|analyst|viewer) [default: analyst]"
    echo ""
    echo "Examples:"
    echo "  $0 john.doe john.doe@company.com SecurePass123 analyst"
    echo "  $0 admin admin@company.com AdminPass456 admin"
}

log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

check_service() {
    local service_name="$1"
    local url="$2"
    
    log "Checking $service_name availability..."
    if curl -s -f --connect-timeout 5 "$url/health" > /dev/null 2>&1 || \
       curl -s -f --connect-timeout 5 "$url" > /dev/null 2>&1; then
        success "$service_name is available"
        return 0
    else
        error "$service_name is not available at $url"
        return 1
    fi
}

provision_superset_user() {
    local username="$1"
    local email="$2" 
    local password="$3"
    local role="$4"
    
    log "Provisioning Superset user: $username"
    
    # Map role to Superset role
    local superset_role
    case "$role" in
        admin) superset_role="Admin" ;;
        analyst) superset_role="Alpha" ;;
        viewer) superset_role="Gamma" ;;
        *) superset_role="Alpha" ;;
    esac
    
    # Use Superset CLI via docker exec
    if docker exec lakehouse-lab-superset-1 superset fab create-user \
        --username "$username" \
        --firstname "$(echo $username | cut -d. -f1 | sed 's/.*/\u&/')" \
        --lastname "$(echo $username | cut -d. -f2- | sed 's/.*/\u&/' | tr '.' ' ')" \
        --email "$email" \
        --password "$password" \
        --role "$superset_role" 2>/dev/null; then
        success "Superset user created with role: $superset_role"
    else
        warn "Superset user creation failed (user may already exist)"
    fi
}

provision_airflow_user() {
    local username="$1"
    local email="$2"
    local password="$3"
    local role="$4"
    
    log "Provisioning Airflow user: $username"
    
    # Map role to Airflow role
    local airflow_role
    case "$role" in
        admin) airflow_role="Admin" ;;
        analyst) airflow_role="User" ;;
        viewer) airflow_role="Viewer" ;;
        *) airflow_role="User" ;;
    esac
    
    # Use Airflow CLI via docker exec
    if docker exec lakehouse-lab-airflow-webserver-1 airflow users create \
        --username "$username" \
        --firstname "$(echo $username | cut -d. -f1 | sed 's/.*/\u&/')" \
        --lastname "$(echo $username | cut -d. -f2- | sed 's/.*/\u&/' | tr '.' ' ')" \
        --email "$email" \
        --password "$password" \
        --role "$airflow_role" 2>/dev/null; then
        success "Airflow user created with role: $airflow_role"
    else
        warn "Airflow user creation failed (user may already exist)"
    fi
}

provision_minio_user() {
    local username="$1"
    local password="$2"
    local role="$3"
    
    log "Provisioning MinIO user: $username"
    
    # Create MinIO user using mc (MinIO Client)
    # First, create a temporary mc config
    if docker exec lakehouse-lab-minio-1 mc alias set local http://localhost:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" 2>/dev/null; then
        
        # Create the user
        if docker exec lakehouse-lab-minio-1 mc admin user add local "$username" "$password" 2>/dev/null; then
            
            # Assign policy based on role
            local minio_policy
            case "$role" in
                admin) minio_policy="consoleAdmin" ;;
                analyst) minio_policy="readwrite" ;;
                viewer) minio_policy="readonly" ;;
                *) minio_policy="readwrite" ;;
            esac
            
            if docker exec lakehouse-lab-minio-1 mc admin policy attach local "$minio_policy" --user="$username" 2>/dev/null; then
                success "MinIO user created with policy: $minio_policy"
            else
                warn "MinIO policy assignment failed"
            fi
        else
            warn "MinIO user creation failed (user may already exist)"
        fi
    else
        error "Failed to configure MinIO client"
    fi
}

provision_jupyterhub_user() {
    local username="$1"
    local password="$2"
    local role="$3"
    
    log "Provisioning JupyterHub user: $username"
    
    # Create system user in the JupyterHub container
    if docker exec lakehouse-lab-jupyter-1 useradd -m -s /bin/bash "$username" 2>/dev/null; then
        # Set password
        if docker exec lakehouse-lab-jupyter-1 bash -c "echo '$username:$password' | chpasswd" 2>/dev/null; then
            
            # Make admin if needed
            if [ "$role" = "admin" ]; then
                docker exec lakehouse-lab-jupyter-1 usermod -aG sudo "$username" 2>/dev/null || true
            fi
            
            success "JupyterHub user created"
        else
            error "Failed to set JupyterHub user password"
        fi
    else
        warn "JupyterHub user creation failed (user may already exist)"
    fi
}

# Main function
main() {
    # Parse arguments
    if [ $# -lt 3 ] || [ $# -gt 4 ]; then
        usage
        exit 1
    fi
    
    USERNAME="$1"
    EMAIL="$2"
    PASSWORD="$3"
    ROLE="${4:-analyst}"
    
    # Validate inputs
    if [[ ! "$USERNAME" =~ ^[a-zA-Z0-9._-]+$ ]]; then
        error "Invalid username. Use only alphanumeric characters, dots, underscores, and hyphens."
        exit 1
    fi
    
    if [[ ! "$EMAIL" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        error "Invalid email format."
        exit 1
    fi
    
    if [ ${#PASSWORD} -lt 8 ]; then
        error "Password must be at least 8 characters long."
        exit 1
    fi
    
    if [[ ! "$ROLE" =~ ^(admin|analyst|viewer)$ ]]; then
        error "Invalid role. Must be: admin, analyst, or viewer"
        exit 1
    fi
    
    # Display summary
    echo ""
    echo "======================================"
    echo "  Lakehouse Lab - User Provisioning  "
    echo "======================================"
    echo "Username: $USERNAME"
    echo "Email:    $EMAIL"
    echo "Role:     $ROLE"
    echo "======================================"
    echo ""
    
    read -p "Proceed with user creation? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "User creation cancelled."
        exit 0
    fi
    
    # Check service availability
    log "Checking service availability..."
    local services_available=true
    
    check_service "Superset" "$SUPERSET_URL" || services_available=false
    check_service "Airflow" "$AIRFLOW_URL" || services_available=false
    check_service "MinIO" "$MINIO_URL" || services_available=false
    check_service "JupyterHub" "$JUPYTERHUB_URL" || services_available=false
    
    if [ "$services_available" = false ]; then
        error "Some services are not available. Please check that all containers are running."
        exit 1
    fi
    
    echo ""
    
    # Provision user in each service
    provision_superset_user "$USERNAME" "$EMAIL" "$PASSWORD" "$ROLE"
    provision_airflow_user "$USERNAME" "$EMAIL" "$PASSWORD" "$ROLE"
    provision_minio_user "$USERNAME" "$PASSWORD" "$ROLE"
    provision_jupyterhub_user "$USERNAME" "$PASSWORD" "$ROLE"
    
    echo ""
    success "User provisioning completed!"
    echo ""
    echo "======================================"
    echo "       Access Information            "
    echo "======================================"
    echo "Username: $USERNAME"
    echo "Password: $PASSWORD"
    echo ""
    echo "Service URLs:"
    echo "• Superset:   http://localhost:9030"
    echo "• Airflow:    http://localhost:9020"
    echo "• JupyterHub: http://localhost:9041"
    echo "• MinIO:      http://localhost:9001"
    echo "• Vizro:      http://localhost:9050 (no auth)"
    echo ""
    echo "Role Permissions:"
    case "$ROLE" in
        admin)   echo "• Full admin access to all services" ;;
        analyst) echo "• Create/edit dashboards, run workflows, read/write data" ;;
        viewer)  echo "• View dashboards and data, read-only access" ;;
    esac
    echo "======================================"
}

# Run main function
main "$@"