# shellcheck shell=bash
# AI assist settings (CONTRACT Phase 5, GATEWAY): the providers behind the ai-gateway.
# Sourced by install.sh (--ai-local-url, --ai-mock) and lab (`lab ai ...`). Needs lib.sh.
#
# Where each setting lives:
#   .env          LAB_AI_LOCAL_URL, LAB_AI_LOCAL_MODEL   local OpenAI-compatible server
#                 LAB_AI_ANTHROPIC_MODEL, LAB_AI_OPENAI_MODEL (optional model overrides)
#                 LAB_AI_MOCK=true                        test installs only (mock model)
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
  printf '  %-10s %s USD per user per %s, %s requests/min (LAB_AI_USER_BUDGET_USD, LAB_AI_BUDGET_DURATION, LAB_AI_USER_RPM in .env)\n' \
    budget "$(env_get "$LAB_ENV_FILE" LAB_AI_USER_BUDGET_USD | grep . || echo 5)" \
    "$(env_get "$LAB_ENV_FILE" LAB_AI_BUDGET_DURATION | grep . || echo 30d)" \
    "$(env_get "$LAB_ENV_FILE" LAB_AI_USER_RPM | grep . || echo 30)"
  if [ -z "$(ai_enabled_providers)" ]; then
    info "  No provider enabled: AI features answer \"AI isn't configured; ask your lab admin\" and the lab makes no outbound AI calls."
  fi
}
