#!/usr/bin/env bash
# Installer end-to-end test against a real Docker daemon, using the stub stack in
# fixtures/compose.yaml (no published ports) as compose project v3-p1-inst.
# Runs install.sh and lab exactly as a user would, from a copied tree.
# It only ever touches project v3-p1-inst; it checks that nothing else changed.
# shellcheck disable=SC2015
set -uo pipefail
HERE=$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=testlib.sh
. "$HERE/testlib.sh"
export NO_COLOR=1

PROJECT=v3-p1-inst
WORK=$(mktemp -d "${TMPDIR:-/tmp}/lab-inst-e2e.XXXXXX")
T="$WORK/v3"
make_tree "$T"

# Per-user workspace stand-ins (what JupyterHub's DockerSpawner creates): a container and a
# home volume labelled com.docker.compose.project=<project> + lab.role=workspace, outside
# compose. DECOY is a second v3-* project of this test whose objects must survive.
DECOY=v3-p1-inst-decoy
IMG="caddy:$(awk -F= '$1 == "CADDY_VERSION" {print $2}' "$T/versions.env")"
ws_run() {  # ws_run USER PROJECT [NETWORK]
  docker volume create --label "com.docker.compose.project=$2" --label lab.role=workspace "$2-home-$1" >/dev/null
  docker run -d --name "$2-ws-$1" --label "com.docker.compose.project=$2" --label lab.role=workspace \
    ${3:+--network "$3"} -v "$2-home-$1:/home/lab" "$IMG" sleep 600 >/dev/null
}
decoy_cleanup() {
  docker rm -f "$DECOY-ws-bob" >/dev/null 2>&1 || true
  docker volume rm "$DECOY-home-bob" >/dev/null 2>&1 || true
}

cleanup() {
  if [ -f "$T/.env" ]; then "$T/lab" reset --all --yes >/dev/null 2>&1 || true; fi
  decoy_cleanup
  rm -rf "$WORK"
}
trap cleanup EXIT

others() {  # containers and volumes that belong to anything but $PROJECT
  {
    docker ps -a --format '{{.Names}} {{.Label "com.docker.compose.project"}} {{.ID}}' | awk -v p="$PROJECT" '$2 != p'
    docker volume ls --format '{{.Name}} {{.Label "com.docker.compose.project"}}' | awk -v p="$PROJECT" '$2 != p'
  } | sort
}
cid() { docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" --filter "label=com.docker.compose.service=$1"; }
vol_exists() { docker volume inspect "${PROJECT}_data" >/dev/null 2>&1; }

before=$(others)

echo "== install"
t_begin install
t0=$(date +%s)
out=$("$T/install.sh" --non-interactive --domain lab.localhost --project-name "$PROJECT" \
  --https-port 18443 --http-port 18080 --seed-test-users 2>&1); rc=$?
assert_eq "install.sh exit 0 ($(( $(date +%s) - t0 ))s)" 0 "$rc"
[ "$rc" = 0 ] || printf '%s\n' "$out"
assert_contains "reports healthy stack" "Stack healthy" "$out"
assert_eq "edge healthy" healthy "$(docker inspect -f '{{.State.Health.Status}}' "$(cid edge)" 2>/dev/null)"
assert_eq "one-shot exited 0 (env + secrets reached it)" "exited 0" "$(docker inspect -f '{{.State.Status}} {{.State.ExitCode}}' "$(cid oneshot)" 2>/dev/null)"
ports=$(docker ps --filter "label=com.docker.compose.project=$PROJECT" --format '{{.Ports}}' | grep -o '[0-9.:]*->' || true)
assert_eq "no published ports" "" "$ports"
assert "volume ${PROJECT}_data created by compose" vol_exists
assert_eq "volume carries the project label" "$PROJECT" "$(docker volume inspect -f '{{index .Labels "com.docker.compose.project"}}' "${PROJECT}_data" 2>/dev/null)"
assert "lab status healthy" "$T/lab" status
docker exec "$(cid edge)" sh -c 'echo keep-me > /data/marker'

echo "== idempotent re-install"
t_begin reinstall
hs=$(sha256sum "$T/.secrets.env"); hc=$(sha256sum "$T/state/ca/root.crt" "$T/state/ca/root.key")
edge_id=$(cid edge)
assert "install.sh again" "$T/install.sh" --non-interactive
assert_eq "secrets unchanged" "$hs" "$(sha256sum "$T/.secrets.env")"
assert_eq "CA unchanged" "$hc" "$(sha256sum "$T/state/ca/root.crt" "$T/state/ca/root.key")"
assert_eq "running container not recreated" "$edge_id" "$(cid edge)"
assert_eq "data kept" keep-me "$(docker exec "$(cid edge)" cat /data/marker 2>/dev/null)"

echo "== lab down / up / logs / urls / test / ca"
t_begin lab
ws_run alice "$PROJECT" "${PROJECT}_default"
ws_run bob "$DECOY"
assert_eq "workspace stand-in running" running "$(docker inspect -f '{{.State.Status}}' "$PROJECT-ws-alice" 2>/dev/null)"
assert "lab down" "$T/lab" down
assert_eq "containers gone after down (incl. workspace)" "" "$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT")"
assert_not "network removed (no workspace kept it in use)" docker network inspect "${PROJECT}_default"
assert "volume kept after down" vol_exists
assert "home volume kept after down" docker volume inspect "$PROJECT-home-alice"
assert_eq "other project's workspace untouched by down" running "$(docker inspect -f '{{.State.Status}}' "$DECOY-ws-bob" 2>/dev/null)"
assert_not "lab status fails when down" "$T/lab" status
assert "lab up" "$T/lab" up
assert_eq "data survived down/up" keep-me "$(docker exec "$(cid edge)" cat /data/marker 2>/dev/null)"
assert_contains "lab logs oneshot" "env ok for lab.localhost" "$("$T/lab" logs --no-follow oneshot 2>&1)"
assert_contains "lab urls" "https://trino.lab.localhost:18443/ui/" "$("$T/lab" urls)"
assert_contains "lab ca" "$T/state/ca/root.crt" "$("$T/lab" ca)"
assert "lab test runs the smoke script" "$T/lab" test

echo "== lab reset"
t_begin reset
ws_run alice "$PROJECT" "${PROJECT}_default"
assert "lab reset --yes" "$T/lab" reset --yes
assert_not "home volume deleted by reset" docker volume inspect "$PROJECT-home-alice"
assert_eq "other project's workspace untouched by reset" running "$(docker inspect -f '{{.State.Status}}' "$DECOY-ws-bob" 2>/dev/null)"
assert "other project's home volume untouched by reset" docker volume inspect "$DECOY-home-bob"
assert_eq "containers gone" "" "$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT")"
assert_not "data volume deleted" vol_exists
assert_eq "CA kept by reset" "$hc" "$(sha256sum "$T/state/ca/root.crt" "$T/state/ca/root.key")"
assert "lab up after reset" "$T/lab" up
assert_eq "fresh volume" "" "$(docker exec "$(cid edge)" cat /data/marker 2>/dev/null)"
assert "lab reset --all --yes" "$T/lab" reset --all --yes
assert_not "state dir removed by --all" test -e "$T/state"
assert "install.sh after --all makes a new CA" "$T/install.sh" --non-interactive
assert_not "new CA differs" test "$hc" = "$(sha256sum "$T/state/ca/root.crt" "$T/state/ca/root.key")"
assert "lab reset --all again" "$T/lab" reset --all --yes

echo "== isolation"
t_begin isolation
decoy_cleanup
after=$(others)
assert_eq "no other project's containers/volumes changed" "$before" "$after"

t_summary "installer e2e"
