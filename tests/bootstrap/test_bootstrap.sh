#!/usr/bin/env bash
# Tests for the root install.sh (the one-line bootstrap). No network and no Docker: each
# test clones a throwaway local repository (file://) whose v3/install.sh is a fake that
# records the arguments it was given.
#
# Usage: bash tests/bootstrap/test_bootstrap.sh
set -euo pipefail

REPO_DIR=$(cd -P "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
BOOTSTRAP="$REPO_DIR/install.sh"
WORK=$(mktemp -d "${TMPDIR:-/tmp}/lakehouse-bootstrap-test.XXXXXX")
trap 'rm -rf "$WORK"' EXIT

export GIT_AUTHOR_NAME=test GIT_AUTHOR_EMAIL=test@example.invalid
export GIT_COMMITTER_NAME=test GIT_COMMITTER_EMAIL=test@example.invalid
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
export GIT_TERMINAL_PROMPT=0
export BOOT_TEST_OUT="$WORK/installer-args"

pass=0 fail=0
ok() { pass=$((pass + 1)); printf 'ok   %s\n' "$1"; }
not_ok() { fail=$((fail + 1)); printf 'FAIL %s\n' "$1"; [ -z "${2:-}" ] || printf '     %s\n' "$2"; }
check() { # check NAME COMMAND...
  local name=$1; shift
  if "$@"; then ok "$name"; else not_ok "$name" "command: $*"; fi
}

# No controlling terminal, so the bootstrap never waits for an answer.
if command -v setsid >/dev/null 2>&1; then NOTTY=(setsid -w); else NOTTY=(); fi
run_boot() { # run_boot DIR ARGS... -> runs install.sh from a file, cwd DIR; output in $WORK/out
  local cwd=$1; shift
  (cd "$cwd" && "${NOTTY[@]}" bash "$BOOTSTRAP" "$@") >"$WORK/out" 2>&1 </dev/null
}
pipe_boot() { # pipe_boot DIR ARGS... -> 'cat install.sh | bash -s -- ARGS', cwd DIR
  local cwd=$1; shift
  (cd "$cwd" && "${NOTTY[@]}" bash -s -- "$@" <"$BOOTSTRAP") >"$WORK/out" 2>&1
}
out_has() { grep -qF -- "$1" "$WORK/out"; }
args_were() { [ -f "$BOOT_TEST_OUT" ] && [ "$(cat "$BOOT_TEST_OUT")" = "$1" ]; }

# --- a throwaway source repository with branch v3 and a tag -------------------------
SRC="$WORK/src"
mkdir -p "$SRC/v3"
cp "$BOOTSTRAP" "$SRC/install.sh"
cat >"$SRC/v3/install.sh" <<'EOF'
#!/usr/bin/env bash
# Fake v3 installer for the bootstrap tests: records its arguments.
printf '%s\n' "$*" >"$BOOT_TEST_OUT"
EOF
printf '#!/usr/bin/env bash\n' >"$SRC/v3/lab"
chmod +x "$SRC/install.sh" "$SRC/v3/install.sh" "$SRC/v3/lab"
git -C "$SRC" init -q -b v3
git -C "$SRC" add -A
git -C "$SRC" commit -q -m "v3 layout"
git -C "$SRC" tag v9.9.9-test
URL="file://$SRC"

# --- tests ----------------------------------------------------------------------------
run_boot "$WORK" --help
check "--help exits 0 and clones nothing" test ! -e "$WORK/lakehouse-lab"
check "--help lists the bootstrap options" out_has "--ref REF"

rm -f "$BOOT_TEST_OUT"
if run_boot "$WORK" --repo "$URL" --ref v3 --dir "$WORK/a" --profile engineer --domain lab.localhost; then
  ok "fresh clone at --ref v3 succeeds"
else
  not_ok "fresh clone at --ref v3 succeeds" "$(cat "$WORK/out")"
fi
check "the checkout exists on branch v3" test "$(git -C "$WORK/a" symbolic-ref --short HEAD 2>/dev/null)" = v3
check "unknown options reach v3/install.sh unchanged" args_were "--profile engineer --domain lab.localhost"
check "the plan names the ref and directory" out_has "ref        : v3"
check "the plan shows the clone command" out_has "git clone --branch v3"

rm -f "$BOOT_TEST_OUT"
pipe_boot "$WORK" --repo "$URL" --ref v3 --dir "$WORK/b" -- --help || true
check "piped to bash (bash -s --): '--' passes --help to v3/install.sh" args_were "--help"

rm -f "$BOOT_TEST_OUT"
mkdir -p "$WORK/default-dir"
pipe_boot "$WORK/default-dir" --repo "$URL" --ref v3 --non-interactive || true
check "default --dir is ./lakehouse-lab" test -f "$WORK/default-dir/lakehouse-lab/v3/install.sh"
check "--non-interactive is passed on (and implies --yes)" args_were "--non-interactive"

# A partial download must run nothing: cut the script at several points and pipe each.
partial_ok=1
size=$(wc -c <"$BOOTSTRAP")
for cut in 200 1000 3000 $((size / 2)) $((size - 40)) $((size - 3)); do
  rm -rf "$WORK/partial" "$BOOT_TEST_OUT"; mkdir -p "$WORK/partial"
  (cd "$WORK/partial" && head -c "$cut" "$BOOTSTRAP" | LAKEHOUSE_REPO="$URL" LAKEHOUSE_REF=v3 "${NOTTY[@]}" bash) >/dev/null 2>&1 || true
  if [ -n "$(ls -A "$WORK/partial")" ] || [ -f "$BOOT_TEST_OUT" ]; then partial_ok=0; echo "     cut at $cut bytes did something"; fi
done
check "a truncated download runs nothing" test "$partial_ok" = 1

mkdir -p "$WORK/notrepo"; echo keep >"$WORK/notrepo/file.txt"
if run_boot "$WORK" --repo "$URL" --ref v3 --dir "$WORK/notrepo" --yes; then
  not_ok "refuses a non-empty directory that is not a checkout"
else
  ok "refuses a non-empty directory that is not a checkout"
fi
check "  ...and leaves it unchanged" test "$(ls -A "$WORK/notrepo")" = file.txt

mkdir -p "$WORK/v2"; git -C "$WORK/v2" init -q -b main
touch "$WORK/v2/docker-compose.yml" "$WORK/v2/start-lakehouse.sh"
git -C "$WORK/v2" add -A; git -C "$WORK/v2" commit -q -m v2
if run_boot "$WORK" --repo "$URL" --ref v3 --dir "$WORK/v2" --yes; then
  not_ok "refuses a V2 install"
else
  ok "refuses a V2 install"
fi
check "  ...and explains how to keep V2" out_has "v2.1.1-final"
check "  ...and leaves it unchanged" test ! -e "$WORK/v2/v3"
if run_boot "$WORK/v2" --repo "$URL" --ref v3 --yes; then
  not_ok "run from inside a V2 install with no --dir: refuses (no nested clone)"
else
  ok "run from inside a V2 install with no --dir: refuses (no nested clone)"
fi
check "  ...and creates nothing inside it" test ! -e "$WORK/v2/lakehouse-lab"

# Update an existing, clean checkout: fast-forward to the new commit.
echo new >"$SRC/NEW_FILE"; git -C "$SRC" add NEW_FILE; git -C "$SRC" commit -q -m "new file"
rm -f "$BOOT_TEST_OUT"
if run_boot "$WORK" --repo "$URL" --ref v3 --dir "$WORK/a" --yes; then
  ok "updates an existing clean checkout"
else
  not_ok "updates an existing clean checkout" "$(cat "$WORK/out")"
fi
check "  ...fast-forwarded to the new commit" test -f "$WORK/a/NEW_FILE"
check "  ...and ran the installer" test -f "$BOOT_TEST_OUT"

# A ref without v3/ (like a V2 tag) never replaces a V3 checkout.
git -C "$SRC" checkout -q --orphan v2-like
git -C "$SRC" rm -rq --cached . && rm -rf "${SRC:?}/v3" && touch "$SRC/docker-compose.yml"
git -C "$SRC" add docker-compose.yml && git -C "$SRC" commit -q -m "v2-like" && git -C "$SRC" tag v2-like-tag
git -C "$SRC" checkout -q -f v3
if run_boot "$WORK" --repo "$URL" --ref v2-like-tag --dir "$WORK/a" --yes; then
  not_ok "refuses to move a V3 checkout to a ref without v3/"
else
  ok "refuses to move a V3 checkout to a ref without v3/"
fi
check "  ...and leaves the checkout on v3" test -f "$WORK/a/v3/install.sh"

echo "local change" >>"$WORK/a/v3/lab"
if run_boot "$WORK" --repo "$URL" --ref v3 --dir "$WORK/a" --yes; then
  not_ok "refuses a checkout with uncommitted changes"
else
  ok "refuses a checkout with uncommitted changes"
fi
check "  ...and keeps the change" grep -q "local change" "$WORK/a/v3/lab"
git -C "$WORK/a" checkout -q -- v3/lab

# Untracked per-install files (settings, secrets) do not block an update.
echo "LAB_DOMAIN=lab.localhost" >"$WORK/a/v3/.env"
if run_boot "$WORK" --repo "$URL" --ref v3 --dir "$WORK/a" --yes; then
  ok "untracked settings files do not block an update"
else
  not_ok "untracked settings files do not block an update" "$(cat "$WORK/out")"
fi
check "  ...and are kept" test -f "$WORK/a/v3/.env"

if run_boot "$WORK" --repo "file://$WORK/v2" --ref v3 --dir "$WORK/a" --yes; then
  not_ok "refuses a checkout of a different repository"
else
  ok "refuses a checkout of a different repository"
fi

if run_boot "$WORK" --repo "$URL" --ref v9.9.9-test --dir "$WORK/tag" --yes; then
  ok "a tag ref clones"
else
  not_ok "a tag ref clones" "$(cat "$WORK/out")"
fi
check "  ...at the tag" test "$(git -C "$WORK/tag" describe --tags 2>/dev/null)" = v9.9.9-test

if run_boot "$WORK" --repo "$URL" --ref no-such-branch --dir "$WORK/missing" --yes; then
  not_ok "an unknown ref fails"
else
  ok "an unknown ref fails"
fi
check "  ...and leaves no directory behind" test ! -e "$WORK/missing"

for bad in "--upload-pack=touch${IFS:0:1}x" "-x" "main..v3" 'a;b'; do
  if run_boot "$WORK" --repo "$URL" --ref "$bad" --dir "$WORK/bad" --yes; then
    not_ok "rejects --ref '$bad'"
  else
    ok "rejects --ref '$bad'"
  fi
done
check "  ...and clones nothing" test ! -e "$WORK/bad"

rm -f "$BOOT_TEST_OUT"
run_boot "$WORK" --repo "$URL" --ref v3 --dir "$WORK/c" --yes --github-client-secret s3cr3t-value --admin-user=ann || true
check "secret values are hidden in the printed plan" bash -c "! grep -q s3cr3t-value '$WORK/out'"
check "  ...but reach v3/install.sh" args_were "--github-client-secret s3cr3t-value --admin-user=ann"

# ./install.sh inside a checkout with no --dir/--ref uses that checkout (no nested clone).
rm -f "$BOOT_TEST_OUT"
(cd "$WORK/c" && "${NOTTY[@]}" bash ./install.sh --profile core) >"$WORK/out" 2>&1 </dev/null || true
check "./install.sh in a checkout runs its own v3/install.sh" args_were "--profile core"
check "  ...without cloning into it" test ! -e "$WORK/c/lakehouse-lab"

# 'curl | bash' from the top of a checkout also uses it.
rm -f "$BOOT_TEST_OUT"
pipe_boot "$WORK/c" --repo "$URL" --ref v3 --yes --profile full || true
check "piped from the top of a checkout: uses it" args_were "--profile full"
check "  ...without cloning into it" test ! -e "$WORK/c/lakehouse-lab"

echo
echo "bootstrap tests: $pass passed, $fail failed"
[ "$fail" = 0 ]
