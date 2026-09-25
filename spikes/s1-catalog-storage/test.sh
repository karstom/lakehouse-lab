#!/usr/bin/env bash
# Spike S-1 test. Run ON THE SERVER from this directory (idempotent; exits 0 only if all criteria pass).
# Exit codes: 0 = all pass, 2 = PARTIAL (only C3b fails, for Trino), 1 = anything else fails.
#
# Sync from a workstation first:
#   ssh $LAB_SERVER mkdir -p lakehouse-v3/spikes
#   rsync -a --exclude secrets spikes/versions.env spikes/s1-catalog-storage $LAB_SERVER:lakehouse-v3/spikes/
#   ssh $LAB_SERVER 'cd lakehouse-v3/spikes/s1-catalog-storage && ./test.sh'
#
# Leaves the stack running. Cleanup: docker compose -p v3-s1 down -v
set -uo pipefail
cd "$(dirname "$0")"

DC=(docker compose -p v3-s1 --env-file ../versions.env --env-file versions.local.env)
declare -A RESULT
fail=0
hdr() { printf '\n==== %s ====\n' "$*"; }
verdict() { # name pass|fail evidence
  RESULT[$1]="$2"; [ "$2" = pass ] || fail=1
  printf -- '--> %s: %s  (%s)\n' "$1" "${2^^}" "$3"
}
sign_requests() { # distinct remote-sign requests seen by Lakekeeper since $1
  "${DC[@]}" logs --no-log-prefix --since "$1" lakekeeper 2>/dev/null \
    | grep '/v1/aws/s3/sign' | grep -o '"request_id":"[^"]*"' | sort -u | wc -l
}

./gen-secrets.sh

# ---------------------------------------------------------------- criterion 4 (static checks)
hdr "C4: compose config + version pinning"
c4=pass; ev=""
if "${DC[@]}" config -q; then ev="config -q OK"; else c4=fail; ev="config -q FAILED"; fi
# every image:/FROM must be a ${VAR} reference; no :latest anywhere
lit=$(grep -nE '^\s*(image:|FROM )' compose.yaml spark/Dockerfile | grep -v '\${' || true)
if [ -n "$lit" ]; then c4=fail; ev="$ev; literal image refs: $lit"; else ev="$ev; all image:/FROM use \${VAR}"; fi
if grep -rn ':latest' compose.yaml spark/ trino/ bootstrap/ >/dev/null; then c4=fail; ev="$ev; :latest found"; fi
"${DC[@]}" config --images | sed 's/^/    image: /'
verdict C4 "$c4" "$ev"

# ---------------------------------------------------------------- bring up + bootstrap
hdr "Stack up (build uses cached layers when unchanged)"
"${DC[@]}" up -d --build --wait --wait-timeout 300 postgres seaweedfs lakekeeper trino spark-master spark-worker 2>&1 | tail -3
bout=$("${DC[@]}" run --rm -T bootstrap 2>&1); bs=$?
echo "$bout" | grep -E '\[bootstrap\]' | sed 's/^/    /'
[ "$bs" = 0 ] || { echo "$bout"; echo "bootstrap failed (exit $bs)"; exit 1; }

# ---------------------------------------------------------------- criterion 1
hdr "C1: Spark creates namespace + table and inserts rows (REST catalog, remote signing)"
t0=$(date -u +%Y-%m-%dT%H:%M:%SZ)
out=$("${DC[@]}" run --rm -T spark-job 01_spark_create.sql 2>&1); rc=$?
echo "$out" | grep -E '^S1_|Exception' | sed 's/^/    /'
sleep 1; s1=$(sign_requests "$t0")
echo "    Lakekeeper remote-sign requests during Spark job: $s1"
if [ $rc -eq 0 ] && echo "$out" | grep -qP '^S1_SPARK_COUNT\t5$' && [ "$s1" -gt 0 ]; then
  verdict C1 pass "5 rows, 1 snapshot, $s1 remote-sign requests"
else echo "$out" | grep -vE '^\s+at ' | tail -40; verdict C1 fail "rc=$rc sign=$s1"; fi

# ---------------------------------------------------------------- criterion 2
hdr "C2: Trino reads, UPDATEs, DELETEs; Spark sees Trino's snapshots"
t1=$(date -u +%Y-%m-%dT%H:%M:%SZ)
tout=$("${DC[@]}" exec -T trino trino --output-format TSV --file /opt/spikes/sql/02_trino.sql 2>&1); trc=$?
echo "$tout" | sed 's/^/    /'
sleep 1; s2=$(sign_requests "$t1")
echo "    Lakekeeper remote-sign requests during Trino: $s2"
sout=$("${DC[@]}" run --rm -T spark-job 03_spark_verify.sql 2>&1); src=$?
echo "$sout" | grep -E '^S1_|Exception' | sed 's/^/    /'
rows=$(echo "$sout" | grep -P '^S1_SPARK_ROWS' | cut -f2- | tr '\t\n' ',;')
trino_snaps=$(echo "$sout" | grep -P '^S1_SPARK_SNAP\t.*\ttrue$' | wc -l)
if [ $trc -eq 0 ] && [ $src -eq 0 ] \
   && echo "$tout" | grep -qP '^S1_TRINO_COUNT\t5$' && echo "$tout" | grep -qP '^S1_TRINO_AFTER\t3\t305.0$' \
   && [ "$rows" = "1,click,100.0;2,click,200.0;5,buy,5.0;" ] && [ "$trino_snaps" -ge 2 ]; then
  verdict C2 pass "Trino read 5, UPDATE 2 + DELETE 2; Spark sees 3 rows [$rows] and $trino_snaps Trino snapshots"
else verdict C2 fail "trino rc=$trc spark rc=$src rows=[$rows] trino_snaps=$trino_snaps"; fi

# ---------------------------------------------------------------- criterion 3
# Criterion 3 = "no static S3 keys in engine configs" (C3a) AND "storage access is via Lakekeeper
# remote signing" (C3b, for EVERY engine). C3b is asserted per engine; Trino 483 cannot remote-sign,
# so C3b FAILS by design and test.sh exits non-zero. C3c records the fallback (vended STS scoping).
hdr "C3a: no static S3 keys in Spark/Trino rendered configs or env"
c3a=pass; ev=""
# shellcheck disable=SC1091
. secrets/s3-admin.env
rendered=$( {
  "${DC[@]}" config spark-master spark-worker trino 2>/dev/null
  "${DC[@]}" --profile jobs config spark-job 2>/dev/null
  "${DC[@]}" exec -T spark-master cat /opt/spark/conf/spark-defaults.conf
  "${DC[@]}" exec -T spark-worker cat /opt/spark/conf/spark-defaults.conf
  "${DC[@]}" exec -T trino sh -c 'cat /etc/trino/catalog/*.properties /etc/trino/config.properties'
  for s in spark-master spark-worker trino; do docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "v3-s1-$s-1"; done
} )
pat='access-key|secret-key|access\.key|secret\.key|aws_access_key_id|aws_secret_access_key|AWS_ACCESS_KEY|AWS_SECRET|s3\.aws-|fs\.s3a\.(access|secret)'
hits=$(echo "$rendered" | grep -vE '^\s*#' | grep -inE "$pat" || true)
if [ -n "$hits" ]; then c3a=fail; ev="key-like settings found: $hits"; else ev="no key-like settings in $(echo "$rendered" | wc -l) lines of rendered engine config/env"; fi
if echo "$rendered" | grep -qF -e "$S3_ADMIN_ACCESS_KEY" -e "$S3_ADMIN_SECRET_KEY"; then c3a=fail; ev="$ev; ADMIN KEY VALUE LEAKED"; else ev="$ev; admin key values absent"; fi
verdict C3a "$c3a" "$ev"

hdr "C3b: storage access via Lakekeeper REMOTE SIGNING for every engine"
probe=$("${DC[@]}" exec -T spark-master python3 - < probe_catalog.py 2>&1)
echo "$probe" | sed 's/^/    /'
spark_rs=pass; sev="Spark: $s1 remote-sign requests"
[ "${s1:-0}" -gt 0 ] || { spark_rs=fail; sev="Spark: no remote-sign requests"; }
echo "$probe" | grep '^PROBE remote-signing' | grep -q '"s3.remote-signing-enabled": "true"' || { spark_rs=fail; sev="$sev; catalog offers no remote-signing config"; }
echo "$probe" | grep '^PROBE remote-signing' | grep -q 's3.access-key-id' && { spark_rs=fail; sev="$sev; remote-signing mode leaks keys"; }
trino_rs=pass; tev="Trino: $s2 remote-sign requests"
if [ "${s2:-0}" -le 0 ]; then
  trino_rs=fail
  tev="Trino: 0 remote-sign requests -- Trino 483 supports only vended-credentials (no remote-signing option in io.trino_trino-iceberg-483.jar; upstream trinodb/trino#21189)"
fi
echo "    Spark remote signing: ${spark_rs^^} ($sev)"
echo "    Trino remote signing: ${trino_rs^^} ($tev)"
if [ "$spark_rs" = pass ] && [ "$trino_rs" = pass ]; then c3b=pass; else c3b=fail; fi
verdict C3b "$c3b" "$sev; $tev"

hdr "C3c (informational, fallback): Trino's vended STS creds exist and are table-scoped"
echo "$probe" | grep '^PROBE vended-credentials' | grep -q '"s3.access-key-id": "ASIA' \
  && echo "    Lakekeeper vends ASIA... STS credentials (vended-credentials mode)" \
  || echo "    WARNING: no STS credentials vended"
scope=$("${DC[@]}" exec -T spark-master python3 - < scope_probe.py 2>&1)
echo "$scope" | sed 's/^/    /'
echo "    (C3c does not change the exit status; it evidences the proposed ADR-006 fallback)"

hdr "Summary"
for k in C1 C2 C3a C3b C4; do echo "  $k ${RESULT[$k]:-fail}"; done
if [ "$fail" = 0 ]; then echo "  OVERALL: PASS"; exit 0; fi
if [ "${RESULT[C1]:-}" = pass ] && [ "${RESULT[C2]:-}" = pass ] && [ "${RESULT[C3a]:-}" = pass ] \
   && [ "${RESULT[C4]:-}" = pass ] && [ "$spark_rs" = pass ]; then
  echo "  OVERALL: PARTIAL -- criterion 3 not met: Trino cannot remote-sign (uses vended STS). Exit 2."
  exit 2
fi
echo "  OVERALL: FAIL"; exit 1
