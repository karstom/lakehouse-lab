#!/usr/bin/env python3
"""Fail on version literals anywhere in v3/ outside versions.env (ADR-012).

Every version is written once, in v3/versions.env, and referenced elsewhere as ${VAR}
(compose, scripts) or as a build ARG (Dockerfiles). This scans v3/ and reports:

  image-tag       an image reference with a literal tag      (image: <name>:<literal>)
  image-untagged  an image reference with no tag            (image: postgres  -> :latest)
  latest          any ':latest'
  from            a Dockerfile FROM with a literal tag/digest, or with no tag
  from-digest     a Dockerfile FROM (other than scratch or an earlier stage) without
                  '@${*_DIGEST}': base images are pinned by tag AND digest (ADR-012)
  syntax          a '# syntax=' directive (it cannot read versions.env; BuildKit's
                  built-in frontend is used instead)
  arg-default     ARG/ENV with a version-looking literal default
  version-var     *_VERSION / *_TAG / *_DIGEST assigned a literal (VAR=1.2, VAR: 1.2)
  var-default     ${VAR:-<version>} fallback that is a version (or any fallback of a
                  *_VERSION/*_TAG/*_DIGEST variable)
  digest          a literal sha256 digest
  pip-pin         pkg==1.2 (also ~= >= <= !=) in requirements files or pip commands
  npm-pin         pkg@1.2 in npm/npx/yarn/pnpm commands; dependency ranges in package.json
  jar             jar coordinates or file names with a version (group:artifact:<ver>,
                  artifact-<ver>.jar, Maven repository paths, Scala-suffixed artifacts such as *_2.13)

Exempt:
  - v3/versions.env, and pending pins in v3/.pins/*.env
  - files whose first line starts with '# GENERATED' (generated lockfiles, ADR-012)
  - v3/tests/lint/ (this checker's own fixtures)
  - full-line comments (except the '# syntax=' check)
  - a line carrying '# check-versions: ignore <reason>' (test data that is not a pin;
    the reason is mandatory and shows up in review)
  - untracked, git-ignored files (.env, .secrets.env, state/, out/)

Not pins (deliberately not in versions.env): minimum-requirement thresholds for host
tools, e.g. LAB_MIN_DOCKER / LAB_MIN_COMPOSE in installer/checks.sh. They gate the host,
they do not select what the lab runs or builds.

Output is 'path:line:col: [rule] message' with the offending line; exit 1 if anything is
found. '--format github' also emits workflow annotations.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

V3_DIR = Path(__file__).resolve().parent.parent

# Paths relative to the v3 dir (POSIX globs).
EXEMPT_GLOBS = (
    "versions.env",
    ".pins/*.env",
    "tests/lint/*",
    "tests/lint/**/*",
)
# Never scanned even when not git-ignored (per-install files, contract §Runtime).
SKIP_GLOBS = (".env", ".secrets.env", "state/*", "state/**/*", "**/out/*", "**/out/**/*")
BINARY_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2", ".ttf", ".jar",
    ".gz", ".tgz", ".zip", ".pdf", ".crt", ".key", ".pem", ".der", ".p12", ".jks",
}
GENERATED_MARK = "# GENERATED"
# Per-line escape hatch for test data that is not a pin (e.g. a fake Docker version fed
# to a shim to test the installer's minimum-version check). A reason is mandatory.
PRAGMA = re.compile(r"check-versions:\s*ignore\b(?P<reason>.*)$")

# --- patterns -------------------------------------------------------------------------

VER = r"v?\d+(?:\.\d+)+(?:[-+._][0-9A-Za-z.+_-]*)?"  # 1.2 / v1.2.3 / 4.1.3-scala2.13
VERSIONISH = re.compile(rf"^{VER}$")
VERSION3 = re.compile(r"^(?:v\d+(?:\.\d+)*|\d+\.\d+\.\d+)")
VERSION_NAME = re.compile(r"(?:VERSION|_TAG|_DIGEST)$")

# An image reference: [registry/]name[:tag][@digest]. Token must not follow a URL char,
# so https://host:18443/... never matches.
IMG_NAME = r"[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?(?:/[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?)*"
IMAGE_KEY = re.compile(r"""^\s*-?\s*image\s*:\s*(?:&\S+\s+)?["']?(?P<ref>[^\s"'#*][^\s"'#]*)""")
FROM_LINE = re.compile(r"^\s*FROM\s+(?P<rest>.+)$", re.I)
SYNTAX_LINE = re.compile(r"^\s*#\s*syntax\s*=", re.I)
ARG_ENV_LINE = re.compile(r"^\s*(?P<kw>ARG|ENV)\s+(?P<body>.+)$", re.I)
KV = re.compile(r"""(?P<k>[A-Za-z_][A-Za-z0-9_]*)=(?P<v>"[^"]*"|'[^']*'|[^\s]+)""")
VERSION_VAR = re.compile(
    r"""\b(?P<k>[A-Za-z0-9_]*(?:VERSION|_TAG|_DIGEST))\b["']?\s*(?:=|:)\s*"""
    r"""(?P<v>"[^"]*"|'[^']*'|[^\s,;#]+)"""
)
VAR_DEFAULT = re.compile(r"\$\{(?P<k>[A-Za-z_][A-Za-z0-9_]*):?[-=](?P<v>[^}]*)\}")
LATEST = re.compile(r"[\w./-]:latest\b")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
GENERIC_IMAGE = re.compile(
    rf"(?<![\w./:@$-])(?P<name>{IMG_NAME}):(?P<tag>{VER}|\d+)(?![\w:/])"
)
PIP_CMD = re.compile(r"\b(?:pip3?|uv\s+pip|pipx|python3?\s+-m\s+pip)\s+install\b")
PIP_PIN = re.compile(
    r"""(?<![\w$-])(?P<pkg>[A-Za-z][A-Za-z0-9._-]*(?:\[[^\]]*\])?)\s*(?:===|==|~=|>=|<=|!=|>|<)\s*(?P<v>v?\d[\w.*+-]*)"""
)
NPM_CMD = re.compile(r"\b(?:npm\s+(?:i|install|add|ci|exec)|npx|yarn\s+(?:add|dlx)|pnpm\s+(?:add|dlx)|bunx?)\b")
NPM_PIN = re.compile(r"""(?<![\w/])(?P<pkg>@?[a-z0-9][\w.-]*(?:/[\w.-]+)?)@(?P<v>[\^~>=<]*v?\d[\w.-]*)""")
PKG_JSON_DEP = re.compile(r"""^\s*"(?P<pkg>[^"]+)"\s*:\s*"(?P<v>[\^~>=<]*\s*v?\d[^"]*)"\s*,?\s*$""")
MAVEN_COORD = re.compile(r"(?<![\w.-])[a-z][\w.-]*:[A-Za-z][\w.-]*:(?:jar:)?" + VER)
JAR_FILE = re.compile(r"[A-Za-z][\w.-]*?-" + VER + r"\.jar\b")
MAVEN_PATH = re.compile(r"/maven2?/(?:[\w.-]+/)+" + VER + "/")
SCALA_SUFFIX = re.compile(r"(?:[A-Za-z][\w-]*|\})_2\.1[0-9]\b")
SPARK_RUNTIME = re.compile(r"iceberg-spark(?:-runtime)?-\d")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    col: int
    rule: str
    message: str
    text: str

    def render(self) -> str:
        return f"{self.path}:{self.line}:{self.col}: [{self.rule}] {self.message}\n    {self.text.strip()}"

    def annotation(self) -> str:
        msg = f"[{self.rule}] {self.message}".replace("%", "%25").replace("\n", "%0A")
        return f"::error file={self.path},line={self.line},col={self.col},title=check_versions::{msg}"


def _has_interp(s: str) -> bool:
    return "$" in s


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    return s


def _split_image(ref: str) -> tuple[str, str | None, str | None]:
    """name, tag, digest (tag/digest None when absent)."""
    # Mask ${...} so ':' / '@' / '/' inside a variable expansion are not separators.
    masked = re.sub(r"\$\{[^}]*\}", lambda m: "$" * len(m.group(0)), ref)
    digest = None
    at = masked.find("@")
    if at >= 0:
        ref, digest, masked = ref[:at], ref[at + 1:], masked[:at]
    tag = None
    slash = masked.rfind("/")
    colon = masked.find(":", slash + 1)
    if colon >= 0:
        ref, tag = ref[:colon], ref[colon + 1:]
    return ref, tag, digest


def check_image_ref(ref: str) -> tuple[str, str] | None:
    """(rule, message) if an image reference is not fully driven by variables."""
    ref = _strip_quotes(ref)
    if ref.startswith("${") and ref.endswith("}") and ref.count("${") == 1:
        return None  # whole reference comes from a variable
    name, tag, digest = _split_image(ref)
    if tag is not None and tag.lower() == "latest":
        return "latest", f"':latest' is banned; pin the tag in versions.env ({ref})"
    if digest is not None and not _has_interp(digest):
        return "digest", f"literal image digest; put it in versions.env as *_IMAGE_DIGEST ({ref})"
    if tag is None and digest is None:
        if _has_interp(name) and name.rstrip().endswith("}"):
            return None  # e.g. ${REGISTRY}/foo${SUFFIX}: cannot judge
        return "image-untagged", f"image has no tag (implicit :latest); use :${{..._VERSION}} ({ref})"
    if tag is not None and not _has_interp(tag):
        return "image-tag", f"literal image tag '{tag}'; reference a versions.env variable ({ref})"
    return None


FROM_DIGEST_VAR = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*_DIGEST\}$")


def check_from_digest(ref: str) -> tuple[str, str] | None:
    """ADR-012 amendment: a Dockerfile base image is pinned by tag AND digest, both from
    versions.env (FROM name:${X_IMAGE_TAG}@${X_IMAGE_DIGEST}). Called after
    check_image_ref, so literal tags/digests are already reported."""
    ref = _strip_quotes(ref)
    _name, tag, digest = _split_image(ref)
    if tag is None and digest is None:
        return "from-digest", (f"base image '{ref}' comes whole from a variable; write it as "
                               "name:${..._TAG}@${..._DIGEST} so the digest pin is visible")
    if digest is None or not FROM_DIGEST_VAR.match(digest):
        return "from-digest", (f"base image '{ref}' has no @${{..._DIGEST}}; pin it by tag and "
                               "digest from versions.env (ADR-012)")
    return None


def classify_path(rel: str) -> str:
    base = rel.rsplit("/", 1)[-1]
    low = base.lower()
    if low == "dockerfile" or low.startswith("dockerfile.") or low.endswith(".dockerfile") or low == "containerfile":
        return "dockerfile"
    if low == "package.json":
        return "package-json"
    if re.match(r"^(requirements|constraints)[\w.-]*\.(txt|in)$", low) or low.endswith(".requirements.txt"):
        return "requirements"
    if low.endswith((".yml", ".yaml")):
        return "yaml"
    return "text"


def is_comment(line: str, kind: str) -> bool:
    if kind == "package-json":
        return False
    return line.lstrip().startswith(("#", "//"))


def scan_text(rel: str, text: str) -> list[Finding]:
    lines = text.splitlines()
    if lines and lines[0].startswith(GENERATED_MARK):
        return []
    kind = classify_path(rel)
    findings: list[Finding] = []
    stages: set[str] = set()  # Dockerfile stage names seen so far

    def add(lineno: int, col: int, rule: str, msg: str, line: str) -> None:
        findings.append(Finding(rel, lineno, col + 1, rule, msg, line))

    for lineno, line in enumerate(lines, 1):
        hit_rules: set[str] = set()
        pm = PRAGMA.search(line)
        if pm:
            if len(pm.group("reason").strip()) < 3:
                add(lineno, pm.start(), "pragma", "'check-versions: ignore' needs a reason after it", line)
            continue

        def hit(col: int, rule: str, msg: str) -> None:
            hit_rules.add(rule)
            add(lineno, col, rule, msg, line)

        if kind == "dockerfile" and SYNTAX_LINE.match(line):
            hit(0, "syntax", "'# syntax=' pins a frontend image outside versions.env; drop it (BuildKit's built-in frontend supports RUN --mount and heredocs)")
            continue
        if is_comment(line, kind):
            continue

        # Dockerfile FROM / ARG / ENV
        if kind == "dockerfile":
            m = FROM_LINE.match(line)
            if m:
                toks = [t for t in m.group("rest").split() if not t.startswith("--")]
                if toks:
                    ref = toks[0]
                    if len(toks) >= 3 and toks[1].lower() == "as":
                        stage_as = toks[2].lower()
                    else:
                        stage_as = None
                    if ref.lower() != "scratch" and ref.lower() not in stages:
                        res = check_image_ref(ref) or check_from_digest(ref)
                        if res:
                            rule, msg = res
                            hit(m.start("rest"), "from" if rule in ("image-tag", "image-untagged", "digest") else rule, msg)
                    if stage_as:
                        stages.add(stage_as)
                continue
            m = ARG_ENV_LINE.match(line)
            if m:
                for kv in KV.finditer(m.group("body")):
                    k, v = kv.group("k"), _strip_quotes(kv.group("v"))
                    if not v or _has_interp(v):
                        continue
                    if VERSIONISH.match(v) or DIGEST.search(v) or (VERSION_NAME.search(k) and re.search(r"\d", v)):
                        hit(m.start("body") + kv.start(), "arg-default", f"{m.group('kw').upper()} {k} has a literal version default '{v}'; pass it as a build arg from versions.env")
                    elif GENERIC_IMAGE.search(v) or LATEST.search(v):
                        res = check_image_ref(v)
                        if res:
                            hit(m.start("body") + kv.start(), "arg-default", f"{m.group('kw').upper()} {k} defaults to an image with a literal tag; {res[1]}")

        # compose/k8s style `image:` keys (any YAML, and text files that embed YAML)
        m = IMAGE_KEY.match(line)
        if m and kind in ("yaml", "text"):
            res = check_image_ref(m.group("ref"))
            if res:
                hit(m.start("ref"), res[0], res[1])

        if kind == "requirements":
            s = line.split("#", 1)[0]
            for pm in PIP_PIN.finditer(s):
                if not _has_interp(pm.group("v")):
                    hit(pm.start(), "pip-pin", f"pip pin '{pm.group(0).strip()}'; use ${{VAR}} from versions.env or a '# GENERATED' lock")
        elif PIP_CMD.search(line):
            after = line[PIP_CMD.search(line).end():]
            off = len(line) - len(after)
            for pm in PIP_PIN.finditer(after):
                if not _has_interp(pm.group("v")):
                    hit(off + pm.start(), "pip-pin", f"pip pin '{pm.group(0).strip()}' in a command; use ${{VAR}} from versions.env")

        if kind == "package-json":
            pm = PKG_JSON_DEP.match(line)
            if pm and pm.group("pkg") not in ("version", "node", "npm"):
                hit(pm.start("v"), "npm-pin", f"package.json pins {pm.group('pkg')}@{pm.group('v')}; generate package.json from versions.env instead")
        elif NPM_CMD.search(line):
            after = line[NPM_CMD.search(line).end():]
            off = len(line) - len(after)
            for pm in NPM_PIN.finditer(after):
                hit(off + pm.start(), "npm-pin", f"npm pin '{pm.group(0)}'; use ${{VAR}} from versions.env")

        for rx, what in ((MAVEN_COORD, "Maven coordinate"), (JAR_FILE, "jar file name"), (MAVEN_PATH, "Maven repository path")):
            jm = rx.search(line)
            if jm and "jar" not in hit_rules:
                hit(jm.start(), "jar", f"{what} with a literal version '{jm.group(0)}'; build it from versions.env variables")
        if "jar" not in hit_rules:
            jm = SPARK_RUNTIME.search(line) or SCALA_SUFFIX.search(line)
            if jm:
                hit(jm.start(), "jar", f"artifact name embeds a Spark/Scala version literal '{jm.group(0)}'; derive it from SPARK_VERSION / SCALA_BINARY_VERSION")

        for vm in VERSION_VAR.finditer(line):
            v = _strip_quotes(vm.group("v").rstrip("`.,;)"))
            if v and not _has_interp(v) and re.search(r"\d", v) and not v.startswith("-"):
                if kind == "dockerfile" and "arg-default" in hit_rules:
                    continue
                hit(vm.start(), "version-var", f"{vm.group('k')} is assigned a literal '{v}'; define it only in versions.env")

        for dm in VAR_DEFAULT.finditer(line):
            k, v = dm.group("k"), dm.group("v").strip()
            # Two-part numbers (cpus: ${X_CPUS:-2.0}) are not versions; three parts or a
            # leading 'v' are, and so is any fallback of a *_VERSION/_TAG/_DIGEST variable.
            if v and not _has_interp(v) and (VERSION_NAME.search(k) or VERSION3.match(v) or GENERIC_IMAGE.search(v)):
                hit(dm.start(), "var-default", f"${{{k}}} falls back to a literal '{v}'; versions.env is always loaded, drop the fallback")

        if "latest" not in hit_rules:
            lm = LATEST.search(line)
            if lm:
                hit(lm.start() + 1, "latest", "':latest' is banned; pin the tag in versions.env")

        if not hit_rules & {"digest", "from", "arg-default", "version-var"}:
            dm = DIGEST.search(line)
            if dm:
                hit(dm.start(), "digest", "literal sha256 digest; put it in versions.env (*_DIGEST)")

        # Generic image refs in scripts/docs (docker run foo/bar:1.2). Only when no
        # specific rule fired on this line, to keep the report to one finding.
        if not hit_rules:
            for gm in GENERIC_IMAGE.finditer(line):
                name, tag = gm.group("name"), gm.group("tag")
                if tag.isdigit() and "/" not in name:
                    continue  # host:port
                if not re.search(r"[a-z]", name.rsplit("/", 1)[-1]):
                    continue
                hit(gm.start(), "image-tag", f"image reference with a literal tag '{gm.group(0)}'; reference a versions.env variable")
                break
    return findings


# --- file discovery -------------------------------------------------------------------

def _match_any(rel: str, globs: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(rel, g) for g in globs)


def list_files(v3_dir: Path) -> list[Path]:
    """Tracked + untracked-not-ignored files under v3_dir (git), else a plain walk."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "."],
            cwd=v3_dir, check=True, capture_output=True,
        ).stdout.decode()
        files = [v3_dir / p for p in out.split("\0") if p]
        return sorted({f for f in files if f.is_file()})
    except (OSError, subprocess.CalledProcessError):
        files = []
        for root, dirs, names in os.walk(v3_dir):
            dirs[:] = [d for d in dirs if d not in (".git", "state", "out", "__pycache__", "node_modules")]
            files += [Path(root) / n for n in names]
        return sorted(files)


def scan(v3_dir: Path, only: list[Path] | None = None) -> list[Finding]:
    v3_dir = v3_dir.resolve()
    files = [p.resolve() for p in only] if only else list_files(v3_dir)
    findings: list[Finding] = []
    for f in files:
        try:
            rel_v3 = f.relative_to(v3_dir).as_posix()
        except ValueError:
            rel_v3 = f.name
        if _match_any(rel_v3, EXEMPT_GLOBS) or _match_any(rel_v3, SKIP_GLOBS):
            continue
        if "__pycache__" in f.parts or f.suffix.lower() in BINARY_EXT:
            continue
        try:
            data = f.read_bytes()
        except OSError:
            continue
        if b"\0" in data[:4096]:
            continue
        text = data.decode("utf-8", errors="replace")
        shown = Path(os.path.relpath(f, Path.cwd())).as_posix()
        for fd in scan_text(rel_v3, text):
            findings.append(Finding(shown, fd.line, fd.col, fd.rule, fd.message, fd.text))
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="*", type=Path, help="limit the scan to these files (default: all of v3/)")
    ap.add_argument("--v3-dir", type=Path, default=V3_DIR, help="v3 directory (default: %(default)s)")
    ap.add_argument("--format", choices=("text", "github"), default="text")
    args = ap.parse_args(argv)

    findings = scan(args.v3_dir, args.files or None)
    for fd in findings:
        print(fd.render())
        if args.format == "github":
            print(fd.annotation())
    if findings:
        print(f"\ncheck_versions: {len(findings)} version literal(s) outside versions.env "
              f"(ADR-012). Move each into v3/versions.env and reference it as ${{VAR}}.", file=sys.stderr)
        return 1
    print("check_versions: OK (no version literals outside versions.env)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
