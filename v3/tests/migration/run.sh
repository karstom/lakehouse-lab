#!/usr/bin/env bash
# V2 -> V3 migration guide, proven (docs/MIGRATION.md; CONTRACT Phase 6, MIGRATION).
#
# Runs the guide's commands against a THROWAWAY "V2": a MinIO container with synthetic data
# (the same MinIO release V2 ships), on its own Docker network, copying into the V3 install
# this script lives in (any profile; the Spark example needs engineer or full, and
# LAB_SEED_TEST_USERS=true for the browser login as alice). Never point it at a real V2:
# every object it creates is named "<COMPOSE_PROJECT_NAME>-v2src*", and it refuses to run for
# a project named like V2's (lakehouse-lab).
#
# Usage: tests/migration/run.sh [all | source-up | seed | copy | verify | reader | postgres |
#                                login | files | load | reader-delete | source-down]
#   all = source-up seed copy verify reader postgres [login] files load reader-delete, then
#         source-down (also on failure).
# Env:   MIG_OUT     work dir (default tests/migration/out; git-ignored, mode 700). Logs of
#                    every step go to $MIG_OUT/<step>.log.
#        MIG_BIG_MIB size of the large object (default 300: above rclone's 200 MiB multipart
#                    cutoff, so the multipart path is used on both sides)
#        MIG_KEEP=1  with `all`: keep the throwaway V2 afterwards
#
# The lines marked "# guide:" are the guide's commands with only the names replaced
# (V2_ENV, V2_NET, V3_NET, container and volume names).
set -euo pipefail

HERE=$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)
V3_DIR=$(cd -P "$HERE/../.." && pwd)
# shellcheck source=../../installer/lib.sh
. "$V3_DIR/installer/lib.sh"
[ -f "$LAB_ENV_FILE" ] && [ -f "$LAB_SECRETS_FILE" ] || { echo "migration: run install.sh first" >&2; exit 2; }
lab_settings
PROJECT=$COMPOSE_PROJECT_NAME
case "$PROJECT" in
  lakehouse-lab|lakehouse-lab_*) echo "migration: refusing project '$PROJECT' (V2's name)" >&2; exit 2 ;;
esac

# Pins: versions.env only.
set -a
# shellcheck disable=SC1091
. "$V3_DIR/versions.env"
set +a
: "${RCLONE_IMAGE_TAG:?}" "${RCLONE_IMAGE_DIGEST:?}" "${MIGRATION_TEST_MINIO_IMAGE_TAG:?}" "${MIGRATION_TEST_MINIO_IMAGE_DIGEST:?}"
RCLONE_IMAGE="rclone/rclone:${RCLONE_IMAGE_TAG}@${RCLONE_IMAGE_DIGEST}"
MINIO_IMAGE="minio/minio:${MIGRATION_TEST_MINIO_IMAGE_TAG}@${MIGRATION_TEST_MINIO_IMAGE_DIGEST}"
WORKSPACE_IMAGE="lakehouse-lab/v3-workspace:${JUPYTERHUB_VERSION}"
PG_IMAGE="postgres:${POSTGRES_VERSION}"

# The throwaway V2 (names only ever start with the V3 test project's name).
SRC="${PROJECT}-v2src"
V2_NET="$SRC"                          # stands in for V2's network, lakehouse-lab_lakehouse
V3_NET="${PROJECT}_lab"
SRC_MINIO="$SRC-minio"                 # network alias `minio`, as in V2
SRC_PG="$SRC-postgres"                 # network alias `postgres`, as in V2
SRC_VOLS=("$SRC-minio-data" "$SRC-notebooks" "$SRC-dags")
SEAWEEDFS_CTR="${PROJECT}-seaweedfs-1"
MIG_USER=alice
HOME_VOL="${PROJECT}-home-${MIG_USER}"
LABEL=(--label lab.test=migration --label "lab.test.project=$PROJECT")

OUT=${MIG_OUT:-$HERE/out}
mkdir -p "$OUT"
chmod 700 "$OUT"
V2_ENV="$OUT/v2.env"                   # stands in for V2's .env (MINIO_ROOT_USER/PASSWORD)
MIG_DIR="$OUT/lab-migration"           # the guide's ~/lab-migration
export MIG_BIG_MIB=${MIG_BIG_MIB:-300}

log() { printf '\n=== %s  %s\n' "$(date -u +%H:%M:%S)" "$*"; }

# guide: envget FILE KEY -> the value of KEY in a dotenv file (no shell evaluation)
envget() { sed -n "s/^$2=//p" "$1" | tail -n 1 | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/"; }

# guide: rc ARGS... -> rclone in a container on both networks, remotes from rclone.env
rc() {
  docker run --rm --network "$V2_NET" --network "$V3_NET" --env-file "$MIG_DIR/rclone.env" \
    "$RCLONE_IMAGE" --config "" "$@"
}

# ---------------------------------------------------------------- the throwaway V2
step_source_up() {
  log "source-up: throwaway MinIO ($MINIO_IMAGE) and Postgres on network $V2_NET"
  if [ ! -f "$V2_ENV" ]; then
    (umask 077; printf 'MINIO_ROOT_USER=admin\nMINIO_ROOT_PASSWORD=%s\nPOSTGRES_PASSWORD=%s\n' \
      "$(openssl rand -hex 20)" "$(openssl rand -hex 20)" >"$V2_ENV")
  fi
  docker network inspect "$V2_NET" >/dev/null 2>&1 || docker network create "${LABEL[@]}" "$V2_NET" >/dev/null
  local v
  for v in "${SRC_VOLS[@]}"; do
    docker volume inspect "$v" >/dev/null 2>&1 || docker volume create "${LABEL[@]}" "$v" >/dev/null
  done
  if [ -z "$(docker ps -aq --filter "name=^${SRC_MINIO}\$")" ]; then
    MINIO_ROOT_USER=$(envget "$V2_ENV" MINIO_ROOT_USER) MINIO_ROOT_PASSWORD=$(envget "$V2_ENV" MINIO_ROOT_PASSWORD) \
    docker run -d --name "$SRC_MINIO" "${LABEL[@]}" --network "$V2_NET" --network-alias minio \
      -e MINIO_ROOT_USER -e MINIO_ROOT_PASSWORD -v "$SRC-minio-data:/data" \
      --memory 1g "$MINIO_IMAGE" server /data >/dev/null
  fi
  if [ -z "$(docker ps -aq --filter "name=^${SRC_PG}\$")" ]; then
    POSTGRES_PASSWORD=$(envget "$V2_ENV" POSTGRES_PASSWORD) \
    docker run -d --name "$SRC_PG" "${LABEL[@]}" --network "$V2_NET" --network-alias postgres \
      -e POSTGRES_PASSWORD -e POSTGRES_DB=lakehouse --memory 512m "$PG_IMAGE" >/dev/null
  fi
  local i
  for i in $(seq 1 60); do
    if docker exec "$SRC_MINIO" curl -fsS -o /dev/null http://localhost:9000/minio/health/live 2>/dev/null &&
       docker exec "$SRC_PG" pg_isready -q -U postgres -d lakehouse 2>/dev/null; then
      echo "MinIO and Postgres ready after ${i}s"; return 0
    fi
    sleep 1
  done
  echo "throwaway V2 did not become ready" >&2; return 1
}

step_source_down() {
  log "source-down: remove the throwaway V2 (containers, volumes, network: $SRC*)"
  # -v: also the anonymous volume the postgres image declares for its data directory.
  docker rm -f -v "$SRC_MINIO" "$SRC_PG" >/dev/null 2>&1 || true
  local v
  for v in "${SRC_VOLS[@]}"; do docker volume rm "$v" >/dev/null 2>&1 || true; done
  docker network rm "$V2_NET" >/dev/null 2>&1 || true
  rm -rf "$OUT/data"
  docker ps -a --filter label=lab.test=migration --filter "label=lab.test.project=$PROJECT" --format '{{.Names}}'
  docker volume ls -q --filter label=lab.test=migration --filter "label=lab.test.project=$PROJECT"
  echo "left over (should be empty above)"
}

# ---------------------------------------------------------------- synthetic V2 content
step_seed() {
  log "seed: synthetic buckets, prefixes, special-character keys and a ${MIG_BIG_MIB} MiB object"
  rm -rf "$OUT/data"
  mkdir -p "$OUT/data"
  docker run --rm --user "$(id -u):$(id -g)" -e MIG_BIG_MIB -v "$OUT/data:/data" -v "$HERE:/mig:ro" \
    --entrypoint python3 "$WORKSPACE_IMAGE" /mig/make_data.py /data
  # A seeding-only rclone config for the throwaway MinIO (the guide's file comes in `copy`).
  (umask 077; {
    echo RCLONE_CONFIG_V2_TYPE=s3
    echo RCLONE_CONFIG_V2_PROVIDER=Minio
    echo RCLONE_CONFIG_V2_ENDPOINT=http://minio:9000
    echo "RCLONE_CONFIG_V2_ACCESS_KEY_ID=$(envget "$V2_ENV" MINIO_ROOT_USER)"
    echo "RCLONE_CONFIG_V2_SECRET_ACCESS_KEY=$(envget "$V2_ENV" MINIO_ROOT_PASSWORD)"
  } >"$OUT/seed-rclone.env")
  local b
  for b in lakehouse analytics-exports big-files; do
    docker run --rm --network "$V2_NET" --env-file "$OUT/seed-rclone.env" -v "$OUT/data:/data:ro" \
      "$RCLONE_IMAGE" --config "" copy "/data/$b" "v2:$b" --stats-log-level NOTICE --stats 0 || return 1
  done
  # A large object written by another client (MinIO's own mc, multipart), as V2's tools
  # (Spark s3a, mc, the Console) wrote them: its ETag is not an MD5 and it carries no
  # rclone MD5 metadata, so `rclone check` can only compare its size (see verify).
  docker exec "$SRC_MINIO" sh -c 'mc alias set v2 http://localhost:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null &&
    head -c 157286400 /dev/urandom | mc pipe --quiet v2/big-files/exports/from-mc-150MiB.bin >/dev/null'
  # An empty "folder" as the MinIO Console makes it (a zero-byte key ending in /).
  docker run --rm --network "$V2_NET" --env-file "$OUT/seed-rclone.env" "$RCLONE_IMAGE" --config "" \
    mkdir --s3-directory-markers "v2:lakehouse/raw-data/empty-folder"
  # V2-style notebooks and DAGs volumes (jovyan 1000:100, airflow 50000:0 as in V2's images).
  docker run --rm -v "$SRC-notebooks:/nb" -v "$SRC-dags:/dags" --entrypoint sh "$RCLONE_IMAGE" -c '
    mkdir -p "/nb/examples/sub dir" && printf "%s\n" "{\"cells\": [], \"metadata\": {}, \"nbformat\": 4, \"nbformat_minor\": 5}" > "/nb/examples/sub dir/Analysis (v2) ü.ipynb" &&
    printf "print(1)\n" > /nb/helpers.py && chown -R 1000:100 /nb &&
    printf "from airflow import DAG\nfrom airflow.operators.python import PythonOperator\n" > /dags/v2_example_dag.py &&
    chown -R 50000:0 /dags && chmod 644 /dags/*.py'
  # A small analytics table in the throwaway V2 Postgres.
  docker exec -i "$SRC_PG" psql -q -v ON_ERROR_STOP=1 -U postgres -d lakehouse <<'SQL'
CREATE TABLE IF NOT EXISTS customers (id int PRIMARY KEY, name text, city text, since date);
TRUNCATE customers;
INSERT INTO customers SELECT g, 'customer-' || g, (ARRAY['Oslo','Lyon','Porto','Graz'])[1 + g % 4],
  DATE '2020-01-01' + g FROM generate_series(1, 1000) AS g;
SQL
  echo "--- V2 (throwaway) now holds:"
  docker run --rm --network "$V2_NET" --env-file "$OUT/seed-rclone.env" "$RCLONE_IMAGE" --config "" lsd v2:
  cat "$OUT/data/expected.json"
}

# ---------------------------------------------------------------- guide steps 1-3: copy
step_copy() {
  log "copy: guide steps 1-3 (credentials file, look, copy into landing)"
  # guide step 1: the credentials file (mode 600, in a mode-700 directory)
  mkdir -p "$MIG_DIR" && chmod 700 "$MIG_DIR"
  ( umask 077
    cat >"$MIG_DIR/rclone.env" <<EOF
RCLONE_CONFIG_V2_TYPE=s3
RCLONE_CONFIG_V2_PROVIDER=Minio
RCLONE_CONFIG_V2_ENDPOINT=http://minio:9000
RCLONE_CONFIG_V2_ACCESS_KEY_ID=$(envget "$V2_ENV" MINIO_ROOT_USER)
RCLONE_CONFIG_V2_SECRET_ACCESS_KEY=$(envget "$V2_ENV" MINIO_ROOT_PASSWORD)
RCLONE_CONFIG_V3_TYPE=s3
RCLONE_CONFIG_V3_PROVIDER=SeaweedFS
RCLONE_CONFIG_V3_ENDPOINT=http://seaweedfs:8333
RCLONE_CONFIG_V3_ACCESS_KEY_ID=$(envget "$V3_DIR/.secrets.env" SEAWEEDFS_ADMIN_ACCESS_KEY)
RCLONE_CONFIG_V3_SECRET_ACCESS_KEY=$(envget "$V3_DIR/.secrets.env" SEAWEEDFS_ADMIN_SECRET_KEY)
EOF
  )
  stat -c '%A %n' "$MIG_DIR/rclone.env"
  # guide step 2: look
  rc lsd v2:
  rc size v2:lakehouse
  # guide step 3: copy each bucket into landing/v2/<bucket>
  rc mkdir v3:landing
  local b t0
  t0=$(date +%s)
  for b in $(rc lsf --dirs-only v2: | tr -d /); do
    echo "--- copying $b"
    rc copy "v2:$b" "v3:landing/v2/$b" --transfers 8 --stats 30s --stats-one-line --stats-log-level NOTICE || return 1
  done
  echo "copy took $(( $(date +%s) - t0 ))s"
  echo "--- re-run (resume check: nothing left to transfer)"
  for b in $(rc lsf --dirs-only v2: | tr -d /); do
    rc copy "v2:$b" "v3:landing/v2/$b" --stats-one-line --stats-log-level NOTICE --stats 1h -v 2>&1 |
      grep -E "Transferred|There was nothing to transfer|ERROR" || true
  done
}

# ---------------------------------------------------------------- guide step 4: verify
step_verify() {
  log "verify: guide step 4 (counts, sizes, checksums)"
  local b fail=0 a z
  for b in $(rc lsf --dirs-only v2: | tr -d /); do
    echo "== $b"
    a=$(rc size "v2:$b" --json); z=$(rc size "v3:landing/v2/$b" --json)
    echo "  V2: $a"; echo "  V3: $z"
    [ "$a" = "$z" ] || { echo "  COUNT/SIZE MISMATCH"; fail=1; }
    rc check "v2:$b" "v3:landing/v2/$b" --one-way || fail=1
  done
  echo "--- special-character keys, as listed in V3:"
  rc lsf -R "v3:landing/v2/lakehouse/raw-data/weird names"
  echo "--- the large objects: MD5 as each side reports it (empty = not known without reading)"
  rc md5sum "v2:big-files"; rc md5sum "v3:landing/v2/big-files"
  rc lsl "v3:landing/v2/big-files"
  echo "--- byte-for-byte check of big-files (guide: check --download)"
  rc check "v2:big-files" "v3:landing/v2/big-files" --one-way --download || fail=1
  echo "--- the empty folder marker (not copied: no data)"
  rc lsf "v2:lakehouse/raw-data" --dirs-only; rc lsf "v3:landing/v2/lakehouse/raw-data" --dirs-only
  if [ "$fail" = 0 ]; then echo "VERIFY: PASS"; else echo "VERIFY: FAIL"; return 1; fi
}

# ---------------------------------------------------------------- guide step 5: read-only key
step_reader() {
  log "reader: guide step 5 (a read-only key for landing, for the loading notebook)"
  # guide step 5
  AK=landing$(openssl rand -hex 8); SK=$(openssl rand -hex 24)
  printf 's3.configure -user=landing-reader -actions=Read,List -buckets=landing -access_key=%s -secret_key=%s -apply\n' "$AK" "$SK" |
    docker exec -i "$SEAWEEDFS_CTR" weed shell >/dev/null
  ( umask 077; printf 'access key: %s\nsecret key: %s\n' "$AK" "$SK" >"$MIG_DIR/landing-reader.txt" )
  echo "landing-reader created; key in $MIG_DIR/landing-reader.txt ($(stat -c %a "$MIG_DIR/landing-reader.txt"))"
}

step_reader_delete() {
  log "reader-delete: guide clean-up (remove the landing-reader identity)"
  local ak
  ak=$(sed -n 's/^access key: //p' "$MIG_DIR/landing-reader.txt")
  # guide: clean-up
  printf 's3.configure -user=landing-reader -delete -apply\n' | docker exec -i "$SEAWEEDFS_CTR" weed shell >/dev/null
  # Check: the old key is now refused (403), not merely failing for another reason.
  local out
  out=$(docker run --rm --network "$V3_NET" -e RCLONE_CONFIG_LR_TYPE=s3 -e RCLONE_CONFIG_LR_PROVIDER=SeaweedFS \
       -e RCLONE_CONFIG_LR_ENDPOINT=http://seaweedfs:8333 -e "RCLONE_CONFIG_LR_ACCESS_KEY_ID=$ak" \
       -e "RCLONE_CONFIG_LR_SECRET_ACCESS_KEY=$(sed -n 's/^secret key: //p' "$MIG_DIR/landing-reader.txt")" \
       "$RCLONE_IMAGE" --config "" lsf lr:landing --max-depth 1 2>&1) && {
    echo "READER-DELETE: FAIL (the deleted key still lists landing)"; return 1; }
  grep -Eo 'StatusCode: 403|InvalidAccessKeyId|AccessDenied' <<<"$out" | sort -u
  grep -Eq 'StatusCode: 403|InvalidAccessKeyId|AccessDenied' <<<"$out" || {
    echo "READER-DELETE: FAIL (unexpected error: ${out: -300})"; return 1; }
  echo "READER-DELETE: PASS (the deleted key is refused)"
}

# ---------------------------------------------------------------- guide: Postgres (optional)
step_postgres() {
  log "postgres: optional guide section (dump for safekeeping; one table as CSV into landing)"
  # guide: a full dump, kept outside both stacks
  docker exec "$SRC_PG" pg_dump -U postgres -Fc lakehouse >"$MIG_DIR/v2-lakehouse.dump"
  stat -c '%s bytes %n' "$MIG_DIR/v2-lakehouse.dump"
  docker run --rm -i "$PG_IMAGE" pg_restore --list <"$MIG_DIR/v2-lakehouse.dump" | grep "TABLE DATA"
  # guide: a table as CSV into landing
  docker exec "$SRC_PG" psql -U postgres -d lakehouse -c "\copy customers TO STDOUT WITH (FORMAT csv, HEADER)" |
    docker run --rm -i --network "$V2_NET" --network "$V3_NET" --env-file "$MIG_DIR/rclone.env" \
      "$RCLONE_IMAGE" --config "" rcat v3:landing/v2/postgres/customers.csv
  local rows
  rows=$(rc cat v3:landing/v2/postgres/customers.csv | tail -n +2 | wc -l)
  echo "customers.csv in landing: $rows rows (V2 table: $(docker exec "$SRC_PG" psql -tA -U postgres -d lakehouse -c 'select count(*) from customers'))"
  if [ "$rows" = 1000 ]; then echo "POSTGRES: PASS"; else echo "POSTGRES: FAIL"; return 1; fi
}

# ---------------------------------------------------------------- guide: notebooks and DAGs
step_files() {
  log "files: optional guide section (V2 notebooks and DAGs into $MIG_USER's home)"
  if ! docker volume inspect "$HOME_VOL" >/dev/null 2>&1; then
    echo "no $HOME_VOL yet: log $MIG_USER in once first (run.sh login)"; return 1
  fi
  # guide: copy (V2 volumes read-only; files end up owned by the workspace user 1000:100)
  docker run --rm --user 1000:100 -v "$SRC-notebooks:/from:ro" -v "$HOME_VOL:/to" --entrypoint sh "$RCLONE_IMAGE" \
    -c 'mkdir -p /to/migrated-from-v2/notebooks && cp -R /from/. /to/migrated-from-v2/notebooks/'
  docker run --rm --user 1000:100 -v "$SRC-dags:/from:ro" -v "$HOME_VOL:/to" --entrypoint sh "$RCLONE_IMAGE" \
    -c 'mkdir -p /to/migrated-from-v2/dags && cp -R /from/. /to/migrated-from-v2/dags/'
  docker run --rm -v "$HOME_VOL:/h:ro" --entrypoint sh "$RCLONE_IMAGE" -c 'cd /h/migrated-from-v2 && find . -type f -exec ls -ln {} +'
}

# ---------------------------------------------------------------- guide step 6: load (browser)
step_load() {
  log "load: guide step 6 in $MIG_USER's workspace (Spark as in E1; Trino + PyIceberg)"
  local spark=false check_home=false probe
  profile_includes "$LAB_PROFILE" spark && spark=true
  docker volume inspect "$HOME_VOL" >/dev/null 2>&1 && check_home=true
  rc lsf -R --files-only v3:warehouse >"$OUT/warehouse-files.txt"
  probe=$(head -n 1 "$OUT/warehouse-files.txt")
  python3 - "$OUT/load-params.json" "$MIG_DIR/landing-reader.txt" "$OUT/data/expected.json" \
    "$spark" "$check_home" "warehouse/$probe" <<'PY'
import json, os, sys
out, keyfile, expected, spark, check_home, probe = sys.argv[1:]
keys = dict(l.split(": ", 1) for l in open(keyfile).read().splitlines())
old = os.umask(0o077)
with open(out, "w") as f:
    json.dump({"landing_access_key": keys["access key"], "landing_secret_key": keys["secret key"],
               "expected": json.load(open(expected)), "spark": spark == "true",
               "check_home": check_home == "true", "warehouse_probe_key": probe}, f)
os.umask(old)
PY
  mkdir -p "$OUT/smoke"
  LAB_SMOKE_OUT="$OUT/smoke" lab_compose --profile test run --rm --no-deps \
    --user "$(id -u):$(id -g)" -e HOME=/tmp/mig-home -e MIG_USER="$MIG_USER" \
    -e MIG_PARAMS=/mig-out/load-params.json \
    -v "$HERE:/opt/migration:ro" -v "$OUT:/mig-out:ro" \
    --entrypoint /opt/migration/in-smoke.sh smoke
}

# A login that only spawns the user's workspace (JupyterHub creates the home volume then).
step_login() {
  log "login: $MIG_USER logs in once (creates the home volume)"
  mkdir -p "$OUT/smoke"
  LAB_SMOKE_OUT="$OUT/smoke" lab_compose --profile test run --rm --no-deps \
    --user "$(id -u):$(id -g)" -e HOME=/tmp/mig-home -e MIG_USER="$MIG_USER" -e MIG_LOGIN_ONLY=1 \
    -v "$HERE:/opt/migration:ro" --entrypoint /opt/migration/in-smoke.sh smoke
}

run_all() {
  local rc_all=0
  if step_source_up && step_seed && step_copy && step_verify && step_reader && step_postgres; then
    if ! docker volume inspect "$HOME_VOL" >/dev/null 2>&1; then
      step_login || rc_all=1
    fi
    { [ "$rc_all" = 0 ] && step_files && step_load && step_reader_delete; } || rc_all=1
  else
    rc_all=1
  fi
  [ "${MIG_KEEP:-0}" = 1 ] || step_source_down
  return $rc_all
}

sub=${1:-all}
case "$sub" in
  all) run_all 2>&1 | tee "$OUT/all.log"; exit "${PIPESTATUS[0]}" ;;
  source-up|seed|copy|verify|reader|login|load|files|postgres|reader-delete|source-down)
    fn="step_${sub//-/_}"; "$fn" 2>&1 | tee "$OUT/$sub.log"; exit "${PIPESTATUS[0]}" ;;
  *) sed -n '2,25p' "$0" >&2; exit 2 ;;
esac
