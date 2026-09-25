"""Unit tests for v3/tools/check_compat.py (offline rules + online logic with a fake fetcher)."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import check_compat as cc  # noqa: E402

GOOD = {
    "SPARK_VERSION": "4.1.3",
    "SPARK_IMAGE_TAG": "4.1.3-scala2.13-java17-python3-ubuntu",
    "SCALA_BINARY_VERSION": "2.13",
    "ICEBERG_VERSION": "1.11.0",
    "PYSPARK_VERSION": "4.1.3",
    "PYTHON_IMAGE_TAG": "3.12.14-slim-bookworm",
    "AIRFLOW_PYTHON": "3.12",
}


def offline(**over) -> cc.Report:
    v = {**GOOD, **over}
    v = {k: val for k, val in v.items() if val is not None}
    rep = cc.Report()
    cc.check_offline(v, rep)
    return rep


class Offline(unittest.TestCase):
    def test_current_matrix_ok(self):
        rep = offline()
        self.assertEqual(rep.errors, [])
        self.assertEqual(rep.warnings, [])

    def test_repo_versions_env_ok(self):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            rc = cc.main(["-q"])
        self.assertEqual(rc, 0, out.getvalue())

    def test_spark_without_iceberg_runtime(self):
        rep = offline(SPARK_VERSION="4.1.3", ICEBERG_VERSION="1.10.1")
        self.assertTrue(any("no Spark 4.1 runtime" in e for e in rep.errors), rep.errors)

    def test_unknown_iceberg_line(self):
        rep = offline(ICEBERG_VERSION="1.12.0")
        self.assertTrue(any("not in the offline rule table" in e for e in rep.errors), rep.errors)

    def test_unknown_spark_minor(self):
        rep = offline(SPARK_VERSION="4.2.0", PYSPARK_VERSION="4.2.0", SPARK_IMAGE_TAG="4.2.0-scala2.13-java17-python3-ubuntu")
        self.assertTrue(any("Spark 4.2" in e for e in rep.errors), rep.errors)

    def test_scala_mismatch(self):
        rep = offline(SCALA_BINARY_VERSION="2.12", SPARK_IMAGE_TAG="4.1.3-scala2.12-java17-python3-ubuntu")
        self.assertTrue(any("built for Scala 2.13" in e for e in rep.errors), rep.errors)

    def test_spark_3_5_scala_2_12_ok(self):
        rep = offline(SPARK_VERSION="3.5.6", PYSPARK_VERSION="3.5.6", SCALA_BINARY_VERSION="2.12",
                      SPARK_IMAGE_TAG="3.5.6-scala2.12-java17-python3-ubuntu")
        self.assertEqual(rep.errors, [])

    def test_image_tag_mismatch(self):
        rep = offline(SPARK_IMAGE_TAG="4.1.2-scala2.13-java17-python3-ubuntu")
        self.assertTrue(any("SPARK_IMAGE_TAG" in e for e in rep.errors), rep.errors)

    def test_pyspark_minor_mismatch(self):
        rep = offline(PYSPARK_VERSION="4.0.1")
        self.assertTrue(any("client must match" in e for e in rep.errors), rep.errors)

    def test_pyspark_patch_skew_warns(self):
        rep = offline(PYSPARK_VERSION="4.1.2")
        self.assertEqual(rep.errors, [])
        self.assertEqual(len(rep.warnings), 1)

    def test_python_too_old(self):
        rep = offline(AIRFLOW_PYTHON="3.9")
        self.assertTrue(any("needs Python >= 3.10" in e for e in rep.errors), rep.errors)

    def test_missing_keys(self):
        rep = offline(PYSPARK_VERSION=None)
        self.assertTrue(any("missing PYSPARK_VERSION" in e for e in rep.errors), rep.errors)

    def test_derive(self):
        d = cc.derive(GOOD)
        self.assertEqual(d["SPARK_MINOR"], "4.1")
        self.assertEqual(d["ICEBERG_SPARK_RUNTIME_ARTIFACT"], "iceberg-spark-runtime-4.1_2.13")
        self.assertTrue(d["ICEBERG_SPARK_RUNTIME_COORD"].endswith(":" + GOOD["ICEBERG_VERSION"]))


class Cli(unittest.TestCase):
    def _env(self, body: str) -> Path:
        d = Path(tempfile.mkdtemp())
        (d / "versions.env").write_text(body)
        return d / "versions.env"

    def test_strict_and_emit(self):
        base = "\n".join(f"{k}={v}" for k, v in GOOD.items())
        p = self._env(base.replace("PYSPARK_VERSION=4.1.3", "PYSPARK_VERSION=4.1.2") + "\n")
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(cc.main(["--versions", str(p), "--no-pins"]), 0)
            self.assertEqual(cc.main(["--versions", str(p), "--no-pins", "--strict"]), 1)
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(cc.main(["--versions", str(self._env(base + "\n")), "--no-pins", "--emit"]), 0)
        self.assertIn("ICEBERG_SPARK_RUNTIME_ARTIFACT=iceberg-spark-runtime-4.1_2.13", out.getvalue())

    def test_fail_exit(self):
        base = "\n".join(f"{k}={v}" for k, v in GOOD.items()).replace("SCALA_BINARY_VERSION=2.13", "SCALA_BINARY_VERSION=2.12")
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(cc.main(["--versions", str(self._env(base + "\n")), "--no-pins"]), 1)


class Online(unittest.TestCase):
    def fetcher(self, maven: dict[str, list[str]], pypi: dict[str, str] | None, tags: set[str]):
        def fetch(url: str) -> bytes:
            if url.startswith(cc.MAVEN):
                art = url[len(cc.MAVEN) + 1:].split("/")[0]
                if art not in maven:
                    raise urllib.error.HTTPError(url, 404, "nf", None, None)
                return ("<metadata>" + "".join(f"<version>{v}</version>" for v in maven[art]) + "</metadata>").encode()
            if url.startswith(cc.PYPI):
                ver = url.split("/")[-2]
                if pypi is None or ver not in pypi:
                    raise urllib.error.HTTPError(url, 404, "nf", None, None)
                return json.dumps({"info": {"version": ver, "requires_python": pypi[ver]}}).encode()
            if url.startswith(cc.DOCKERHUB):
                if url.rsplit("/", 1)[-1] in tags:
                    return b"{}"
                raise urllib.error.HTTPError(url, 404, "nf", None, None)
            raise AssertionError(url)
        return fetch

    def test_all_present(self):
        rep = cc.Report()
        cc.check_online(GOOD, rep, self.fetcher(
            {"iceberg-spark-runtime-4.1_2.13": ["1.11.0"], "iceberg-aws-bundle": ["1.10.0", "1.11.0"]},
            {"4.1.3": ">=3.10"}, {GOOD["SPARK_IMAGE_TAG"]}))
        self.assertEqual(rep.errors, [])

    def test_missing_everything(self):
        rep = cc.Report()
        cc.check_online(GOOD, rep, self.fetcher({"iceberg-aws-bundle": ["1.10.0"]}, None, set()))
        self.assertEqual(len(rep.errors), 4, rep.errors)

    def test_requires_python_excludes(self):
        rep = cc.Report()
        cc.check_online(GOOD, rep, self.fetcher(
            {"iceberg-spark-runtime-4.1_2.13": ["1.11.0"], "iceberg-aws-bundle": ["1.11.0"]},
            {"4.1.3": ">=3.10,<3.12"}, {GOOD["SPARK_IMAGE_TAG"]}))
        self.assertEqual(len(rep.errors), 2, rep.errors)  # PYTHON_IMAGE_TAG and AIRFLOW_PYTHON


if __name__ == "__main__":
    unittest.main()
