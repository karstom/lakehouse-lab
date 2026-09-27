"""Helpers for the engineer track's reference solutions (test-only; never copied into homes).

A solution runs as the learner inside their workspace:

    python ~/<solutions>/engineer/<module>/solve.py ~/tracks/engineer/<module>

and, where the module has a notebook, solves it the way a learner does: it fills the
YOUR TURN cells of the lesson's own notebook with the answers and executes it top to bottom
(nbclient, the kernel a learner uses). So CI tests the lesson content itself, not a copy of
it. The executed notebook is written next to the solution, never into the module folder.
"""
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def module_dir():
    if len(sys.argv) < 2:
        raise SystemExit("usage: solve.py <module dir>, e.g. ~/tracks/engineer/E1-files-to-iceberg")
    d = os.path.abspath(os.path.expanduser(sys.argv[1]))
    if not os.path.isfile(os.path.join(d, "module.json")):
        raise SystemExit(f"{d} is not a track module (no module.json)")
    sys.path.insert(0, os.path.join(d, "..", "_shared"))
    sys.path.insert(0, d)
    return d


def reset(mod):
    """Start from the module's starting state (idempotent solutions)."""
    import trackcheck
    trackcheck.reset(mod, log=lambda m: print(f"[solve] reset:{m}"))


def solve_notebook(mod, name, answers, timeout=900, out_dir=None):
    """Fill the notebook's TODO lines with `answers` ({exact line text: replacement}),
    execute it with the module folder as working directory, and fail if any cell failed or
    any answer did not match exactly once."""
    import nbformat
    from nbclient import NotebookClient

    src = os.path.join(mod, name)
    nb = nbformat.read(src, as_version=4)
    for old, new in answers.items():
        hits = [c for c in nb.cells if c.cell_type == "code" and old in c.source]
        if len(hits) != 1:
            raise SystemExit(f"answer anchor {old!r} found in {len(hits)} cells of {name}, want 1")
        hits[0].source = hits[0].source.replace(old, new)
    t0 = time.time()
    client = NotebookClient(nb, timeout=timeout, kernel_name="python3",
                            resources={"metadata": {"path": mod}})
    try:
        client.execute()
    finally:
        out_dir = out_dir or os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "out")
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, name.replace(".ipynb", ".executed.ipynb"))
        nbformat.write(nb, out)
        print(f"[solve] executed {name} in {time.time() - t0:.0f}s -> {out}")
    for c in nb.cells:
        for o in c.get("outputs", []):
            if o.get("output_type") == "error":
                raise SystemExit(f"cell failed: {o.get('ename')}: {o.get('evalue')}")
    return nb


def outputs_text(nb):
    """All text a notebook printed (for logs and expected-output checks)."""
    parts = []
    for c in nb.cells:
        for o in c.get("outputs", []):
            if o.get("output_type") == "stream":
                parts.append(o.get("text", ""))
            elif o.get("output_type") in ("execute_result", "display_data"):
                parts.append(o.get("data", {}).get("text/plain", ""))
    return "".join(parts)


def copy_into(src, dst):
    """Copy a file or folder (the learner's `cp`), creating parents."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.isdir(src):
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst)
    print(f"[solve] copied {src} -> {dst}")


def wait_for(fn, what, timeout=900, every=10):
    """Poll fn() until it returns a truthy value (e.g. an Airflow run's output appeared)."""
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        try:
            v = fn()
            if v:
                print(f"[solve] {what}: ready after {time.time() - t0:.0f}s ({v})")
                return v
        except Exception as e:  # noqa: BLE001 - keep polling; show the last error on timeout
            last = f"{type(e).__name__}: {e}"
        time.sleep(every)
    raise SystemExit(f"[solve] {what}: not ready after {timeout}s" + (f" (last error: {last})" if last else ""))


def wait_for_runs(tables, timeout, note=""):
    """Wait until every table (schema, table) exists, i.e. an Airflow run of the learner's
    DAG wrote it (the solution reset dropped it first). No trigger is needed on a DAG's first
    appearance: a new, unpaused @daily DAG with catchup=False gets one scheduled run for the
    latest midnight straight away (the lab creates DAGs unpaused). A learner, or a harness
    that has the learner's Airflow login, can also press Trigger; either run satisfies this.
    `--no-wait` skips the wait (the caller triggers and waits itself)."""
    if "--no-wait" in sys.argv:
        print("[solve] --no-wait: not waiting for Airflow runs")
        return
    import trackcheck
    t = trackcheck.Trino()
    left = list(tables)

    def ready():
        for schema, table in list(left):
            if t.table_exists(schema, table):
                left.remove((schema, table))
        return not left and "all written"
    wait_for(ready, f"Airflow runs writing {', '.join(f'{a}.{b}' for a, b in tables)}{note}",
             timeout=timeout, every=15)


def show(obj):
    print(json.dumps(obj, indent=1, default=str))
