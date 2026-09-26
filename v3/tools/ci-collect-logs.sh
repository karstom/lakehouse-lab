#!/usr/bin/env bash
# Collect diagnostics after a failed CI run (or locally) into DIR, with every value from
# v3/.secrets.env redacted. Never copies .secrets.env or the CA key.
# Usage: v3/tools/ci-collect-logs.sh DIR
set -uo pipefail
V3_DIR=$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
out=${1:?usage: ci-collect-logs.sh DIR}
mkdir -p "$out"

run() { # run NAME CMD... -> $out/NAME (stdout+stderr), never fails
  local name=$1; shift
  { echo "\$ $*"; "$@"; } >"$out/$name" 2>&1 || true
}

project=lakehouse profile=core
if [ -f "$V3_DIR/.env" ]; then
  cp "$V3_DIR/.env" "$out/dot-env.txt"
  p=$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' "$V3_DIR/.env" | tail -n1)
  [ -n "$p" ] && project=$p
  p=$(sed -n 's/^LAB_PROFILE=//p' "$V3_DIR/.env" | tail -n1)
  [ -n "$p" ] && profile=$p
fi
dc=(docker compose -p "$project" --project-directory "$V3_DIR" --env-file "$V3_DIR/versions.env")
[ -f "$V3_DIR/.env" ] && dc+=(--env-file "$V3_DIR/.env")
dc+=(--profile "$profile")

run docker-info.txt docker info
run disk.txt df -h
run memory.txt free -m
run compose-ps.txt "${dc[@]}" ps -a
run compose-logs.txt "${dc[@]}" logs --no-color --timestamps
run docker-stats.txt docker stats --no-stream
for svc in $("${dc[@]}" ps -a --services 2>/dev/null); do
  run "logs-$svc.txt" "${dc[@]}" logs --no-color --timestamps "$svc"
  cid=$("${dc[@]}" ps -a -q "$svc" 2>/dev/null | head -n1)
  [ -n "$cid" ] && run "inspect-$svc.json" docker inspect --format '{{json .State}}' "$cid"
done
# Per-user workspaces (created by JupyterHub, not compose services): this project's only,
# selected by the exact labels, never by name.
if [[ "$project" =~ ^[a-z0-9][a-z0-9_-]*$ ]]; then
  for cid in $(docker ps -aq --filter "label=com.docker.compose.project=$project" \
                 --filter label=lab.role=workspace 2>/dev/null); do
    run "logs-workspace-$cid.txt" docker logs --timestamps "$cid"
    run "inspect-workspace-$cid.json" docker inspect --format '{{json .State}}' "$cid"
  done
fi
# Smoke-test and installer outputs (v3/**/out/ is git-ignored scratch).
while IFS= read -r -d '' d; do
  rel=${d#"$V3_DIR"/}
  mkdir -p "$out/files/$rel"
  cp -a "$d/." "$out/files/$rel/" 2>/dev/null || true
done < <(find "$V3_DIR" -type d -name out -not -path '*/state/*' -print0 2>/dev/null)

# Redact secrets from everything collected.
if [ -f "$V3_DIR/.secrets.env" ]; then
  python3 - "$V3_DIR/.secrets.env" "$out" <<'PY'
import os, sys
secrets = []
for line in open(sys.argv[1], encoding="utf-8"):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        v = line.split("=", 1)[1].strip().strip("'\"")
        if len(v) >= 6:
            secrets.append(v)
secrets.sort(key=len, reverse=True)
for root, _, files in os.walk(sys.argv[2]):
    for f in files:
        p = os.path.join(root, f)
        try:
            data = open(p, "rb").read()
        except OSError:
            continue
        new = data
        for s in secrets:
            new = new.replace(s.encode(), b"***REDACTED***")
        if new != data:
            open(p, "wb").write(new)
PY
fi
find "$out" \( -name '*.key' -o -name '.secrets.env' -o -name '*secrets*' \) -type f -delete 2>/dev/null || true
echo "diagnostics written to $out"
