#!/usr/bin/env bash
# Image ENTRYPOINT (under tini). No installs, no network: only per-home wiring, then exec.
# Runs for every start, including when a spawner overrides the CMD.
set -euo pipefail

# $HOME is a JupyterHub-mounted volume, so image content under it would be hidden.
# DuckDB has no env var for its extension directory; link the baked, versioned directory
# into DuckDB's default search path (~/.duckdb/extensions/<version>).
for vdir in "${DUCKDB_EXT_DIR}"/v*; do
  [ -d "$vdir" ] || continue
  mkdir -p "$HOME/.duckdb/extensions"
  link="$HOME/.duckdb/extensions/$(basename "$vdir")"
  [ -e "$link" ] || ln -s "$vdir" "$link"
done

# A CMD that names a program (spawner cmd override, `docker run IMG python ...`): run it as-is.
if [ $# -gt 0 ] && [ "${1#-}" = "$1" ]; then
  exec "$@"
fi
# Empty CMD, or only flags: choose the server. Flags are passed through.
if [ -n "${JUPYTERHUB_API_TOKEN:-}" ]; then
  exec jupyterhub-singleuser "$@"     # spawned by JupyterHub (DockerSpawner passes JUPYTERHUB_* env)
fi
exec jupyter lab --ip=0.0.0.0 --port=8888 --no-browser "$@"
