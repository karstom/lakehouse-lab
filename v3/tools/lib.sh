# shellcheck shell=bash
# Shared helpers for the v3 tooling scripts. Sourced, never executed.
# Callers set V3_DIR first.

: "${V3_DIR:?V3_DIR must be set before sourcing tools/lib.sh}"

# load_pins -> export every KEY=VALUE from v3/.pins/*.env, then v3/versions.env (which wins).
# Plain KEY=VALUE files only; values are taken literally (no shell evaluation).
load_pins() {
  local f line key val
  for f in "$V3_DIR"/.pins/*.env "$V3_DIR/versions.env"; do
    [ -f "$f" ] || continue
    while IFS= read -r line || [ -n "$line" ]; do
      case "$line" in ''|'#'*) continue ;; esac
      key=${line%%=*}
      val=${line#*=}
      [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
      export "$key=$val"
    done <"$f"
  done
}

# pinned_image TAG_VAR DIGEST_VAR REPO -> REPO:TAG@DIGEST from the loaded pins.
pinned_image() {
  local tag=${!1:-} digest=${!2:-}
  [ -n "$tag" ] && [ -n "$digest" ] || { echo "missing pin $1/$2 (v3/versions.env)" >&2; return 1; }
  printf '%s:%s@%s\n' "$3" "$tag" "$digest"
}

# v3_files -> NUL-separated paths (relative to the repo root) of tracked and
# untracked-but-not-ignored files under v3/.
v3_files() {
  git -C "$V3_DIR/.." ls-files -z --cached --others --exclude-standard -- v3
}
