# Tutor notes · E2 Table maintenance

For the Phase 5 AI tutor and for human facilitators. Guide the learner to the answer; do not
paste the solution. `lab-tracks check E2` says which check fails first.

## Learning objectives

By the end the learner can:

1. Explain an Iceberg snapshot as "a list of immutable data files", and a commit as moving
   the table's current pointer to a new snapshot.
2. Query an older version with `VERSION AS OF <snapshot id>` (or `TIMESTAMP AS OF`), and
   explain why a snapshot is not a backup.
3. Undo a bad write with `CALL lakehouse.system.rollback_to_snapshot(...)`, and say why it is
   instant (no data copied).
4. Describe the small files problem and fix it with `rewrite_data_files` (operation
   `replace`; same rows, fewer files).
5. Explain why snapshots must be expired (storage, deleted data still readable) and what is
   lost when they are (time travel to them), and run `expire_snapshots`.
6. Order maintenance safely: rescue or roll back first, expire last.

## Prerequisites

- Group `engineer` or `lab-admin`; profile `engineer` or `full`.
- Running notebook cells; E1's idea of a snapshot helps but is not required.

## Common mistakes and how to guide

| Symptom | Likely cause | Hint to give (in order, stop when they get it) |
|---|---|---|
| Checkpoint: "none above 30 C: the accidental delete is still in effect" | Step 6 not done, or failed | 1. "Which snapshot still has the deleted rows?" 2. `before_delete` from step 5. 3. Write `{before_delete}` in the f-string. |
| Same failure, but rollback says the snapshot does not exist | Expired (step 8) before rolling back | Explain it is gone for good (that is the point of expiry). `lab-tracks reset E2` and redo in order. Ask: "what would you do before expiring in production?" |
| "2400 rows in 12 batches" | Step 2 ran twice | Ask what `INSERT` does on a rerun. Reset and run once. Name the idea: idempotency (E3 uses `CREATE OR REPLACE`). |
| `readings_first_batch has 1200 rows` | Step 4 without `VERSION AS OF` | "Which version of the table did you copy?" Plain `DROP TABLE` the copy, rerun. |
| `cannot resolve TODO_SNAPSHOT_ID` | Placeholder left in step 6 | Point at the variable name; braces inside an f-string. |
| Procedure error mentioning `lakehouse.eng_...` | Catalog name passed to a procedure | Procedures take `'<namespace>.<table>'`. |
| "12 data files (operations: append, ...)" | Step 7 skipped | Run step 7; compare `.files` before and after. |
| "N snapshots are still kept" | Step 8 skipped or `retain_last` too high | Run step 8 as written. Discuss real retention (days, not 1). |
| `NotAuthorized` / token expired after ~1 h | Spark session token expired | Rerun the step 1 cell (a new session gets a fresh token). |
| Wants `DROP TABLE ... PURGE` | Habit from other Spark setups | Never in this lab: the catalog deletes the files; a plain `DROP` is right. |

## Hints ladder for the YOUR TURN cells

- Step 4: "How do you say *as of a version* in SQL?" → "`VERSION AS OF` goes right after the
  table name" → `SELECT * FROM {table} VERSION AS OF {first_snapshot}`.
- Step 6: "Which variable holds the snapshot before the delete?" → "It's printed in step 5" →
  `{before_delete}`.

## Questions to check understanding

- Why did the rollback take no time even though 328 rows came back?
- After compaction, how many snapshots does the table have, and why is it still using space
  for the 12 small files? (Until expiry, older snapshots still reference them.)
- A user asks you to delete their personal data. Is a `DELETE` enough? (No: expire the
  snapshots that still reference it.)
- Why is `retain_last => 1` fine here but a bad idea in production?

## Facts the tutor can rely on

- Table `lakehouse.eng_<user>.readings`: 12 batches × 100 rows = 1200 rows; 328 readings are
  above 30 °C, so after the accidental delete 872 rows remain.
- `readings_first_batch`: 100 rows, `batch_no` = 1 only.
- After step 7 there is 1 data file; after step 8, 1 snapshot (operation `replace`).
- Snapshot ids and timestamps differ per learner and per run.
- `lab-tracks reset E2` drops `readings` and `readings_first_batch` (plain `DROP TABLE`
  through Trino) and the namespace if it is then empty.
