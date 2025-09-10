#!/usr/bin/env bash
# Lakehouse Lab Health Summary Dashboard
# Aggregates health status from all core services

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Service list: name:url/health
SERVICES=(
  "Superset:http://localhost:9030/health"
  "Airflow:http://localhost:9020/health"
  "MinIO:http://localhost:9001/minio/health/live"
  "JupyterLab:http://localhost:9040"
  "JupyterHub:http://localhost:9041/hub/health"
  "Portainer:http://localhost:9060"
  "Spark:http://localhost:8080"
  "LanceDB:http://localhost:9080/health"
  "Postgres:docker"
)

printf "\n${YELLOW}Lakehouse Lab Service Health Summary${NC}\n"
printf "%-12s | %-8s | %-30s\n" "Service" "Status" "Details"
printf "%s\n" "---------------------------------------------------------------"

for entry in "${SERVICES[@]}"; do
  IFS=":" read -r name url <<< "$entry"
  status=""
  details=""

  if [[ "$url" == "docker" ]]; then
    # Check Postgres container status
    if docker compose ps | grep -q "postgres.*Up"; then
      status="${GREEN}UP${NC}"
      details="Container running"
    else
      status="${RED}DOWN${NC}"
      details="Container not running"
    fi
  else
    # Try health endpoint or port
    if curl -sf --max-time 3 "$url" >/dev/null 2>&1; then
      status="${GREEN}HEALTHY${NC}"
      details="$url"
    else
      # Try just the base URL (for non-/health endpoints)
      baseurl=$(echo "$url" | sed 's|/health.*||')
      if curl -sf --max-time 3 "$baseurl" >/dev/null 2>&1; then
        status="${YELLOW}UP${NC}"
        details="No /health, but port open"
      else
        status="${RED}DOWN${NC}"
        details="No response on $url"
      fi
    fi
  fi

  printf "%-12s | %-8b | %-30s\n" "$name" "$status" "$details"
done

printf "%s\n" "---------------------------------------------------------------"
echo -e "${YELLOW}Tip:${NC} For more details, run: docker compose ps, or check service logs."