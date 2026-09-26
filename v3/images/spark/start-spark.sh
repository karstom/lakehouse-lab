#!/usr/bin/env bash
# Entrypoint of the Spark image: start-spark.sh master|worker|connect
# Settings come from /opt/spark/conf/spark-defaults.conf (config/spark, mounted read-only)
# and the container environment set in compose/spark.yaml. Nothing is installed or
# downloaded at start.
set -euo pipefail

role="${1:-}"
master_url="spark://${SPARK_MASTER_HOST:-spark-master}:7077"

case "$role" in
  master)
    exec spark-class org.apache.spark.deploy.master.Master \
      --host "${SPARK_MASTER_HOST:-spark-master}" --port 7077 --webui-port 8080
    ;;
  worker)
    exec spark-class org.apache.spark.deploy.worker.Worker \
      --cores "${SPARK_WORKER_CORES:-2}" --memory "${SPARK_WORKER_MEMORY:-1g}" \
      --webui-port 8081 "$master_url"
    ;;
  connect)
    # The shared Spark Connect server: a client-mode driver on the standalone cluster. Each
    # client gets its own session; the Iceberg catalog is configured per session with the
    # user's own token (OQ-15, see config/spark/spark-defaults.conf).
    exec spark-submit \
      --class org.apache.spark.sql.connect.service.SparkConnectServer \
      --name "Spark Connect" \
      --master "$master_url" \
      --driver-memory "${SPARK_CONNECT_DRIVER_MEMORY:-1g}" \
      --executor-memory "${SPARK_EXECUTOR_MEMORY:-1g}"
    ;;
  *)
    echo "usage: start-spark.sh master|worker|connect" >&2
    exit 64
    ;;
esac
