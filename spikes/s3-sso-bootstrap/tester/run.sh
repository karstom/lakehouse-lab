#!/bin/bash
# Trust Caddy's root CA the way a beginner would (import into the browser's NSS store),
# then run the SSO test. No --ignore-certificate-errors anywhere.
set -euo pipefail
mkdir -p "$HOME/.pki/nssdb"
certutil -d "sql:$HOME/.pki/nssdb" -N --empty-password 2>/dev/null || true
certutil -d "sql:$HOME/.pki/nssdb" -D -n lakehouse-caddy 2>/dev/null || true
certutil -d "sql:$HOME/.pki/nssdb" -A -t "C,," -n lakehouse-caddy -i /trust/caddy-root.crt
export SSL_CERT_FILE=/trust/ca-bundle.crt
# Playwright's APIRequestContext runs in Node, which does not read NSS: trust the root there too.
export NODE_EXTRA_CA_CERTS=/trust/caddy-root.crt
exec python3 /opt/tester/sso_test.py "$@"
