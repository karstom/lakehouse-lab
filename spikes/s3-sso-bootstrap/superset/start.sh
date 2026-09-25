#!/bin/bash
# Idempotent: migrate, create roles/permissions, then serve. No local admin user (Keycloak owns users).
set -euo pipefail
superset db upgrade
superset init
exec /usr/bin/run-server.sh
