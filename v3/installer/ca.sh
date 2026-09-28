# shellcheck shell=bash
# Lab root CA (CONTRACT.md "CA root"; DEC_V3_KEYCLOAK_SSO_SUBDOMAINS).
# Created ONCE in ${LAB_STATE_DIR}/ca/{root.crt,root.key}, valid 10 years. Caddy mounts the
# directory read-only as its PKI root and issues its own short-lived intermediates.
# Nothing here ever regenerates an existing root: a new root means every browser that
# trusted the lab has to re-import it.

LAB_CA_DAYS=3650

# ca_create DIR -> create root.crt/root.key if neither exists; verify them if both exist.
ca_create() {
  local dir=$1 crt key cn tmpd
  crt="$dir/root.crt"; key="$dir/root.key"
  if [ -e "$crt" ] || [ -e "$key" ]; then
    ca_verify "$dir" || return 1
    ok "Kept existing lab CA: $crt ($(ca_subject "$crt"))"
    return 0
  fi
  mkdir -p "$dir"
  chmod 700 "$dir" 2>/dev/null || true
  # Unique name per install, so two labs are distinguishable in a browser's trust store.
  cn="Lakehouse Lab Local CA $(date -u +%Y-%m-%d) $(rand_hex 3)"
  # Build in a temp dir inside $dir and move into place, so an interrupted run
  # never leaves a half-written root behind.
  tmpd=$(mktemp -d "$dir/.new.XXXXXX")
  if ! (
    umask 077
    openssl ecparam -name prime256v1 -genkey -noout -out "$tmpd/ec.key" 2>/dev/null &&
    openssl pkcs8 -topk8 -nocrypt -in "$tmpd/ec.key" -out "$tmpd/root.key" 2>/dev/null &&
    openssl req -x509 -new -sha256 -key "$tmpd/root.key" -days "$LAB_CA_DAYS" \
      -subj "/O=Lakehouse Lab/CN=${cn}" \
      -addext "basicConstraints=critical,CA:TRUE" \
      -addext "keyUsage=critical,keyCertSign,cRLSign" \
      -addext "subjectKeyIdentifier=hash" \
      -out "$tmpd/root.crt" 2>/dev/null
  ); then
    rm -rf "$tmpd"
    err "openssl failed to create the lab CA (needs OpenSSL >= 1.1.1 for -addext)"
    return 1
  fi
  chmod 600 "$tmpd/root.key"
  chmod 644 "$tmpd/root.crt"
  mv "$tmpd/root.key" "$key"
  mv "$tmpd/root.crt" "$crt"
  rm -rf "$tmpd"
  ok "Created lab CA: $crt ($cn, valid ${LAB_CA_DAYS} days)"
}

# ca_verify DIR -> both files present, cert is a CA, key matches cert.
ca_verify() {
  local dir=$1 crt key a b
  crt="$dir/root.crt"; key="$dir/root.key"
  if [ ! -s "$crt" ] || [ ! -s "$key" ]; then
    err "incomplete lab CA in $dir (need both root.crt and root.key)."
    err "Refusing to regenerate it: restore the missing file, or remove the directory to start a new CA (every browser must then re-trust it)."
    return 1
  fi
  if ! openssl x509 -in "$crt" -noout -text 2>/dev/null | grep -q 'CA:TRUE'; then
    err "$crt is not a CA certificate."
    return 1
  fi
  a=$(openssl x509 -in "$crt" -noout -pubkey 2>/dev/null | openssl sha256 2>/dev/null)
  b=$(openssl pkey -in "$key" -pubout 2>/dev/null | openssl sha256 2>/dev/null)
  if [ -z "$a" ] || [ "$a" != "$b" ]; then
    err "$key does not match $crt."
    return 1
  fi
  if ! openssl x509 -in "$crt" -noout -checkend 2592000 >/dev/null 2>&1; then
    warn "the lab CA $crt expires within 30 days."
  fi
}

ca_subject() {
  openssl x509 -in "$1" -noout -subject -nameopt multiline 2>/dev/null |
    awk -F' = ' '/commonName/ {print $2}'
}

ca_fingerprint() {
  openssl x509 -in "$1" -noout -fingerprint -sha256 2>/dev/null | cut -d= -f2
}
