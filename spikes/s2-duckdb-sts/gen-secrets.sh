#!/bin/sh
# Generate spike-local secrets once (idempotent). Never committed (see .gitignore).
set -eu
cd "$(dirname "$0")"
mkdir -p secrets; chmod 700 secrets
rnd() { head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c "$1"; }
if [ ! -f secrets/pg.env ]; then
  pw=$(rnd 32)
  printf 'POSTGRES_PASSWORD=%s\nLAKEKEEPER__PG_PASSWORD=%s\nLAKEKEEPER__PG_ENCRYPTION_KEY=%s\n' "$pw" "$pw" "$(rnd 40)" > secrets/pg.env
fi
if [ ! -f secrets/s3-admin.env ]; then
  printf 'S3_ADMIN_ACCESS_KEY=%s\nS3_ADMIN_SECRET_KEY=%s\n' "AK$(rnd 18)" "$(rnd 40)" > secrets/s3-admin.env
fi
chmod 600 secrets/*.env
# SeaweedFS advanced IAM config: STS (for vended credentials to Trino) - contains the STS signing key.
if [ ! -f secrets/seaweedfs-iam.json ]; then
  key=$(head -c 32 /dev/urandom | base64)
  sed "s|__STS_SIGNING_KEY__|$key|" seaweedfs/iam.template.json > secrets/seaweedfs-iam.json
fi
chmod 644 secrets/seaweedfs-iam.json   # read by the non-root seaweed user inside the container
