#!/usr/bin/env bash
# Image ENTRYPOINT (under tini). No installs, no network: only per-home wiring, then exec.
# Runs for every start, including when a spawner overrides the CMD (ADR-007 rule).
set -euo pipefail

# $HOME is the user's volume, so image content under it would be hidden.
# DuckDB has no env var for its extension directory; link the baked, versioned directory
# into DuckDB's default search path (~/.duckdb/extensions/<version>). A new DuckDB version
# gets a new link, so this also survives image upgrades.
for vdir in "${DUCKDB_EXT_DIR}"/v*; do
  [ -d "$vdir" ] || continue
  mkdir -p "$HOME/.duckdb/extensions"
  link="$HOME/.duckdb/extensions/$(basename "$vdir")"
  [ -e "$link" ] || ln -s "$vdir" "$link"
done

# Starter content: copied once, on the first start of a new home. Never overwrites: the
# marker stops a re-copy after the user deletes or renames it, and --no-clobber keeps any
# file that already exists (for example in a home volume restored from elsewhere).
marker="$HOME/.lakehouse/starter-copied"
if [ ! -e "$marker" ] && [ -d /opt/lakehouse/starter ]; then
  mkdir -p "$HOME/.lakehouse" "$HOME/starter"
  cp -R --no-clobber /opt/lakehouse/starter/. "$HOME/starter/"
  date -u +%Y-%m-%dT%H:%M:%SZ >"$marker"
fi

# A CMD that names a program (spawner cmd override, `docker run IMG python ...`): run it as-is.
if [ $# -gt 0 ] && [ "${1#-}" = "$1" ]; then
  exec "$@"
fi
# Empty CMD, or only flags: choose the server. Flags are passed through.
if [ -n "${JUPYTERHUB_API_TOKEN:-}" ]; then
  exec jupyterhub-singleuser "$@"     # spawned by JupyterHub (DockerSpawner passes JUPYTERHUB_* env)
fi
exec jupyter lab --ip=0.0.0.0 --port=8888 --no-browser "$@"
