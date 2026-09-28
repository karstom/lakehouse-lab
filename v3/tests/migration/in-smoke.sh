#!/bin/bash
# Entry point of the smoke container for the migration test's load step (run.sh load):
# trusts the lab CA like tests/smoke/in-container.sh does, then runs load_driver.py.
set -euo pipefail
mkdir -p "$HOME/.pki/nssdb"
certutil -d "sql:$HOME/.pki/nssdb" -N --empty-password 2>/dev/null || true
certutil -d "sql:$HOME/.pki/nssdb" -D -n lakehouse-lab 2>/dev/null || true
certutil -d "sql:$HOME/.pki/nssdb" -A -t "C,," -n lakehouse-lab -i /trust/root.crt
export REQUESTS_CA_BUNDLE=/trust/ca-bundle.crt
export SSL_CERT_FILE=/trust/ca-bundle.crt
exec python3 /opt/migration/load_driver.py "$@"
