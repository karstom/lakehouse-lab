#!/usr/bin/env bash
# docker compose wrapper: fixed project name + all env files (versions, local pins, lab, secrets).
set -euo pipefail
cd "$(dirname "$0")"
[ -f .secrets.env ] || ./gen-secrets.sh
exec docker compose -p v3-s3 \
  --env-file ../versions.env --env-file versions.local.env \
  --env-file lab.env --env-file .secrets.env "$@"
