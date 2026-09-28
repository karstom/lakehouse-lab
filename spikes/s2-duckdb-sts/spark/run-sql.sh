#!/bin/sh
# One-shot Spark SQL job against the Lakekeeper catalog. Usage: run-sql.sh <file-in-/opt/spikes/sql>
# Query results go to stdout; on failure the exception lines (not the stack frames) go to stderr.
set -eu
if /opt/spark/bin/spark-sql --conf spark.driver.memory=1g -f "/opt/spikes/sql/$1" 2>/tmp/spark-sql.err; then
  exit 0
fi
grep -vE '^\s+at |^\s+\.\.\. [0-9]+ more' /tmp/spark-sql.err | grep -E 'Exception|Error|Caused by' | head -30 >&2
exit 1
