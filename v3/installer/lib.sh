# shellcheck shell=bash
# Constants here are read by install.sh, lab and the other modules (SC2034).
# shellcheck disable=SC2034
# Shared helpers for install.sh and lab. Sourced, never executed.
#
# Paths: V3_DIR is the directory that holds compose.yaml, versions.env, .env and
# .secrets.env. Callers set it before sourcing (from their own location), so the
# same scripts work in a copied tree (tests/installer uses that).

: "${V3_DIR:?V3_DIR must be set before sourcing installer/lib.sh}"

LAB_ENV_FILE="${V3_DIR}/.env"
LAB_SECRETS_FILE="${V3_DIR}/.secrets.env"
LAB_VERSIONS_FILE="${V3_DIR}/versions.env"
LAB_COMPOSE_FILE="${V3_DIR}/compose.yaml"

# Profiles from docs/v3/ARCHITECTURE.md section 8. Only these are selectable today.
LAB_KNOWN_PROFILES="core engineer full server"
LAB_AVAILABLE_PROFILES="core"

# Public subdomains Caddy serves in Phase 1 (CONTRACT.md, stack conventions).
LAB_PUBLIC_SERVICES="console auth trino catalog"

# Defaults from the runtime contract.
LAB_DEFAULT_PROJECT="lakehouse"
LAB_DEFAULT_DOMAIN="lab.localhost"
LAB_DEFAULT_HTTPS_PORT="443"
LAB_DEFAULT_HTTP_PORT="80"
LAB_DEFAULT_PROFILE="core"
LAB_DEFAULT_STATE_DIR="./state"

# ---------------------------------------------------------------- output
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  _c_red=$'\033[31m'; _c_yel=$'\033[33m'; _c_grn=$'\033[32m'; _c_bld=$'\033[1m'; _c_off=$'\033[0m'
else
  _c_red=""; _c_yel=""; _c_grn=""; _c_bld=""; _c_off=""
fi
info() { printf '%s\n' "$*"; }
ok()   { printf '%s[ok]%s %s\n' "$_c_grn" "$_c_off" "$*"; }
warn() { printf '%s[warn]%s %s\n' "$_c_yel" "$_c_off" "$*" >&2; }
err()  { printf '%s[error]%s %s\n' "$_c_red" "$_c_off" "$*" >&2; }
die()  { err "$*"; exit 1; }
hdr()  { printf '\n%s== %s%s\n' "$_c_bld" "$*" "$_c_off"; }

# ---------------------------------------------------------------- env files
# env_get FILE KEY -> prints the value (last assignment wins), empty if absent.
# Plain KEY=value parsing, no shell evaluation of the file.
env_get() {
  local file=$1 key=$2
  [ -f "$file" ] || return 0
  awk -v k="$key" '
    /^[[:space:]]*#/ { next }
    { i = index($0, "=") }
    i > 0 && substr($0, 1, i - 1) == k { v = substr($0, i + 1); found = 1 }
    END { if (found) print v }
  ' "$file"
}

# env_has FILE KEY -> 0 if KEY is assigned a non-empty value.
env_has() {
  [ -n "$(env_get "$1" "$2")" ]
}

# env_set FILE KEY VALUE -> replace KEY's line in place, or append it.
# The value goes through ENVIRON, so no quoting or regex issues.
env_set() {
  local file=$1 key=$2 value=$3 tmp
  case "$value" in *$'\n'*) die "env_set: newline in value for $key";; esac
  tmp="${file}.tmp.$$"
  if [ -f "$file" ]; then
    # The temp file is private from the start; the original mode is copied after.
    (umask 077; : >"$tmp")
    K="$key" V="$value" awk '
      BEGIN { k = ENVIRON["K"]; v = ENVIRON["V"] }
      { i = index($0, "=") }
      i > 0 && $0 !~ /^[[:space:]]*#/ && substr($0, 1, i - 1) == k {
        if (!done) print k "=" v; done = 1; next
      }
      { print }
      END { if (!done) print k "=" v }
    ' "$file" >"$tmp"
    # Keep the original file's mode (600 for secrets).
    chmod --reference="$file" "$tmp" 2>/dev/null || true
    mv -f "$tmp" "$file"
  else
    printf '%s=%s\n' "$key" "$value" >"$file"
  fi
}

# load_env FILE -> export every KEY=value from FILE into the environment
# without evaluating it as shell (values may contain any characters but newline).
load_env() {
  local file=$1 line key
  [ -f "$file" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ''|'#'*|[[:space:]]*'#'*) continue;; esac
    key=${line%%=*}
    [ "$key" = "$line" ] && continue
    case "$key" in *[!A-Za-z0-9_]*|[0-9]*|'') continue;; esac
    export "$key=${line#*=}"
  done <"$file"
}

# ---------------------------------------------------------------- settings
# lab_settings -> export every key of .env and fill in contract defaults.
# .env is the source of truth: it overrides whatever the calling shell has exported.
# Compose gives shell variables precedence over --env-file, so a stray
# COMPOSE_PROJECT_NAME or LAB_DOMAIN in the user's shell would otherwise point
# compose at another project or domain.
lab_settings() {
  local k
  for k in COMPOSE_PROJECT_NAME LAB_DOMAIN LAB_HTTPS_PORT LAB_HTTP_PORT LAB_PROFILE LAB_STATE_DIR; do
    unset "$k"
  done
  load_env "$LAB_ENV_FILE"
  export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-$LAB_DEFAULT_PROJECT}"
  export LAB_DOMAIN="${LAB_DOMAIN:-$LAB_DEFAULT_DOMAIN}"
  export LAB_HTTPS_PORT="${LAB_HTTPS_PORT:-$LAB_DEFAULT_HTTPS_PORT}"
  export LAB_HTTP_PORT="${LAB_HTTP_PORT:-$LAB_DEFAULT_HTTP_PORT}"
  export LAB_PROFILE="${LAB_PROFILE:-$LAB_DEFAULT_PROFILE}"
  export LAB_STATE_DIR="${LAB_STATE_DIR:-$LAB_DEFAULT_STATE_DIR}"
}

# state_dir_abs -> LAB_STATE_DIR resolved like compose does (relative to the project dir).
state_dir_abs() {
  case "$LAB_STATE_DIR" in
    /*) printf '%s\n' "$LAB_STATE_DIR" ;;
    *)  printf '%s/%s\n' "$V3_DIR" "${LAB_STATE_DIR#./}" ;;
  esac
}

ca_dir() { printf '%s/ca\n' "$(state_dir_abs)"; }

# ---------------------------------------------------------------- compose
# lab_compose ARGS... -> the contract's compose invocation:
#   docker compose --project-directory v3 --env-file v3/versions.env --env-file v3/.env \
#     --profile core <ARGS>
# COMPOSE_PROJECT_NAME comes from .env (exported by lab_settings as well, so a stale
# shell variable can never point compose at another project).
# LAB_DRY_RUN=1 prints the command instead of running it (tests).
lab_compose() {
  local -a cmd=(docker compose --project-directory "$V3_DIR"
    --env-file "$LAB_VERSIONS_FILE" --env-file "$LAB_ENV_FILE"
    --profile "$LAB_PROFILE" "$@")
  if [ "${LAB_DRY_RUN:-0}" = 1 ]; then
    printf '%s\n' "COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME} ${cmd[*]}"
    return 0
  fi
  COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME" "${cmd[@]}"
}

# ---------------------------------------------------------------- misc
# version_ge A B -> 0 if dotted version A >= B (numeric parts only).
version_ge() {
  local a=$1 b=$2 i x y
  local -a pa pb
  IFS=. read -r -a pa <<<"${a%%[!0-9.]*}"
  IFS=. read -r -a pb <<<"${b%%[!0-9.]*}"
  for i in 0 1 2 3; do
    x=${pa[i]:-0}; y=${pb[i]:-0}
    x=$((10#${x:-0})); y=$((10#${y:-0}))
    [ "$x" -gt "$y" ] && return 0
    [ "$x" -lt "$y" ] && return 1
  done
  return 0
}

# service_url SVC -> https URL for a public subdomain; the port is omitted when 443.
service_url() {
  local port=""
  [ "$LAB_HTTPS_PORT" = 443 ] || port=":${LAB_HTTPS_PORT}"
  printf 'https://%s.%s%s\n' "$1" "$LAB_DOMAIN" "$port"
}

# confirm PROMPT -> 0 on y/yes. Fails closed when there is no terminal.
confirm() {
  local ans
  [ -t 0 ] || return 1
  read -r -p "$1 [y/N] " ans || return 1
  case "$ans" in y|Y|yes|YES) return 0;; *) return 1;; esac
}

valid_project_name() {
  [[ "$1" =~ ^[a-z0-9][a-z0-9_-]*$ ]]
}

valid_port() {
  [[ "$1" =~ ^[0-9]+$ ]] && [ "$1" -ge 1 ] && [ "$1" -le 65535 ]
}

profile_available() {
  case " $LAB_AVAILABLE_PROFILES " in *" $1 "*) return 0;; esac
  return 1
}

# print_urls -> the lab's public URLs (from .env settings).
print_urls() {
  local svc
  printf '  %-9s %s\n' "Console" "$(service_url console)/"
  printf '  %-9s %s\n' "Keycloak" "$(service_url auth)/  (admin console: $(service_url auth)/admin/)"
  printf '  %-9s %s\n' "Trino" "$(service_url trino)/ui/"
  printf '  %-9s %s\n' "Catalog" "$(service_url catalog)/ui/"
  for svc in $LAB_PUBLIC_SERVICES; do
    case "$svc" in console|auth|trino|catalog) ;; *) printf '  %-9s %s\n' "$svc" "$(service_url "$svc")/";; esac
  done
  if is_localhost_domain "$LAB_DOMAIN"; then
    local p=""
    [ "$LAB_HTTP_PORT" = 80 ] || p=":$LAB_HTTP_PORT"
    printf '  %-9s http://console.%s%s/ (plain HTTP works only on *.localhost)\n' "" "$LAB_DOMAIN" "$p"
  fi
}
