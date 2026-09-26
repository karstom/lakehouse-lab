# Lakehouse Lab V3 Spark image (profile `engineer`): the master, the worker and the shared
# Spark Connect server all run it. Pins: versions.env only (ADR-012).
#
# Spark and its JDK come from the official apache/spark image (tag AND digest). They sit on
# the same Python base image as the workspace, because Python UDFs run on the workers and
# PySpark refuses a worker whose Python minor differs from the client's (the official image
# ships Python 3.10; the workspace runs PYTHON_IMAGE_TAG). INV_SPARK_VERSION_ALIGNMENT.
#
# The Iceberg Spark runtime and the Iceberg AWS bundle are baked in and checked by sha256
# (S-1 recipe; no hadoop-aws and no AWS SDK jars, no --packages download at runtime).
ARG SPARK_IMAGE_TAG
ARG SPARK_IMAGE_DIGEST
ARG PYTHON_IMAGE_TAG
ARG PYTHON_IMAGE_DIGEST
FROM apache/spark:${SPARK_IMAGE_TAG}@${SPARK_IMAGE_DIGEST} AS spark

FROM python:${PYTHON_IMAGE_TAG}@${PYTHON_IMAGE_DIGEST}
ARG SPARK_VERSION
ARG SCALA_BINARY_VERSION
ARG ICEBERG_VERSION
ARG ICEBERG_SPARK_RUNTIME_DIGEST
ARG ICEBERG_AWS_BUNDLE_DIGEST
ARG PYARROW_VERSION
ARG PANDAS_VERSION

ENV JAVA_HOME=/opt/java/openjdk \
    SPARK_HOME=/opt/spark \
    PYSPARK_PYTHON=python3 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SPARK_NO_DAEMONIZE=true
ENV PATH=${JAVA_HOME}/bin:${SPARK_HOME}/bin:${PATH}

COPY --from=spark /opt/java/openjdk /opt/java/openjdk
COPY --from=spark /opt/spark /opt/spark

RUN --mount=type=bind,source=fetch-jars.py,target=/tmp/fetch-jars.py \
    python3 /tmp/fetch-jars.py /opt/spark/jars "${SPARK_VERSION}" "${SCALA_BINARY_VERSION}" \
      "${ICEBERG_VERSION}" "${ICEBERG_SPARK_RUNTIME_DIGEST}" "${ICEBERG_AWS_BUNDLE_DIGEST}"

RUN --mount=type=bind,source=lock/constraints.txt,target=/tmp/constraints.txt \
    pip install --no-cache-dir -c /tmp/constraints.txt \
      "pyarrow==${PYARROW_VERSION}" \
      "pandas==${PANDAS_VERSION}"

# Same uid/gid as the official image. Spark writes only to its work dir and /tmp.
RUN groupadd --gid 185 spark \
    && useradd --uid 185 --gid spark --home-dir /opt/spark --no-create-home --shell /usr/sbin/nologin spark \
    && mkdir -p /opt/spark/work \
    && chown spark:spark /opt/spark/work

COPY --chmod=0755 start-spark.sh /usr/local/bin/start-spark.sh
COPY --chmod=0755 spark-health.py /usr/local/bin/spark-health.py
COPY --chmod=0755 spark-bind-ip.py /usr/local/bin/spark-bind-ip.py

USER spark
WORKDIR /opt/spark/work
ENTRYPOINT ["/usr/local/bin/start-spark.sh"]
