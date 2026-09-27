"""Reference solution for E2 (test-only; never copied into homes).

    python solve.py ~/tracks/engineer/E2-table-maintenance

Resets the module, then runs the lesson's own notebook with the YOUR TURN cells filled in.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_lib"))
import solvelib  # noqa: E402

ANSWERS = {
    "SELECT * FROM {table}   -- TODO: read the table as of the first snapshot":
        "SELECT * FROM {table} VERSION AS OF {first_snapshot}",
    "TODO_SNAPSHOT_ID": "{before_delete}",
}

mod = solvelib.module_dir()
solvelib.reset(mod)
nb = solvelib.solve_notebook(mod, "notebook.ipynb", ANSWERS)
print(solvelib.outputs_text(nb)[-4000:])
