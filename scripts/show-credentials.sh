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

# Check if .env exists
if [[ ! -f ".env" ]]; then
    echo -e "${RED}❌ No .env file found!${NC}"
    echo -e "${YELLOW}💡 Run './scripts/generate-credentials.sh' to create credentials${NC}"
    exit 1
fi

# Source environment variables
set -a  # Mark variables for export
source .env
set +a  # Stop marking variables for export

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
echo -e "│   ├── URL:      ${BLUE}http://localhost:9020${NC}"
echo -e "│   ├── Username: ${YELLOW}${AIRFLOW_ADMIN_USER:-admin}${NC}"
echo -e "│   └── Password: ${YELLOW}${AIRFLOW_ADMIN_PASSWORD:-Not Set}${NC}"
echo -e "│"
echo -e "${GREEN}├── Superset BI Dashboard:${NC}"
echo -e "│   ├── URL:      ${BLUE}http://localhost:9030${NC}"
echo -e "│   ├── Username: ${YELLOW}${SUPERSET_ADMIN_USER:-admin}${NC}"
echo -e "│   └── Password: ${YELLOW}${SUPERSET_ADMIN_PASSWORD:-Not Set}${NC}"
echo -e "│"
echo -e "${GREEN}├── JupyterLab Notebooks:${NC}"
echo -e "│   ├── URL:      ${BLUE}http://localhost:9040${NC}"
echo -e "│   └── Token:    ${YELLOW}${JUPYTER_TOKEN:-Not Set}${NC}"
echo -e "│   └── Full URL: ${BLUE}http://localhost:9040?token=${JUPYTER_TOKEN:-TOKEN}${NC}"
echo -e "│"
echo -e "${GREEN}├── MinIO Object Storage:${NC}"
echo -e "│   ├── Console:  ${BLUE}http://localhost:9001${NC}"
echo -e "│   ├── Username: ${YELLOW}${MINIO_ROOT_USER:-minio}${NC}"
echo -e "│   └── Password: ${YELLOW}${MINIO_ROOT_PASSWORD:-Not Set}${NC}"
echo -e "│"
echo -e "${GREEN}├── Spark Master UI:${NC}"
echo -e "│   └── URL:      ${BLUE}http://localhost:8080${NC}"
echo -e "│"
echo -e "${GREEN}├── Portainer (Docker Management):${NC}"
echo -e "│   └── URL:      ${BLUE}http://localhost:9060${NC}"
echo -e "│"
echo -e "${GREEN}└── Homer Dashboard:${NC}"
echo -e "    └── URL:      ${BLUE}http://localhost:9061${NC}"

echo
echo -e "${CYAN}💾 DATABASE ACCESS:${NC}"
echo -e "${GREEN}└── PostgreSQL:${NC}"
echo -e "    ├── Host:     ${BLUE}localhost:5432${NC}"
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
echo -e "${GREEN}✨ All services accessible after running: ${BLUE}./start-lakehouse.sh${NC}"