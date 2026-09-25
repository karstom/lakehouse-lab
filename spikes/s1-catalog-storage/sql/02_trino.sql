SELECT 'S1_TRINO_COUNT', count(*) FROM lakehouse.s1.events;
UPDATE lakehouse.s1.events SET amount = amount * 100 WHERE kind = 'click';
DELETE FROM lakehouse.s1.events WHERE kind = 'view';
SELECT 'S1_TRINO_AFTER', count(*), sum(amount) FROM lakehouse.s1.events;
