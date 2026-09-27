"""Reference solution for E1 (test-only; never copied into homes).

    python solve.py ~/tracks/engineer/E1-files-to-iceberg

Resets the module, then runs the lesson's own notebook with the two YOUR TURN cells filled
in, as the learner. Safe to run again.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_lib"))
import solvelib  # noqa: E402

ANSWERS = {
    "-- TODO: partition by the day of shipped_at":
        "PARTITIONED BY (days(shipped_at))",
    "# TODO: load the files of 2026-03-02 and 2026-03-03 here":
        'load_file("data/shipments_2026-03-02.csv")\nload_file("data/shipments_2026-03-03.csv")',
}

mod = solvelib.module_dir()
solvelib.reset(mod)
nb = solvelib.solve_notebook(mod, "notebook.ipynb", ANSWERS)
print(solvelib.outputs_text(nb)[-3000:])
