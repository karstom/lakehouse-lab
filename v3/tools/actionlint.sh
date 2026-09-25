#!/usr/bin/env bash
# Lint the V3 GitHub workflows (.github/workflows/v3-*.yml) with the pinned actionlint
# container. It embeds ShellCheck, so run: blocks are checked too.
# Usage: v3/tools/actionlint.sh [workflow files...]
set -euo pipefail
V3_DIR=$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
REPO_DIR=$(cd -P "$V3_DIR/.." && pwd)
# shellcheck source=v3/tools/lib.sh
. "$V3_DIR/tools/lib.sh"
load_pins
image=$(pinned_image ACTIONLINT_IMAGE_TAG ACTIONLINT_IMAGE_DIGEST rhysd/actionlint)

if [ $# -gt 0 ]; then
  files=("$@")
else
  files=()
  for f in "$REPO_DIR"/.github/workflows/v3-*.yml; do
    [ -f "$f" ] && files+=(".github/workflows/${f##*/}")
  done
fi
[ ${#files[@]} -gt 0 ] || { echo "actionlint: no v3 workflows found" >&2; exit 1; }
echo "actionlint ($image): ${files[*]}"
docker run --rm --network none -v "$REPO_DIR:/repo:ro" -w /repo "$image" -color "${files[@]}"
echo "actionlint: OK"
