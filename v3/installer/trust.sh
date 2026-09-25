# shellcheck shell=bash
# How to trust the lab CA, per OS (spikes/s3-sso-bootstrap/RESULTS.md, OQ-3).

# print_trust_instructions CRT
print_trust_instructions() {
  local crt=$1 host fp
  fp=$(ca_fingerprint "$crt")
  host=$(hostname 2>/dev/null || echo this-host)
  cat <<EOF
Lab root CA:  $crt
  $(ca_subject "$crt")
  SHA-256 $fp

Browsers only accept the lab's HTTPS certificates after this CA is trusted, once per
machine that opens the lab. Import root.crt (not root.key; the key never leaves this host).

Copy it to the machine with the browser, if that is not this one:
    scp ${USER:-you}@${host}:${crt} ./lakehouse-root-ca.crt

Windows (Chrome, Edge; recent Firefox also reads the Windows store):
    double-click the .crt -> Install Certificate -> Current User ->
    "Place all certificates in the following store" -> Trusted Root Certification Authorities
  or in PowerShell:
    certutil -user -addstore -f ROOT lakehouse-root-ca.crt
EOF
  if is_wsl; then
    cat <<EOF
  From this WSL2 shell (your browser runs on Windows, so trust it there):
    certutil.exe -user -addstore -f ROOT "\$(wslpath -w '$crt')"
EOF
  fi
  cat <<EOF

macOS:
    sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain lakehouse-root-ca.crt

Linux, Chrome/Chromium (NSS store; needs libnss3-tools):
    certutil -d sql:\$HOME/.pki/nssdb -A -t "C,," -n lakehouse-lab -i lakehouse-root-ca.crt
Linux, Firefox (own store):
    Settings -> Privacy & Security -> Certificates -> View Certificates -> Authorities -> Import
Linux, command-line tools (curl, wget, most Python):
    Debian/Ubuntu: sudo cp lakehouse-root-ca.crt /usr/local/share/ca-certificates/lakehouse-lab.crt && sudo update-ca-certificates
    Fedora/RHEL:   sudo trust anchor lakehouse-root-ca.crt

Python clients (requests, PyIceberg, dbt) without a system import:
    export REQUESTS_CA_BUNDLE=/path/to/lakehouse-root-ca.crt SSL_CERT_FILE=/path/to/lakehouse-root-ca.crt
Java clients (trino CLI/JDBC):
    keytool -importcert -noprompt -alias lakehouse-lab -file lakehouse-root-ca.crt -keystore lab.jks -storepass <choose-a-keystore-password>
EOF
  if is_localhost_domain "${LAB_DOMAIN:-}"; then
    cat <<EOF

On *.localhost the lab also answers plain HTTP on port ${LAB_HTTP_PORT:-80} (browsers treat
localhost as a secure context), but HTTPS with the trusted CA is the supported path.
EOF
  fi
}
