#!/bin/bash
# Superset container entrypoint (baked into the image). Every step is idempotent and runs
# before the web server starts, in order, so nothing races the app or the database
# (REG_SUPERSET_SETUP):
#   1. schema migrations (the database itself is created by the superset-db one-shot);
#   2. built-in roles and permissions;
#   3. lab_init.py: the lab_data role and the bundled "Revenue by region" dashboard.
# There is no local admin user: Keycloak owns users.
set -euo pipefail
superset db upgrade
superset init
python /app/lakehouse/lab_init.py
exec /usr/bin/run-server.sh
