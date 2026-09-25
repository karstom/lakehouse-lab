-- S-2 criterion 3 cross-check: does Spark see the row(s) DuckDB inserted?
REFRESH TABLE lakehouse.s2.events;
SELECT 'S2_SPARK_AFTER', count(*), sum(amount) FROM lakehouse.s2.events;
SELECT 'S2_SPARK_DUCK_ROW', id, kind, amount FROM lakehouse.s2.events WHERE id >= 100 ORDER BY id;
SELECT 'S2_SPARK_SNAP', operation, summary['engine-name'] FROM lakehouse.s2.events.snapshots ORDER BY committed_at;
