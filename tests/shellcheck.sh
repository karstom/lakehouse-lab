#!/usr/bin/env bash
# ShellCheck the repository-level shell scripts (the root install.sh bootstrap and tests/)
# with the same pinned ShellCheck image as v3/tools/shellcheck.sh (which covers v3/).
# legacy/ is archived V2 code and is not checked.
# Usage: bash tests/shellcheck.sh [extra shellcheck args]
set -euo pipefail
REPO_DIR=$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
V3_DIR="$REPO_DIR/v3"
# shellcheck source=v3/tools/lib.sh
. "$V3_DIR/tools/lib.sh"
load_pins
image=$(pinned_image SHELLCHECK_IMAGE_TAG SHELLCHECK_IMAGE_DIGEST koalaman/shellcheck)

files=(install.sh)
while IFS= read -r -d '' f; do
  [ -f "$REPO_DIR/$f" ] && files+=("$f")
done < <(git -C "$REPO_DIR" ls-files -z --cached --others --exclude-standard -- 'tests/*.sh')

echo "shellcheck ($image): ${files[*]}"
docker run --rm --network none -v "$REPO_DIR:/mnt:ro" -w /mnt "$image" \
  -x --source-path=SCRIPTDIR --external-sources -S warning "$@" "${files[@]}"
echo "shellcheck: OK"
