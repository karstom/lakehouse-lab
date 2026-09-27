#!/bin/bash
# Entry point of the `smoke` container. Trusts the lab CA the way a user would (import into
# Chromium's NSS store; no --ignore-certificate-errors anywhere), then runs smoke.py, or,
# with first argument `kernel-loop`, the workspace-kernel loop (kernel-loop.sh).
set -euo pipefail
mkdir -p "$HOME/.pki/nssdb"
certutil -d "sql:$HOME/.pki/nssdb" -N --empty-password 2>/dev/null || true
certutil -d "sql:$HOME/.pki/nssdb" -D -n lakehouse-lab 2>/dev/null || true
certutil -d "sql:$HOME/.pki/nssdb" -A -t "C,," -n lakehouse-lab -i /trust/root.crt
# Python clients (requests: trino, pyiceberg) and Node (Playwright's APIRequestContext).
export REQUESTS_CA_BUNDLE=/trust/ca-bundle.crt
export SSL_CERT_FILE=/trust/ca-bundle.crt
export NODE_EXTRA_CA_CERTS=/trust/root.crt
if [ "${1:-}" = kernel-loop ]; then
  shift
  cd /opt/smoke
  exec python3 /opt/smoke/kernel_loop.py "$@"
fi
exec python3 /opt/smoke/smoke.py "$@"
