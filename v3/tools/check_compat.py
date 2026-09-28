#!/usr/bin/env python3
"""Check the Spark <-> Iceberg runtime <-> Scala <-> PySpark matrix in versions.env.

ADR-012 / ARCHITECTURE §6. INV_SPARK_VERSION_ALIGNMENT: the Spark engine, the Iceberg
Spark runtime artifact (iceberg-spark-runtime-<spark minor>_<scala>) and the PySpark
client must agree. V2 broke this repeatedly (REG_ICEBERG_JAR_VERSIONS,
REG_JUPYTER_PYSPARK_VERSIONS).

Offline (default) the rules come from the table below, which records what Maven Central
and PyPI published (verified 2026-09-25). A version outside the table fails: verify it
with --online, then extend the table in the same change.

  --online   also query Maven Central (iceberg-spark-runtime / iceberg-aws-bundle
             metadata), PyPI (pyspark release + requires_python) and Docker Hub
             (apache/spark tag). Network errors are reported as failures.
  --emit     print derived values (SPARK_MINOR, ICEBERG_SPARK_RUNTIME_ARTIFACT, ...)
             as KEY=VALUE lines, for build scripts.

Exit 0 when every rule holds, 1 on a violation (warnings do not fail unless --strict).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from versionsenv import VERSIONS_FILE, load_versions  # noqa: E402

# --- offline rule table ---------------------------------------------------------------
# Iceberg release line -> Spark minors it ships iceberg-spark-runtime-<minor>_<scala> for.
ICEBERG_SPARK_MINORS: dict[str, tuple[str, ...]] = {
    "1.6": ("3.4", "3.5"),
    "1.7": ("3.4", "3.5"),
    "1.8": ("3.4", "3.5"),
    "1.9": ("3.4", "3.5"),
    "1.10": ("3.4", "3.5", "4.0"),
    "1.11": ("3.4", "3.5", "4.0", "4.1"),
}
# Spark minor -> Scala binary versions its Iceberg runtime is published for.
SPARK_SCALA: dict[str, tuple[str, ...]] = {
    "3.4": ("2.12", "2.13"),
    "3.5": ("2.12", "2.13"),
    "4.0": ("2.13",),
    "4.1": ("2.13",),
}
# PySpark minor -> minimum Python (PyPI requires_python).
PYSPARK_MIN_PYTHON: dict[str, tuple[int, int]] = {
    "3.4": (3, 7),
    "3.5": (3, 8),
    "4.0": (3, 9),
    "4.1": (3, 10),
}

REQUIRED = ("SPARK_VERSION", "SCALA_BINARY_VERSION", "ICEBERG_VERSION", "PYSPARK_VERSION")

MAVEN = "https://repo1.maven.org/maven2/org/apache/iceberg"
PYPI = "https://pypi.org/pypi"
DOCKERHUB = "https://hub.docker.com/v2/repositories"


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    oks: list[str] = field(default_factory=list)

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def ok(self, msg: str) -> None:
        self.oks.append(msg)


def minor(v: str) -> str:
    m = re.match(r"^v?(\d+)\.(\d+)", v)
    if not m:
        raise ValueError(f"not a version: {v!r}")
    return f"{m.group(1)}.{m.group(2)}"


def py_minor(tag: str) -> tuple[int, int] | None:
    m = re.match(r"^(\d+)\.(\d+)", tag)
    return (int(m.group(1)), int(m.group(2))) if m else None


def derive(v: dict[str, str]) -> dict[str, str]:
    sm = minor(v["SPARK_VERSION"])
    scala = v["SCALA_BINARY_VERSION"]
    artifact = f"iceberg-spark-runtime-{sm}_{scala}"
    return {
        "SPARK_MINOR": sm,
        "ICEBERG_SPARK_RUNTIME_ARTIFACT": artifact,
        "ICEBERG_SPARK_RUNTIME_COORD": f"org.apache.iceberg:{artifact}:{v['ICEBERG_VERSION']}",
        "ICEBERG_AWS_BUNDLE_COORD": f"org.apache.iceberg:iceberg-aws-bundle:{v['ICEBERG_VERSION']}",
    }


def check_offline(v: dict[str, str], rep: Report) -> None:
    missing = [k for k in REQUIRED if not v.get(k)]
    if missing:
        rep.error(f"versions.env is missing {', '.join(missing)}")
        return
    try:
        spark_minor = minor(v["SPARK_VERSION"])
        ice_line = minor(v["ICEBERG_VERSION"])
        pys_minor = minor(v["PYSPARK_VERSION"])
    except ValueError as e:
        rep.error(str(e))
        return
    scala = v["SCALA_BINARY_VERSION"]
    d = derive(v)

    # Spark minor <-> Iceberg runtime
    supported = ICEBERG_SPARK_MINORS.get(ice_line)
    if supported is None:
        rep.error(f"ICEBERG_VERSION={v['ICEBERG_VERSION']}: Iceberg {ice_line} is not in the offline rule table; "
                  "verify with --online and add it to ICEBERG_SPARK_MINORS in v3/tools/check_compat.py")
    elif spark_minor not in supported:
        rep.error(f"Iceberg {ice_line} publishes no Spark {spark_minor} runtime "
                  f"(it supports Spark {', '.join(supported)}); change SPARK_VERSION or ICEBERG_VERSION")
    else:
        rep.ok(f"Iceberg {v['ICEBERG_VERSION']} ships {d['ICEBERG_SPARK_RUNTIME_ARTIFACT']}")

    # Spark minor <-> Scala binary
    scalas = SPARK_SCALA.get(spark_minor)
    if scalas is None:
        rep.error(f"SPARK_VERSION={v['SPARK_VERSION']}: Spark {spark_minor} is not in the offline rule table "
                  "(SPARK_SCALA); verify with --online and extend the table")
    elif scala not in scalas:
        rep.error(f"SCALA_BINARY_VERSION={scala}: Spark {spark_minor} is built for Scala {', '.join(scalas)}")
    else:
        rep.ok(f"Spark {spark_minor} / Scala {scala}")

    # Spark image tag must carry the same Spark version and Scala binary
    tag = v.get("SPARK_IMAGE_TAG")
    if tag:
        expect = f"{v['SPARK_VERSION']}-scala{scala}"
        if not tag.startswith(expect + "-") and tag != expect:
            rep.error(f"SPARK_IMAGE_TAG={tag} does not start with '{expect}' (SPARK_VERSION + SCALA_BINARY_VERSION)")
        else:
            rep.ok(f"SPARK_IMAGE_TAG matches Spark {v['SPARK_VERSION']} / Scala {scala}")

    # PySpark client <-> Spark engine (Spark Connect needs the same minor; patch skew is
    # tolerated but watched: WATCH_SPARK_PATCH_SKEW)
    if pys_minor != spark_minor:
        rep.error(f"PYSPARK_VERSION={v['PYSPARK_VERSION']} (minor {pys_minor}) != SPARK_VERSION={v['SPARK_VERSION']} "
                  f"(minor {spark_minor}); the client must match the engine minor")
    elif v["PYSPARK_VERSION"] != v["SPARK_VERSION"]:
        rep.warn(f"PySpark {v['PYSPARK_VERSION']} vs Spark {v['SPARK_VERSION']}: patch skew (WATCH_SPARK_PATCH_SKEW)")
    else:
        rep.ok(f"PySpark {v['PYSPARK_VERSION']} == Spark {v['SPARK_VERSION']}")

    # PySpark <-> Python of the images that import it
    min_py = PYSPARK_MIN_PYTHON.get(pys_minor)
    for key in ("PYTHON_IMAGE_TAG", "AIRFLOW_PYTHON"):
        pv = py_minor(v.get(key, ""))
        if pv is None:
            continue
        if min_py is None:
            rep.warn(f"PySpark {pys_minor} is not in PYSPARK_MIN_PYTHON; cannot check {key}")
        elif pv < min_py:
            rep.error(f"{key}={v[key]}: PySpark {pys_minor} needs Python >= {min_py[0]}.{min_py[1]}")
        else:
            rep.ok(f"{key} Python {pv[0]}.{pv[1]} >= {min_py[0]}.{min_py[1]} for PySpark {pys_minor}")


# --- online ---------------------------------------------------------------------------

def _get(url: str, timeout: float = 20.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "lakehouse-lab-check-compat"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (fixed https hosts)
        return r.read()


def _maven_versions(artifact: str, fetch=_get) -> list[str]:
    xml = fetch(f"{MAVEN}/{artifact}/maven-metadata.xml").decode()
    return re.findall(r"<version>([^<]+)</version>", xml)


def _python_ok(requires: str, pv: tuple[int, int]) -> bool:
    """Tiny evaluator for requires_python clauses like '>=3.10' or '>=3.9,<3.14'."""
    for clause in filter(None, (c.strip() for c in (requires or "").split(","))):
        m = re.match(r"^(>=|>|<=|<|==|!=)\s*(\d+)\.(\d+)", clause)
        if not m:
            continue
        op, want = m.group(1), (int(m.group(2)), int(m.group(3)))
        ok = {">=": pv >= want, ">": pv > want, "<=": pv <= want, "<": pv < want,
              "==": pv == want, "!=": pv != want}[op]
        if not ok:
            return False
    return True


def check_online(v: dict[str, str], rep: Report, fetch=_get) -> None:
    d = derive(v)
    ice = v["ICEBERG_VERSION"]
    for artifact in (d["ICEBERG_SPARK_RUNTIME_ARTIFACT"], "iceberg-aws-bundle"):
        try:
            versions = _maven_versions(artifact, fetch)
        except (urllib.error.URLError, OSError) as e:
            rep.error(f"online: cannot read Maven metadata for {artifact}: {e}")
            continue
        if ice in versions:
            rep.ok(f"online: Maven Central has org.apache.iceberg:{artifact}:{ice}")
        else:
            rep.error(f"online: Maven Central has no org.apache.iceberg:{artifact}:{ice}")

    for key in ("PYSPARK_VERSION",):
        ver = v[key]
        try:
            info = json.loads(fetch(f"{PYPI}/pyspark/{ver}/json"))["info"]
        except urllib.error.HTTPError as e:
            rep.error(f"online: PyPI has no pyspark {ver} ({e.code})")
            continue
        except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
            rep.error(f"online: cannot read PyPI metadata for pyspark {ver}: {e}")
            continue
        rep.ok(f"online: PyPI has pyspark {ver} (requires_python {info.get('requires_python')})")
        for pkey in ("PYTHON_IMAGE_TAG", "AIRFLOW_PYTHON"):
            pv = py_minor(v.get(pkey, ""))
            if pv and not _python_ok(info.get("requires_python") or "", pv):
                rep.error(f"online: pyspark {ver} requires_python '{info.get('requires_python')}' excludes {pkey}={v[pkey]}")

    tag = v.get("SPARK_IMAGE_TAG")
    if tag:
        try:
            fetch(f"{DOCKERHUB}/apache/spark/tags/{tag}")
            rep.ok(f"online: Docker Hub has apache/spark tag {tag}")
        except urllib.error.HTTPError as e:
            rep.error(f"online: Docker Hub has no apache/spark tag {tag} ({e.code})")
        except (urllib.error.URLError, OSError) as e:
            rep.error(f"online: cannot query Docker Hub for apache/spark tag {tag}: {e}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--versions", type=Path, default=VERSIONS_FILE, help="versions.env (default: %(default)s)")
    ap.add_argument("--no-pins", action="store_true", help="ignore pending pins in v3/.pins/*.env")
    ap.add_argument("--online", action="store_true", help="also verify against Maven Central, PyPI and Docker Hub")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    ap.add_argument("--emit", action="store_true", help="print derived KEY=VALUE lines and exit 0 if the matrix holds")
    ap.add_argument("-q", "--quiet", action="store_true", help="print problems only")
    args = ap.parse_args(argv)

    v = load_versions(args.versions, include_pins=not args.no_pins)
    rep = Report()
    check_offline(v, rep)
    if args.online and not rep.errors:
        check_online(v, rep)

    failed = bool(rep.errors) or (args.strict and bool(rep.warnings))
    if args.emit and not failed:
        for k, val in derive(v).items():
            print(f"{k}={val}")
        return 0
    if not args.quiet:
        for m in rep.oks:
            print(f"ok    {m}")
    for m in rep.warnings:
        print(f"WARN  {m}")
    for m in rep.errors:
        print(f"ERROR {m}")
    print(f"check_compat: {'FAIL' if failed else 'OK'} ({len(rep.errors)} error(s), {len(rep.warnings)} warning(s))",
          file=sys.stderr if failed else sys.stdout)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
