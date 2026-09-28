#!/usr/bin/env bash
# Build-time only: install code-server from the official release tarball (bundles node).
set -euo pipefail
version="$1"
arch="$(dpkg --print-architecture)"   # amd64 | arm64
url="https://github.com/coder/code-server/releases/download/v${version}/code-server-${version}-linux-${arch}.tar.gz"
mkdir -p /opt/code-server
curl -fsSL "$url" | tar -xz --strip-components=1 -C /opt/code-server
ln -s /opt/code-server/bin/code-server /usr/local/bin/code-server
code-server --version
