# shellcheck shell=bash
# AI assist settings (CONTRACT Phase 5, GATEWAY): the providers behind the ai-gateway.
# Sourced by install.sh (--ai-local-url, --ai-mock) and lab (`lab ai ...`). Needs lib.sh.
#
# Where each setting lives:
#   .env          LAB_AI_LOCAL_URL, LAB_AI_LOCAL_MODEL   local OpenAI-compatible server
#                 LAB_AI_ANTHROPIC_MODEL, LAB_AI_OPENAI_MODEL (optional model overrides)
#                 LAB_AI_MOCK=true                        test installs only (mock model)
#                 LAB_AI_QUIET_HOURS, LAB_AI_QUIET_TZ     local model's quiet hours (Phase 6;
#                 `lab ai quiet-hours`): the gateway refuses requests that would reach the
#                 local provider in that window, before routing; empty = off (the default)
#   .secrets.env  LAB_AI_ANTHROPIC_API_KEY, LAB_AI_OPENAI_API_KEY   hosted providers
#                 (present = enabled; `lab ai enable-hosted`/`disable-hosted`; the gateway is
#                 the only service that receives them)
# Nothing is enabled by default: with no provider the gateway has an empty model list and
# the lab makes no outbound AI calls (OQ-8).
#
# The local server is only ever probed with metadata calls (GET /health and GET /v1/models),
# never with a completion or embedding request.

LAB_AI_PROVIDERS_HOSTED="anthropic openai"

# ai_key_var PROVIDER -> the .secrets.env key holding that provider's API key
ai_key_var() {
  case "$1" in
    anthropic) echo LAB_AI_ANTHROPIC_API_KEY ;;
    openai)    echo LAB_AI_OPENAI_API_KEY ;;
    *) return 1 ;;
  esac
}

# ai_model_var PROVIDER -> the .env key of that provider's model override
ai_model_var() {
  case "$1" in
    anthropic) echo LAB_AI_ANTHROPIC_MODEL ;;
    openai)    echo LAB_AI_OPENAI_MODEL ;;
    *) return 1 ;;
  esac
}

valid_ai_model() { [[ "$1" =~ ^[A-Za-z0-9/][A-Za-z0-9._:/@+-]{0,199}$ ]]; }

# ai_normalize_url URL -> normalized OpenAI-compatible base URL (".../v1"), or fails.
# http(s) only; no credentials, spaces or quotes; a URL without a path gets /v1. A localhost
# URL is rewritten to host.docker.internal (the gateway runs in a container, where localhost
# is the container itself; compose maps host.docker.internal to the host).
ai_normalize_url() {
  local u=${1%/} scheme hostport host path out
  local re='^(https?)://([A-Za-z0-9.-]+(:[0-9]{1,5})?)(/[A-Za-z0-9._~%/-]*)?$'
  [[ "$u" =~ $re ]] || return 1
  scheme=${BASH_REMATCH[1]} hostport=${BASH_REMATCH[2]} path=${BASH_REMATCH[4]:-}
  host=${hostport%%:*}
  case "$host" in
    localhost|127.*) out=host.docker.internal${hostport#"$host"} ;;
    *) out=$hostport ;;
  esac
  path=${path%/}
  [ -n "$path" ] || path=/v1
  printf '%s://%s%s\n' "$scheme" "$out" "$path"
}

# ai_probe_url URL -> the same URL as seen from this host (host.docker.internal -> 127.0.0.1)
ai_probe_url() {
  printf '%s\n' "${1/:\/\/host.docker.internal/://127.0.0.1}"
}

# ai_probe_local URL -> metadata-only reachability check of a local server. Prints the first
# model id from GET <url>/models (empty if none). Returns 1 if the server does not answer.
# NEVER sends an inference request (the owner's GPU server must stay idle).
ai_probe_local() {
  local base root models id
  base=$(ai_probe_url "$1")
  root=${base%/v1}
  command -v curl >/dev/null 2>&1 || { warn "curl not found: skipping the reachability check"; return 0; }
  if ! curl -fsS --max-time 5 -o /dev/null "$root/health" 2>/dev/null &&
     ! curl -fsS --max-time 5 -o /dev/null "$base/models" 2>/dev/null; then
    return 1
  fi
  models=$(curl -fsS --max-time 5 "$base/models" 2>/dev/null) || models=""
  id=$(grep -o '"id"[[:space:]]*:[[:space:]]*"[^"]*"' <<<"$models" | head -n 1 | sed 's/.*"\([^"]*\)"$/\1/')
  valid_ai_model "$id" && printf '%s\n' "$id"
  return 0
}

# ai_set_local URL|none [MODEL] [PROBE(1|0)] -> write LAB_AI_LOCAL_URL/MODEL to .env
ai_set_local() {
  local url=$1 model=${2:-} probe=${3:-1} norm found=""
  if [ "$url" = none ] || [ -z "$url" ]; then
    env_set "$LAB_ENV_FILE" LAB_AI_LOCAL_URL ""
    env_unset "$LAB_ENV_FILE" LAB_AI_LOCAL_MODEL
    ok "Local AI model: none"
    return 0
  fi
  norm=$(ai_normalize_url "$url") || die "invalid local model URL '$url' (expected http(s)://host[:port][/v1], no credentials)"
  [ "$norm" = "${url%/}" ] || info "  using $norm"
  if [ -n "$model" ] && ! valid_ai_model "$model"; then
    die "invalid model name '$model'"
  fi
  if [ "$probe" = 1 ]; then
    if found=$(ai_probe_local "$norm"); then
      if [ -n "$found" ]; then
        ok "Local model server answers ($(ai_probe_url "$norm")); it serves \"$found\""
      else
        ok "Local model server answers ($(ai_probe_url "$norm"))"
      fi
    else
      warn "no answer from $(ai_probe_url "$norm")/models (checked only /health and /v1/models). Saved anyway; AI requests fail until it is up."
    fi
  fi
  model=${model:-$found}
  env_set "$LAB_ENV_FILE" LAB_AI_LOCAL_URL "$norm"
  if [ -n "$model" ]; then env_set "$LAB_ENV_FILE" LAB_AI_LOCAL_MODEL "$model"; else env_unset "$LAB_ENV_FILE" LAB_AI_LOCAL_MODEL; fi
  if [ -n "$model" ]; then ok "Local AI model: $norm (model \"$model\")"; else ok "Local AI model: $norm"; fi
}

# ai_set_local_key FILE|none -> LAB_AI_LOCAL_API_KEY in .secrets.env (mode 600), or removed.
# The local model server's key (e.g. llama-server --api-key-file): only the ai-gateway gets
# it, so workspaces cannot call the model server around the gateway (Phase 5 known gap).
ai_set_local_key() {
  local f=$1 key
  [ -f "$LAB_SECRETS_FILE" ] || die "no $LAB_SECRETS_FILE; run install.sh first"
  if [ "$f" = none ]; then
    if env_has "$LAB_SECRETS_FILE" LAB_AI_LOCAL_API_KEY; then
      env_unset "$LAB_SECRETS_FILE" LAB_AI_LOCAL_API_KEY
      ok "Local model API key removed from $LAB_SECRETS_FILE"
    fi
    return 0
  fi
  key=$(ai_read_key_file "$f")
  env_set "$LAB_SECRETS_FILE" LAB_AI_LOCAL_API_KEY "$key"
  chmod 600 "$LAB_SECRETS_FILE"
  ok "Local model API key stored in $LAB_SECRETS_FILE (only the ai-gateway receives it)"
}

# ai_read_key_file FILE -> the API key in FILE (one line, no spaces). Never printed.
ai_read_key_file() {
  local f=$1 key
  [ -f "$f" ] && [ -r "$f" ] || die "key file '$f' not found or not readable"
  [ "$(wc -l <"$f" | tr -d ' ')" -le 1 ] || die "key file '$f' must hold one line (the API key only)"
  key=$(tr -d '\r\n' <"$f")
  [[ "$key" =~ ^[A-Za-z0-9._-]{20,300}$ ]] || die "key file '$f' does not look like an API key (20-300 letters, digits, '.', '_' or '-')"
  printf '%s\n' "$key"
}

# ai_enable_hosted PROVIDER KEYFILE [MODEL] -> key into .secrets.env (mode 600)
ai_enable_hosted() {
  local p=$1 f=$2 model=${3:-} var mvar key
  var=$(ai_key_var "$p") || die "unknown provider '$p' (use: $LAB_AI_PROVIDERS_HOSTED)"
  mvar=$(ai_model_var "$p")
  [ -n "$f" ] || die "--key-file is required"
  if [ -n "$model" ] && ! valid_ai_model "$model"; then die "invalid model name '$model'"; fi
  key=$(ai_read_key_file "$f") || exit 1
  case "$p:$key" in
    anthropic:sk-ant-*|openai:sk-*) ;;
    *) warn "the key does not start like a $p API key; saving it anyway" ;;
  esac
  [ -f "$LAB_SECRETS_FILE" ] || die "no $LAB_SECRETS_FILE; run install.sh first"
  env_set "$LAB_SECRETS_FILE" "$var" "$key"
  chmod 600 "$LAB_SECRETS_FILE"
  if [ -n "$model" ]; then env_set "$LAB_ENV_FILE" "$mvar" "$model"; fi
  ok "Hosted provider $p enabled (key stored in $LAB_SECRETS_FILE; only the ai-gateway receives it)"
}

# ai_disable_hosted PROVIDER|all -> remove the key(s)
ai_disable_hosted() {
  local p var list=$1
  [ "$list" = all ] && list=$LAB_AI_PROVIDERS_HOSTED
  for p in $list; do
    var=$(ai_key_var "$p") || die "unknown provider '$p' (use: $LAB_AI_PROVIDERS_HOSTED or all)"
    if env_has "$LAB_SECRETS_FILE" "$var"; then
      env_unset "$LAB_SECRETS_FILE" "$var"
      ok "Hosted provider $p disabled (key removed from $LAB_SECRETS_FILE)"
    else
      info "Hosted provider $p: already off"
    fi
  done
}

# ---------------------------------------------------------------- quiet hours (Phase 6)
# ai_valid_quiet_window SPEC -> HH:MM-HH:MM (24-hour clock), start != end. The gateway checks
# the same rule (config/ai/render_config.py parse_quiet_hours).
ai_valid_quiet_window() {
  [[ "$1" =~ ^([01][0-9]|2[0-3]):[0-5][0-9]-([01][0-9]|2[0-3]):[0-5][0-9]$ ]] && [ "${1%%-*}" != "${1#*-}" ]
}

# ai_valid_tz NAME -> an IANA time zone this host knows (Area/City, e.g. America/New_York).
ai_valid_tz() {
  local z=$1
  [[ "$z" =~ ^[A-Za-z0-9_+-]+(/[A-Za-z0-9_+-]+){0,2}$ ]] || return 1
  if command -v python3 >/dev/null 2>&1; then
    python3 -c 'import sys, zoneinfo; zoneinfo.ZoneInfo(sys.argv[1])' "$z" 2>/dev/null
    return
  fi
  [ -f "/usr/share/zoneinfo/$z" ]
}

# _ai_minutes HH:MM -> minutes since midnight
_ai_minutes() { local h=${1%%:*} m=${1#*:}; echo $((10#$h * 60 + 10#$m)); }

# ai_quiet_end_now SPEC TZ [NOW_HHMM] -> prints the window's end (HH:MM) and returns 0 when the
# wall clock in TZ (or NOW_HHMM, for tests) is inside the window; returns 1 otherwise.
# Start inclusive, end exclusive; start > end crosses midnight. Display only: the gateway
# decides for itself (render_config.quiet_until).
ai_quiet_end_now() {
  local spec=$1 tz=$2 now=${3:-} s e n
  [ -n "$now" ] || now=$(TZ="$tz" date +%H:%M)
  s=$(_ai_minutes "${spec%%-*}") e=$(_ai_minutes "${spec#*-}") n=$(_ai_minutes "$now")
  if { [ "$s" -lt "$e" ] && [ "$n" -ge "$s" ] && [ "$n" -lt "$e" ]; } ||
     { [ "$s" -gt "$e" ] && { [ "$n" -ge "$s" ] || [ "$n" -lt "$e" ]; }; }; then
    printf '%s\n' "${spec#*-}"
    return 0
  fi
  return 1
}

# ai_set_quiet_hours SPEC|off [TZ] -> LAB_AI_QUIET_HOURS / LAB_AI_QUIET_TZ in .env. "off" stores
# empty values (not a removal), so a stray variable in the caller's shell can never win.
ai_set_quiet_hours() {
  local spec=$1 tz=${2:-}
  if [ "$spec" = off ]; then
    env_set "$LAB_ENV_FILE" LAB_AI_QUIET_HOURS ""
    env_set "$LAB_ENV_FILE" LAB_AI_QUIET_TZ ""
    ok "Local AI model quiet hours: off"
    return 0
  fi
  ai_valid_quiet_window "$spec" || die "invalid quiet hours '$spec' (expected HH:MM-HH:MM on a 24-hour clock, e.g. 22:00-07:00; start and end must differ)"
  [ -n "$tz" ] || die "a time zone is needed: --tz Area/City (e.g. America/New_York)"
  ai_valid_tz "$tz" || die "unknown time zone '$tz' (expected an IANA name such as America/New_York or Europe/Berlin)"
  env_set "$LAB_ENV_FILE" LAB_AI_QUIET_HOURS "$spec"
  env_set "$LAB_ENV_FILE" LAB_AI_QUIET_TZ "$tz"
  ok "Local AI model quiet hours: $spec $tz (requests to the local model are refused then; hosted models are not affected)"
  env_has "$LAB_ENV_FILE" LAB_AI_LOCAL_URL ||
    info "  No local model is set yet; this applies once one is ('lab ai set-local')."
}

# ai_quiet_hours_status -> one line for 'lab ai status' / 'lab ai quiet-hours'
ai_quiet_hours_status() {
  local spec tz end
  spec=$(env_get "$LAB_ENV_FILE" LAB_AI_QUIET_HOURS)
  tz=$(env_get "$LAB_ENV_FILE" LAB_AI_QUIET_TZ)
  if [ -z "$spec" ]; then
    printf '  %-10s %s\n' quiet off
  elif end=$(ai_quiet_end_now "$spec" "${tz:-UTC}"); then
    printf '  %-10s %s\n' quiet "$spec ${tz:-UTC}, local model only (now: resting until $end)"
  else
    printf '  %-10s %s\n' quiet "$spec ${tz:-UTC}, local model only (now: outside the window)"
  fi
}

# ai_ask_quiet_hours -> installer question (interactive installs only), asked once when a local
# model URL is set; the answer (empty = off) is stored, so a re-run does not ask again.
ai_ask_quiet_hours() {
  local spec tz def tries=0
  env_has "$LAB_ENV_FILE" LAB_AI_LOCAL_URL || return 0
  grep -q '^LAB_AI_QUIET_HOURS=' "$LAB_ENV_FILE" 2>/dev/null && return 0
  info "Quiet hours: times when the lab sends nothing to the local model server (e.g. at night,"
  info "when its fans would wake someone). Hosted providers are not affected. Change it later"
  info "with './lab ai quiet-hours HH:MM-HH:MM --tz Area/City' or '... off'."
  while :; do
    read -r -p "Local model quiet hours, e.g. 22:00-07:00 [none]: " spec || spec=""
    spec=${spec// /}
    case "$spec" in ""|none|off) ai_set_quiet_hours off; return 0 ;; esac
    ai_valid_quiet_window "$spec" && break
    warn "expected HH:MM-HH:MM on a 24-hour clock (start and end different), or empty for none"
    tries=$((tries + 1)); [ "$tries" -lt 3 ] || { ai_set_quiet_hours off; return 0; }
  done
  def=$(env_get "$LAB_ENV_FILE" LAB_TZ)
  ai_valid_tz "$def" || def=UTC
  tries=0
  while :; do
    read -r -p "Time zone of those hours [$def]: " tz || tz=""
    tz=${tz:-$def}
    ai_valid_tz "$tz" && break
    warn "unknown time zone '$tz' (an IANA name such as America/New_York)"
    tries=$((tries + 1)); [ "$tries" -lt 3 ] || { ai_set_quiet_hours off; return 0; }
  done
  ai_set_quiet_hours "$spec" "$tz"
}

# ai_enabled_providers -> space-separated enabled providers (mock local anthropic openai)
ai_enabled_providers() {
  local out="" p
  [ "$(env_get "$LAB_ENV_FILE" LAB_AI_MOCK)" = true ] && out="mock"
  env_has "$LAB_ENV_FILE" LAB_AI_LOCAL_URL && out="$out local"
  for p in $LAB_AI_PROVIDERS_HOSTED; do
    env_has "$LAB_SECRETS_FILE" "$(ai_key_var "$p")" && out="$out $p"
  done
  printf '%s\n' "${out# }"
}

# ai_print_config -> the configured providers (never a key)
ai_print_config() {
  local p on m
  if ! profile_includes "$LAB_PROFILE" ai; then
    info "AI assist runs on profile full only (this lab: $LAB_PROFILE). Settings below apply once it is full."
  fi
  if env_has "$LAB_ENV_FILE" LAB_AI_LOCAL_URL; then
    m=$(env_get "$LAB_ENV_FILE" LAB_AI_LOCAL_MODEL)
    printf '  %-10s %s%s\n' local "$(env_get "$LAB_ENV_FILE" LAB_AI_LOCAL_URL)" "${m:+ (model $m)}"
    if env_has "$LAB_SECRETS_FILE" LAB_AI_LOCAL_API_KEY; then printf '  %-10s %s\n' "" "API key: set (in .secrets.env)"; fi
  else
    printf '  %-10s %s\n' local off
  fi
  for p in $LAB_AI_PROVIDERS_HOSTED; do
    on=off
    if env_has "$LAB_SECRETS_FILE" "$(ai_key_var "$p")"; then
      m=$(env_get "$LAB_ENV_FILE" "$(ai_model_var "$p")")
      on="on (key in .secrets.env${m:+; model $m})"
    fi
    printf '  %-10s %s\n' "$p" "$on"
  done
  if [ "$(env_get "$LAB_ENV_FILE" LAB_AI_MOCK)" = true ]; then
    printf '  %-10s %s\n' mock "on (test model; tests/ai/mock_llm)"
  fi
  ai_quiet_hours_status
  printf '  %-10s %s USD per user per %s, %s requests/min (LAB_AI_USER_BUDGET_USD, LAB_AI_BUDGET_DURATION, LAB_AI_USER_RPM in .env)\n' \
    budget "$(env_get "$LAB_ENV_FILE" LAB_AI_USER_BUDGET_USD | grep . || echo 5)" \
    "$(env_get "$LAB_ENV_FILE" LAB_AI_BUDGET_DURATION | grep . || echo 30d)" \
    "$(env_get "$LAB_ENV_FILE" LAB_AI_USER_RPM | grep . || echo 30)"
  if [ -z "$(ai_enabled_providers)" ]; then
    info "  No provider enabled: AI features answer \"AI isn't configured; ask your lab admin\" and the lab makes no outbound AI calls."
  fi
}
