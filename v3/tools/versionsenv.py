"""Read v3/versions.env (and pending pins in v3/.pins/*.env).

Shared by the v3 tools. Stdlib only, so it runs on a bare CI runner.

versions.env is the only place versions are written (ADR-012). Workstreams stage new
pins in v3/.pins/<workstream>.env until the lead promotes them; tools read both, and
versions.env wins on a conflict.
"""

from __future__ import annotations

import re
from pathlib import Path

V3_DIR = Path(__file__).resolve().parent.parent
VERSIONS_FILE = V3_DIR / "versions.env"
PINS_DIR = V3_DIR / ".pins"

_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE lines. Blank lines and # comments are skipped; one level of
    matching quotes around the value is removed. No interpolation."""
    out: dict[str, str] = {}
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _LINE.match(line)
        if not m:
            raise ValueError(f"{path}:{lineno}: not a KEY=VALUE line: {raw!r}")
        key, value = m.group(1), m.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        out[key] = value
    return out


def pin_files(v3_dir: Path = V3_DIR) -> list[Path]:
    pins = v3_dir / ".pins"
    return sorted(pins.glob("*.env")) if pins.is_dir() else []


def load_versions(
    versions_file: Path | None = None,
    extra: list[Path] | None = None,
    include_pins: bool = True,
) -> dict[str, str]:
    """versions.env merged over the pending pins (versions.env wins)."""
    versions_file = versions_file or VERSIONS_FILE
    merged: dict[str, str] = {}
    files = list(extra or [])
    if include_pins:
        files = pin_files(versions_file.parent) + files
    for f in files:
        merged.update(parse_env_file(f))
    merged.update(parse_env_file(versions_file))
    return merged
