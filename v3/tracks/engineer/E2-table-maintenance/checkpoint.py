"""E2 checkpoint: undo, compact, expire. Did your table end up healthy and complete?

Run it with `lab-tracks check E2` (or `python checkpoint.py`). It looks at the RESULT only,
as you, through Trino: your tables and their snapshot metadata.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_shared"))

from trackcheck import Checkpoint, Fail, Trino, namespace  # noqa: E402

BATCHES, PER_BATCH = 12, 100


def expected_hot():
    """How many readings are above 30 C (the rows the 'accident' deletes); same formula as
    the notebook's write_batch()."""
    return sum(1 for b in range(1, BATCHES + 1) for i in range(PER_BATCH)
               if round(18 + (i * 7 + b * 13) % 17 + (i % 3) * 0.5, 1) > 30)


cp = Checkpoint("E2", "Table maintenance")
S = {}


def q(sql):
    return S["trino"].rows(sql)


@cp.check("the readings table exists")
def _table():
    S["trino"], S["ns"] = Trino(), namespace()
    S["t"] = f'lakehouse."{S["ns"]}"."readings"'
    if not S["trino"].table_exists(S["ns"], "readings"):
        raise Fail(f"no table lakehouse.{S['ns']}.readings", "Run steps 1 and 2 of the notebook.")
    return f"lakehouse.{S['ns']}.readings"


@cp.check("all 12 batches are there, and the deleted readings are back")
def _rows():
    n, batches, hot = q(f"SELECT count(*), count(DISTINCT batch_no), "
                        f"count_if(temperature_c > 30) FROM {S['t']}")[0]
    want = BATCHES * PER_BATCH
    if n == want - expected_hot() and hot == 0:
        raise Fail(f"{n} rows and none above 30 C: the accidental delete of step 5 is still in effect",
                   "Roll back to the snapshot before the delete (step 6): "
                   "CALL lakehouse.system.rollback_to_snapshot('<namespace>.readings', <snapshot id>).\n"
                   "If you already expired that snapshot, reset the module (lab-tracks reset E2) and "
                   "start again.")
    if n != want or batches != BATCHES:
        raise Fail(f"{n} rows in {batches} batches, want {want} rows in {BATCHES} batches",
                   "Write each of the 12 batches once (step 2). If you ran step 2 twice, reset the "
                   "module (lab-tracks reset E2) and start again.")
    if hot != expected_hot():
        raise Fail(f"{hot} readings above 30 C, want {expected_hot()}",
                   "Some rows are missing or changed. Reset the module and start again.")
    return f"{n} rows, {batches} batches, {hot} readings above 30 C"


@cp.check("the first batch is saved in its own table")
def _first_batch():
    if not S["trino"].table_exists(S["ns"], "readings_first_batch"):
        raise Fail(f"no table lakehouse.{S['ns']}.readings_first_batch",
                   "Step 4: CREATE TABLE ... AS SELECT * FROM <table> VERSION AS OF <first snapshot>.")
    n, lo, hi = q(f'SELECT count(*), min(batch_no), max(batch_no) '
                  f'FROM lakehouse."{S["ns"]}"."readings_first_batch"')[0]
    if n != PER_BATCH or lo != 1 or hi != 1:
        raise Fail(f"readings_first_batch has {n} rows of batches {lo}..{hi}; want {PER_BATCH} rows "
                   f"of batch 1 only",
                   "The copy must read the table AS OF THE FIRST SNAPSHOT (VERSION AS OF ...), not "
                   "the current table. Drop readings_first_batch (plain DROP TABLE) and redo step 4.")
    return f"{n} rows of batch 1"


@cp.check("small files are compacted")
def _compacted():
    files = S["trino"].one(f'SELECT count(*) FROM lakehouse."{S["ns"]}"."readings$files"')
    ops = [r[3] for r in S["trino"].snapshots(S["ns"], "readings")]
    if "replace" not in ops or files > 2:
        raise Fail(f"{files} data files (operations: {', '.join(ops) or 'none'})",
                   "Run step 7: CALL lakehouse.system.rewrite_data_files(table => '<namespace>.readings').")
    return f"{files} data file(s) after rewrite_data_files"


@cp.check("old snapshots are expired")
def _expired():
    snaps = S["trino"].snapshots(S["ns"], "readings")
    if len(snaps) > 2:
        raise Fail(f"{len(snaps)} snapshots are still kept",
                   "Run step 8: CALL lakehouse.system.expire_snapshots(table => '<namespace>.readings', "
                   "older_than => current_timestamp(), retain_last => 1).")
    return f"{len(snaps)} snapshot(s) left, current operation: {snaps[-1][3]}"


if __name__ == "__main__":
    sys.exit(cp.run())
