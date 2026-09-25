#!/bin/sh
# Download the Iceberg Spark runtime and AWS bundle matching the pinned versions into /opt/spark/jars.
set -eu
SPARK_VERSION="$1"; SCALA="$2"; ICEBERG="$3"
SPARK_MINOR=$(echo "$SPARK_VERSION" | cut -d. -f1,2)
M2=https://repo1.maven.org/maven2/org/apache/iceberg
for a in "iceberg-spark-runtime-${SPARK_MINOR}_${SCALA}" "iceberg-aws-bundle"; do
  curl -fsSL -o "/opt/spark/jars/${a}-${ICEBERG}.jar" "${M2}/${a}/${ICEBERG}/${a}-${ICEBERG}.jar"
  echo "fetched ${a}-${ICEBERG}.jar"
done
