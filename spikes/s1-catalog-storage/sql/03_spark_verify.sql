-- Criterion 2 (second half): Spark sees Trino's UPDATE + DELETE as new snapshots.
REFRESH TABLE lakehouse.s1.events;
SELECT 'S1_SPARK_ROWS', id, kind, amount FROM lakehouse.s1.events ORDER BY id;
SELECT 'S1_SPARK_SNAP', snapshot_id, operation, summary['trino_query_id'] IS NOT NULL AS by_trino
  FROM lakehouse.s1.events.snapshots ORDER BY committed_at;
