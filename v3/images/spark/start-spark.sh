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
    #
    # Only gRPC 15002 listens on every interface (workspaces and Airflow reach it on `lab`).
    # The driver RPC, the block manager and the application UI (4040; Spark's WebUI binds to
    # SPARK_LOCAL_IP) bind to this container's `spark` address alone, so a notebook on `lab`
    # cannot open them; engineers see the app UI through the master's reverse proxy at
    # spark.<LAB_DOMAIN> (CONTRACT Phase 3, Networks). No fallback to 0.0.0.0.
    bind_ip="$(spark-bind-ip.py "${SPARK_BIND_PEER:?SPARK_BIND_PEER names a host on the spark network}")"
    export SPARK_LOCAL_IP="$bind_ip"
    echo "start-spark: driver and application UI bind to ${bind_ip} (route to ${SPARK_BIND_PEER})" >&2
    exec spark-submit \
      --class org.apache.spark.sql.connect.service.SparkConnectServer \
      --name "Spark Connect" \
      --master "$master_url" \
      --conf "spark.driver.bindAddress=${bind_ip}" \
      --driver-memory "${SPARK_CONNECT_DRIVER_MEMORY:-1g}" \
      --executor-memory "${SPARK_EXECUTOR_MEMORY:-1g}"
    ;;
  *)
    echo "usage: start-spark.sh master|worker|connect" >&2
    exit 64
    ;;
esac
