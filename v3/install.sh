#!/usr/bin/env bash
# Lakehouse Lab V3 installer.
#
# Checks prerequisites, chooses LAB_DOMAIN once, writes v3/.env and v3/.secrets.env,
# creates the lab root CA once, and starts the stack with the contract's compose command.
# Safe to re-run: existing settings, secrets and the CA are kept.
#
# Usage: ./install.sh [options]      (./install.sh --help)
set -euo pipefail

V3_DIR=$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=installer/lib.sh
. "$V3_DIR/installer/lib.sh"
# shellcheck source=installer/checks.sh
. "$V3_DIR/installer/checks.sh"
# shellcheck source=installer/domain.sh
. "$V3_DIR/installer/domain.sh"
# shellcheck source=installer/secrets.sh
. "$V3_DIR/installer/secrets.sh"
# shellcheck source=installer/ca.sh
. "$V3_DIR/installer/ca.sh"
# shellcheck source=installer/trust.sh
. "$V3_DIR/installer/trust.sh"

usage() {
  cat <<EOF
Usage: ./install.sh [options]

  --non-interactive       never prompt; use flags, then existing .env, then defaults
  --domain DOMAIN         base domain; services become <svc>.DOMAIN
                          (default ${LAB_DEFAULT_DOMAIN}; 'sslip' = <this-host-dashed-ip>.sslip.io)
  --https-port PORT       host HTTPS port (default ${LAB_DEFAULT_HTTPS_PORT})
  --http-port PORT        host HTTP port (default ${LAB_DEFAULT_HTTP_PORT})
  --project-name NAME     compose project name (default ${LAB_DEFAULT_PROJECT})
  --profile NAME          profile to run (available: ${LAB_AVAILABLE_PROFILES})
  --seed-test-users       create the test users alice/eddie/anna/victor (dev and CI)
  --no-seed-test-users    turn test users off again
  --admin-user NAME       first lab admin's username (only used when secrets are first generated)
  --reconfigure           allow changing the domain or project name of an existing install
  --no-start              write configuration only; do not start the stack
  -h, --help              this help

Re-running keeps .env settings (unless a flag overrides them), all secrets, and the CA.
EOF
}

NON_INTERACTIVE=0
RECONFIGURE=0
NO_START=0
OPT_DOMAIN="" OPT_HTTPS="" OPT_HTTP="" OPT_PROJECT="" OPT_PROFILE="" OPT_SEED=""
need_arg() { [ $# -ge 2 ] && [ -n "$2" ] || die "$1 needs a value"; }
while [ $# -gt 0 ]; do
  case "$1" in
    --non-interactive) NON_INTERACTIVE=1 ;;
    --domain) need_arg "$@"; OPT_DOMAIN=$2; shift ;;
    --domain=*) OPT_DOMAIN=${1#*=} ;;
    --https-port) need_arg "$@"; OPT_HTTPS=$2; shift ;;
    --https-port=*) OPT_HTTPS=${1#*=} ;;
    --http-port) need_arg "$@"; OPT_HTTP=$2; shift ;;
    --http-port=*) OPT_HTTP=${1#*=} ;;
    --project-name) need_arg "$@"; OPT_PROJECT=$2; shift ;;
    --project-name=*) OPT_PROJECT=${1#*=} ;;
    --profile) need_arg "$@"; OPT_PROFILE=$2; shift ;;
    --profile=*) OPT_PROFILE=${1#*=} ;;
    --seed-test-users) OPT_SEED=true ;;
    --no-seed-test-users) OPT_SEED=false ;;
    --admin-user) need_arg "$@"; LAB_ADMIN_USER_OVERRIDE=$2; shift ;;
    --admin-user=*) LAB_ADMIN_USER_OVERRIDE=${1#*=} ;;
    --reconfigure) RECONFIGURE=1 ;;
    --no-start) NO_START=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; die "unknown option: $1" ;;
  esac
  shift
done
[ -t 0 ] || NON_INTERACTIVE=1
export LAB_ADMIN_USER_OVERRIDE="${LAB_ADMIN_USER_OVERRIDE:-}"
if [ -n "$LAB_ADMIN_USER_OVERRIDE" ] && ! [[ "$LAB_ADMIN_USER_OVERRIDE" =~ ^[a-z][a-z0-9._-]{1,30}$ ]]; then
  die "--admin-user: use 2-31 lowercase letters, digits, '.', '_' or '-', starting with a letter"
fi

# detect_tz -> host timezone name (IANA), UTC if unknown.
detect_tz() {
  local tz=""
  if [ -n "${TZ:-}" ]; then tz=${TZ#:}
  elif command -v timedatectl >/dev/null 2>&1; then tz=$(timedatectl show -p Timezone --value 2>/dev/null || true)
  fi
  if [ -z "$tz" ] && [ -r /etc/timezone ]; then tz=$(head -n1 /etc/timezone)
  fi
  if [ -z "$tz" ] && [ -L /etc/localtime ]; then tz=$(readlink /etc/localtime | sed 's#.*/zoneinfo/##')
  fi
  [[ "$tz" =~ ^[A-Za-z0-9_+/-]+$ ]] || tz=UTC
  printf '%s\n' "$tz"
}

# pick FLAG EXISTING DEFAULT -> first non-empty
pick() {
  if [ -n "$1" ]; then printf '%s\n' "$1"
  elif [ -n "$2" ]; then printf '%s\n' "$2"
  else printf '%s\n' "$3"
  fi
}

info "Lakehouse Lab V3 installer ($V3_DIR)"

hdr "Checking prerequisites"
run_prereq_checks || die "prerequisites not met (see above)."

hdr "Configuration"
[ -f "$LAB_VERSIONS_FILE" ] || die "missing $LAB_VERSIONS_FILE"
existing_env=0
[ -f "$LAB_ENV_FILE" ] && existing_env=1
cur_project=$(env_get "$LAB_ENV_FILE" COMPOSE_PROJECT_NAME)
cur_domain=$(env_get "$LAB_ENV_FILE" LAB_DOMAIN)
cur_https=$(env_get "$LAB_ENV_FILE" LAB_HTTPS_PORT)
cur_http=$(env_get "$LAB_ENV_FILE" LAB_HTTP_PORT)
cur_profile=$(env_get "$LAB_ENV_FILE" LAB_PROFILE)
cur_state=$(env_get "$LAB_ENV_FILE" LAB_STATE_DIR)
cur_tz=$(env_get "$LAB_ENV_FILE" LAB_TZ)
cur_seed=$(env_get "$LAB_ENV_FILE" LAB_SEED_TEST_USERS)

# Project name
project=$(pick "$OPT_PROJECT" "$cur_project" "$LAB_DEFAULT_PROJECT")
valid_project_name "$project" || die "invalid project name '$project' (lowercase letters, digits, '-' and '_')"
if [ -n "$cur_project" ] && [ "$project" != "$cur_project" ] && [ "$RECONFIGURE" != 1 ]; then
  die "this install uses project '$cur_project'. Changing it orphans its volumes; pass --reconfigure if you really mean to."
fi

# Domain: chosen once.
if [ -n "$OPT_DOMAIN" ]; then
  domain=$(resolve_domain_arg "$OPT_DOMAIN") || exit 1
elif [ -n "$cur_domain" ]; then
  domain=$cur_domain
elif [ "$NON_INTERACTIVE" = 1 ]; then
  domain=$LAB_DEFAULT_DOMAIN
else
  domain=$(prompt_domain) || die "no domain chosen"
fi
valid_domain "$domain" || die "invalid LAB_DOMAIN '$domain' in $LAB_ENV_FILE"
if [ -n "$cur_domain" ] && [ "$domain" != "$cur_domain" ]; then
  [ "$RECONFIGURE" = 1 ] || die "this install uses LAB_DOMAIN=$cur_domain. The domain is chosen once (OIDC issuer, redirect URIs and certificates depend on it); pass --reconfigure to change it."
  warn "changing LAB_DOMAIN $cur_domain -> $domain. Browser bookmarks and trusted sessions for the old domain stop working."
fi
if [ -n "${SSH_CONNECTION:-}" ] && is_localhost_domain "$domain"; then
  warn "you are on SSH but LAB_DOMAIN=$domain only works in a browser on this machine. For other machines use --domain sslip (or your own domain) with --reconfigure."
fi

# Ports
https_port=$(pick "$OPT_HTTPS" "$cur_https" "$LAB_DEFAULT_HTTPS_PORT")
http_port=$(pick "$OPT_HTTP" "$cur_http" "$LAB_DEFAULT_HTTP_PORT")
valid_port "$https_port" || die "invalid --https-port '$https_port'"
valid_port "$http_port" || die "invalid --http-port '$http_port'"
[ "$https_port" != "$http_port" ] || die "HTTPS and HTTP ports must differ"

# Profile
if [ -n "$OPT_PROFILE" ]; then
  profile=$OPT_PROFILE
elif [ -n "$cur_profile" ]; then
  profile=$cur_profile
else
  profile=$LAB_DEFAULT_PROFILE
  if [ "$NON_INTERACTIVE" != 1 ] && [ "$(wc -w <<<"$LAB_AVAILABLE_PROFILES")" -gt 1 ]; then
    read -r -p "Profile ($LAB_AVAILABLE_PROFILES) [$LAB_DEFAULT_PROFILE]: " profile || true
    profile=${profile:-$LAB_DEFAULT_PROFILE}
  fi
fi
case " $LAB_KNOWN_PROFILES " in *" $profile "*) ;; *) die "unknown profile '$profile' (known: $LAB_KNOWN_PROFILES)";; esac
profile_available "$profile" || die "profile '$profile' is not available yet (available: $LAB_AVAILABLE_PROFILES)"

state_dir=$(pick "" "$cur_state" "$LAB_DEFAULT_STATE_DIR")
tz=$(pick "" "$cur_tz" "$(detect_tz)")
seed=$(pick "$OPT_SEED" "$cur_seed" false)

if [ "$existing_env" = 0 ]; then
  cat >"$LAB_ENV_FILE" <<'EOF'
# Lakehouse Lab settings (non-secret). Written by install.sh; you may edit it.
# Secrets live in .secrets.env. Neither file is committed.
# LAB_DOMAIN and COMPOSE_PROJECT_NAME are chosen once: change them with
# './install.sh --reconfigure', not here.
EOF
  chmod 644 "$LAB_ENV_FILE"
fi
env_set "$LAB_ENV_FILE" COMPOSE_PROJECT_NAME "$project"
env_set "$LAB_ENV_FILE" LAB_DOMAIN "$domain"
env_set "$LAB_ENV_FILE" LAB_HTTPS_PORT "$https_port"
env_set "$LAB_ENV_FILE" LAB_HTTP_PORT "$http_port"
env_set "$LAB_ENV_FILE" LAB_PROFILE "$profile"
env_set "$LAB_ENV_FILE" LAB_STATE_DIR "$state_dir"
env_set "$LAB_ENV_FILE" LAB_TZ "$tz"
env_set "$LAB_ENV_FILE" LAB_SEED_TEST_USERS "$seed"
if [ "$existing_env" = 1 ]; then ok "Updated $LAB_ENV_FILE (kept your other settings)"; else ok "Wrote $LAB_ENV_FILE"; fi
lab_settings
info "  project=$COMPOSE_PROJECT_NAME domain=$LAB_DOMAIN https=$LAB_HTTPS_PORT http=$LAB_HTTP_PORT profile=$LAB_PROFILE test-users=$seed"

hdr "Secrets"
ensure_secrets "$LAB_SECRETS_FILE"

hdr "Lab certificate authority"
mkdir -p "$(state_dir_abs)"
ca_create "$(ca_dir)" || die "lab CA problem (see above)."

hdr "Ports"
check_privileged_port "$LAB_HTTPS_PORT"
check_privileged_port "$LAB_HTTP_PORT"
check_port "$LAB_HTTPS_PORT"
check_port "$LAB_HTTP_PORT"
ok "HTTPS ${LAB_HTTPS_PORT}, HTTP ${LAB_HTTP_PORT}"

if [ "$NO_START" = 1 ]; then
  info ""
  info "Configuration written. Start the lab with: $V3_DIR/lab up"
  exit 0
fi
if [ ! -f "$LAB_COMPOSE_FILE" ]; then
  warn "$LAB_COMPOSE_FILE not found; configuration is written but nothing was started."
  exit 0
fi

hdr "Starting the lab (profile $LAB_PROFILE); first start builds/pulls images and can take several minutes"
t0=$(date +%s)
if ! lab_compose up -d --wait --remove-orphans; then
  err "the stack did not become healthy."
  info "  See what failed:  $V3_DIR/lab status"
  info "  Service logs:     $V3_DIR/lab logs <service>"
  info "  Re-run this installer after fixing it; it keeps your settings, secrets and CA."
  exit 1
fi
ok "Stack healthy in $(( $(date +%s) - t0 ))s"

hdr "Your lab"
print_urls
info ""
admin_user=$(env_get "$LAB_SECRETS_FILE" LAB_ADMIN_USER)
if [ "$NON_INTERACTIVE" = 1 ]; then
  info "Admin login: $admin_user  (password: LAB_ADMIN_PASSWORD in $LAB_SECRETS_FILE)"
else
  info "Admin login: $admin_user / $(env_get "$LAB_SECRETS_FILE" LAB_ADMIN_PASSWORD)"
  info "  (stored in $LAB_SECRETS_FILE; Keycloak's own admin is KC_ADMIN_USER in the same file)"
fi
[ "${LAB_SEED_TEST_USERS:-false}" != true ] || info "Test users alice/eddie/anna/victor: password LAB_TEST_USER_PASSWORD in $LAB_SECRETS_FILE"
info ""
hdr "Trust the lab CA"
print_trust_instructions "$(ca_dir)/root.crt"
info ""
info "Manage the lab with $V3_DIR/lab (up | down | status | urls | logs | reset | test | ca)."
