#!/usr/bin/env bash
# Spike S-2 test (ADR-006, OQ-1): DuckDB reads a Spark-written Iceberg table via Lakekeeper using
# STS credentials vended from SeaweedFS. Run ON THE SERVER from this directory. Idempotent.
# Exits 0 only if C0-C3 all pass; 1 otherwise. Leaves the stack running.
#
# Sync from a workstation first:
#   ssh $LAB_SERVER mkdir -p lakehouse-v3/spikes
#   rsync -a --exclude secrets spikes/versions.env spikes/s2-duckdb-sts $LAB_SERVER:lakehouse-v3/spikes/
#   ssh $LAB_SERVER 'cd lakehouse-v3/spikes/s2-duckdb-sts && ./test.sh'
# (The Spark image definition is reused from ../s1-catalog-storage/spark; it must be synced too.)
#
# Cleanup: docker compose -p v3-s2 down -v
set -uo pipefail
cd "$(dirname "$0")"

DC=(docker compose -p v3-s2 --env-file ../versions.env --env-file versions.local.env)
declare -A RESULT
fail=0
hdr() { printf '\n==== %s ====\n' "$*"; }
verdict() { RESULT[$1]="$2"; [ "$2" = pass ] || fail=1; printf -- '--> %s: %s  (%s)\n' "$1" "${2^^}" "$3"; }
has() { grep -qP "$1" <<<"$2"; }

./gen-secrets.sh

# ---------------------------------------------------------------- C0 static checks
hdr "C0: compose config + version pinning"
c0=pass; ev=""
if "${DC[@]}" --profile jobs config -q; then ev="config -q OK"; else c0=fail; ev="config -q FAILED"; fi
lit=$(grep -nE '^\s*(image:|FROM )' compose.yaml duckdb/Dockerfile | grep -v '\${' || true)
[ -z "$lit" ] && ev="$ev; all image:/FROM use \${VAR}" || { c0=fail; ev="$ev; literal image refs: $lit"; }
if grep -rn ':latest' compose.yaml duckdb/ versions.local.env >/dev/null; then c0=fail; ev="$ev; :latest found"; fi
"${DC[@]}" --profile jobs config --images | sort -u | sed 's/^/    image: /'
verdict C0 "$c0" "$ev"

# ---------------------------------------------------------------- stack up + bootstrap + Spark writes table
hdr "Stack up, bootstrap, Spark writes s2.events"
"${DC[@]}" up -d --build --wait --wait-timeout 300 postgres seaweedfs lakekeeper duckdb 2>&1 | tail -2
bout=$("${DC[@]}" run --rm -T bootstrap 2>&1) || { echo "$bout"; echo "bootstrap failed"; exit 1; }
echo "$bout" | grep -E '\[bootstrap\]' | sed 's/^/    /'
sout=$("${DC[@]}" run --rm -T spark-job 01_spark_create.sql 2>&1); src=$?
echo "$sout" | grep -E '^S2_|Exception' | sed 's/^/    /'
if [ $src -ne 0 ] || ! has '^S2_SPARK_COUNT\t5\t15.0$' "$sout"; then echo "$sout" | tail -30; echo "Spark setup failed"; exit 1; fi
t0=$(date -u +%Y-%m-%dT%H:%M:%SZ); sleep 1

# ---------------------------------------------------------------- C1
hdr "C1: Lakekeeper vends temporary (STS) credentials for loadTable(s2.events)"
vout=$("${DC[@]}" exec -T duckdb python /opt/s2/probe_vended.py 2>&1)
echo "$vout" | sed 's/^/    /'
c1=pass; ev="VENDED_VERDICT=$(grep -oP '^VENDED_VERDICT \K\S+' <<<"$vout")"
has '^VENDED_VERDICT sts$' "$vout" || c1=fail
has '^VENDED s3.session-token <redacted' "$vout" || { c1=fail; ev="$ev; no session token"; }
exp=$(grep -oP '^VENDED expiration-time \K[0-9]+' <<<"$vout")
if [ -n "$exp" ]; then
  ttl=$(( exp / 1000 - $(date +%s) )); ev="$ev; expires in ${ttl}s"
  { [ "$ttl" -gt 0 ] && [ "$ttl" -le 3600 ]; } || { c1=fail; ev="$ev (not within (0,3600])"; }
else c1=fail; ev="$ev; no expiration-time"; fi
verdict C1 "$c1" "$ev"
echo "    (informational) scope of the vended credentials:"
"${DC[@]}" exec -T duckdb python /opt/s2/scope_probe.py 2>&1 | grep -E '^SCOPE' | cut -c1-90 | sed 's/^/      /'

# ---------------------------------------------------------------- C2
hdr "C2: DuckDB reads the table with ONLY the vended credentials"
dout=$("${DC[@]}" exec -T duckdb python /opt/s2/duck_s2.py 2>&1); drc=$?
echo "$dout" | sed 's/^/    /'
sts_calls=$("${DC[@]}" logs --no-log-prefix --since "$t0" lakekeeper 2>/dev/null | grep -c 'Fetching new STS credentials' || true)
echo "    Lakekeeper 'Fetching new STS credentials' (AssumeRole) log lines since DuckDB/probe start: $sts_calls"
# Static-key audit of the DuckDB container: rendered compose config + live env.
denv=$( { "${DC[@]}" config duckdb 2>/dev/null; docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' v3-s2-duckdb-1; } )
# shellcheck disable=SC1091
. secrets/s3-admin.env
keyhits=$(grep -inE 'access.?key|secret.?key|aws_|s3_admin' <<<"$denv" || true)
grep -qF -e "$S3_ADMIN_ACCESS_KEY" -e "$S3_ADMIN_SECRET_KEY" <<<"$denv" && keyhits="$keyhits ADMIN-KEY-VALUE"
# Negative control: same ATTACH with ACCESS_DELEGATION_MODE 'none' must NOT be able to read.
nout=$("${DC[@]}" exec -T duckdb python /opt/s2/duck_s2.py none 2>&1); nrc=$?
echo "    negative control (delegation none): exit=$nrc $(grep -oP '^DUCK_READ_ERROR \K.{0,160}' <<<"$nout")"
c2=pass; ev=""
[ $drc -eq 0 ] || { c2=fail; ev="duck_s2 exit $drc; "; }
has '^DUCK_ENV_AWS_VARS none$' "$dout" && has '^DUCK_AWS_DIR absent$' "$dout" || { c2=fail; ev="${ev}AWS env/dir present; "; }
has '^DUCK_SECRETS before-attach count=0$' "$dout" || { c2=fail; ev="${ev}session had secrets before ATTACH; "; }
has '^DUCK_READ 5 15.0$' "$dout" || { c2=fail; ev="${ev}wrong/no read result; "; }
nsec=$(grep -c '^DUCK_SECRET after-read' <<<"$dout"); nice=$(grep -cP '^DUCK_SECRET after-read .*provider=iceberg .*key_id_prefix=ASIA$' <<<"$dout")
{ [ "$nsec" -ge 1 ] && [ "$nsec" = "$nice" ]; } || { c2=fail; ev="${ev}secrets after read not all iceberg-vended ASIA ($nice/$nsec); "; }
[ -z "$keyhits" ] || { c2=fail; ev="${ev}static key-like settings in duckdb container: $keyhits; "; }
{ [ "$nrc" -ne 0 ] && has '^DUCK_READ_ERROR .*403' "$nout"; } || { c2=fail; ev="${ev}negative control did not get 403; "; }
[ "$sts_calls" -ge 1 ] || { c2=fail; ev="${ev}no STS AssumeRole logged by Lakekeeper; "; }
[ "$c2" = pass ] && ev="read 5 rows/15.0; 0 secrets before ATTACH; $nsec secret(s) after, all provider=iceberg ASIA (table-scoped); no AWS env/keys in container; delegation=none -> 403; $sts_calls STS AssumeRole(s)"
verdict C2 "$c2" "$ev"

# ---------------------------------------------------------------- C3
hdr "C3: DuckDB INSERT with vended credentials (and Spark sees it)"
vout2=$("${DC[@]}" run --rm -T spark-job 02_spark_verify.sql 2>&1); vrc=$?
echo "$vout2" | grep -E '^S2_|Exception' | sed 's/^/    /'
c3=pass; ev=""
if has '^DUCK_INSERT ok DUCK_AFTER 6 1015.0$' "$dout"; then ev="DuckDB INSERT ok (6 rows, 1015.0)"
else c3=fail; ev="DuckDB INSERT failed: $(grep -oP '^DUCK_INSERT_ERROR \K.{0,300}' <<<"$dout")"; fi
if [ $vrc -eq 0 ] && has '^S2_SPARK_DUCK_ROW\t100\tduck\t1000.0$' "$vout2"; then ev="$ev; Spark reads DuckDB's row"
else c3=fail; ev="$ev; Spark does not see DuckDB's row"; fi
verdict C3 "$c3" "$ev"
echo "    (informational) DuckDB UPDATE/DELETE with vended creds (removes the inserted row):"
"${DC[@]}" exec -T duckdb python /opt/s2/duck_dml.py 2>&1 | sed 's/^/      /'

hdr "Summary"
for k in C0 C1 C2 C3; do echo "  $k ${RESULT[$k]:-fail}"; done
if [ "$fail" = 0 ]; then echo "  OVERALL: PASS"; exit 0; fi
echo "  OVERALL: FAIL"; exit 1
