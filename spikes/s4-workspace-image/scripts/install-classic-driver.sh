#!/usr/bin/env bash
# Build-time only (OQ-2 comparison stage): JRE + full pyspark wheel (bundled Spark jars).
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends openjdk-17-jre-headless
rm -rf /var/lib/apt/lists/*
pip uninstall -y pyspark-client
pip install "pyspark==$1"
