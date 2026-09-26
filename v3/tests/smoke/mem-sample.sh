#!/usr/bin/env bash
# Memory measurement for CI sizing (CONTRACT Phase 3 exit 5: does `full` fit a 16 GB runner?).
# Samples, every LAB_MEM_SAMPLE_S seconds (default 10), the host's used memory and the
# memory use of THIS lab's containers (compose project from v3/.env, workspaces included:
# they carry the same project label). Nothing outside the project is inspected.
#
#   tests/smoke/mem-sample.sh start DIR   start sampling in the background (DIR/samples.tsv)
#   tests/smoke/mem-sample.sh stop DIR    stop, then print peaks (markdown; also appended to
#                                         $GITHUB_STEP_SUMMARY when set)
#   tests/smoke/mem-sample.sh report DIR  print peaks without stopping
set -uo pipefail
V3=$(cd -P "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cmd=${1:-}
dir=${2:-}
[ -n "$cmd" ] && [ -n "$dir" ] || { echo "usage: mem-sample.sh start|stop|report DIR" >&2; exit 2; }
interval=${LAB_MEM_SAMPLE_S:-10}

project() {
  local p=""
  [ -f "$V3/.env" ] && p=$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' "$V3/.env" | tail -n1)
  [[ "$p" =~ ^[a-z0-9][a-z0-9_-]*$ ]] && printf '%s\n' "$p"
}

# to_mib "1.08GiB" -> 1105.9
to_mib() {
  awk -v v="$1" 'BEGIN {
    n = v + 0; u = v; sub(/^[0-9.]+/, "", u)
    f = (u == "GiB") ? 1024 : (u == "MiB") ? 1 : (u == "KiB") ? 1/1024 : (u == "B") ? 1/1048576 : (u == "GB") ? 953.674 : (u == "MB") ? 0.953674 : (u == "kB") ? 0.000931 : 1
    printf "%.1f\n", n * f }'
}

sample_once() {
  local ts used p ids name usage
  ts=$(date +%s)
  used=$(free -m | awk '/^Mem:/ {print $3}')
  printf '%s\thost\t%s\n' "$ts" "$used"
  p=$(project) || return 0
  ids=$(docker ps -q --filter "label=com.docker.compose.project=$p")
  [ -n "$ids" ] || return 0
  # shellcheck disable=SC2086 # ids are docker IDs, one per word
  docker stats --no-stream --format '{{.Name}}|{{.MemUsage}}' $ids 2>/dev/null |
    while IFS='|' read -r name usage; do
      printf '%s\t%s\t%s\n' "$ts" "$name" "$(to_mib "${usage%% /*}")"
    done
}

report() {
  local f="$dir/samples.tsv"
  [ -s "$f" ] || { echo "mem-sample: no samples in $f"; return 0; }
  awk -F'\t' '
    $2 == "host" { if ($3 > host) host = $3; next }
    { sum[$1] += $3; if ($3 > peak[$2]) peak[$2] = $3 }
    END {
      for (t in sum) if (sum[t] > lab) lab = sum[t]
      printf "| | peak MiB |\n|---|---|\n"
      printf "| host used (free -m) | %d |\n", host
      printf "| this lab, sum at one instant | %d |\n", lab
      n = 0; for (c in peak) names[++n] = c
      for (i = 1; i <= n; i++) for (j = i + 1; j <= n; j++) if (peak[names[j]] > peak[names[i]]) { t = names[i]; names[i] = names[j]; names[j] = t }
      for (i = 1; i <= n; i++) printf "| %s | %d |\n", names[i], peak[names[i]]
    }' "$f"
  printf '\n%s samples, %ss apart; total RAM %s MiB\n' "$(awk -F'\t' '$2=="host"' "$f" | wc -l)" "$interval" \
    "$(free -m | awk '/^Mem:/ {print $2}')"
}

case "$cmd" in
  start)
    mkdir -p "$dir"
    : >"$dir/samples.tsv"
    ( while :; do sample_once >>"$dir/samples.tsv"; sleep "$interval"; done ) >/dev/null 2>&1 &
    echo $! >"$dir/sampler.pid"
    echo "mem-sample: sampling every ${interval}s into $dir/samples.tsv (pid $!)"
    ;;
  stop)
    [ -f "$dir/sampler.pid" ] && kill "$(cat "$dir/sampler.pid")" 2>/dev/null
    rm -f "$dir/sampler.pid"
    out=$(report)
    printf '%s\n' "$out"
    if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
      { echo "### Memory (profile ${LAB_PROFILE:-?})"; echo; printf '%s\n' "$out"; } >>"$GITHUB_STEP_SUMMARY"
    fi
    ;;
  report) report ;;
  *) echo "usage: mem-sample.sh start|stop|report DIR" >&2; exit 2 ;;
esac
