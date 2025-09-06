#!/bin/bash

# Fix credentials after upgrade
# This script regenerates missing credentials and fixes common upgrade issues

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

echo -e "${BLUE}🔧 Lakehouse Lab - Credentials Fixer${NC}"
echo -e "${BLUE}===================================${NC}"
echo ""

# Check if we're in the right directory
if [[ ! -f "docker-compose.yml" ]] || [[ ! -f ".env" ]]; then
    log_error "Please run this script from your Lakehouse Lab directory"
    log_info "Make sure docker-compose.yml and .env files exist"
    exit 1
fi

log_info "Backing up current .env file..."
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
log_success "Backup created"

log_info "Checking and fixing missing credentials..."

# Function to add credential if missing
add_if_missing() {
    local key="$1"
    local value="$2"
    local description="$3"
    
    if ! grep -q "^${key}=" .env; then
        echo "${key}=${value}" >> .env
        log_success "Added ${description}: ${key}"
    else
        local current_value=$(grep "^${key}=" .env | cut -d'=' -f2-)
        if [[ -z "$current_value" ]] || [[ "$current_value" == "CHANGE_ME" ]]; then
            sed -i "s/^${key}=.*/${key}=${value}/" .env
            log_success "Fixed ${description}: ${key}"
        else
            log_info "✓ ${description} already set: ${key}"
        fi
    fi
}

# Generate secure random passwords
generate_password() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-25
}

generate_token() {
    openssl rand -hex 32
}

generate_fernet_key() {
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "$(openssl rand -base64 32)"
}

sync_postgresql_password() {
    local max_attempts=10
    local attempt=1
    local current_postgres_password=$(grep "^POSTGRES_PASSWORD=" .env | cut -d'=' -f2- | tr -d '"')
    
    if [[ -z "$current_postgres_password" ]]; then
        log_warning "No POSTGRES_PASSWORD found in .env - skipping PostgreSQL sync"
        return 0
    fi
    
    log_info "Synchronizing PostgreSQL password with .env file..."
    
    while [[ $attempt -le $max_attempts ]]; do
        # Try to update PostgreSQL password to match .env
        if docker compose exec -T postgres psql -U postgres -d postgres -c "ALTER USER postgres PASSWORD '$current_postgres_password';" >/dev/null 2>&1; then
            log_success "PostgreSQL password synchronized successfully"
            
            # Verify the password works by testing connection
            if docker compose exec -T postgres psql -U postgres -d postgres -c "SELECT 1;" >/dev/null 2>&1; then
                log_success "PostgreSQL password verification successful"
                return 0
            else
                log_warning "PostgreSQL password update succeeded but verification failed"
                return 1
            fi
        else
            log_warning "PostgreSQL password sync attempt $attempt/$max_attempts failed"
            if [[ $attempt -lt $max_attempts ]]; then
                log_info "Waiting 5 seconds before retry..."
                sleep 5
            fi
        fi
        
        attempt=$((attempt + 1))
    done
    
    log_error "PostgreSQL password synchronization failed after $max_attempts attempts"
    log_warning "You may need to manually update the PostgreSQL password:"
    log_info "  docker compose exec postgres psql -U postgres -d postgres -c \"ALTER USER postgres PASSWORD '$current_postgres_password';\""
    return 1
}

# Fix PostgreSQL credentials
POSTGRES_PASSWORD=$(generate_password)
add_if_missing "POSTGRES_PASSWORD" "$POSTGRES_PASSWORD" "PostgreSQL password"
add_if_missing "POSTGRES_USER" "postgres" "PostgreSQL user"
add_if_missing "POSTGRES_DB" "lakehouse" "PostgreSQL database"

# Fix MinIO credentials
MINIO_ROOT_PASSWORD=$(generate_password)
add_if_missing "MINIO_ROOT_USER" "admin" "MinIO root user"
add_if_missing "MINIO_ROOT_PASSWORD" "$MINIO_ROOT_PASSWORD" "MinIO root password"

# Fix Jupyter credentials
JUPYTER_TOKEN=$(generate_token)
add_if_missing "JUPYTER_TOKEN" "$JUPYTER_TOKEN" "Jupyter token"

# Fix Airflow credentials
AIRFLOW_ADMIN_PASSWORD=$(generate_password)
AIRFLOW_SECRET_KEY=$(generate_token)
AIRFLOW_FERNET_KEY=$(generate_fernet_key)
add_if_missing "AIRFLOW_ADMIN_USER" "admin" "Airflow admin user"
add_if_missing "AIRFLOW_ADMIN_PASSWORD" "$AIRFLOW_ADMIN_PASSWORD" "Airflow admin password"
add_if_missing "AIRFLOW_SECRET_KEY" "$AIRFLOW_SECRET_KEY" "Airflow secret key"
add_if_missing "AIRFLOW_FERNET_KEY" "$AIRFLOW_FERNET_KEY" "Airflow fernet key"

# Fix Superset credentials
SUPERSET_ADMIN_PASSWORD=$(generate_password)
SUPERSET_SECRET_KEY=$(generate_token)
add_if_missing "SUPERSET_ADMIN_USER" "admin" "Superset admin user"
add_if_missing "SUPERSET_ADMIN_PASSWORD" "$SUPERSET_ADMIN_PASSWORD" "Superset admin password"
add_if_missing "SUPERSET_SECRET_KEY" "$SUPERSET_SECRET_KEY" "Superset secret key"

# Fix Vizro credentials
VIZRO_SECRET_KEY=$(generate_token)
add_if_missing "VIZRO_SECRET_KEY" "$VIZRO_SECRET_KEY" "Vizro secret key"

# Fix host configuration
HOST_IP=$(hostname -I | awk '{print $1}' 2>/dev/null || echo "localhost")
add_if_missing "HOST_IP" "$HOST_IP" "Host IP address"

# Fix data root path
add_if_missing "LAKEHOUSE_ROOT" "./lakehouse-data" "Lakehouse data root"

echo ""
log_info "Restarting services to apply new credentials..."

# Use restart instead of down/up to preserve containers and data
log_info "Restarting services with new credentials..."
docker compose restart

# Wait for services to be ready
log_info "Waiting for services to be ready..."
sleep 15

# Check if any services failed to start and try to bring them up
log_info "Ensuring all services are running..."
docker compose up -d

# Fix PostgreSQL password synchronization after restart
log_info "Synchronizing PostgreSQL password..."
sync_postgresql_password

echo ""
log_success "✅ Credential fix completed!"
echo ""
echo -e "${CYAN}📋 Your new credentials:${NC}"
echo -e "${YELLOW}────────────────────────────${NC}"
echo -e "🗄️  ${BOLD}PostgreSQL:${NC}"
echo -e "   • User: postgres"
echo -e "   • Password: ${POSTGRES_PASSWORD}"
echo -e "   • Database: lakehouse"
echo ""
echo -e "📦 ${BOLD}MinIO (Object Storage):${NC}"
echo -e "   • User: admin"
echo -e "   • Password: ${MINIO_ROOT_PASSWORD}"
echo -e "   • Console: http://${HOST_IP}:9001"
echo ""
echo -e "📓 ${BOLD}Jupyter:${NC}"
echo -e "   • URL: http://${HOST_IP}:9040"
echo -e "   • Token: ${JUPYTER_TOKEN}"
echo ""
echo -e "🌊 ${BOLD}Airflow:${NC}"
echo -e "   • URL: http://${HOST_IP}:9020"
echo -e "   • User: admin"
echo -e "   • Password: ${AIRFLOW_ADMIN_PASSWORD}"
echo ""
echo -e "📊 ${BOLD}Superset:${NC}"
echo -e "   • URL: http://${HOST_IP}:9030"
echo -e "   • User: admin"
echo -e "   • Password: ${SUPERSET_ADMIN_PASSWORD}"
echo ""
echo -e "${BLUE}💡 To see all credentials anytime: ./scripts/show-credentials.sh${NC}"
echo -e "${BLUE}💾 Backup saved as: .env.backup.$(date +%Y%m%d_%H%M%S)${NC}"