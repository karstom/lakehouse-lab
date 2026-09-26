#!/usr/bin/env bash
# Installer unit tests. No Docker daemon needed: install.sh and lab run against a copied
# tree with a fake 'docker' on PATH that records compose calls.
# SC2015: "cond && t_pass || t_fail" is fine here (t_pass always succeeds).
# SC2016: single-quoted $ patterns are intentional literals.
# shellcheck disable=SC2015,SC2016
set -uo pipefail
HERE=$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SRC=$(cd -P "$HERE/../.." && pwd)
# shellcheck source=testlib.sh
. "$HERE/testlib.sh"

WORK=$(mktemp -d "${TMPDIR:-/tmp}/lab-inst-unit.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
export NO_COLOR=1

# Fake docker first on PATH.
mkdir -p "$WORK/bin"
cp "$HERE/fixtures/docker-shim.sh" "$WORK/bin/docker"
chmod +x "$WORK/bin/docker"
export PATH="$WORK/bin:$PATH"
export SHIM_LOG="$WORK/compose.log"

# Library functions, sourced against a scratch V3_DIR.
V3_DIR="$WORK/libtree"; mkdir -p "$V3_DIR"
# shellcheck source=../../installer/lib.sh
. "$SRC/installer/lib.sh"
# shellcheck source=../../installer/checks.sh
. "$SRC/installer/checks.sh"
# shellcheck source=../../installer/domain.sh
. "$SRC/installer/domain.sh"
# shellcheck source=../../installer/secrets.sh
. "$SRC/installer/secrets.sh"
# shellcheck source=../../installer/ca.sh
. "$SRC/installer/ca.sh"

CONTRACT_SECRETS="POSTGRES_PASSWORD KEYCLOAK_DB_PASSWORD LAKEKEEPER_DB_PASSWORD KC_ADMIN_USER KC_ADMIN_PASSWORD LAB_ADMIN_USER LAB_ADMIN_PASSWORD SEAWEEDFS_ADMIN_ACCESS_KEY SEAWEEDFS_ADMIN_SECRET_KEY SEAWEEDFS_STS_SIGNING_KEY LAKEKEEPER_PG_ENCRYPTION_KEY OIDC_CLIENT_SECRET_TRINO OIDC_CLIENT_SECRET_LAKEKEEPER OIDC_CLIENT_SECRET_CONSOLE OIDC_CLIENT_SECRET_SYNC OIDC_CLIENT_SECRET_JUPYTERHUB JUPYTERHUB_CRYPT_KEY TRINO_INTERNAL_SECRET LAB_TEST_USER_PASSWORD OIDC_CLIENT_SECRET_AIRFLOW OIDC_CLIENT_SECRET_BATCH AIRFLOW_DB_PASSWORD AIRFLOW_FERNET_KEY AIRFLOW_JWT_SECRET OIDC_CLIENT_SECRET_SUPERSET SUPERSET_SECRET_KEY SUPERSET_DB_PASSWORD CONSOLE_COOKIE_SECRET"
CONTRACT_ENV="COMPOSE_PROJECT_NAME LAB_DOMAIN LAB_HTTPS_PORT LAB_HTTP_PORT LAB_PROFILE LAB_STATE_DIR LAB_TZ"
mode_of() { stat -c '%a' "$1"; }
sha() { sha256sum "$1" | cut -d' ' -f1; }

echo "== env file helpers"
t_begin env
f="$WORK/e.env"
printf '# comment\nA=1\nB=x=y\nC=keep\n' >"$f"; chmod 640 "$f"
env_set "$f" A 2; env_set "$f" D 'p/q+r=='
assert_eq "replace in place" 2 "$(env_get "$f" A)"
assert_eq "value with '='" "x=y" "$(env_get "$f" B)"
assert_eq "append new key" 'p/q+r==' "$(env_get "$f" D)"
assert_eq "other keys untouched" keep "$(env_get "$f" C)"
assert_eq "comment kept" "# comment" "$(head -n1 "$f")"
assert_eq "mode preserved" 640 "$(mode_of "$f")"
assert_eq "absent key is empty" "" "$(env_get "$f" NOPE)"
printf 'X=$(touch %s/pwned)\n' "$WORK" >"$WORK/evil.env"
( load_env "$WORK/evil.env"; [ "$X" = "\$(touch $WORK/pwned)" ] ) && t_pass "load_env keeps values literal" || t_fail "load_env keeps values literal"
assert_not "load_env never evaluates" test -e "$WORK/pwned"

echo "== version_ge"
t_begin version
assert "29.1.3 >= 24.0.0" version_ge 29.1.3 24.0.0
assert "24.0.0 >= 24.0.0" version_ge 24.0.0 24.0.0
assert_not "23.0.15 < 24.0.0" version_ge 23.0.15 24.0.0
assert "2.40.3+ds1-0ubuntu1 >= 2.20.0" version_ge "2.40.3+ds1-0ubuntu1" 2.20.0
assert "5.1.4 >= 2.20.0" version_ge 5.1.4 2.20.0
assert_not "2.19.1 < 2.20.0" version_ge 2.19.1 2.20.0
assert "2.20 >= 2.20.0" version_ge 2.20 2.20.0

echo "== domain"
t_begin domain
assert_eq "dashed sslip" "10-0-0-5.sslip.io" "$(sslip_domain 10.0.0.5)"
assert_not "bad ip rejected" sslip_domain 10.0.0.256
for d in lab.localhost localhost 10-0-0-5.sslip.io lab.example.com a-b.c; do
  assert "valid: $d" valid_domain "$d"
done
for d in "" LAB.localhost -lab.localhost lab-.localhost .lab lab. "lab..x" "lab_x.io" "a b.io" "lab.localhost/x"; do
  assert_not "invalid: '$d'" valid_domain "$d"
done
assert_eq "--domain lowercases" "lab.example.com" "$(resolve_domain_arg Lab.Example.COM 2>/dev/null)"
assert_not "--domain rejects junk" resolve_domain_arg 'x;rm -rf' 2>/dev/null
if ip=$(detect_host_ip); then
  assert "detect_host_ip gives IPv4" valid_ipv4 "$ip"
  assert_match "--domain sslip" '^[0-9]+-[0-9]+-[0-9]+-[0-9]+\.sslip\.io$' "$(resolve_domain_arg sslip)"
else
  t_pass "detect_host_ip unavailable here (skipped)"
fi
assert "is_localhost_domain lab.localhost" is_localhost_domain lab.localhost
assert_not "is_localhost_domain sslip" is_localhost_domain 10-0-0-5.sslip.io

echo "== WSL detection"
t_begin wsl
echo "Linux version 6.6.114.1-microsoft-standard-WSL2" >"$WORK/pv-wsl"
echo "Linux version 6.8.0-139-generic (buildd@lcy02)" >"$WORK/pv-linux"
( unset WSL_DISTRO_NAME; is_wsl "$WORK/pv-wsl" ) && t_pass "WSL2 kernel detected" || t_fail "WSL2 kernel detected"
( unset WSL_DISTRO_NAME; is_wsl "$WORK/pv-linux" ) && t_fail "plain Linux not WSL" || t_pass "plain Linux not WSL"
( WSL_DISTRO_NAME=Ubuntu is_wsl "$WORK/pv-linux" ) && t_pass "WSL_DISTRO_NAME detected" || t_fail "WSL_DISTRO_NAME detected"

echo "== secrets"
t_begin secrets
s="$WORK/s1.env"
ensure_secrets "$s" >/dev/null
assert_eq "mode 600" 600 "$(mode_of "$s")"
for k in $CONTRACT_SECRETS; do
  v=$(env_get "$s" "$k")
  if [ -z "$v" ]; then t_fail "$k present"; continue; fi
  if [ "$k" = SEAWEEDFS_STS_SIGNING_KEY ]; then
    assert_eq "$k is 32 random bytes (base64)" 32 "$(printf '%s' "$v" | base64 -d 2>/dev/null | wc -c)"
  elif [ "$k" = AIRFLOW_FERNET_KEY ]; then
    # Fernet format: URL-safe base64 of 32 bytes (padded with one '=').
    assert_match "$k URL-safe base64" '^[A-Za-z0-9_-]{43}=$' "$v"
    assert_eq "$k is 32 random bytes" 32 "$(printf '%s' "$v" | tr -- '-_' '+/' | base64 -d 2>/dev/null | wc -c)"
  else
    assert_match "$k URL-safe" '^[A-Za-z0-9._-]+$' "$v"
    # oauth2-proxy uses it as an AES key: exactly 16, 24 or 32 bytes (we generate 32).
    [ "$k" != CONSOLE_COOKIE_SECRET ] || assert_eq "$k is 32 chars" 32 "${#v}"
  fi
done
assert_match "DB password length" '^[0-9a-f]{48}$' "$(env_get "$s" POSTGRES_PASSWORD)"
assert_match "admin password strength" '^[A-Za-z0-9]{20}$' "$(env_get "$s" LAB_ADMIN_PASSWORD)"
# JupyterHub needs a 32-byte key, hex-encoded (enable_auth_state).
assert_match "JUPYTERHUB_CRYPT_KEY is 32 bytes hex" '^[0-9a-f]{64}$' "$(env_get "$s" JUPYTERHUB_CRYPT_KEY)"
h1=$(sha "$s"); ensure_secrets "$s" >/dev/null
assert_eq "re-run changes nothing" "$h1" "$(sha "$s")"
pg=$(env_get "$s" POSTGRES_PASSWORD)
grep -v '^OIDC_CLIENT_SECRET_CONSOLE=' "$s" >"$s.tmp" && mv "$s.tmp" "$s"; chmod 644 "$s"
ensure_secrets "$s" >/dev/null
assert "missing key regenerated" env_has "$s" OIDC_CLIENT_SECRET_CONSOLE
assert_eq "existing key kept" "$pg" "$(env_get "$s" POSTGRES_PASSWORD)"
assert_eq "mode repaired to 600" 600 "$(mode_of "$s")"
ensure_secrets "$WORK/s2.env" >/dev/null
assert_not "two installs get different secrets" test "$(env_get "$s" LAB_ADMIN_PASSWORD)" = "$(env_get "$WORK/s2.env" LAB_ADMIN_PASSWORD)"
dupes=$(grep -v '^#' "$s" | cut -d= -f1 | sort | uniq -d)
assert_eq "no duplicate keys" "" "$dupes"
# No weak RNG anywhere in the installer (ISSUE_WEAK_CREDENTIAL_RNG).
if grep -nE '\$RANDOM|\$\{RANDOM|shuf |date \+%s%N' "$SRC/install.sh" "$SRC/lab" "$SRC"/installer/*.sh | grep -vE '^[^:]+:[0-9]+:[[:space:]]*#' | grep -q .; then
  t_fail "no \$RANDOM/weak RNG in installer sources"
else
  t_pass "no \$RANDOM/weak RNG in installer sources"
fi

echo "== CA"
t_begin ca
cad="$WORK/state/ca"
ca_create "$cad" >/dev/null
assert "root.crt exists" test -s "$cad/root.crt"
assert_eq "root.key mode 600" 600 "$(mode_of "$cad/root.key")"
assert_contains "basicConstraints CA:TRUE" "CA:TRUE" "$(openssl x509 -in "$cad/root.crt" -noout -text)"
assert_contains "keyCertSign usage" "Certificate Sign" "$(openssl x509 -in "$cad/root.crt" -noout -text)"
assert "valid for 9.9+ years" openssl x509 -in "$cad/root.crt" -noout -checkend $((3640 * 86400))
assert_not "not valid past 10 years + 1 day" openssl x509 -in "$cad/root.crt" -noout -checkend $((3651 * 86400))
assert_contains "key is PEM PKCS8" "BEGIN PRIVATE KEY" "$(head -n1 "$cad/root.key")"
fp=$(ca_fingerprint "$cad/root.crt")
ca_create "$cad" >/dev/null
assert_eq "re-run keeps the same root" "$fp" "$(ca_fingerprint "$cad/root.crt")"
mv "$cad/root.key" "$WORK/key.bak"
assert_not "missing key -> error" ca_create "$cad" 2>/dev/null
assert_eq "missing key -> root not regenerated" "$fp" "$(ca_fingerprint "$cad/root.crt")"
assert_not "missing key -> no new key written" test -e "$cad/root.key"
openssl ecparam -name prime256v1 -genkey -noout -out "$cad/root.key" 2>/dev/null
assert_not "mismatched key -> error" ca_create "$cad" 2>/dev/null
mv "$WORK/key.bak" "$cad/root.key"
assert "restored key -> ok" ca_create "$cad"
assert_eq "no temp dirs left" "" "$(find "$cad" -name '.new.*')"

echo "== install.sh (fake docker)"
t_begin install
T="$WORK/tree"; make_tree "$T"
: >"$SHIM_LOG"
out=$("$T/install.sh" --non-interactive --domain lab.localhost --https-port 18443 --http-port 18080 \
  --project-name v3-p1-inst --seed-test-users 2>&1); rc=$?
assert_eq "install exit 0" 0 "$rc"
[ "$rc" = 0 ] || printf '%s\n' "$out"
for k in $CONTRACT_ENV; do assert "$k in .env" env_has "$T/.env" "$k"; done
assert_eq ".env project" v3-p1-inst "$(env_get "$T/.env" COMPOSE_PROJECT_NAME)"
assert_eq ".env https port" 18443 "$(env_get "$T/.env" LAB_HTTPS_PORT)"
assert_eq ".env seed" true "$(env_get "$T/.env" LAB_SEED_TEST_USERS)"
assert_eq ".env state dir default" ./state "$(env_get "$T/.env" LAB_STATE_DIR)"
assert_eq ".secrets.env mode 600" 600 "$(mode_of "$T/.secrets.env")"
assert "CA created under state/ca" test -s "$T/state/ca/root.crt"
expected="COMPOSE_PROJECT_NAME=v3-p1-inst docker compose --project-directory $T --env-file $T/versions.env --env-file $T/.env --profile core up -d --wait --remove-orphans --build"
assert_eq "exact contract compose command" "$expected" "$(cat "$SHIM_LOG")"
assert_contains "prints trino URL" "https://trino.lab.localhost:18443/ui/" "$out"
assert_contains "prints CA trust help" "certutil" "$out"
assert_contains "non-interactive hides password" "password: LAB_ADMIN_PASSWORD in" "$out"
assert_not "password not printed" grep -qF "$(env_get "$T/.secrets.env" LAB_ADMIN_PASSWORD)" <<<"$out"

# Re-run: user edits and all secrets/CA survive; flags may change ports.
echo "TRINO_MEM=3g" >>"$T/.env"
hs=$(sha "$T/.secrets.env"); fp=$(ca_fingerprint "$T/state/ca/root.crt")
"$T/install.sh" --non-interactive --https-port 28443 >/dev/null 2>&1
assert_eq "re-run keeps secrets" "$hs" "$(sha "$T/.secrets.env")"
assert_eq "re-run keeps CA" "$fp" "$(ca_fingerprint "$T/state/ca/root.crt")"
assert_eq "re-run keeps user keys" 3g "$(env_get "$T/.env" TRINO_MEM)"
assert_eq "re-run keeps domain" lab.localhost "$(env_get "$T/.env" LAB_DOMAIN)"
assert_eq "re-run keeps project" v3-p1-inst "$(env_get "$T/.env" COMPOSE_PROJECT_NAME)"
assert_eq "flag overrides port" 28443 "$(env_get "$T/.env" LAB_HTTPS_PORT)"
assert_eq "re-run keeps seed flag" true "$(env_get "$T/.env" LAB_SEED_TEST_USERS)"
assert_eq "no duplicated .env keys" "" "$(grep -v '^#' "$T/.env" | cut -d= -f1 | sort | uniq -d)"

assert_not "domain change refused" "$T/install.sh" --non-interactive --no-start --domain other.example.com
assert_eq "domain unchanged after refusal" lab.localhost "$(env_get "$T/.env" LAB_DOMAIN)"
assert_not "project change refused" "$T/install.sh" --non-interactive --no-start --project-name other
assert "domain change with --reconfigure" "$T/install.sh" --non-interactive --no-start --reconfigure --domain lab2.localhost
assert_eq "domain changed" lab2.localhost "$(env_get "$T/.env" LAB_DOMAIN)"
assert_not "unknown profile refused" "$T/install.sh" --non-interactive --no-start --profile bogus
assert_not "unavailable profile refused" "$T/install.sh" --non-interactive --no-start --profile server
assert_eq "refused profile leaves .env" core "$(env_get "$T/.env" LAB_PROFILE)"
assert_not "bad port refused" "$T/install.sh" --non-interactive --no-start --https-port 70000
assert_not "unknown flag refused" "$T/install.sh" --frobnicate
assert_not "same https/http port refused" "$T/install.sh" --non-interactive --no-start --https-port 18080 --http-port 18080

# Stale shell variables cannot redirect compose to another project.
: >"$SHIM_LOG"
COMPOSE_PROJECT_NAME=production LAB_DOMAIN=evil.example.com "$T/install.sh" --non-interactive >/dev/null 2>&1
assert_contains "shell COMPOSE_PROJECT_NAME ignored" "COMPOSE_PROJECT_NAME=v3-p1-inst docker compose" "$(cat "$SHIM_LOG")"

# Failing 'up' -> non-zero exit.
SHIM_UP_EXIT=1 "$T/install.sh" --non-interactive >/dev/null 2>&1 && t_fail "failed up -> exit 1" || t_pass "failed up -> exit 1"

# Old Docker / Compose -> hard failure before anything is written.
T2="$WORK/tree2"; make_tree "$T2"
SHIM_DOCKER_VERSION=23.0.6 "$T2/install.sh" --non-interactive >/dev/null 2>&1 && t_fail "Docker 23 refused" || t_pass "Docker 23 refused"  # check-versions: ignore below-minimum test input
SHIM_COMPOSE_VERSION=2.17.0 "$T2/install.sh" --non-interactive >/dev/null 2>&1 && t_fail "Compose 2.17 refused" || t_pass "Compose 2.17 refused"  # check-versions: ignore below-minimum test input
assert_not "nothing written on failed checks" test -e "$T2/.env"
out=$(SHIM_MEM_BYTES=7516192768 "$T2/install.sh" --non-interactive --no-start 2>&1)
assert_contains "low RAM warns" "7 GB of RAM" "$out"
assert_eq "default domain" lab.localhost "$(env_get "$T2/.env" LAB_DOMAIN)"
assert_eq "default project" lakehouse "$(env_get "$T2/.env" COMPOSE_PROJECT_NAME)"
assert_eq "default https port" 443 "$(env_get "$T2/.env" LAB_HTTPS_PORT)"
assert_eq "default seed off" false "$(env_get "$T2/.env" LAB_SEED_TEST_USERS)"
assert_eq "default admin user" labadmin "$(env_get "$T2/.secrets.env" LAB_ADMIN_USER)"

echo "== lab CLI (fake docker)"
t_begin lab
: >"$SHIM_LOG"
assert_not "down -v refused" "$T/lab" down -v
assert_not "down --volumes refused" "$T/lab" down --volumes
assert_eq "refused down made no compose call" "" "$(cat "$SHIM_LOG")"
"$T/lab" down >/dev/null 2>&1
assert_contains "down is plain down" "--profile core down --remove-orphans" "$(cat "$SHIM_LOG")"
assert_not "down never passes -v" grep -q -- ' -v' "$SHIM_LOG"
: >"$SHIM_LOG"
"$T/lab" reset </dev/null >/dev/null 2>&1 && t_fail "reset without tty/--yes refused" || t_pass "reset without tty/--yes refused"
assert_eq "refused reset made no compose call" "" "$(cat "$SHIM_LOG")"
"$T/lab" reset --yes >/dev/null 2>&1
assert_eq "reset scoped to this project" "COMPOSE_PROJECT_NAME=v3-p1-inst docker compose --project-directory $T --env-file $T/versions.env --env-file $T/.env --profile core down -v --remove-orphans" "$(cat "$SHIM_LOG")"
assert "reset keeps CA" test -s "$T/state/ca/root.crt"
assert "reset keeps secrets" test -s "$T/.secrets.env"
out=$("$T/lab" urls)
assert_contains "urls: console" "https://console.lab2.localhost:28443/" "$out"
assert_contains "urls: localhost http hint" "http://console.lab2.localhost:18080/" "$out"
out=$("$T/lab" ca)
assert_contains "ca prints path" "$T/state/ca/root.crt" "$out"
out=$("$T/lab" test --flag 2>&1)
assert_contains "test runs tests/smoke/run.sh with args" "stub smoke: cwd=$T args=--flag" "$out"
STUB_SMOKE_EXIT=3 "$T/lab" test >/dev/null 2>&1; assert_eq "test propagates exit code" 3 "$?"
SHIM_PS='edge|running|healthy|0|Up 1 minute (healthy)\noneshot|exited||0|Exited (0)' "$T/lab" status >/dev/null 2>&1
assert_eq "status healthy -> 0" 0 "$?"
SHIM_PS='edge|running|unhealthy|0|Up (unhealthy)\noneshot|exited||0|Exited (0)' "$T/lab" status >/dev/null 2>&1
assert_eq "status unhealthy -> 1" 1 "$?"
SHIM_PS='edge|running|healthy|0|Up\noneshot|exited||2|Exited (2)' "$T/lab" status >/dev/null 2>&1
assert_eq "status failed one-shot -> 1" 1 "$?"
: >"$SHIM_LOG"
"$T/lab" logs edge >/dev/null 2>&1
assert_contains "logs service (no follow off a tty)" "logs --tail 200 --no-color edge" "$(cat "$SHIM_LOG")"
"$T/lab" reset --all --yes >/dev/null 2>&1
assert_not "reset --all removes state (CA)" test -e "$T/state"
assert "reset --all keeps settings" test -s "$T/.env"
assert_not "lab up without CA refuses" "$T/lab" up
assert_not "unknown command" "$T/lab" frob
rm -f "$T/.env"
assert_not "lab without install refuses" "$T/lab" status

echo "== engineer profile (fake docker)"
t_begin engineer
TE="$WORK/tree-eng"; make_tree "$TE"
: >"$SHIM_LOG"
out=$("$TE/install.sh" --non-interactive --domain lab.localhost --project-name v3-p2-eng \
  --https-port 18643 --http-port 18280 --profile engineer 2>&1); rc=$?
assert_eq "install --profile engineer exit 0" 0 "$rc"
[ "$rc" = 0 ] || printf '%s\n' "$out"
assert_eq ".env LAB_PROFILE=engineer" engineer "$(env_get "$TE/.env" LAB_PROFILE)"
assert_eq "engineer: exact contract compose command" \
  "COMPOSE_PROJECT_NAME=v3-p2-eng docker compose --project-directory $TE --env-file $TE/versions.env --env-file $TE/.env --profile engineer up -d --wait --remove-orphans --build" \
  "$(cat "$SHIM_LOG")"
assert_contains "urls: jupyter" "https://jupyter.lab.localhost:18643/" "$out"
: >"$SHIM_LOG"
"$TE/install.sh" --non-interactive >/dev/null 2>&1
assert_eq "re-run keeps profile engineer" engineer "$(env_get "$TE/.env" LAB_PROFILE)"
assert_not "unchanged profile: no down before up" grep -q ' down ' "$SHIM_LOG"
: >"$SHIM_LOG"
"$TE/lab" down >/dev/null 2>&1
assert_contains "lab down uses the .env profile" "--profile engineer down --remove-orphans" "$(cat "$SHIM_LOG")"
: >"$SHIM_LOG"
"$TE/lab" up >/dev/null 2>&1
assert_contains "lab up uses the .env profile" "--profile engineer up -d --wait --remove-orphans" "$(cat "$SHIM_LOG")"
# engineer -> core: Spark would survive 'up --remove-orphans', so the lab is stopped first.
: >"$SHIM_LOG"
"$TE/install.sh" --non-interactive --profile core >/dev/null 2>&1
assert_eq "profile switch: down (no -v) then up" \
  "COMPOSE_PROJECT_NAME=v3-p2-eng docker compose --project-directory $TE --env-file $TE/versions.env --env-file $TE/.env --profile core down --remove-orphans
COMPOSE_PROJECT_NAME=v3-p2-eng docker compose --project-directory $TE --env-file $TE/versions.env --env-file $TE/.env --profile core up -d --wait --remove-orphans --build" \
  "$(cat "$SHIM_LOG")"
assert_eq ".env LAB_PROFILE=core after switch" core "$(env_get "$TE/.env" LAB_PROFILE)"
: >"$SHIM_LOG"
"$TE/install.sh" --non-interactive --no-start --profile engineer >/dev/null 2>&1
assert_eq "--no-start profile switch makes no compose call" "" "$(cat "$SHIM_LOG")"
out=$(SHIM_MEM_BYTES=8589934592 "$TE/install.sh" --non-interactive --no-start 2>&1)
assert_contains "engineer on 8 GB warns" "profile engineer (Spark, Airflow) wants" "$out"
assert_contains "engineer on 8 GB: OOM hint" "may be OOM-killed; consider --profile core" "$out"
out=$("$TE/install.sh" --non-interactive --no-start 2>&1)
assert_not "engineer on 16 GB: no profile warning" grep -q "profile engineer" <<<"$out"
out=$(SHIM_MEM_BYTES=8589934592 "$TE/install.sh" --non-interactive --no-start --profile core 2>&1)
assert_not "core on 8 GB: no engineer warning" grep -q "profile engineer" <<<"$out"
"$TE/install.sh" --non-interactive --no-start --profile engineer >/dev/null 2>&1

echo "== full profile (fake docker)"
t_begin full
TF="$WORK/tree-full"; make_tree "$TF"
: >"$SHIM_LOG"
out=$("$TF/install.sh" --non-interactive --domain lab.localhost --project-name v3-p3-full \
  --https-port 18643 --http-port 18280 --profile full 2>&1); rc=$?
assert_eq "install --profile full exit 0" 0 "$rc"
[ "$rc" = 0 ] || printf '%s\n' "$out"
assert_eq ".env LAB_PROFILE=full" full "$(env_get "$TF/.env" LAB_PROFILE)"
assert_eq "full: exact contract compose command" \
  "COMPOSE_PROJECT_NAME=v3-p3-full docker compose --project-directory $TF --env-file $TF/versions.env --env-file $TF/.env --profile full up -d --wait --remove-orphans --build" \
  "$(cat "$SHIM_LOG")"
assert_contains "full urls: airflow" "https://airflow.lab.localhost:18643/" "$out"
assert_contains "full urls: spark UI" "https://spark.lab.localhost:18643/" "$out"
assert_contains "full urls: superset" "https://superset.lab.localhost:18643/" "$out"
assert_contains "full on 16 GB: headroom warning" "profile full (Spark, Airflow, Superset) wants 24 GB" "$out"
assert_not "full on 16 GB: no OOM warning" grep -q "may be OOM-killed" <<<"$out"
out=$(SHIM_MEM_BYTES=12884901888 "$TF/install.sh" --non-interactive --no-start 2>&1)
assert_contains "full on 12 GB: OOM warning" "Below 16 GB services may be OOM-killed; consider --profile engineer" "$out"
out=$(SHIM_MEM_BYTES=25769803776 "$TF/install.sh" --non-interactive --no-start 2>&1)
assert_not "full on 24 GB: no profile warning" grep -q "profile full" <<<"$out"
out=$("$TE/lab" urls)
assert_contains "engineer urls: airflow" "https://airflow.lab.localhost:18643/" "$out"
assert_contains "engineer urls: spark UI" "https://spark.lab.localhost:18643/" "$out"
assert_not "engineer urls: no superset" grep -q superset <<<"$out"
out=$("$T2/lab" urls)
assert_not "core urls: no airflow/spark/superset" grep -qE 'airflow|spark|superset' <<<"$out"
: >"$SHIM_LOG"
"$TF/install.sh" --non-interactive --profile engineer >/dev/null 2>&1
assert_contains "full -> engineer: stops the lab first (Superset would survive)" \
  "--profile engineer down --remove-orphans" "$(cat "$SHIM_LOG")"
assert_not "full -> engineer: never -v" grep -q ' -v' "$SHIM_LOG"
for fn in spark:engineer spark:full airflow:engineer airflow:full superset:full; do
  assert "profile_includes ${fn#*:} ${fn%%:*}" profile_includes "${fn#*:}" "${fn%%:*}"
done
for fn in spark:core airflow:core superset:core superset:engineer; do
  assert_not "profile_includes ${fn#*:} ${fn%%:*} is false" profile_includes "${fn#*:}" "${fn%%:*}"
done

echo "== GitHub login flags (ADR-016)"
t_begin github
TG="$WORK/tree-gh"; make_tree "$TG"
GH_ID=Ov23liTESTCLIENTID01
GH_SECRET=0123456789abcdef0123456789abcdef01234567
out=$("$TG/install.sh" --non-interactive --domain lab.localhost --https-port 18743 --http-port 18380 \
  --project-name v3-p3-gh 2>&1); rc=$?
assert_eq "install without GitHub flags exit 0" 0 "$rc"
assert_not "no GitHub keys generated by default" grep -q GITHUB "$TG/.secrets.env"
assert_not "no GitHub hint when off" grep -q "GitHub login" <<<"$out"
out=$("$TG/install.sh" --non-interactive --github-client-id "$GH_ID" --github-client-secret "$GH_SECRET" 2>&1); rc=$?
assert_eq "install with GitHub flags exit 0" 0 "$rc"
assert_eq "client id in .secrets.env" "$GH_ID" "$(env_get "$TG/.secrets.env" OIDC_CLIENT_ID_GITHUB)"
assert_eq "client secret in .secrets.env" "$GH_SECRET" "$(env_get "$TG/.secrets.env" OIDC_CLIENT_SECRET_GITHUB)"
assert_eq ".secrets.env still mode 600" 600 "$(mode_of "$TG/.secrets.env")"
assert_not "client secret never printed" grep -qF "$GH_SECRET" <<<"$out"
assert_not "client secret not in .env" grep -qF "$GH_SECRET" "$TG/.env"
assert_contains "callback URL printed" "https://auth.lab.localhost:18743/realms/lakehouse/broker/github/endpoint" "$out"
assert_contains "no-group hint printed" "A first GitHub login gets no group" "$out"
hs=$(sha "$TG/.secrets.env")
"$TG/install.sh" --non-interactive >/dev/null 2>&1
assert_eq "re-run without flags keeps GitHub keys" "$hs" "$(sha "$TG/.secrets.env")"
"$TG/install.sh" --non-interactive --github-client-secret "${GH_SECRET%?}8" >/dev/null 2>&1
assert_eq "secret alone can be rotated" "${GH_SECRET%?}8" "$(env_get "$TG/.secrets.env" OIDC_CLIENT_SECRET_GITHUB)"
assert_eq "rotation keeps the id" "$GH_ID" "$(env_get "$TG/.secrets.env" OIDC_CLIENT_ID_GITHUB)"
assert_not "--no-github with an id refused" "$TG/install.sh" --non-interactive --no-start --no-github --github-client-id "$GH_ID"
assert_not "bad client id refused" "$TG/install.sh" --non-interactive --no-start --github-client-id 'x;rm -rf /' --github-client-secret "$GH_SECRET"
assert_not "short secret refused" "$TG/install.sh" --non-interactive --no-start --github-client-id "$GH_ID" --github-client-secret short
out=$("$TG/install.sh" --non-interactive --no-github 2>&1); rc=$?
assert_eq "--no-github exit 0" 0 "$rc"
assert_not "--no-github removes both keys" grep -q GITHUB "$TG/.secrets.env"
assert_contains "--no-github says so" "GitHub login turned off" "$out"
assert_eq "--no-github keeps mode 600" 600 "$(mode_of "$TG/.secrets.env")"
hs=$(sha "$TG/.secrets.env")
assert_not "id alone (no stored secret) refused" "$TG/install.sh" --non-interactive --no-start --github-client-id "$GH_ID"
assert_eq "refused half config wrote nothing" "$hs" "$(sha "$TG/.secrets.env")"
f="$WORK/unset.env"; printf 'A=1\nB=2\n# B=comment\nB=3\n' >"$f"; chmod 600 "$f"
env_unset "$f" B
assert_eq "env_unset removes every assignment" "A=1
# B=comment" "$(cat "$f")"
assert_eq "env_unset keeps mode" 600 "$(mode_of "$f")"
env_unset "$f" NOPE; assert_eq "env_unset absent key is a no-op" "A=1
# B=comment" "$(cat "$f")"

echo "== per-user workspace cleanup (fake docker inventory)"
t_begin workspaces
# Inventory: this project's two workspaces + home volumes, and look-alikes that must never
# be touched: another project's workspace, a project whose name has ours as a prefix, this
# project's compose-managed objects (no lab.role), and an unrelated production container.
P=v3-p2-eng
export SHIM_CONTAINERS="$P-ws-alice|com.docker.compose.project=$P,lab.role=workspace
$P-ws-victor|lab.role=workspace,com.docker.compose.project=$P
$P-trino-1|com.docker.compose.project=$P,com.docker.compose.service=trino
v3-other-ws-alice|com.docker.compose.project=v3-other,lab.role=workspace
${P}2-ws-alice|com.docker.compose.project=${P}2,lab.role=workspace
$P-ws-imposter|com.docker.compose.project=$P,lab.role=workspace-not
prod-db|com.docker.compose.project=production"
export SHIM_VOLUMES="$P-home-alice|com.docker.compose.project=$P,lab.role=workspace
$P-home-victor|com.docker.compose.project=$P,lab.role=workspace
${P}_postgres-data|com.docker.compose.project=$P,com.docker.compose.volume=postgres-data
v3-other-home-alice|com.docker.compose.project=v3-other,lab.role=workspace
${P}2-home-alice|com.docker.compose.project=${P}2,lab.role=workspace
prod-data|com.docker.compose.project=production"
never="v3-other|${P}2|imposter|trino-1|postgres-data|prod-"
DC_PREFIX="COMPOSE_PROJECT_NAME=$P docker compose --project-directory $TE --env-file $TE/versions.env --env-file $TE/.env --profile engineer"

rm -f "$WORK/shim-removed"; : >"$SHIM_LOG"
"$TE/lab" down >/dev/null 2>&1; rc=$?
assert_eq "down with workspaces: exit 0" 0 "$rc"
assert_eq "down: stop + rm this project's workspaces, then compose down" \
  "docker stop -t 10 $P-ws-alice $P-ws-victor
docker rm -f $P-ws-alice $P-ws-victor
$DC_PREFIX down --remove-orphans" "$(cat "$SHIM_LOG")"
assert_not "down: no volume removed" grep -q 'volume rm' "$SHIM_LOG"
assert_not "down: look-alikes untouched" grep -qE "$never" "$SHIM_LOG"
: >"$SHIM_LOG"
"$TE/lab" down >/dev/null 2>&1
assert_eq "down again: nothing left to stop" "$DC_PREFIX down --remove-orphans" "$(cat "$SHIM_LOG")"

rm -f "$WORK/shim-removed"; : >"$SHIM_LOG"
"$TE/lab" reset --yes >/dev/null 2>&1; rc=$?
assert_eq "reset with workspaces: exit 0" 0 "$rc"
assert_eq "reset: workspaces, then compose down -v, then this project's home volumes" \
  "docker stop -t 10 $P-ws-alice $P-ws-victor
docker rm -f $P-ws-alice $P-ws-victor
$DC_PREFIX down -v --remove-orphans
docker volume rm $P-home-alice $P-home-victor" "$(cat "$SHIM_LOG")"
assert_not "reset: look-alikes untouched" grep -qE "$never" "$SHIM_LOG"
left=$(docker volume ls -q --filter label=lab.role=workspace | LC_ALL=C sort | tr '\n' ' ')
assert_eq "reset: other projects' home volumes still exist" "v3-other-home-alice ${P}2-home-alice " "$left"
assert "reset keeps settings and CA" test -s "$TE/state/ca/root.crt"

rm -f "$WORK/shim-removed"; : >"$SHIM_LOG"
SHIM_RM_FAIL=1 "$TE/lab" reset --yes >/dev/null 2>&1 && t_fail "reset: stuck workspace -> error" || t_pass "reset: stuck workspace -> error"
assert_not "reset: stuck workspace -> no compose down -v, no volume rm" grep -qE 'down -v|volume rm' "$SHIM_LOG"
rm -f "$WORK/shim-removed"; : >"$SHIM_LOG"
SHIM_RM_FAIL=1 "$TE/lab" down >/dev/null 2>&1 && t_fail "down: stuck workspace -> non-zero" || t_pass "down: stuck workspace -> non-zero"
assert_contains "down: stuck workspace still runs compose down" "down --remove-orphans" "$(cat "$SHIM_LOG")"

# The selector refuses an empty or malformed project (no label wildcard is possible).
( COMPOSE_PROJECT_NAME="" lab_workspace_ids volume ) >/dev/null 2>&1 && t_fail "empty project refused" || t_pass "empty project refused"
( COMPOSE_PROJECT_NAME="x,lab.role=workspace" lab_workspace_ids volume ) >/dev/null 2>&1 && t_fail "malformed project refused" || t_pass "malformed project refused"
assert_eq "selector: exact labels, both required" "$P-home-alice $P-home-victor " \
  "$(rm -f "$WORK/shim-removed"; COMPOSE_PROJECT_NAME=$P lab_workspace_ids volume | tr '\n' ' ')"
unset SHIM_CONTAINERS SHIM_VOLUMES
rm -f "$WORK/shim-removed"

echo "== issuer origin (REG_V3_OIDC_ISSUER_DEFAULT_PORT)"
for pair in "443:https://auth.lab.localhost" "18443:https://auth.lab.localhost:18443"; do
  T3=$(mktemp -d)
  printf 'LAB_DOMAIN=lab.localhost\nLAB_HTTPS_PORT=%s\n' "${pair%%:*}" >"$T3/.env"
  got=$( LAB_ENV_FILE="$T3/.env"; LAB_AUTH_URL=stale; lab_settings; printf '%s' "$LAB_AUTH_URL" )
  assert_eq "LAB_AUTH_URL for port ${pair%%:*}" "${pair#*:}" "$got"
  rm -rf "$T3"
done
for f in compose/identity.yaml compose/catalog.yaml compose/engines.yaml config/trino/config.properties; do
  assert_not "no hand-built auth origin in $f" grep -qF 'https://auth.$' "$SRC/$f"
done

echo "== bind-mounted config hashes (REG_V3_STALE_BIND_MOUNT_CONFIG_ON_UPGRADE)"
t_begin config-hash
T4=$(mktemp -d)
mkdir -p "$T4/config/trino/catalog" "$T4/config/caddy"
echo a >"$T4/config/trino/rules.json"; echo b >"$T4/config/trino/catalog/x.properties"; echo c >"$T4/config/caddy/Caddyfile"
h1=$( V3_DIR=$T4; config_hash config/trino )
h2=$( V3_DIR=$T4; config_hash config/trino )
assert_eq "hash is stable" "$h1" "$h2"
echo a2 >"$T4/config/trino/rules.json"
h3=$( V3_DIR=$T4; config_hash config/trino )
assert_not "hash changes when a file changes" test "$h1" = "$h3"
echo c2 >"$T4/config/caddy/Caddyfile"
h4=$( V3_DIR=$T4; config_hash config/trino )
assert_eq "another service's config does not change it" "$h3" "$h4"
echo d >"$T4/config/trino/catalog/tpch.properties"
h5=$( V3_DIR=$T4; config_hash config/trino )
assert_not "a new file changes it" test "$h4" = "$h5"
assert_eq "missing dir -> none" "none" "$( V3_DIR=$T4; config_hash config/spark )"
got=$( V3_DIR=$T4; LAB_ENV_FILE="$T4/.env"; : >"$LAB_ENV_FILE"; lab_settings; printf '%s' "$LAB_CONFIG_HASH_TRINO" )
assert_eq "lab_settings exports LAB_CONFIG_HASH_TRINO" "$h5" "$got"
for k in AIRFLOW SUPERSET CONSOLE; do
  got=$( V3_DIR=$T4; LAB_ENV_FILE="$T4/.env"; lab_settings; v="LAB_CONFIG_HASH_$k"; printf '%s' "${!v}" )
  assert_eq "lab_settings exports LAB_CONFIG_HASH_$k (no config dir -> none)" none "$got"
done
for pair in edge.yaml:CADDY engines.yaml:TRINO storage.yaml:SEAWEEDFS workspace.yaml:JUPYTERHUB spark.yaml:SPARK; do
  assert "compose/${pair%%:*} labels its service with LAB_CONFIG_HASH_${pair#*:}" \
    grep -qF "lab.config-hash: \${LAB_CONFIG_HASH_${pair#*:}:-}" "$SRC/compose/${pair%%:*}"
done
rm -rf "$T4"

echo "== repo hygiene (public repo)"
t_begin hygiene
leaks=$(grep -rnE '([0-9]{1,3}[.-]){3}[0-9]{1,3}\.sslip\.io|192\.168\.[0-9]+\.[0-9]+' \
  "$SRC/install.sh" "$SRC/lab" "$SRC/installer" "$SRC/tests/installer" 2>/dev/null | grep -v '10-0-0-5\|10\.0\.0\.5' || true)
assert_eq "no host IPs / sslip hosts in installer files" "" "$leaks"
assert "install.sh executable" test -x "$SRC/install.sh"
assert "lab executable" test -x "$SRC/lab"

t_summary "installer unit"
