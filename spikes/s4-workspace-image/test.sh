#!/usr/bin/env bash
# Spike S-4 pass criteria. Run on the server from the spike dir. Idempotent: builds (cached),
# brings the stack up (leaves it running), checks everything, exits 0 only if all pass.
#   CLASSIC=1 ./test.sh   also build/run the OQ-2 classic-driver comparison (informational)
set -uo pipefail
cd "$(dirname "$0")"
set -a; . ../versions.env; . ./versions.local.env; set +a
dc() { docker compose -p v3-s4 --env-file ../versions.env --env-file versions.local.env "$@"; }
IMG=lakehouse-workspace:v3-s4-spike
fails=0
pass() { echo "PASS  $*"; }
fail() { echo "FAIL  $*"; fails=$((fails+1)); }
hdr()  { echo; echo "=== $* === (t+${SECONDS}s)"; }
wx()   { dc exec -T "${PINS[@]}" workspace "$@"; }
PINS=(); for v in JUPYTERHUB_VERSION JUPYTERLAB_VERSION JUPYSQL_VERSION JUPYTERLAB_GIT_VERSION \
  JUPYTER_SERVER_PROXY_VERSION JUPYTER_AI_VERSION PYSPARK_VERSION DUCKDB_VERSION \
  PYICEBERG_VERSION TRINO_PYTHON_VERSION DBT_CORE_VERSION DBT_TRINO_VERSION; do
  PINS+=(-e "$v=${!v}"); done

hdr "build (cached; see build.sh for --relock / --no-cache)"
./build.sh >/tmp/v3-s4-build.log 2>&1 || { tail -30 /tmp/v3-s4-build.log; echo "FAIL build"; exit 1; }
tail -1 /tmp/v3-s4-build.log

hdr "1. no network at container start; environment == lockfile"
dc up -d --wait workspace spark-connect >/dev/null 2>&1 || dc up -d workspace spark-connect
for i in $(seq 60); do wx curl -sf -o /dev/null http://127.0.0.1:8888/api/status 2>/dev/null; [ $? = 22 ] && break; sleep 1; done  # 403 = up
if wx curl -sS -m 5 -o /dev/null https://pypi.org 2>/dev/null; then
  fail "workspace can reach the internet (network should be internal)"
else pass "workspace has no internet egress (internal network); everything below ran offline"; fi
tops=$(sed -e 's/#.*//' -e 's/\[.*//' -e 's/=.*//' requirements.in | grep -v '^$' | tr 'A-Z_.' 'a-z--' | sort)
frz=$(wx pip freeze --all | tr 'A-Z_.' 'a-z--' | grep -v -E '^(pip|setuptools|wheel)==' | sort)
lock=$(grep -v '^#' lock/constraints.txt | tr 'A-Z_.' 'a-z--' | sort)
drift=$(comm -23 <(echo "$frz" | grep -v -E "^($(echo "$tops" | paste -sd'|'))==") <(echo "$lock"))
missing=$(comm -13 <(echo "$frz") <(echo "$lock"))
if [ -z "$drift$missing" ]; then
  pass "installed set = requirements.in (versions.env pins) + $(echo "$lock" | wc -l) locked transitive pins, no drift"
else fail "environment drift vs lock: extra=[$drift] missing=[$missing]"; fi
if dc logs workspace 2>&1 | grep -iE 'pip install|downloading|Collecting' ; then
  fail "installs/downloads seen in container start log"; else pass "no install/download in start log"; fi

hdr "2. image size"
bytes=$(docker image inspect -f '{{.Size}}' "$IMG")
echo "   $IMG: $bytes bytes = $(awk "BEGIN{printf \"%.2f GB (%.2f GiB)\", $bytes/1e9, $bytes/2^30}")"
[ "$bytes" -lt 4000000000 ] && pass "image < 4 GB" || fail "image >= 4 GB"

hdr "3a. imports with pinned versions"
wx python /opt/s4-tests/check_imports.py && pass "all imports at pinned versions" || fail "imports"
hs=$(wx jupyterhub-singleuser --version 2>&1 | tail -1)
[ "$hs" = "$JUPYTERHUB_VERSION" ] && pass "jupyterhub-singleuser $hs matches JupyterHub pin" \
  || fail "jupyterhub-singleuser version '$hs' != $JUPYTERHUB_VERSION"

hdr "3b. dbt --version shows both packages"
dv=$(wx dbt --version 2>&1); echo "$dv" | sed 's/^/   /'
echo "$dv" | grep -q "installed: $DBT_CORE_VERSION" && echo "$dv" | grep -qE "trino: +$DBT_TRINO_VERSION" \
  && pass "dbt-core $DBT_CORE_VERSION + dbt-trino $DBT_TRINO_VERSION" || fail "dbt --version"
wx bash -c 'rm -rf /tmp/dbt_smoke && cp -r /opt/s4-tests/dbt_smoke /tmp/ && cd /tmp/dbt_smoke && dbt parse --profiles-dir . >/tmp/dbt_parse.log 2>&1' \
  && pass "dbt parse of a trino-profile project works offline" || { wx tail -20 /tmp/dbt_parse.log; fail "dbt parse"; }

hdr "3c. DuckDB iceberg offline"
wx python /opt/s4-tests/check_duckdb_iceberg.py && pass "duckdb iceberg" || fail "duckdb iceberg"
ep=$(docker image inspect -f '{{json .Config.Entrypoint}} cmd={{json .Config.Cmd}}' "$IMG"); echo "   image $ep"
# A spawner that overrides cmd, on a brand-new empty home: the ENTRYPOINT still wires DuckDB.
fresh="/tmp/s4-fresh-home-$$"
if dc run --rm --no-deps -T -e HOME="$fresh" workspace python /opt/s4-tests/check_duckdb_iceberg.py >/tmp/v3-s4-cmdov.log 2>&1; then
  pass "cmd override (python ...) on an empty \$HOME: iceberg loads offline ($(grep -c "'iceberg', True, True" /tmp/v3-s4-cmdov.log) iceberg row loaded+installed)"
else cat /tmp/v3-s4-cmdov.log; fail "duckdb iceberg with cmd override"; fi
# Negative control (informational): bypassing the ENTRYPOINT itself leaves DuckDB unwired.
if dc run --rm --no-deps -T -e HOME="$fresh" --entrypoint python workspace /opt/s4-tests/check_duckdb_iceberg.py >/dev/null 2>&1; then
  echo "   control: --entrypoint override also loads iceberg (unexpected)"
else echo "   control: --entrypoint override (bypassing start-workspace.sh) cannot load iceberg offline, as expected"; fi

hdr "3d. code-server through jupyter-server-proxy"
# jupyter_server_mcp (a jupyter-ai dependency) adds its own entry to 'jupyter server list',
# so select the Jupyter server on 8888 explicitly.
tok=$(wx python -c 'import json,subprocess;print(next(d["token"] for d in map(json.loads,subprocess.check_output(["jupyter","server","list","--json"]).splitlines()) if d.get("port")==8888))')
code=$(wx curl -sS -L -m 90 -o /tmp/cs.html -w '%{http_code} %{url_effective}' -H "Authorization: token $tok" http://127.0.0.1:8888/code-server/)
echo "   GET /code-server/ -> $code"
if [[ "$code" == "200 http://127.0.0.1:8888/code-server/"* ]] && wx grep -q 'workbench' /tmp/cs.html; then
  pass "code-server workbench HTML served via /code-server/ ($(wx grep -c workbench /tmp/cs.html) 'workbench' refs)"
else fail "code-server proxy"; fi
wx curl -sS -H "Authorization: token $tok" http://127.0.0.1:8888/server-proxy/servers-info \
  | grep -q '"code-server"' && pass "code-server registered as JupyterLab launcher entry" || fail "launcher entry"

hdr "3e. jupyter-ai enabled"
# jupyter-ai 3.x is a metapackage (jupyter_ai/ is empty); the extension is its components.
AI_SERVER="jupyter_ai_router jupyter_ai_persona_manager jupyter_ai_acp_client jupyter_ai_chat_commands jupyter_ai_tools jupyterlab_chat"
AI_LAB="@jupyter-ai/router @jupyter-ai/persona-manager @jupyter-ai/acp-client @jupyter-ai/chat-commands jupyterlab-chat-extension"
nocolor() { sed 's/\x1b\[[0-9;]*m//g'; }
sx=$(wx jupyter server extension list 2>&1 | nocolor)
lx=$(wx jupyter labextension list 2>&1 | nocolor)
lg=$(dc logs workspace 2>&1)
ok=1
for e in $AI_SERVER; do
  en=no; ld=no
  echo "$sx" | grep -qE "^ *$e .*enabled" && en=yes
  echo "$lg" | grep -qE "$e \| extension was successfully loaded" && ld=yes
  echo "   server ext $e: enabled=$en loaded-by-running-server=$ld"
  [ "$en$ld" = yesyes ] || ok=0
done
for e in $AI_LAB; do
  if echo "$lx" | grep -qE "^ *$e v[^ ]+ enabled +OK"; then echo "   lab ext $e: enabled OK"; else echo "   lab ext $e: MISSING"; ok=0; fi
done
echo "   ACP personas registered: $(wx python -c 'from importlib.metadata import entry_points as e; print(" ".join(sorted(x.name for x in e(group="jupyter_ai.personas"))))')"
[ "$ok" = 1 ] && pass "jupyter-ai $JUPYTER_AI_VERSION server + lab extensions enabled and loaded" || fail "jupyter-ai extensions"

hdr "4. OQ-2 Spark Connect (workspace -> spark-connect:15002)"
for i in $(seq 90); do dc logs spark-connect 2>&1 | grep -q 'Spark Connect server started' && break; sleep 2; done
wx python /opt/s4-tests/check_spark_connect.py && pass "spark connect" || fail "spark connect"
echo "   memory now (docker stats):"
docker stats --no-stream --format '   {{.Name}} {{.MemUsage}}' v3-s4-workspace-1 v3-s4-spark-connect-1

if [ "${CLASSIC:-0}" = 1 ]; then
  hdr "OQ-2 comparison: classic driver (informational)"
  ./build.sh --classic >/tmp/v3-s4-build-classic.log 2>&1 || tail -20 /tmp/v3-s4-build-classic.log
  cb=$(docker image inspect -f '{{.Size}}' lakehouse-workspace:v3-s4-spike-classic)
  echo "   classic image: $cb bytes (+$(( (cb-bytes)/1000000 )) MB vs connect image)"
  dc --profile classic run --rm -T workspace-classic python /opt/s4-tests/check_spark_classic.py
fi

echo; if [ "$fails" = 0 ]; then echo "S-4 RESULT: ALL CRITERIA PASS"; exit 0; fi
echo "S-4 RESULT: $fails check(s) FAILED"; exit 1
