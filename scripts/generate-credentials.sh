#!/bin/bash

# Lakehouse Lab - Secure Credential Generator
# Generates memorable passphrases and secure passwords for all services

set -euo pipefail

# Word lists for memorable passphrases
ADJECTIVES=(
    "swift" "bright" "quiet" "brave" "calm" "deep" "fresh" "green" "happy" "kind"
    "light" "quick" "smart" "strong" "warm" "wise" "bold" "clear" "cool" "fair"
    "fast" "fine" "free" "good" "high" "long" "new" "nice" "open" "pure"
    "safe" "soft" "tall" "true" "wild" "young" "clean" "easy" "gentle" "honest"
)

NOUNS=(
    "river" "ocean" "forest" "mountain" "garden" "meadow" "valley" "bridge" "castle" "tower"
    "stream" "island" "harbor" "beacon" "anchor" "compass" "journey" "voyage" "summit" "horizon"
    "crystal" "diamond" "emerald" "sapphire" "treasure" "wisdom" "courage" "freedom" "harmony" "serenity"
    "sunrise" "sunset" "starlight" "moonbeam" "rainbow" "thunder" "lightning" "breeze" "snowflake" "dewdrop"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
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

# Generate memorable passphrase
generate_passphrase() {
    local adj1=${ADJECTIVES[$RANDOM % ${#ADJECTIVES[@]}]}
    local noun1=${NOUNS[$RANDOM % ${#NOUNS[@]}]}
    local adj2=${ADJECTIVES[$RANDOM % ${#ADJECTIVES[@]}]}
    local number=$((RANDOM % 900 + 100))  # 3-digit number
    
    echo "${adj1}-${noun1}-${adj2}-${number}"
}

# Generate strong password
generate_strong_password() {
    local length=${1:-16}
    # Mix of uppercase, lowercase, numbers, and safe symbols
    local chars='ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789@#$%^&*-_=+'
    local password=""
    
    for i in $(seq 1 $length); do
        password+="${chars:$((RANDOM % ${#chars})):1}"
    done
    
    echo "$password"
}

# Generate database-safe password (no URL-breaking or shell-problematic characters)
generate_db_safe_password() {
    local length=${1:-20}
    # Only alphanumeric and very safe symbols (no @, =, :, /, ?, #, $, *, `, \, ^, &)
    local chars='ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789-_+'
    local password=""
    
    for i in $(seq 1 $length); do
        password+="${chars:$((RANDOM % ${#chars})):1}"
    done
    
    echo "$password"
}

# Generate UUID-style token
generate_token() {
    local format=${1:-"uuid"}
    
    case $format in
        "uuid")
            # Generate UUID v4 format
            printf '%08x-%04x-%04x-%04x-%012x\n' \
                $RANDOM$RANDOM $RANDOM $RANDOM $RANDOM $RANDOM $RANDOM$RANDOM
            ;;
        "base64")
            # Generate 32-byte random string, base64 encoded
            openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
            ;;
        *)
            generate_strong_password 32
            ;;
    esac
}

# Generate Fernet key for Airflow
generate_fernet_key() {
    python3 -c "
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
" 2>/dev/null || echo "$(openssl rand -base64 32)"
}

# Main credential generation
generate_all_credentials() {
    local env_file=${1:-".env"}
    
    log_info "Generating secure credentials for Lakehouse Lab..."
    
    # User-facing service credentials (memorable passphrases)
    AIRFLOW_ADMIN_PASSWORD=$(generate_passphrase)
    SUPERSET_ADMIN_PASSWORD=$(generate_passphrase)
    JUPYTER_TOKEN=$(generate_passphrase)
    
    # Service-to-service credentials (strong passwords)
    POSTGRES_PASSWORD=$(generate_db_safe_password 20)  # Database-safe for connection strings
    MINIO_ROOT_PASSWORD=$(generate_db_safe_password 20)  # Use safe characters for MinIO too
    
    # Validate generated passwords are not empty
    if [[ -z "$POSTGRES_PASSWORD" ]]; then
        log_error "Failed to generate POSTGRES_PASSWORD"
        exit 1
    fi
    if [[ -z "$MINIO_ROOT_PASSWORD" ]]; then
        log_error "Failed to generate MINIO_ROOT_PASSWORD"
        exit 1
    fi
    
    # Secret keys and tokens
    AIRFLOW_SECRET_KEY=$(generate_token "base64")
    AIRFLOW_FERNET_KEY=$(generate_fernet_key)
    SUPERSET_SECRET_KEY=$(generate_token "base64")
    
    # MinIO credentials (memorable for CLI usage)
    MINIO_ROOT_USER="admin"
    
    # Database credentials
    POSTGRES_USER="postgres"  # PostgreSQL superuser
    POSTGRES_DB="lakehouse"
    
    # Debug: Show generated values
    log_info "Generated credentials summary:"
    log_info "  POSTGRES_PASSWORD length: ${#POSTGRES_PASSWORD}"
    log_info "  MINIO_ROOT_PASSWORD length: ${#MINIO_ROOT_PASSWORD}"
    log_info "  AIRFLOW_SECRET_KEY length: ${#AIRFLOW_SECRET_KEY}"
    
    # Write to environment file
    cat > "$env_file" << EOF
# Lakehouse Lab - Generated Credentials
# Generated on: $(date)
# 
# SECURITY WARNING: 
# - Keep this file secure and do not commit to version control
# - Use './scripts/show-credentials.sh' to display credentials
# - Use './scripts/rotate-credentials.sh' to generate new ones

# ===========================================
# USER-FACING SERVICE CREDENTIALS
# ===========================================
# These use memorable passphrases for easy login

# Airflow Web UI (http://localhost:9020)
AIRFLOW_ADMIN_USER=admin
AIRFLOW_ADMIN_PASSWORD="$AIRFLOW_ADMIN_PASSWORD"

# Superset BI (http://localhost:9030) 
SUPERSET_ADMIN_USER=admin
SUPERSET_ADMIN_PASSWORD="$SUPERSET_ADMIN_PASSWORD"

# JupyterLab (http://localhost:9040)
JUPYTER_TOKEN="$JUPYTER_TOKEN"

# ===========================================
# OBJECT STORAGE CREDENTIALS
# ===========================================
# MinIO S3-compatible storage (http://localhost:9001)
MINIO_ROOT_USER="$MINIO_ROOT_USER"
MINIO_ROOT_PASSWORD="$MINIO_ROOT_PASSWORD"

# ===========================================
# DATABASE CREDENTIALS  
# ===========================================
# PostgreSQL database (internal access only)
POSTGRES_USER="$POSTGRES_USER"
POSTGRES_PASSWORD="$POSTGRES_PASSWORD"
POSTGRES_DB="$POSTGRES_DB"

# ===========================================
# SERVICE SECRET KEYS
# ===========================================
# Internal service security (do not share)
AIRFLOW_SECRET_KEY="$AIRFLOW_SECRET_KEY"
AIRFLOW_FERNET_KEY="$AIRFLOW_FERNET_KEY"
SUPERSET_SECRET_KEY="$SUPERSET_SECRET_KEY"

# ===========================================
# PERFORMANCE & RESOURCE LIMITS
# ===========================================
# These can be customized based on your system resources

# Spark Configuration
SPARK_MASTER_MEMORY=2g
SPARK_MASTER_CORES=2
SPARK_WORKER_MEMORY=8g
SPARK_WORKER_CORES=4
SPARK_WORKER_INSTANCES=1

# Database Configuration
POSTGRES_SHARED_BUFFERS=256MB
POSTGRES_EFFECTIVE_CACHE_SIZE=1GB
POSTGRES_MAINTENANCE_WORK_MEM=128MB

# Memory Limits
JUPYTER_MEMORY_LIMIT=8G
AIRFLOW_SCHEDULER_MEMORY_LIMIT=4G
AIRFLOW_WEBSERVER_MEMORY_LIMIT=4G
SUPERSET_MEMORY_LIMIT=4G
MINIO_MEMORY_LIMIT=4G
SPARK_MASTER_MEMORY_LIMIT=4G
SPARK_WORKER_MEMORY_LIMIT=16G
PORTAINER_MEMORY_LIMIT=512M

# Jupyter Spark Configuration
JUPYTER_SPARK_DRIVER_MEMORY=2g
JUPYTER_SPARK_EXECUTOR_MEMORY=2g
JUPYTER_SPARK_EXECUTOR_CORES=2

# Spark Environment Variables (to prevent Docker Compose warnings)
SPARK_HOME=/usr/local/spark
PYTHONPATH=/usr/local/spark/python:/usr/local/spark/python/lib/py4j-0.10.9.7-src.zip

# ===========================================
# NEW SERVICES CONFIGURATION
# ===========================================

# Vizro Dashboard Framework
VIZRO_MEMORY_LIMIT=2G
VIZRO_MEMORY_RESERVATION=512M

# LanceDB Vector Database
LANCEDB_MEMORY_LIMIT=3G
LANCEDB_MEMORY_RESERVATION=1G

EOF

    log_success "Credentials generated and saved to: $env_file"
    
    # Create credential summary
    cat > ".credentials-summary.txt" << EOF
===========================================
LAKEHOUSE LAB - ACCESS CREDENTIALS
===========================================
Generated: $(date)

🌐 WEB INTERFACES:
├── Airflow:     http://localhost:9020
│   └── Login:   admin / ${AIRFLOW_ADMIN_PASSWORD}
├── Superset:    http://localhost:9030  
│   └── Login:   admin / ${SUPERSET_ADMIN_PASSWORD}
├── JupyterLab:  http://localhost:9040
│   └── Token:   ${JUPYTER_TOKEN}
├── MinIO:       http://localhost:9001
│   └── Login:   ${MINIO_ROOT_USER} / ${MINIO_ROOT_PASSWORD}
├── Spark UI:    http://localhost:8080
├── Portainer:   http://localhost:9060
├── Homer:       http://localhost:9061
├── Vizro:       http://localhost:9050
└── LanceDB:     http://localhost:9080

📋 QUICK ACCESS:
- View all credentials: ./scripts/show-credentials.sh
- Rotate credentials:   ./scripts/rotate-credentials.sh  
- Start services:       ./start-lakehouse.sh

🔒 SECURITY:
- All credentials are unique to this installation
- Passphrases use memorable word combinations
- Service keys use cryptographically strong generation
- Keep .env file secure and do not commit to git

EOF

    log_info "Credential summary saved to: .credentials-summary.txt"
    echo
    log_warning "🔒 IMPORTANT SECURITY NOTES:"
    echo "   • Your .env file contains sensitive credentials"
    echo "   • The .env file is automatically git-ignored"  
    echo "   • Use './scripts/show-credentials.sh' to view credentials anytime"
    echo "   • Back up your .env file in a secure location"
    echo
    log_success "🎉 Setup complete! Use './start-lakehouse.sh' to start services"
}

# Script execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Check if .env already exists
    if [[ -f ".env" ]]; then
        log_warning "Found existing .env file"
        echo -n "Do you want to regenerate credentials? This will overwrite existing ones. [y/N]: "
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            log_info "Keeping existing credentials. Use './scripts/show-credentials.sh' to view them."
            exit 0
        fi
        
        # Backup existing .env
        cp ".env" ".env.backup.$(date +%Y%m%d_%H%M%S)"
        log_info "Backed up existing .env file"
    fi
    
    generate_all_credentials ".env"
    
    # Show generated credentials
    log_info "Generated credentials:"
    echo
    cat .credentials-summary.txt
fi