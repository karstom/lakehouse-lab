#!/usr/bin/env bash
# Build-time only: OS packages and the notebook user (uid 1000 / gid 100, as docker-stacks
# and DockerSpawner expect). Debian package versions come from the pinned base image's suite.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates curl git less nano openssh-client procps tini unzip
rm -rf /var/lib/apt/lists/*
useradd --create-home --uid "${NB_UID}" --gid "${NB_GID}" --shell /bin/bash "${NB_USER}"
install -d -o "${NB_UID}" -g "${NB_GID}" /opt/duckdb /opt/duckdb/extensions
