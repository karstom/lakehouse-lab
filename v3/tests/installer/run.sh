#!/usr/bin/env bash
# Installer test entry point.
#   tests/installer/run.sh          shellcheck + unit tests (no Docker daemon needed)
#   tests/installer/run.sh --e2e    ...plus the end-to-end test against the stub stack
#                                   (compose project v3-p1-inst, no published ports)
# ShellCheck: uses a local 'shellcheck' if present, else the pinned koalaman/shellcheck
# image (SHELLCHECK_IMAGE_TAG + SHELLCHECK_IMAGE_DIGEST from versions.env).
set -uo pipefail
HERE=$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)
V3=$(cd -P "$HERE/../.." && pwd)
rc=0

# Globs expand relative to v3/, whatever the caller's working directory is.
cd "$V3" || exit 1
files=(install.sh lab installer/*.sh tests/installer/*.sh tests/installer/fixtures/*.sh)

echo "== shellcheck"
if command -v shellcheck >/dev/null 2>&1; then
  (cd "$V3" && shellcheck -x -P SCRIPTDIR "${files[@]}") || rc=1
else
  tag=$(awk -F= '$1 == "SHELLCHECK_IMAGE_TAG" {print $2}' "$V3/versions.env")
  digest=$(awk -F= '$1 == "SHELLCHECK_IMAGE_DIGEST" {print $2}' "$V3/versions.env")
  if [ -n "$tag" ] && [ -n "$digest" ] && command -v docker >/dev/null 2>&1; then
    docker run --rm -v "$V3:/mnt:ro" -w /mnt "koalaman/shellcheck:${tag}@${digest}" -x -P SCRIPTDIR "${files[@]}" || rc=1
  else
    echo "shellcheck not available (no binary, no SHELLCHECK_IMAGE_TAG/DIGEST pin or no docker)"; rc=1
  fi
fi
[ "$rc" = 0 ] && echo "  clean"

echo "== unit"
out=$(bash "$HERE/test_unit.sh" 2>&1); urc=$?
grep -v '^  ok ' <<<"$out"
[ "$urc" = 0 ] || rc=1

if [ "${1:-}" = --e2e ]; then
  echo "== e2e"
  bash "$HERE/test_e2e.sh" || rc=1
fi
exit "$rc"
