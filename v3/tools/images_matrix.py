#!/usr/bin/env python3
"""Build matrix for v3/images/*: one entry per Dockerfile, with build args from versions.env.

Used by .github/workflows/v3-images.yml, and runnable locally to see exactly what CI
would build:

  v3/tools/compose-check.sh --profile full --json-out c.json
  v3/tools/images_matrix.py --compose-json c.json  # JSON matrix on stdout, build contexts
                                                 # from 'docker compose config --format json'
  v3/tools/images_matrix.py ... --github-output  # also write matrix=/count= to $GITHUB_OUTPUT

Each entry: name, dockerfile and context (repo-relative), image
(<registry>/lakehouse-<name>), and build_args (newline-separated KEY=VALUE for every ARG
the Dockerfile declares that versions.env or v3/.pins/*.env defines), and build_contexts
(newline-separated NAME=PATH, repo-relative) from the compose service's
`build.additional_contexts`, for `COPY --from=<name>` (e.g. the workspace's starter). A declared
*_VERSION / *_TAG / *_DIGEST ARG that versions.env does not define is an error, so an
image can never silently build with an empty pin. Likewise a `COPY --from=<name>` that
names neither a stage nor a build context is an error (the compose JSON must come from a
profile that includes every built service: `full`).
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
FROM_AS_RE = re.compile(r"^\s*FROM\s+.*\s+AS\s+([A-Za-z0-9_.-]+)\s*$", re.I)
COPY_FROM_RE = re.compile(r"^\s*(?:COPY|ADD)\b.*?--from=(\S+)", re.I)


def dockerfile_args(path: Path) -> list[tuple[str, bool]]:
    """(name, has_default) for every ARG, in order, deduplicated."""
    seen: dict[str, bool] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = ARG_RE.match(line)
        if m and m.group(1) not in seen:
            seen[m.group(1)] = m.group(2) is not None
    return list(seen.items())


def unresolved_copy_from(path: Path, contexts: set[str]) -> list[str]:
    """Names in 'COPY --from=<name>' that are neither a build stage, a named build context
    nor an image reference (contains ':', '/' or '@'), nor a stage index.

    buildx would try to pull such a name as an image and fail, e.g. superset's
    'COPY --from=config' when the compose JSON came from a profile without superset.
    """
    stages: set[str] = set()
    bad: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = FROM_AS_RE.match(line)
        if m:
            stages.add(m.group(1).lower())
            continue
        m = COPY_FROM_RE.match(line)
        if not m:
            continue
        name = m.group(1)
        if (name.lower() in stages or name in contexts or name.isdigit()
                or any(c in name for c in ":/@$")):
            continue
        if name not in bad:
            bad.append(name)
    return bad


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


def compose_extra_contexts(compose_json: Path) -> dict[Path, dict[str, Path]]:
    """Dockerfile path -> {name: path} of the service's build.additional_contexts."""
    data = json.loads(compose_json.read_text(encoding="utf-8"))
    out: dict[Path, dict[str, Path]] = {}
    for svc in (data.get("services") or {}).values():
        build = svc.get("build")
        if not isinstance(build, dict) or not build.get("context"):
            continue
        extra = build.get("additional_contexts") or {}
        if not extra:
            continue
        ctx = Path(build["context"])
        df = Path(build.get("dockerfile") or "Dockerfile")
        df = df if df.is_absolute() else ctx / df
        out[df.resolve()] = {k: (ctx / v).resolve() for k, v in extra.items()}
    return out


def build_matrix(v3_dir: Path, versions: dict[str, str], registry: str,
                 contexts: dict[Path, Path] | None = None,
                 extra_contexts: dict[Path, dict[str, Path]] | None = None,
                 ) -> tuple[list[dict], list[str]]:
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
        extra = (extra_contexts or {}).get(df.resolve(), {})
        unresolved = unresolved_copy_from(df, set(extra))
        if unresolved:
            errors.append(
                f"{df.relative_to(repo)}: COPY --from={', '.join(unresolved)} is neither a stage "
                "nor a build context (pass --compose-json from a profile that includes the "
                "service, e.g. compose-check.sh --profile full --json-out)")
        entries.append({
            "name": name,
            "dockerfile": df.resolve().relative_to(repo).as_posix(),
            "context": os.path.relpath(ctx, repo).replace(os.sep, "/"),
            "image": f"{registry.rstrip('/')}/lakehouse-{name}".lower(),
            "build_args": "\n".join(args),
            "build_contexts": "\n".join(
                f"{k}={os.path.relpath(v, repo).replace(os.sep, '/')}"
                for k, v in sorted(extra.items())),
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
    extra = compose_extra_contexts(args.compose_json) if args.compose_json else None
    entries, errors = build_matrix(args.v3_dir, versions, args.registry, contexts, extra)
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
