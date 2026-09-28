#!/bin/sh
# One-shot: publish the lab root CA to the shared `trust` volume.
#   /trust/root.crt       the lab root (PEM) - for clients that take a single CA file (Trino)
#   /trust/ca-bundle.crt  system CAs + lab root - for SSL_CERT_FILE / REQUESTS_CA_BUNDLE
# Idempotent: rewrites both files from the mounted root every run.
set -eu
SRC=/lab-ca/root.crt
SYS=/etc/ssl/certs/ca-certificates.crt
[ -s "$SRC" ] || { echo "trust-init: no lab root CA at $SRC (run install.sh)" >&2; exit 1; }
grep -q 'BEGIN CERTIFICATE' "$SRC" || { echo "trust-init: $SRC is not a PEM certificate" >&2; exit 1; }
[ -s "$SYS" ] || { echo "trust-init: no system CA bundle at $SYS" >&2; exit 1; }
cp "$SRC" /trust/root.crt.tmp
cat "$SYS" "$SRC" >/trust/ca-bundle.crt.tmp
chmod 0644 /trust/root.crt.tmp /trust/ca-bundle.crt.tmp
mv /trust/root.crt.tmp /trust/root.crt
mv /trust/ca-bundle.crt.tmp /trust/ca-bundle.crt
echo "trust-init: wrote /trust/root.crt and /trust/ca-bundle.crt"
