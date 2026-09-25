#!/bin/bash
# One-shot bootstrap: DB schema + Keycloak authorization model for the Airflow client.
set -euo pipefail
airflow db migrate
python /opt/lakehouse/ensure_keycloak_authz.py
