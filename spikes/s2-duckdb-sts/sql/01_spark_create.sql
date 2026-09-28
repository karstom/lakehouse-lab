-- S-2 setup: Spark writes the table DuckDB will read (5 rows, sum(amount) = 15.0).
CREATE NAMESPACE IF NOT EXISTS lakehouse.s2;
DROP TABLE IF EXISTS lakehouse.s2.events;
CREATE TABLE lakehouse.s2.events (id BIGINT, kind STRING, amount DOUBLE) USING iceberg;
INSERT INTO lakehouse.s2.events VALUES
  (1, 'click', 1.0), (2, 'click', 2.0), (3, 'view', 3.0), (4, 'view', 4.0), (5, 'buy', 5.0);
SELECT 'S2_SPARK_COUNT', count(*), sum(amount) FROM lakehouse.s2.events;
