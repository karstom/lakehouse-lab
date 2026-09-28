# shellcheck shell=bash
# LAB_DOMAIN selection (ADR-005). The installer decides the domain ONCE and writes it to
# .env; nothing else in V3 detects the host. detect_host_ip below is the only copy of
# host-IP detection (retires V2's four copies, REG_HOST_IP_DETECTION).

# detect_host_ip -> the host's primary IPv4 address (the one with the default route).
detect_host_ip() {
  local ip=""
  if command -v ip >/dev/null 2>&1; then
    ip=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i < NF; i++) if ($i == "src") {print $(i + 1); exit}}')
  fi
  if [ -z "$ip" ] && command -v hostname >/dev/null 2>&1; then
    ip=$(hostname -I 2>/dev/null | awk '{print $1}')
  fi
  valid_ipv4 "$ip" || return 1
  printf '%s\n' "$ip"
}

valid_ipv4() {
  local ip=$1 o
  [[ "$ip" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || return 1
  IFS=. read -r -a _oct <<<"$ip"
  for o in "${_oct[@]}"; do
    [ "$((10#$o))" -le 255 ] || return 1
  done
}

# sslip_domain IP -> <dashed-ip>.sslip.io
sslip_domain() {
  valid_ipv4 "$1" || return 1
  printf '%s.sslip.io\n' "${1//./-}"
}

# valid_domain NAME -> RFC 1123 hostname, lowercase, leaves room for "<svc>." prefixes.
valid_domain() {
  local d=$1 label
  [ -n "$d" ] && [ "${#d}" -le 240 ] || return 1
  [[ "$d" =~ ^[a-z0-9.-]+$ ]] || return 1
  case "$d" in .*|*.|*..*) return 1;; esac
  IFS=. read -r -a _labels <<<"$d"
  for label in "${_labels[@]}"; do
    [ "${#label}" -le 63 ] || return 1
    [[ "$label" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ ]] || return 1
  done
}

is_localhost_domain() {
  case "$1" in localhost|*.localhost) return 0;; esac
  return 1
}

# resolve_domain_arg VALUE -> the literal domain for --domain VALUE.
# "sslip" is a shortcut for <this host's dashed IP>.sslip.io.
resolve_domain_arg() {
  local v ip
  v=$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')
  if [ "$v" = sslip ]; then
    ip=$(detect_host_ip) || { err "could not detect this host's IP for --domain sslip; pass --domain <a-b-c-d>.sslip.io"; return 1; }
    sslip_domain "$ip"
    return 0
  fi
  valid_domain "$v" || { err "invalid domain '$1' (lowercase hostname like lab.localhost, 10-0-0-5.sslip.io or lab.example.com)"; return 1; }
  printf '%s\n' "$v"
}

# prompt_domain -> interactive choice; prints the chosen domain on stdout.
prompt_domain() {
  local ip="" sslip="" def=1 choice d
  ip=$(detect_host_ip 2>/dev/null) && sslip=$(sslip_domain "$ip")
  # Over SSH the browser is almost certainly on another machine.
  [ -n "${SSH_CONNECTION:-}" ] && [ -n "$sslip" ] && def=2
  {
    echo
    echo "Where will you open the lab in a browser?"
    echo "  1) On this machine only            -> ${LAB_DEFAULT_DOMAIN}"
    if [ -n "$sslip" ]; then
      echo "  2) From other machines on the LAN  -> ${sslip}  (no DNS setup; uses sslip.io)"
    else
      echo "  2) From other machines on the LAN  -> (could not detect this host's IP)"
    fi
    echo "  3) My own domain with wildcard DNS (*.example.com -> this host)"
    echo "The domain is chosen once; changing it later needs './install.sh --reconfigure'."
  } >&2
  while :; do
    read -r -p "Choice [$def]: " choice || return 1
    choice=${choice:-$def}
    case "$choice" in
      1) printf '%s\n' "$LAB_DEFAULT_DOMAIN"; return 0 ;;
      2) [ -n "$sslip" ] && { printf '%s\n' "$sslip"; return 0; }
         echo "No IP detected; use option 3 and type <a-b-c-d>.sslip.io." >&2 ;;
      3) read -r -p "Domain (services become <svc>.<domain>): " d || return 1
         d=$(resolve_domain_arg "$d") && { printf '%s\n' "$d"; return 0; } ;;
      *) echo "Please answer 1, 2 or 3." >&2 ;;
    esac
  done
}
