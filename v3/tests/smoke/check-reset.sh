#!/usr/bin/env bash
# After the smoke test: `lab reset --yes` must leave NOTHING of this project behind, including
# the per-user workspace home volumes JupyterHub created outside compose (CONTRACT Phase 2).
# Everything is selected by this project's compose label only; other projects are only
# counted, never touched, and must be unchanged afterwards.
#
# DESTRUCTIVE for this lab (it is a reset). CI runs it as its last e2e step.
# Usage: tests/smoke/check-reset.sh     Env: CHECK_RESET_MIN_HOMES (default 1)
set -uo pipefail
V3=$(cd -P "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
[ -f "$V3/.env" ] || { echo "check-reset: no $V3/.env" >&2; exit 2; }
P=$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' "$V3/.env" | tail -n1)
[[ "$P" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || { echo "check-reset: bad COMPOSE_PROJECT_NAME '$P'" >&2; exit 2; }
min_homes=${CHECK_RESET_MIN_HOMES:-1}

mine() {  # mine KIND [extra filters...] -> this project's objects of KIND
  local kind=$1; shift
  case "$kind" in
    container) docker ps -aq --filter "label=com.docker.compose.project=$P" "$@" ;;
    volume)    docker volume ls -q --filter "label=com.docker.compose.project=$P" "$@" ;;
    network)   docker network ls -q --filter "label=com.docker.compose.project=$P" "$@" ;;
  esac
}
others() {  # fingerprint of every other project's containers and volumes (names only)
  {
    docker ps -a --format '{{.Names}} {{.Label "com.docker.compose.project"}}' | awk -v p="$P" '$2 != p'
    docker volume ls --format '{{.Name}} {{.Label "com.docker.compose.project"}}' | awk -v p="$P" '$2 != p'
  } | sort
}

rc=0
homes=$(mine volume --filter label=lab.role=workspace | wc -l)
echo "check-reset: project $P has $homes per-user home volume(s) before reset"
if [ "$homes" -lt "$min_homes" ]; then
  echo "[FAIL] expected at least $min_homes home volume(s) (did the smoke test spawn a workspace?)"
  rc=1
fi
before=$(others)

"$V3/lab" reset --yes || { echo "[FAIL] lab reset exited non-zero"; rc=1; }

for kind in container volume network; do
  left=$(mine "$kind" | tr '\n' ' ')
  if [ -n "$left" ]; then echo "[FAIL] $kind(s) of $P left after reset: $left"; rc=1
  else echo "[PASS] no $kind of $P left after reset"; fi
done
if [ "$(others)" = "$before" ]; then echo "[PASS] other projects' containers and volumes unchanged"
else echo "[FAIL] other projects' containers or volumes changed"; rc=1; fi
exit "$rc"
