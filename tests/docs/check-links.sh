#!/usr/bin/env bash
# Check the links in every tracked Markdown file with markdown-link-check and the
# repository's mlc_config.json (the same check CI runs in documentation-check.yml).
#
# Usage: bash tests/docs/check-links.sh [--offline] [files...]
#   --offline   check only links inside the repository (files and anchors), not web links
# Needs Node.js (npx). The markdown-link-check version is pinned here.
set -euo pipefail

MLC_VERSION=3.15.0
REPO_DIR=$(cd -P "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$REPO_DIR"

config=mlc_config.json
tmp=""
trap '[ -z "$tmp" ] || rm -f "$tmp"' EXIT
if [ "${1:-}" = --offline ]; then
  shift
  tmp=$(mktemp "${TMPDIR:-/tmp}/mlc-offline.XXXXXX.json")
  python3 - "$config" "$tmp" <<'EOF'
import json, sys
cfg = json.load(open(sys.argv[1]))
cfg.setdefault("ignorePatterns", []).append({"pattern": "^(https?|mailto):"})
json.dump(cfg, open(sys.argv[2], "w"))
EOF
  config=$tmp
fi

files=()
if [ $# -gt 0 ]; then
  files=("$@")
else
  # Tracked files plus new ones not yet added (but never git-ignored ones).
  while IFS= read -r -d '' f; do
    [ -f "$f" ] && files+=("$f")
  done < <(git ls-files -z --cached --others --exclude-standard -- '*.md' | sort -zu)
fi

echo "link check (markdown-link-check $MLC_VERSION): ${#files[@]} file(s)"
if ! npx --yes "markdown-link-check@$MLC_VERSION" --quiet --retry --config "$config" "${files[@]}"; then
  echo "link check: broken links (see ERROR lines above)"
  exit 1
fi
echo "link check: OK"
