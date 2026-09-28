#!/bin/sh
# One-shot in the stub stack: proves .env and .secrets.env reach containers.
set -eu
for v in LAB_DOMAIN POSTGRES_PASSWORD LAB_ADMIN_PASSWORD SEAWEEDFS_STS_SIGNING_KEY; do
  eval "val=\${$v:-}"
  [ -n "$val" ] || { echo "missing $v" >&2; exit 1; }
done
echo "env ok for ${LAB_DOMAIN}"
