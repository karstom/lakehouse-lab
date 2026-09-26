#!/usr/bin/env python3
"""Lint the learning tracks (v3/tracks) against the module interface in v3/tracks/README.md.

Errors (exit 1):
  * a module.json that lab-tracks would reject (same rules: lakehouse/tracks.py validate_meta),
    or a module id used twice
  * a module without README.md, tutor.md or its checkpoint, or a checkpoint that does not
    handle both `--json` and `--reset`
  * no reference solution v3/tests/tracks/solutions/<track>/<module>/solve.py
  * Spark `DROP TABLE ... PURGE` in code (Lakekeeper's signer rejects the client-side deletes;
    anti-pattern, DEC_V3_CATALOG_VENDED_STORAGE_ACCESS)
  * an internet download in code (pip install, wget, curl, urlretrieve, urlopen/requests/pandas
    reading an http(s) URL): lessons use lab data only
Warnings: `minutes` outside 30-60; a `reset.tables` entry outside the learner's own objects:
its schema part has no {user}/{ns} placeholder, and it is not one of the learner's own
production tables `lakehouse.analytics.{prod}<name>` (u_<you>_*, the lead's Phase 4 decision
DEC_V3_TRACK_USER_PRODUCTION_TABLES). The contract lets `reset` drop only the learner's own
objects (v3/tracks/README.md, "The learner's own objects").

"Code" is .py/.sql/.sh files and the code cells of notebooks, in v3/tracks and in the
solutions. Prose (Markdown, notebook markdown cells) may mention these things.

Usage: python3 v3/tools/check_tracks.py [--root v3] [--format github]
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.dirname(HERE)

PURGE = re.compile(r"\bDROP\s+TABLE\b[^;\n]*\bPURGE\b", re.IGNORECASE)
DOWNLOADS = [
    (re.compile(r"(^|[\s!%;&|])pip3?\s+install\b"), "pip install (images are pre-built; no runtime installs)"),
    (re.compile(r"(^|[\s!;&|])(wget|curl)\s[^\n]*https?://"), "wget/curl of an http(s) URL"),
    (re.compile(r"\burlretrieve\s*\("), "urlretrieve"),
    (re.compile(r"\burlopen\s*\(\s*[\"']https?://"), "urlopen of an http(s) URL"),
    (re.compile(r"\brequests\.(get|post)\s*\(\s*[\"']https?://"), "requests of a literal http(s) URL"),
    (re.compile(r"\bread_(csv|parquet|json|excel)\s*\(\s*[\"']https?://"), "reading data from an http(s) URL"),
]
CODE_EXT = (".py", ".sql", ".sh")
OWN_SCHEMA = re.compile(r"\{(user|ns)\}")


def load_validate():
    sys.path.insert(0, os.path.join(V3, "images", "workspace"))
    from lakehouse.tracks import validate_meta  # noqa: E402 - stdlib-only module
    return validate_meta


def code_chunks(path):
    """[(line number, text)] of the code in a file (notebooks: code cells only)."""
    if path.endswith(".ipynb"):
        try:
            with open(path, encoding="utf-8") as f:
                nb = json.load(f)
        except (OSError, ValueError) as e:
            return [(0, f"<unreadable notebook: {e}>")]
        out = []
        for i, cell in enumerate(nb.get("cells", [])):
            if cell.get("cell_type") == "code":
                src = cell.get("source", "")
                out.append((i + 1, "".join(src) if isinstance(src, list) else src))
        return out
    if path.endswith(CODE_EXT):
        with open(path, encoding="utf-8", errors="replace") as f:
            return [(1, f.read())]
    return []


def scan_code(root):
    """-> [(path, where, message)] for PURGE and downloads under root."""
    hits = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in ("__pycache__", ".ipynb_checkpoints")]
        for name in sorted(files):
            p = os.path.join(d, name)
            for where, text in code_chunks(p):
                lines = text.splitlines()
                for n, line in enumerate(lines, 1):
                    if line.lstrip().startswith("#") or line.lstrip().startswith("--"):
                        continue
                    loc = f"cell {where} line {n}" if p.endswith(".ipynb") else f"line {n}"
                    if PURGE.search(line):
                        hits.append((p, loc, "Spark DROP TABLE ... PURGE: use a plain DROP TABLE"))
                    for rx, what in DOWNLOADS:
                        if rx.search(line):
                            hits.append((p, loc, f"internet download ({what}): use lab data only"))
    return hits


def check(v3=V3):
    """-> (errors, warnings), each a list of (path, message)."""
    validate_meta = load_validate()
    tracks = os.path.join(v3, "tracks")
    sols = os.path.join(v3, "tests", "tracks", "solutions")
    errors, warnings = [], []
    ids = {}
    if not os.path.isdir(tracks):
        return [(tracks, "no tracks directory")], []
    for track in sorted(os.listdir(tracks)):
        tdir = os.path.join(tracks, track)
        if not os.path.isdir(tdir) or track.startswith((".", "_")):
            continue
        for d in sorted(os.listdir(tdir)):
            mdir = os.path.join(tdir, d)
            mj = os.path.join(mdir, "module.json")
            if not os.path.isdir(mdir) or d.startswith(("_", ".")):
                continue
            if not os.path.isfile(mj):
                errors.append((mdir, "module folder without module.json (helpers go in _shared/)"))
                continue
            try:
                with open(mj, encoding="utf-8") as f:
                    meta = json.load(f)
            except (OSError, ValueError) as e:
                errors.append((mj, f"not valid JSON: {e}"))
                continue
            for p in validate_meta(meta, track):
                errors.append((mj, p))
            mid = str(meta.get("id", "")).lower()
            if mid in ids:
                errors.append((mj, f"id {meta.get('id')} also used by {ids[mid]}"))
            ids[mid] = f"{track}/{d}"
            if not re.match(r"^[A-Za-z]+\d+-[a-z0-9-]+$", d):
                warnings.append((mdir, "folder name should be <ID>-<slug>, e.g. E1-files-to-iceberg"))
            elif mid and not d.lower().startswith(mid + "-"):
                errors.append((mdir, f"folder name does not start with the module id {meta.get('id')}-"))
            for need in ("README.md", "tutor.md"):
                if not os.path.isfile(os.path.join(mdir, need)):
                    errors.append((mdir, f"missing {need}"))
            cp = os.path.join(mdir, meta.get("checkpoint", "checkpoint.py"))
            if not os.path.isfile(cp):
                errors.append((mdir, f"missing checkpoint {os.path.basename(cp)}"))
            else:
                # The flags may be handled by the track's shared helpers (<track>/_shared/).
                src = ""
                shared = os.path.join(tdir, "_shared")
                for p in [cp] + ([os.path.join(shared, x) for x in sorted(os.listdir(shared))
                                  if x.endswith(".py")] if os.path.isdir(shared) else []):
                    with open(p, encoding="utf-8", errors="replace") as f:
                        src += f.read()
                for flag in ("--json", "--reset"):
                    if flag not in src:
                        errors.append((cp, f"does not handle {flag} (see v3/tracks/README.md)"))
            if not os.path.isfile(os.path.join(sols, track, d, "solve.py")):
                errors.append((mdir, f"no reference solution tests/tracks/solutions/{track}/{d}/solve.py"))
            reset = meta.get("reset") if isinstance(meta.get("reset"), dict) else {}
            for t in reset.get("tables") or []:
                parts = str(t).split(".")
                schema = parts[-2] if len(parts) >= 2 else ""
                own_prod = schema == "analytics" and parts[-1].startswith("{prod}")
                if not (OWN_SCHEMA.search(schema) or own_prod):
                    warnings.append((mj, f"reset table {t}: schema {schema or '?'} is not the "
                                         f"learner's own ({{user}}/{{ns}}, or analytics.{{prod}}*); "
                                         f"a shared schema needs a lead decision"))
            m = meta.get("minutes")
            if isinstance(m, int) and not 30 <= m <= 60:
                warnings.append((mj, f"minutes {m}: a module should take 30-60 minutes"))
    for root in (tracks, sols):
        if os.path.isdir(root):
            for p, loc, msg in scan_code(root):
                errors.append((p, f"{loc}: {msg}"))
    return errors, warnings


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=V3, help="the v3 directory")
    ap.add_argument("--format", choices=("text", "github"), default="text")
    a = ap.parse_args(argv)
    errors, warnings = check(os.path.abspath(a.root))
    for kind, items in (("error", errors), ("warning", warnings)):
        for p, msg in items:
            rel = os.path.relpath(p, os.path.dirname(os.path.abspath(a.root)))
            if a.format == "github":
                print(f"::{kind} file={rel}::{msg}")
            else:
                print(f"{kind}: {rel}: {msg}")
    print(f"check_tracks: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
