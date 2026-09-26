"""Unit tests for v3/tools/images_matrix.py."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import images_matrix as im  # noqa: E402


class Matrix(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        self.v3 = self.repo / "v3"
        (self.v3 / "images" / "bootstrap").mkdir(parents=True)
        (self.v3 / "images" / "bootstrap" / "Dockerfile").write_text(
            "ARG PYTHON_IMAGE_TAG\nARG PYTHON_IMAGE_DIGEST\n"
            "FROM python:${PYTHON_IMAGE_TAG}@${PYTHON_IMAGE_DIGEST}\n"
            "ARG PYICEBERG_VERSION\nARG TARGETARCH\nARG PYTHON_IMAGE_TAG\n")
        (self.v3 / "versions.env").write_text(
            "PYTHON_IMAGE_TAG=t\nPYTHON_IMAGE_DIGEST=sha256:d\nPYICEBERG_VERSION=p\nTRINO_VERSION=x\n")

    def run_main(self, *extra: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = im.main(["--v3-dir", str(self.v3), "--registry", "ghcr.io/Owner", *extra])
        return rc, out.getvalue(), err.getvalue()

    def test_entry(self):
        rc, out, _ = self.run_main()
        self.assertEqual(rc, 0)
        (e,) = json.loads(out)["include"]
        self.assertEqual(e["name"], "bootstrap")
        self.assertEqual(e["dockerfile"], "v3/images/bootstrap/Dockerfile")
        self.assertEqual(e["context"], "v3/images/bootstrap")
        self.assertEqual(e["image"], "ghcr.io/owner/lakehouse-bootstrap")
        self.assertEqual(e["build_args"].splitlines(),
                         ["PYTHON_IMAGE_TAG=t", "PYTHON_IMAGE_DIGEST=sha256:d", "PYICEBERG_VERSION=p"])

    def test_missing_pin_is_error(self):
        df = self.v3 / "images" / "bootstrap" / "Dockerfile"
        df.write_text(df.read_text() + "ARG DUCKDB_VERSION\n")
        rc, _, err = self.run_main()
        self.assertEqual(rc, 1)
        self.assertIn("DUCKDB_VERSION", err)

    def test_context_from_compose(self):
        cj = self.repo / "c.json"
        cj.write_text(json.dumps({"services": {"bootstrap": {"build": {
            "context": str(self.v3), "dockerfile": "images/bootstrap/Dockerfile"}}}}))
        rc, out, _ = self.run_main("--compose-json", str(cj))
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["include"][0]["context"], "v3")

    def test_github_output(self):
        gh = self.repo / "gh_out"
        import os
        os.environ["GITHUB_OUTPUT"] = str(gh)
        try:
            rc, _, _ = self.run_main("--github-output")
        finally:
            del os.environ["GITHUB_OUTPUT"]
        self.assertEqual(rc, 0)
        lines = gh.read_text().splitlines()
        self.assertTrue(lines[0].startswith("matrix={"))
        self.assertEqual(lines[1], "count=1")

    def _superset(self) -> Path:
        d = self.v3 / "images" / "superset"
        d.mkdir(parents=True)
        (d / "Dockerfile").write_text(
            "FROM apache/superset:6 AS base\n"
            "COPY --from=base /app /app\n"
            "COPY --from=ghcr.io/x/y:1 /bin/z /bin/z\n"
            "COPY --from=config superset_config.py /app/pythonpath/\n")
        return d

    def test_copy_from_unknown_context_is_error(self):
        self._superset()
        rc, _, err = self.run_main()
        self.assertEqual(rc, 1)
        self.assertIn("COPY --from=config", err)
        self.assertNotIn("--from=base", err)

    def test_copy_from_missing_when_service_not_in_profile(self):
        # compose JSON from a profile without superset (the v3-images.yml bug): no context.
        self._superset()
        cj = self.repo / "c.json"
        cj.write_text(json.dumps({"services": {"bootstrap": {"build": {
            "context": str(self.v3), "dockerfile": "images/bootstrap/Dockerfile"}}}}))
        rc, _, err = self.run_main("--compose-json", str(cj))
        self.assertEqual(rc, 1)
        self.assertIn("superset", err)

    def test_copy_from_resolved_by_compose_context(self):
        d = self._superset()
        (self.v3 / "config" / "superset").mkdir(parents=True)
        cj = self.repo / "c.json"
        cj.write_text(json.dumps({"services": {"superset": {"build": {
            "context": str(d), "additional_contexts": {"config": "../../config/superset"}}}}}))
        rc, out, err = self.run_main("--compose-json", str(cj))
        self.assertEqual(rc, 0, err)
        e = {x["name"]: x for x in json.loads(out)["include"]}["superset"]
        self.assertEqual(e["build_contexts"], "config=v3/config/superset")

    def test_real_tree_full_profile_json(self):
        """Every real Dockerfile resolves its COPY --from with contexts from profile full."""
        real_v3 = Path(__file__).resolve().parents[2]
        data = {"services": {
            "superset": {"build": {"context": str(real_v3 / "images" / "superset"),
                                   "additional_contexts": {"config": "../../config/superset"}}},
            "workspace-image": {"build": {"context": str(real_v3 / "images" / "workspace"),
                                          "additional_contexts": {"starter": "../../starter"}}}}}
        cj = self.repo / "full.json"
        cj.write_text(json.dumps(data))
        extra = im.compose_extra_contexts(cj)
        for df in sorted((real_v3 / "images").glob("*/Dockerfile")):
            self.assertEqual(im.unresolved_copy_from(df, set(extra.get(df.resolve(), {}))), [],
                             df)


if __name__ == "__main__":
    unittest.main()
