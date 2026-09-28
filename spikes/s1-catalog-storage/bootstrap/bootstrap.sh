#!/bin/sh
# S-1 one-shot bootstrap (idempotent):
#   1. SeaweedFS: create the admin S3 identity (keys from secrets/s3-admin.env) and the bucket
#   2. Lakekeeper: bootstrap the server (allow-all authz) and create the warehouse with a
#      SeaweedFS storage profile that has REMOTE SIGNING enabled.
# Runs in the SeaweedFS image (has weed + curl). Env: S3_ADMIN_ACCESS_KEY, S3_ADMIN_SECRET_KEY,
# BUCKET, WAREHOUSE, S3_REGION.
set -eu

MASTER=seaweedfs:9333
FILER=seaweedfs:8888
S3=http://seaweedfs:8333
LK=http://lakekeeper:8181

log() { echo "[bootstrap] $*"; }

# --- 1. SeaweedFS identity + bucket -------------------------------------------------------
log "configuring SeaweedFS S3 identity 'lakekeeper'"
printf 's3.configure -user=lakekeeper -access_key=%s -secret_key=%s -actions=Read,Write,List,Tagging,Admin -apply\n' \
  "$S3_ADMIN_ACCESS_KEY" "$S3_ADMIN_SECRET_KEY" \
  | weed shell -master="$MASTER" -filer="$FILER" >/tmp/s3conf.out 2>&1 || { cat /tmp/s3conf.out; exit 1; }

if printf 's3.bucket.list\n' | weed shell -master="$MASTER" -filer="$FILER" 2>/dev/null | grep -qw "$BUCKET"; then
  log "bucket '$BUCKET' exists"
else
  log "creating bucket '$BUCKET'"
  printf 's3.bucket.create -name=%s\n' "$BUCKET" | weed shell -master="$MASTER" -filer="$FILER"
fi

# Anonymous access must now be refused (identities exist -> auth enforced).
code=$(curl -s -o /dev/null -w '%{http_code}' "$S3/$BUCKET/")
log "anonymous GET $S3/$BUCKET/ -> HTTP $code (expect 403)"

# --- 2. Lakekeeper --------------------------------------------------------------------------
info=$(curl -fsS "$LK/management/v1/info")
if echo "$info" | grep -q '"bootstrapped":true'; then
  log "lakekeeper already bootstrapped"
else
  log "bootstrapping lakekeeper"
  curl -fsS -X POST "$LK/management/v1/bootstrap" -H 'Content-Type: application/json' \
    -d '{"accept-terms-of-use": true, "is-operator": true}'
fi

# Storage profile for SeaweedFS. Remote signing is the default path (Spark); STS vending is also
# enabled because Trino 483 cannot remote-sign (it only understands vended credentials).
PROFILE=$(cat <<JSON
{
    "type": "s3",
    "flavor": "s3-compat",
    "bucket": "$BUCKET",
    "key-prefix": "$WAREHOUSE",
    "endpoint": "$S3",
    "region": "$S3_REGION",
    "path-style-access": true,
    "remote-signing-enabled": true,
    "remote-signing-url-style": "path",
    "sts-enabled": true,
    "sts-role-arn": "$STS_ROLE_ARN",
    "sts-token-validity-seconds": 3600
}
JSON
)
CRED=$(cat <<JSON
{"type": "s3", "credential-type": "access-key",
 "access-key-id": "$S3_ADMIN_ACCESS_KEY", "secret-access-key": "$S3_ADMIN_SECRET_KEY"}
JSON
)

wh_id=$(curl -fsS "$LK/management/v1/warehouse" | tr '{' '\n' | grep "\"name\":\"$WAREHOUSE\"" | sed -n 's/.*"warehouse-id":"\([^"]*\)".*/\1/p' | head -1)
if [ -n "$wh_id" ]; then
  log "warehouse '$WAREHOUSE' exists ($wh_id); re-applying storage profile"
  printf '{"storage-profile": %s, "storage-credential": %s}' "$PROFILE" "$CRED" >/tmp/req.json
  url="$LK/management/v1/warehouse/$wh_id/storage"
else
  log "creating warehouse '$WAREHOUSE'"
  printf '{"warehouse-name": "%s", "storage-profile": %s, "storage-credential": %s, "delete-profile": {"type": "hard"}}' \
    "$WAREHOUSE" "$PROFILE" "$CRED" >/tmp/req.json
  url="$LK/management/v1/warehouse"
fi
code=$(curl -sS -o /tmp/resp.json -w '%{http_code}' -X POST "$url" -H 'Content-Type: application/json' -d @/tmp/req.json)
rm -f /tmp/req.json
log "POST $url -> HTTP $code"
cat /tmp/resp.json; echo
case "$code" in 2*) ;; *) exit 1 ;; esac
log "done"
