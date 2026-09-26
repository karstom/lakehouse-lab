#!/usr/bin/env bash
# Workspace-kernel loop (CONTRACT Phase 4, "Required: root-cause the intermittent
# workspace-kernel failures"). NOT part of `lab test`: a reproduction harness for a dev lab.
#
# For N iterations, for each user: headless login -> spawn -> kernel -> Trino (+ Spark) step
# -> stop, through the same code as smoke checks 8-10 (tests/smoke/kernel_loop.py in the
# `smoke` container). Meanwhile this script follows the logs of every workspace container of
# THIS project (they are auto-removed on stop, so their logs would be lost), and afterwards
# saves the JupyterHub and docker-proxy logs and, per failed iteration, the slice of every
# log for that iteration's time window.
#
# Usage: tests/smoke/kernel-loop.sh [--iterations N] [--users a,b] [--label TEXT] [--no-build]
#          [--stress N]  N probes per user in ONE workspace each (no re-spawn between them)
#          [--race N]    N bare kernel-websocket round trips per mode (immediate/handshake)
# Output: $LAB_SMOKE_OUT/kernel-loop (default tests/smoke/out/kernel-loop):
#   iterations.jsonl, summary.json, loop.log, logs/<service>.log (hub, proxy, engines),
#   logs/ws/<container>-<id>.log, failures/<iter>-<user>/{record.json,*.log}
# Selects workspace containers only by this project's labels (DEC_V3_WORKSPACE_CLEANUP_BY_LABEL).
set -uo pipefail

iterations=30 users=alice,eddie,anna,victor label="" build=(--build) extra=()
while [ $# -gt 0 ]; do
  case "$1" in
    --iterations) iterations=$2; shift 2 ;;
    --users) users=$2; shift 2 ;;
    --label) label=$2; shift 2 ;;
    --no-build) build=(); shift ;;
    --stress) extra+=(--stress "$2"); shift 2 ;;
    --race) extra+=(--race "$2"); shift 2 ;;
    *) echo "usage: kernel-loop.sh [--iterations N] [--users a,b] [--label TEXT] [--no-build] [--stress N | --race N]" >&2; exit 2 ;;
  esac
done
[[ "$iterations" =~ ^[0-9]+$ ]] || { echo "kernel-loop: --iterations must be a number" >&2; exit 2; }
[[ "$users" =~ ^[a-z0-9,_-]+$ ]] || { echo "kernel-loop: bad --users" >&2; exit 2; }

V3_DIR=$(cd -P "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
# shellcheck source=../../installer/lib.sh
. "$V3_DIR/installer/lib.sh"
[ -f "$LAB_ENV_FILE" ] || { echo "kernel-loop: no $LAB_ENV_FILE (run install.sh first)" >&2; exit 2; }
lab_settings
valid_project_name "$COMPOSE_PROJECT_NAME" || { echo "kernel-loop: bad project name" >&2; exit 2; }
P=$COMPOSE_PROJECT_NAME

base=${LAB_SMOKE_OUT:-$V3_DIR/tests/smoke/out}
out="$base/kernel-loop"
mkdir -p "$out/logs/ws" "$out/failures"
: >"$out/iterations.jsonl"
start_ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Follow every workspace container of this project as it appears (exact labels, AND-ed).
follow_workspaces() {
  local id name
  declare -A seen=()
  while :; do
    while read -r id name; do
      [ -n "$id" ] || continue
      [ -n "${seen[$id]:-}" ] && continue
      seen[$id]=1
      docker logs -f -t "$id" >"$out/logs/ws/${name}-${id}.log" 2>&1 &
    done < <(docker ps --no-trunc --filter "label=com.docker.compose.project=$P" \
               --filter "label=lab.role=workspace" --format '{{.ID}} {{.Names}}' 2>/dev/null)
    sleep 1
  done
}
follow_workspaces &
follower=$!
trap 'kill "$follower" 2>/dev/null; pkill -P "$follower" 2>/dev/null' EXIT

echo "kernel-loop: project $P, profile $LAB_PROFILE, $iterations iteration(s) x users $users -> $out"
rc=0
LAB_SMOKE_OUT="$base" lab_compose --profile test run --rm ${build[@]+"${build[@]}"} \
  --user "$(id -u):$(id -g)" -e HOME=/tmp/smoke-home -e LAB_PROFILE="$LAB_PROFILE" \
  smoke kernel-loop --iterations "$iterations" --users "$users" --label "$label" ${extra[@]+"${extra[@]}"} \
  2>&1 | tee "$out/loop.log" || rc=1
[ "${PIPESTATUS[0]}" = 0 ] || rc=1

kill "$follower" 2>/dev/null; pkill -P "$follower" 2>/dev/null
# The hub and proxy (auth, spawn, Docker calls) and the engines a probe step talks to (a hang
# in user code shows up as a request that never finished there). Absent services are skipped.
for svc in jupyterhub docker-proxy spark-connect trino lakekeeper; do
  lab_compose logs --no-color --timestamps --since "$start_ts" "$svc" >"$out/logs/$svc.log" 2>&1 || true
done

# Per failed iteration: its record and the slice of each log for [start - 5 s, end + 5 s].
python3 - "$out" <<'PY'
import datetime, glob, json, os, re, sys
out = sys.argv[1]
TS = re.compile(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z?)")
def parse(s):
    s = s.rstrip("Z")
    if "." in s:
        head, frac = s.split(".")
        s = f"{head}.{frac[:6]}"
    return datetime.datetime.fromisoformat(s).replace(tzinfo=datetime.timezone.utc)
logs = glob.glob(os.path.join(out, "logs", "*.log")) + glob.glob(os.path.join(out, "logs", "ws", "*.log"))
n = 0
for line in open(os.path.join(out, "iterations.jsonl")):
    rec = json.loads(line)
    if rec.get("outcome") == "ok":
        continue
    n += 1
    lo = parse(rec["start"]) - datetime.timedelta(seconds=5)
    hi = parse(rec["end"]) + datetime.timedelta(seconds=5)
    d = os.path.join(out, "failures", f"{rec['iter']:03d}-{rec['user']}")
    os.makedirs(d, exist_ok=True)
    json.dump(rec, open(os.path.join(d, "record.json"), "w"), indent=1)
    for path in logs:
        keep = []
        for l in open(path, errors="replace"):
            m = TS.search(l[:80])
            if m:
                try:
                    t = parse(m.group(1))
                except ValueError:
                    continue
                if lo <= t <= hi:
                    keep.append(l)
        if keep:
            open(os.path.join(d, os.path.basename(path)), "w").writelines(keep)
print(f"kernel-loop: {n} failed iteration(s) with evidence under {out}/failures")
PY
exit "$rc"
