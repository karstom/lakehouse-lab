#!/usr/bin/env bash
# Tiny Spark Connect server for OQ-2: driver + local executors in one JVM, no cluster.
set -euo pipefail
exec /opt/spark/sbin/start-connect-server.sh \
  --master "local[4]" \
  --conf spark.driver.memory=2g \
  --conf spark.connect.grpc.binding.port=15002 \
  --conf spark.ui.port=4040
