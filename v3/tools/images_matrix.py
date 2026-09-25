#!/usr/bin/env python3
"""Build matrix for v3/images/*: one entry per Dockerfile, with build args from versions.env.

Used by .github/workflows/v3-images.yml, and runnable locally to see exactly what CI
would build:

  v3/tools/images_matrix.py                      # JSON matrix on stdout
  v3/tools/images_matrix.py --github-output      # also write matrix=/count= to $GITHUB_OUTPUT
  v3/tools/images_matrix.py --compose-json c.json  # take build contexts from
                                                 # 'docker compose config --format json'

Each entry: name, dockerfile and context (repo-relative), image
(<registry>/lakehouse-<name>), and build_args (newline-separated KEY=VALUE for every ARG
the Dockerfile declares that versions.env or v3/.pins/*.env defines). A declared
*_VERSION / *_TAG / *_DIGEST ARG that versions.env does not define is an error, so an
image can never silently build with an empty pin.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from versionsenv import V3_DIR, VERSIONS_FILE, load_versions  # noqa: E402

REPO_DIR = V3_DIR.parent
ARG_RE = re.compile(r"^\s*ARG\s+([A-Za-z_][A-Za-z0-9_]*)(=.*)?\s*$", re.I)
PIN_NAME = re.compile(r"(?:VERSION|_TAG|_DIGEST)$")


def dockerfile_args(path: Path) -> list[tuple[str, bool]]:
    """(name, has_default) for every ARG, in order, deduplicated."""
    seen: dict[str, bool] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = ARG_RE.match(line)
        if m and m.group(1) not in seen:
            seen[m.group(1)] = m.group(2) is not None
    return list(seen.items())


def compose_contexts(compose_json: Path) -> dict[Path, Path]:
    """Dockerfile path -> build context, from 'docker compose config --format json'."""
    data = json.loads(compose_json.read_text(encoding="utf-8"))
    out: dict[Path, Path] = {}
    for svc in (data.get("services") or {}).values():
        build = svc.get("build")
        if not isinstance(build, dict) or not build.get("context"):
            continue
        ctx = Path(build["context"])
        df = Path(build.get("dockerfile") or "Dockerfile")
        df = df if df.is_absolute() else ctx / df
        out[df.resolve()] = ctx.resolve()
    return out


def build_matrix(v3_dir: Path, versions: dict[str, str], registry: str,
                 contexts: dict[Path, Path] | None = None) -> tuple[list[dict], list[str]]:
    entries: list[dict] = []
    errors: list[str] = []
    repo = v3_dir.parent.resolve()
    for df in sorted((v3_dir / "images").glob("*/Dockerfile")):
        name = df.parent.name
        ctx = (contexts or {}).get(df.resolve(), df.parent.resolve())
        args, missing = [], []
        for arg, has_default in dockerfile_args(df):
            if arg in versions:
                args.append(f"{arg}={versions[arg]}")
            elif PIN_NAME.search(arg) and not has_default:
                missing.append(arg)
        if missing:
            errors.append(f"{df.relative_to(repo)}: ARG {', '.join(missing)} not defined in versions.env")
        entries.append({
            "name": name,
            "dockerfile": df.resolve().relative_to(repo).as_posix(),
            "context": os.path.relpath(ctx, repo).replace(os.sep, "/"),
            "image": f"{registry.rstrip('/')}/lakehouse-{name}".lower(),
            "build_args": "\n".join(args),
        })
    return entries, errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--v3-dir", type=Path, default=V3_DIR)
    ap.add_argument("--versions", type=Path, default=None, help="default: <v3-dir>/versions.env")
    ap.add_argument("--registry", default="ghcr.io/lakehouse-lab", help="image prefix (default: %(default)s)")
    ap.add_argument("--compose-json", type=Path, help="output of 'docker compose config --format json'")
    ap.add_argument("--github-output", action="store_true", help="append matrix= and count= to $GITHUB_OUTPUT")
    args = ap.parse_args(argv)

    versions = load_versions(args.versions or (args.v3_dir / VERSIONS_FILE.name))
    contexts = compose_contexts(args.compose_json) if args.compose_json else None
    entries, errors = build_matrix(args.v3_dir, versions, args.registry, contexts)
    for e in errors:
        print(f"ERROR {e}", file=sys.stderr)
    if errors:
        return 1
    matrix = json.dumps({"include": entries}, separators=(",", ":"))
    print(json.dumps({"include": entries}, indent=2))
    if args.github_output:
        out = os.environ.get("GITHUB_OUTPUT")
        if not out:
            print("GITHUB_OUTPUT is not set", file=sys.stderr)
            return 2
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"matrix={matrix}\ncount={len(entries)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
