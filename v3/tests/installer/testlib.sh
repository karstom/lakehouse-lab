# shellcheck shell=bash
# Tiny assertion helpers for the installer tests (plain bash, no bats).

T_PASS=0
T_FAIL=0
T_NAME=""

t_begin() { T_NAME=$1; }
t_pass()  { T_PASS=$((T_PASS + 1)); printf '  ok   %s\n' "${T_NAME}${1:+: $1}"; }
t_fail()  { T_FAIL=$((T_FAIL + 1)); printf '  FAIL %s\n' "${T_NAME}${1:+: $1}"; }

assert() {  # assert "desc" cmd args...
  local d=$1; shift
  if "$@" >/dev/null 2>&1; then t_pass "$d"; else t_fail "$d"; fi
}
assert_not() {
  local d=$1; shift
  if "$@" >/dev/null 2>&1; then t_fail "$d"; else t_pass "$d"; fi
}
assert_eq() {  # assert_eq "desc" expected actual
  if [ "$2" = "$3" ]; then t_pass "$1"; else t_fail "$1 (expected '$2', got '$3')"; fi
}
assert_match() {  # assert_match "desc" regex value
  if [[ "$3" =~ $2 ]]; then t_pass "$1"; else t_fail "$1 ('$3' !~ /$2/)"; fi
}
assert_contains() {  # assert_contains "desc" needle haystack
  case "$3" in *"$2"*) t_pass "$1" ;; *) t_fail "$1 (missing '$2')" ;; esac
}

t_summary() {
  printf '%s: %d passed, %d failed\n' "${1:-tests}" "$T_PASS" "$T_FAIL"
  [ "$T_FAIL" -eq 0 ]
}

# make_tree DIR -> a copy of the installer (install.sh, lab, installer/, versions.env)
# with the stub compose fixture in place of the real compose.yaml.
make_tree() {
  local dst=$1 src
  src=$(cd -P "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
  mkdir -p "$dst/tests/smoke"
  cp "$src/install.sh" "$src/lab" "$src/versions.env" "$dst/"
  cp -r "$src/installer" "$dst/installer"
  cp "$src/tests/installer/fixtures/compose.yaml" "$src/tests/installer/fixtures/check-env.sh" "$dst/"
  cp "$src/tests/installer/fixtures/smoke-run.sh" "$dst/tests/smoke/run.sh"
}
