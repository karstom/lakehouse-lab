#!/usr/bin/env bash
# Fake 'docker' for unit tests: answers the installer's version/info probes and records
# every compose invocation (one line per call) in $SHIM_LOG. Never talks to a daemon.
# Knobs: SHIM_DOCKER_VERSION, SHIM_COMPOSE_VERSION, SHIM_MEM_BYTES, SHIM_PS (ps rows),
#        SHIM_UP_EXIT (exit code for 'compose up').
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
case "${1:-} ${2:-} ${3:-}" in
  "version --format "*) echo "${SHIM_DOCKER_VERSION:-27.3.1}" ;;  # check-versions: ignore fake version reported by the test shim
  "info --format "*)
    case "$3" in
      *MemTotal*) echo "${SHIM_MEM_BYTES:-17179869184}" ;;
      *) echo "" ;;
    esac ;;
  "ps "*) : ;;
  *) echo "docker-shim: unsupported: $*" >&2; exit 1 ;;
esac
