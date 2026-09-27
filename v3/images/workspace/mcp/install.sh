#!/usr/bin/env bash
# Build step of the workspace image (Dockerfile RUN, as root): the lab's MCP servers.
# Creates /opt/lakehouse/mcp/venv (its own venv: dbt-mcp pins exact versions of mcp, fastapi,
# pyjwt, ...; the notebook environment stays untouched), installs requirements.in with the
# GENERATED lock, copies the lab_mcp package and servers.json, and puts `lab-mcp` on PATH.
# Versions come from the build args (versions.env) that pip expands in requirements.in.
# No network at runtime: everything is installed here.
set -euo pipefail
src=$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)
dest=${LAB_MCP_HOME:-/opt/lakehouse/mcp}
for v in DBT_MCP_VERSION MCP_SDK_VERSION SQLGLOT_VERSION TRINO_PYTHON_VERSION; do
  [ -n "${!v:-}" ] || { echo "mcp/install.sh: build arg $v is not set" >&2; exit 1; }
done
python -m venv "$dest/venv"
"$dest/venv/bin/pip" install --no-cache-dir -r "$src/requirements.in" -c "$src/lock/constraints.txt"
"$dest/venv/bin/pip" check
rm -rf "$dest/lab_mcp"
cp -R "$src/lab_mcp" "$dest/lab_mcp"
install -m 0644 "$src/servers.json" "$dest/servers.json"
install -m 0644 "$src/README.md" "$dest/README.md"
install -m 0755 "$src/bin/lab-mcp" /opt/lakehouse/bin/lab-mcp
chmod -R a+rX,go-w "$dest"
"$dest/venv/bin/python" -m compileall -q "$dest/lab_mcp"
# Smoke: every server module imports in the venv (with the lab's package on the path).
PYTHONPATH="$dest:/opt/lakehouse/python" "$dest/venv/bin/python" -c \
  'import lab_mcp.trino_server, lab_mcp.context_server, lab_mcp.dbt_launcher, dbt_mcp.main'
