# Spark + Iceberg runtime + Iceberg AWS bundle baked in at build time (no runtime --packages download).
ARG SPARK_IMAGE_TAG
FROM apache/spark:${SPARK_IMAGE_TAG}
ARG SPARK_VERSION
ARG SCALA_BINARY_VERSION
ARG ICEBERG_VERSION
USER root
COPY fetch-jars.sh /tmp/fetch-jars.sh
RUN sh /tmp/fetch-jars.sh "${SPARK_VERSION}" "${SCALA_BINARY_VERSION}" "${ICEBERG_VERSION}" && rm /tmp/fetch-jars.sh
USER spark
