#!/bin/sh
# SeaweedFS start (runs as root in the stock image, which then drops to the seaweed user).
# Renders, from the environment (.secrets.env):
#   /etc/seaweedfs/s3-identities.json  the admin identity "lakekeeper" (S3 auth is on from the
#                                      first request: "identity before first start", S-1)
#   /etc/seaweedfs/iam.json            STS: signing key, role LakekeeperVended whose trust
#                                      policy names only the lakekeeper identity (ADR-006)
#   /etc/seaweedfs/security.toml       JWT keys (volume + filer), derived from the STS key
# then execs the image's entrypoint with an all-in-one `server`.
set -eu

: "${SEAWEEDFS_ADMIN_ACCESS_KEY:?}" "${SEAWEEDFS_ADMIN_SECRET_KEY:?}" "${SEAWEEDFS_STS_SIGNING_KEY:?}"
SRC=/opt/lab/seaweedfs
OUT=/etc/seaweedfs

# Values are substituted into JSON/TOML with sed: allow only characters that need no escaping.
check() { # name value charset-regex
  if ! printf '%s' "$2" | grep -Eq "^$3\$"; then
    echo "entrypoint: $1 has unexpected characters or is empty" >&2
    exit 1
  fi
}
check SEAWEEDFS_ADMIN_ACCESS_KEY "$SEAWEEDFS_ADMIN_ACCESS_KEY" '[A-Za-z0-9]{16,128}'
check SEAWEEDFS_ADMIN_SECRET_KEY "$SEAWEEDFS_ADMIN_SECRET_KEY" '[A-Za-z0-9+/=_-]{16,128}'
check SEAWEEDFS_STS_SIGNING_KEY "$SEAWEEDFS_STS_SIGNING_KEY" '[A-Za-z0-9+/=]{44,128}'
if [ "$(printf '%s' "$SEAWEEDFS_STS_SIGNING_KEY" | base64 -d 2>/dev/null | wc -c)" -lt 32 ]; then
  echo "entrypoint: SEAWEEDFS_STS_SIGNING_KEY must be base64 of at least 32 bytes" >&2
  exit 1
fi

derive() { printf '%s:%s' "$1" "$SEAWEEDFS_STS_SIGNING_KEY" | sha256sum | cut -d' ' -f1; }

mkdir -p "$OUT"
umask 077
sed -e "s|__ADMIN_ACCESS_KEY__|$SEAWEEDFS_ADMIN_ACCESS_KEY|" \
    -e "s|__ADMIN_SECRET_KEY__|$SEAWEEDFS_ADMIN_SECRET_KEY|" \
    "$SRC/identities.template.json" >"$OUT/s3-identities.json"
sed -e "s|__STS_SIGNING_KEY__|$SEAWEEDFS_STS_SIGNING_KEY|" \
    "$SRC/iam.template.json" >"$OUT/iam.json"
sed -e "s|__JWT_VOLUME_KEY__|$(derive jwt-volume)|" \
    -e "s|__JWT_VOLUME_READ_KEY__|$(derive jwt-volume-read)|" \
    -e "s|__JWT_FILER_KEY__|$(derive jwt-filer)|" \
    -e "s|__JWT_FILER_READ_KEY__|$(derive jwt-filer-read)|" \
    "$SRC/security.template.toml" >"$OUT/security.toml"
chown -R seaweed:seaweed "$OUT"

# The admin key only needs to reach weed through the rendered files.
unset SEAWEEDFS_ADMIN_ACCESS_KEY SEAWEEDFS_ADMIN_SECRET_KEY SEAWEEDFS_STS_SIGNING_KEY

exec /entrypoint.sh server \
  -volume.max=0 \
  -master.volumeSizeLimitMB=256 \
  -filer \
  -s3 -s3.port=8333 \
  -s3.config="$OUT/s3-identities.json" \
  -s3.iam.config="$OUT/iam.json"
