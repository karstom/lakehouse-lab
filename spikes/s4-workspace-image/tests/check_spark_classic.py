"""OQ-2 comparison: the same op on a classic in-container JVM driver (local mode)."""
import subprocess
import time

from pyspark.sql import SparkSession

t0 = time.time()
s = SparkSession.builder.master("local[2]").config("spark.driver.memory", "1g") \
    .config("spark.ui.enabled", "true").getOrCreate()
print(f"   JVM start+session: {time.time() - t0:.2f}s  spark.version={s.version}")
t0 = time.time()
res = (s.range(5_000_000).selectExpr("id % 10 AS k", "id")
       .groupBy("k").agg({"id": "sum"}).orderBy("k").collect())
print(f"   groupBy over 5M rows: {time.time() - t0:.2f}s  first={res[0]}")
print(f"   Spark UI in the user's container: {s.sparkContext.uiWebUrl}")
print("   " + subprocess.run(["ps", "-o", "rss=,comm=", "-C", "java"],
                              capture_output=True, text=True).stdout.strip() + " (KB RSS, java)")
s.stop()
print("PASS  classic driver")
