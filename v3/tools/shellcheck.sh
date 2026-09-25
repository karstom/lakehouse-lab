#!/usr/bin/env bash
# ShellCheck every v3 shell script (*.sh, *.bash, *.bats, and extension-less files with a
# sh/bash shebang, e.g. v3/install.sh and v3/lab) with the pinned ShellCheck container.
# Usage: v3/tools/shellcheck.sh [extra shellcheck args]
# Default severity is 'warning' (info/style notes are shown by '-S info' but do not fail).
set -euo pipefail
V3_DIR=$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
REPO_DIR=$(cd -P "$V3_DIR/.." && pwd)
# shellcheck source=v3/tools/lib.sh
. "$V3_DIR/tools/lib.sh"
load_pins
image=$(pinned_image SHELLCHECK_IMAGE_TAG SHELLCHECK_IMAGE_DIGEST koalaman/shellcheck)

files=()
while IFS= read -r -d '' f; do
  [ -f "$REPO_DIR/$f" ] || continue
  case "${f##*/}" in
    *.sh|*.bash|*.bats) files+=("$f") ;;
    *.*) ;;
    *) head -n1 "$REPO_DIR/$f" 2>/dev/null | grep -Eq '^#!.*\b(ba)?sh\b' && files+=("$f") ;;
  esac
done < <(v3_files)

if [ ${#files[@]} -eq 0 ]; then
  echo "shellcheck: no shell scripts under v3/"
  exit 0
fi
echo "shellcheck ($image): ${#files[@]} file(s)"
# -x follows 'source' lines; source-path=SCRIPTDIR resolves them relative to each script.
docker run --rm --network none -v "$REPO_DIR:/mnt:ro" -w /mnt "$image" \
  -x --source-path=SCRIPTDIR --external-sources -S warning "$@" "${files[@]}"
echo "shellcheck: OK"
