#!/bin/bash

# Lakehouse Lab - Credential Viewer
# Displays current credentials in a user-friendly format

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Function to detect proper host IP address
detect_host_ip() {
    local detected_ip
    
    # Prefer HOST_IP environment variable if set and valid
    if [[ -n "${HOST_IP:-}" && "$HOST_IP" != "localhost" && "$HOST_IP" != "127.0.0.1" ]]; then
        echo "$HOST_IP"
        return 0
    fi
    
    # Try to detect from the host system - multiple fallback methods
    # Method 1: Use hostname -I (most reliable on Linux) - exclude Docker IPs
    if command -v hostname >/dev/null 2>&1; then
        detected_ip=$(hostname -I 2>/dev/null | awk '{print $1}')
        if [[ -n "$detected_ip" && "$detected_ip" != "127.0.0.1" && ! "$detected_ip" =~ ^172\.(1[6-9]|2[0-9]|3[0-1])\. ]]; then
            echo "$detected_ip"
            return 0
        fi
    fi
    
    # Method 2: Use ip route to get the IP used for external connectivity  
    detected_ip=$(ip route get 8.8.8.8 2>/dev/null | awk '/src/ {print $7}' | head -1)
    if [[ -n "$detected_ip" && "$detected_ip" != "127.0.0.1" && ! "$detected_ip" =~ ^172\.(1[6-9]|2[0-9]|3[0-1])\. ]]; then
        echo "$detected_ip"
        return 0
    fi
    
    # Method 3: Get first non-loopback, non-Docker IP from interfaces
    detected_ip=$(ip addr show | grep 'inet ' | grep -v '127.0.0.1' | grep -v 'docker' | grep -v '172\.1[6-9]\.' | grep -v '172\.2[0-9]\.' | grep -v '172\.3[0-1]\.' | head -1 | awk '{print $2}' | cut -d'/' -f1)
    if [[ -n "$detected_ip" && "$detected_ip" != "127.0.0.1" ]]; then
        echo "$detected_ip"
        return 0
    fi
    
    # Method 4: Try using default gateway interface (exclude Docker interfaces)
    local default_interface=$(ip route | grep '^default' | awk '{print $5}' | head -1)
    if [[ -n "$default_interface" && "$default_interface" != docker* && "$default_interface" != br-* ]]; then
        detected_ip=$(ip addr show "$default_interface" 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d'/' -f1)
        if [[ -n "$detected_ip" && "$detected_ip" != "127.0.0.1" ]]; then
            echo "$detected_ip"
            return 0
        fi
    fi
    
    # Final fallback to localhost
    echo "localhost"
}

# Find the correct .env file by looking for lakehouse installation
find_env_file() {
    local current_dir="$(pwd)"
    local env_file=""
    
    # Check current directory first
    if [[ -f ".env" ]] && [[ -f "docker-compose.yml" ]]; then
        echo ".env"
        return 0
    fi
    
    # Check if we're in a subdirectory of a lakehouse installation
    # Look for parent directories that contain both .env and docker-compose.yml
    local check_dir="$current_dir"
    while [[ "$check_dir" != "/" ]]; do
        if [[ -f "$check_dir/.env" ]] && [[ -f "$check_dir/docker-compose.yml" ]]; then
            echo "$check_dir/.env"
            return 0
        fi
        check_dir="$(dirname "$check_dir")"
    done
    
    # Check for lakehouse-lab subdirectory (common case: running from parent of installation)
    if [[ -f "lakehouse-lab/.env" ]] && [[ -f "lakehouse-lab/docker-compose.yml" ]]; then
        echo "lakehouse-lab/.env"
        return 0
    fi
    
    return 1
}

# Find and source the environment file
ENV_FILE=$(find_env_file)
if [[ -z "$ENV_FILE" ]]; then
    echo -e "${RED}❌ No .env file found!${NC}"
    echo -e "${YELLOW}💡 Make sure you're running from a Lakehouse Lab directory${NC}"
    echo -e "${YELLOW}   Or run './scripts/generate-credentials.sh' to create credentials${NC}"
    exit 1
fi

echo -e "${BLUE}📍 Using environment file: ${YELLOW}$ENV_FILE${NC}"

# Source environment variables
set -a  # Mark variables for export
source "$ENV_FILE"
set +a  # Stop marking variables for export

# Detect the host IP address for service URLs
HOST_IP=$(detect_host_ip)

# Display credentials
clear
echo -e "${BOLD}${BLUE}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════════╗
║                    LAKEHOUSE LAB CREDENTIALS                  ║
╚═══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

echo -e "${CYAN}🌐 WEB INTERFACES:${NC}"
echo -e "${GREEN}├── Airflow Orchestration:${NC}"
echo -e "│   ├── URL:      ${BLUE}http://${HOST_IP}:9020${NC}"
echo -e "│   ├── Username: ${YELLOW}${AIRFLOW_ADMIN_USER:-admin}${NC}"
echo -e "│   └── Password: ${YELLOW}${AIRFLOW_ADMIN_PASSWORD:-Not Set}${NC}"
echo -e "│"
echo -e "${GREEN}├── Superset BI Dashboard:${NC}"
echo -e "│   ├── URL:      ${BLUE}http://${HOST_IP}:9030${NC}"
echo -e "│   ├── Username: ${YELLOW}${SUPERSET_ADMIN_USER:-admin}${NC}"
echo -e "│   └── Password: ${YELLOW}${SUPERSET_ADMIN_PASSWORD:-Not Set}${NC}"
echo -e "│"
echo -e "${GREEN}├── JupyterLab Notebooks:${NC}"
echo -e "│   ├── URL:      ${BLUE}http://${HOST_IP}:9040${NC}"
echo -e "│   └── Token:    ${YELLOW}${JUPYTER_TOKEN:-Not Set}${NC}"
echo -e "│   └── Full URL: ${BLUE}http://${HOST_IP}:9040?token=${JUPYTER_TOKEN:-TOKEN}${NC}"
echo -e "│"
echo -e "${GREEN}├── MinIO Object Storage:${NC}"
echo -e "│   ├── Console:  ${BLUE}http://${HOST_IP}:9001${NC}"
echo -e "│   ├── Username: ${YELLOW}${MINIO_ROOT_USER:-minio}${NC}"
echo -e "│   └── Password: ${YELLOW}${MINIO_ROOT_PASSWORD:-Not Set}${NC}"
echo -e "│"
echo -e "${GREEN}├── Spark Master UI:${NC}"
echo -e "│   └── URL:      ${BLUE}http://${HOST_IP}:8080${NC}"
echo -e "│"
echo -e "${GREEN}├── Vizro Interactive Dashboards:${NC}"
echo -e "│   └── URL:      ${BLUE}http://${HOST_IP}:9050${NC}"
echo -e "│"
echo -e "${GREEN}├── LanceDB Vector Database:${NC}"
echo -e "│   ├── API:      ${BLUE}http://${HOST_IP}:9080${NC}"
echo -e "│   └── API Docs: ${BLUE}http://${HOST_IP}:9080/docs${NC}"
echo -e "│"
echo -e "${GREEN}├── Portainer (Docker Management):${NC}"
echo -e "│   └── URL:      ${BLUE}http://${HOST_IP}:9060${NC}"
echo -e "│"
echo -e "${GREEN}└── Homer Dashboard:${NC}"
echo -e "    └── URL:      ${BLUE}http://${HOST_IP}:9061${NC}"

echo
echo -e "${CYAN}💾 DATABASE ACCESS:${NC}"
echo -e "${GREEN}└── PostgreSQL:${NC}"
echo -e "    ├── Internal Host: ${BLUE}postgres:5432${NC} (Docker network only)"
echo -e "    ├── External Host: ${BLUE}${HOST_IP}:5432${NC} (if port mapping enabled)"
echo -e "    ├── Database: ${YELLOW}${POSTGRES_DB:-lakehouse}${NC}"
echo -e "    ├── Username: ${YELLOW}${POSTGRES_USER:-postgres}${NC}"
echo -e "    └── Password: ${YELLOW}${POSTGRES_PASSWORD:-Not Set}${NC}"

echo
echo -e "${CYAN}🔧 QUICK COMMANDS:${NC}"
echo -e "${GREEN}├── Start Services:${NC}       ${BLUE}./start-lakehouse.sh${NC}"
echo -e "${GREEN}├── View Logs:${NC}            ${BLUE}docker compose logs -f [service]${NC}"
echo -e "${GREEN}├── Stop Services:${NC}        ${BLUE}docker compose down${NC}"
echo -e "${GREEN}├── Regenerate Passwords:${NC} ${BLUE}./scripts/generate-credentials.sh${NC}"
echo -e "${GREEN}└── Service Status:${NC}       ${BLUE}docker compose ps${NC}"

echo
echo -e "${CYAN}📋 COPY-PASTE READY:${NC}"
echo -e "${GREEN}Airflow:${NC}   ${AIRFLOW_ADMIN_USER:-admin} / ${AIRFLOW_ADMIN_PASSWORD:-Not Set}"
echo -e "${GREEN}Superset:${NC}  ${SUPERSET_ADMIN_USER:-admin} / ${SUPERSET_ADMIN_PASSWORD:-Not Set}"
echo -e "${GREEN}Jupyter:${NC}   ${JUPYTER_TOKEN:-Not Set}"
echo -e "${GREEN}MinIO:${NC}     ${MINIO_ROOT_USER:-minio} / ${MINIO_ROOT_PASSWORD:-Not Set}"

echo
echo -e "${YELLOW}🔒 Security Notes:${NC}"
echo -e "   • Credentials are unique to this installation"
echo -e "   • Passphrases use memorable word combinations for easy typing"  
echo -e "   • Keep your .env file secure and do not share publicly"
echo -e "   • Use './scripts/rotate-credentials.sh' to generate new passwords"

echo
echo -e "${CYAN}🌐 Network Access:${NC}"
if [[ "$HOST_IP" == "localhost" ]]; then
    echo -e "   • ${YELLOW}Using localhost${NC} - services accessible on this machine only"
    echo -e "   • ${BLUE}Tip:${NC} Set HOST_IP environment variable for remote access"
else
    echo -e "   • ${GREEN}Using detected IP: ${HOST_IP}${NC} - services accessible remotely"
    echo -e "   • ${BLUE}Note:${NC} Ensure firewall allows connections to these ports"
fi

echo
echo -e "${GREEN}✨ All services accessible after running: ${BLUE}./start-lakehouse.sh${NC}"