#!/usr/bin/env bash
# Fake 'docker' for unit tests: answers the installer's version/info probes and records
# every compose invocation (one line per call) in $SHIM_LOG. Never talks to a daemon.
# Knobs: SHIM_DOCKER_VERSION, SHIM_COMPOSE_VERSION, SHIM_MEM_BYTES, SHIM_PS (ps rows),
#        SHIM_UP_EXIT (exit code for 'compose up').
#
# Per-user workspace objects (lab down/reset): a fake inventory of containers and volumes
# that honours exact-match '--filter label=K=V' filters (ANDed, like Docker):
#   SHIM_CONTAINERS / SHIM_VOLUMES  one object per line: NAME|LABEL=VALUE,LABEL=VALUE...
#   SHIM_STATE_DIR                  where removals are remembered (default: dirname SHIM_LOG)
#   SHIM_RM_FAIL=1                  'rm' and 'volume rm' fail and remove nothing
# stop/rm/volume rm calls are logged to $SHIM_LOG as "docker <args>". Removing a name that
# is not in the inventory is an error (like Docker), and removed objects stop matching.
set -u
if [ "${1:-}" = compose ]; then
  shift
  case " $* " in
    *" version --short "*) echo "${SHIM_COMPOSE_VERSION:-2.40.3}"; exit 0 ;;  # check-versions: ignore fake version reported by the test shim
  esac
  printf 'COMPOSE_PROJECT_NAME=%s docker compose %s\n' "${COMPOSE_PROJECT_NAME:-}" "$*" >>"${SHIM_LOG:?}"
  case " $* " in
    *" up "*) exit "${SHIM_UP_EXIT:-0}" ;;
    *" ps "*) [ -n "${SHIM_PS:-}" ] && printf '%b\n' "$SHIM_PS"; exit 0 ;;
  esac
  exit 0
fi

state_dir=${SHIM_STATE_DIR:-$(dirname "${SHIM_LOG:?}")}
removed_file="$state_dir/shim-removed"

# inventory KIND -> NAME|LABELS lines not yet removed
inventory() {
  local src
  if [ "$1" = container ]; then src=${SHIM_CONTAINERS:-}; else src=${SHIM_VOLUMES:-}; fi
  [ -n "$src" ] || return 0
  printf '%b\n' "$src" | while IFS= read -r line; do
    [ -n "$line" ] || continue
    if [ -f "$removed_file" ] && grep -qxF "$1:${line%%|*}" "$removed_file"; then continue; fi
    printf '%s\n' "$line"
  done
}

# list KIND ARGS... -> names matching every --filter label=K=V (other filters match nothing)
list() {
  local kind=$1; shift
  local -a want=()
  local other=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --filter) shift; case "${1:-}" in label=*=*) want+=("${1#label=}") ;; *) other=1 ;; esac ;;
      --filter=*) case "${1#--filter=}" in label=*=*) want+=("${1#--filter=label=}") ;; *) other=1 ;; esac ;;
      -a|-q|--all|--quiet) ;;
      *) other=1 ;;
    esac
    shift
  done
  [ "$other" = 0 ] || return 0
  inventory "$kind" | while IFS='|' read -r name labels; do
    local w ok=1
    for w in "${want[@]}"; do
      case ",$labels," in *",$w,"*) ;; *) ok=0 ;; esac
    done
    [ "$ok" = 1 ] && printf '%s\n' "$name"
  done
}

# remove KIND NAMES... -> forget them; error on an unknown name
remove() {
  local kind=$1 n rc=0; shift
  [ "${SHIM_RM_FAIL:-0}" = 1 ] && { echo "Error response from daemon: simulated failure" >&2; return 1; }
  for n in "$@"; do
    case "$n" in -*) continue ;; esac
    if inventory "$kind" | cut -d'|' -f1 | grep -qxF "$n"; then
      printf '%s:%s\n' "$kind" "$n" >>"$removed_file"
    else
      echo "Error response from daemon: No such $kind: $n" >&2; rc=1
    fi
  done
  return "$rc"
}

case "${1:-}" in
  ps)
    shift; list container "$@"; exit 0 ;;
  stop)
    printf 'docker %s\n' "$*" >>"$SHIM_LOG"
    shift
    [ "${1:-}" = -t ] && shift 2
    for n in "$@"; do inventory container | cut -d'|' -f1 | grep -qxF "$n" || { echo "No such container: $n" >&2; exit 1; }; done
    exit 0 ;;
  rm)
    printf 'docker %s\n' "$*" >>"$SHIM_LOG"
    shift; remove container "$@"; exit $? ;;
  volume)
    case "${2:-}" in
      ls) shift 2; list volume "$@"; exit 0 ;;
      rm) printf 'docker %s\n' "$*" >>"$SHIM_LOG"; shift 2; remove volume "$@"; exit $? ;;
    esac ;;
esac
case "${1:-} ${2:-} ${3:-}" in
  "version --format "*) echo "${SHIM_DOCKER_VERSION:-27.3.1}" ;;  # check-versions: ignore fake version reported by the test shim
  "info --format "*)
    case "$3" in
      *MemTotal*) echo "${SHIM_MEM_BYTES:-17179869184}" ;;
      *) echo "" ;;
    esac ;;
  *) echo "docker-shim: unsupported: $*" >&2; exit 1 ;;
esac
