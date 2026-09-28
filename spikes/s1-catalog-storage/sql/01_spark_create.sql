-- Criterion 1: Spark creates namespace + Iceberg table and inserts rows via the REST catalog.
CREATE NAMESPACE IF NOT EXISTS lakehouse.s1;
-- Plain DROP (not PURGE): with remote signing, Spark/Iceberg 1.11 tries to delete the old files
-- client-side AFTER the catalog drop, and Lakekeeper's signer rejects requests for a table that no
-- longer exists ("Table does not exist ... at location"). See RESULTS.md.
DROP TABLE IF EXISTS lakehouse.s1.events;
CREATE TABLE lakehouse.s1.events (id BIGINT, kind STRING, amount DOUBLE) USING iceberg;
INSERT INTO lakehouse.s1.events VALUES
  (1, 'click', 1.0), (2, 'click', 2.0), (3, 'view', 3.0), (4, 'view', 4.0), (5, 'buy', 5.0);
SELECT 'S1_SPARK_COUNT', count(*) FROM lakehouse.s1.events;
SELECT 'S1_SPARK_SNAPSHOTS', count(*) FROM lakehouse.s1.events.snapshots;
