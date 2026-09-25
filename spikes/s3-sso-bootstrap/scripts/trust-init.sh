#!/bin/sh
# Waits for Caddy's internal root CA, then publishes it (and a system+Caddy bundle) to the
# shared "trust" volume so every service can verify https://auth.<LAB_DOMAIN>:<LAB_PORT>.
set -eu
ROOT=/caddy-data/caddy/pki/authorities/local/root.crt
i=0
until [ -s "$ROOT" ]; do
  i=$((i + 1)); [ "$i" -gt 120 ] && { echo "no Caddy root CA after 120s" >&2; exit 1; }
  sleep 1
done
cp "$ROOT" /trust/caddy-root.crt
cat /etc/ssl/certs/ca-certificates.crt "$ROOT" > /trust/ca-bundle.crt
chmod 0644 /trust/caddy-root.crt /trust/ca-bundle.crt
echo "trust bundle written"
