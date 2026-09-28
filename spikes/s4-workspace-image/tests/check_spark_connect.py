"""OQ-2: DataFrame ops from the workspace through Spark Connect, plus session isolation."""
import os
import time

from pyspark.sql import SparkSession

remote = os.environ["SPARK_REMOTE"]
t0 = time.time()
a = SparkSession.builder.remote(remote).getOrCreate()
print(f"   connect+session: {time.time() - t0:.2f}s  server spark.version={a.version}")

t0 = time.time()
res = (a.range(5_000_000).selectExpr("id % 10 AS k", "id")
       .groupBy("k").agg({"id": "sum"}).orderBy("k").collect())
print(f"   groupBy over 5M rows: {time.time() - t0:.2f}s  first={res[0]}")
assert len(res) == 10

pdf = a.createDataFrame([(1, "a"), (2, "b")], "id int, v string").toPandas()
assert list(pdf["v"]) == ["a", "b"]

# Two sessions (as two users would have) on the same server: temp views are per session.
b = SparkSession.builder.remote(remote).create()
a.range(3).createOrReplaceTempView("only_in_a")
print(f"   session ids: a={a.session_id[:8]} b={b.session_id[:8]}")
visible_in_b = [t.name for t in b.catalog.listTables()]
assert "only_in_a" not in visible_in_b, visible_in_b
# ...but they share one JVM, one SparkContext and its resources:
print(f"   a sees 'only_in_a': {'only_in_a' in [t.name for t in a.catalog.listTables()]}, "
      f"b sees it: False")
b.stop()
a.stop()
print("PASS  spark connect DataFrame op + session isolation")
