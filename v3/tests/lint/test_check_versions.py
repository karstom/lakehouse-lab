"""Unit tests for v3/tools/check_versions.py. Run: python3 -m unittest discover -s v3/tests/lint"""

from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import check_versions as cv  # noqa: E402


def rules(path: str, text: str) -> list[tuple[int, str]]:
    return [(f.line, f.rule) for f in cv.scan_text(path, textwrap.dedent(text).lstrip("\n"))]


class ComposeImages(unittest.TestCase):
    def test_literal_tag(self):
        self.assertEqual(rules("compose/core.yaml", "services:\n  t:\n    image: trinodb/trino:483\n"), [(3, "image-tag")])

    def test_literal_tag_quoted_and_registry_port(self):
        self.assertEqual(rules("c.yaml", 'image: "quay.io:443/keycloak/keycloak:26.7.4"\n'), [(1, "image-tag")])

    def test_variable_tag_ok(self):
        self.assertEqual(rules("c.yaml", "image: trinodb/trino:${TRINO_VERSION}\n"), [])
        self.assertEqual(rules("c.yaml", "image: python:${PYTHON_IMAGE_TAG}@${PYTHON_IMAGE_DIGEST}\n"), [])
        self.assertEqual(rules("c.yaml", "image: ${LAB_REGISTRY}/lakehouse-bootstrap:${LAB_VERSION}\n"), [])

    def test_whole_ref_from_variable_ok(self):
        self.assertEqual(rules("c.yaml", "image: ${PLAYWRIGHT_IMAGE}\n"), [])

    def test_latest(self):
        self.assertEqual(rules("c.yaml", "image: caddy:latest\n"), [(1, "latest")])

    def test_untagged(self):
        self.assertEqual(rules("c.yaml", "image: postgres\n"), [(1, "image-untagged")])

    def test_literal_digest(self):
        self.assertEqual(rules("c.yaml", "image: caddy:${CADDY_VERSION}@sha256:" + "a" * 64 + "\n"), [(1, "digest")])

    def test_yaml_anchor_and_alias(self):
        self.assertEqual(rules("c.yaml", "image: &img lakehouse/x:${LAB_VERSION}\nimage: *img\n"), [])

    def test_variable_default_in_tag(self):
        self.assertEqual(rules("c.yaml", "image: trinodb/trino:${TRINO_VERSION:-483}\n"), [(1, "var-default")])

    def test_comment_ignored(self):
        self.assertEqual(rules("c.yaml", "# image: trinodb/trino:483 was the spike pin\n"), [])


class Dockerfiles(unittest.TestCase):
    def test_from_literal(self):
        self.assertEqual(rules("images/x/Dockerfile", "FROM python:3.12-slim\n"), [(1, "from")])

    def test_from_untagged(self):
        self.assertEqual(rules("images/x/Dockerfile", "FROM ubuntu AS base\n"), [(1, "from")])

    def test_from_args_ok_and_stage_reuse(self):
        self.assertEqual(rules("images/x/Dockerfile", """
            ARG PYTHON_IMAGE_TAG
            ARG PYTHON_IMAGE_DIGEST
            FROM --platform=$BUILDPLATFORM python:${PYTHON_IMAGE_TAG}@${PYTHON_IMAGE_DIGEST} AS build
            FROM build AS final
            FROM scratch
            """), [])

    def test_from_without_digest(self):
        # ADR-012 amendment: tag AND digest, both from versions.env.
        self.assertEqual(rules("images/smoke/Dockerfile",
                               "FROM mcr.microsoft.com/playwright/python:${PLAYWRIGHT_IMAGE_TAG}\n"),
                         [(1, "from-digest")])
        self.assertEqual(rules("Dockerfile", "FROM python:${PYTHON_IMAGE_TAG}@${PYTHON_IMAGE_TAG}\n"),
                         [(1, "from-digest")])
        self.assertEqual(rules("Dockerfile", "FROM ${BASE_IMAGE}\n"), [(1, "from-digest")])
        self.assertEqual(rules("Dockerfile", "FROM ${BASE_IMAGE} AS base\nFROM base\n"), [(1, "from-digest")])

    def test_from_with_digest_ok(self):
        self.assertEqual(rules("images/smoke/Dockerfile",
                               "FROM mcr.microsoft.com/playwright/python:${PLAYWRIGHT_IMAGE_TAG}@${PLAYWRIGHT_IMAGE_DIGEST}\n"),
                         [])

    def test_from_latest(self):
        self.assertEqual(rules("Dockerfile", "FROM alpine:latest\n"), [(1, "latest")])

    def test_arg_defaults(self):
        self.assertEqual(rules("Dockerfile", """
            ARG TRINO_VERSION=483
            ARG ICEBERG=1.11.0
            ARG BASE=eclipse-temurin:21-jre
            ARG USER_ID=1000
            ARG NAME=${OTHER}
            """), [(1, "arg-default"), (2, "arg-default"), (3, "arg-default")])

    def test_env_version(self):
        self.assertEqual(rules("Dockerfile", "ENV SPARK_VERSION=4.1.3 HOME=/opt\n"), [(1, "arg-default")])

    def test_syntax_directive(self):
        self.assertEqual(rules("Dockerfile", "# syntax=docker/dockerfile:1\nFROM scratch\n"), [(1, "syntax")])

    def test_pip_in_run(self):
        self.assertEqual(rules("Dockerfile", "RUN pip install --no-cache-dir 'trino==0.340.0' duckdb\n"), [(1, "pip-pin")])
        self.assertEqual(rules("Dockerfile", 'RUN pip install "trino==${TRINO_PYTHON_VERSION}"\n'), [])


class Packages(unittest.TestCase):
    def test_requirements(self):
        self.assertEqual(rules("images/w/requirements.in", """
            jupyterlab==${JUPYTERLAB_VERSION}
            duckdb==1.5.5
            pyiceberg[s3fs]>=0.12
            # pandas==2.0 (comment)
            requests
            """), [(2, "pip-pin"), (3, "pip-pin")])

    def test_generated_lock_exempt(self):
        self.assertEqual(rules("images/w/lock/constraints.txt", "# GENERATED by relock. Do not edit.\nagate==1.9.1\n"), [])

    def test_generated_marker_must_be_first_line(self):
        self.assertEqual(rules("constraints.txt", "agate==1.9.1\n# GENERATED\n"), [(1, "pip-pin")])

    def test_pip_command_in_script(self):
        self.assertEqual(rules("bootstrap/x.sh", "python3 -m pip install pyiceberg==0.12.0\n"), [(1, "pip-pin")])

    def test_python_comparison_not_pip(self):
        self.assertEqual(rules("bootstrap/x.py", "if len(rows) >= 2 and sys.version_info >= (3, 12):\n"), [])

    def test_npm(self):
        self.assertEqual(rules("tests/smoke/run.sh", "npx playwright@1.63.0 test\n"), [(1, "npm-pin")])
        self.assertEqual(rules("tests/smoke/run.sh", 'npm install "@playwright/test@${PLAYWRIGHT_VERSION}"\n'), [])

    def test_package_json(self):
        self.assertEqual(rules("tests/smoke/package.json", """
            {
              "name": "smoke",
              "version": "0.0.0",
              "dependencies": {
                "@playwright/test": "^1.63.0"
              }
            }
            """), [(5, "npm-pin")])


class Jars(unittest.TestCase):
    def test_maven_coordinate(self):
        self.assertEqual(rules("x.sh", "--packages org.apache.iceberg:iceberg-aws-bundle:1.11.0\n"), [(1, "jar")])

    def test_jar_filename(self):
        self.assertEqual(rules("x.sh", "cp iceberg-aws-bundle-1.11.0.jar /opt/spark/jars/\n"), [(1, "jar")])

    def test_maven_path(self):
        self.assertEqual(rules("x.sh", "curl -fO https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-aws-bundle/1.11.0/x.jar\n"), [(1, "jar")])

    def test_scala_suffix_and_runtime_minor(self):
        self.assertEqual(rules("x.sh", 'A="iceberg-spark-runtime-4.1_${SCALA_BINARY_VERSION}"\n'), [(1, "jar")])
        self.assertEqual(rules("x.sh", 'A="iceberg-spark-runtime-${SPARK_MINOR}_2.13"\n'), [(1, "jar")])

    def test_derived_ok(self):
        self.assertEqual(rules("x.sh", 'A="iceberg-spark-runtime-${SPARK_MINOR}_${SCALA_BINARY_VERSION}-${ICEBERG_VERSION}.jar"\n'), [])


class Variables(unittest.TestCase):
    def test_version_var_assignments(self):
        self.assertEqual(rules("installer/lib.sh", 'MIN_COMPOSE_VERSION="2.24.0"\n'), [(1, "version-var")])
        self.assertEqual(rules("compose/a.yaml", "      args:\n        TRINO_VERSION: 483\n"), [(2, "version-var")])
        self.assertEqual(rules("compose/a.yaml", "        TRINO_VERSION: ${TRINO_VERSION}\n"), [])

    def test_var_default(self):
        self.assertEqual(rules("x.sh", 'v="${SPARK_VERSION:-4.1.3}"\n'), [(1, "var-default")])
        self.assertEqual(rules("x.sh", 'img="${IMG:-caddy:2.11.4}"\n'), [(1, "var-default")])
        # Non-version fallbacks are fine (contract: ${SVC_MEM:-default}).
        self.assertEqual(rules("c.yaml", "mem_limit: ${TRINO_MEM:-2g}\ncpus: ${TRINO_CPUS:-2.0}\n"), [])

    def test_pragma(self):
        self.assertEqual(rules("tests/x.sh", 'SHIM_DOCKER_VERSION=23.0.6 run  # check-versions: ignore fake version for the min-version test\n'), [])
        self.assertEqual(rules("tests/x.sh", 'SHIM_DOCKER_VERSION=23.0.6 run  # check-versions: ignore\n'), [(1, "pragma")])

    def test_bare_digest(self):
        self.assertEqual(rules("x.sh", "echo sha256:" + "0" * 64 + "\n"), [(1, "digest")])


class NoFalsePositives(unittest.TestCase):
    def test_urls_ports_ips(self):
        self.assertEqual(rules("config/trino/config.properties", """
            http-server.https.port=8443
            discovery.uri=http://trino:8080
            http-server.authentication.oauth2.issuer=https://auth.${LAB_DOMAIN}:18443/realms/lakehouse
            jdbc:postgresql://postgres:5432/lakekeeper
            host=10.0.0.1:5432
            """), [])

    def test_prose_versions(self):
        self.assertEqual(rules("README.md", "Trino 483 reads Iceberg tables; Spark 4.1 uses Scala 2.13.\n"), [])

    def test_times_and_sizes(self):
        self.assertEqual(rules("c.yaml", "start_period: 30s\nmem_limit: 1.5g\ntimeout: 1m30s\n"), [])

    def test_host_port_in_script(self):
        self.assertEqual(rules("x.sh", "curl -fsS http://lakekeeper:8181/health\nwait_for postgres:5432\n"), [])


class Cli(unittest.TestCase):
    def _tree(self, files: dict[str, str]) -> Path:
        d = Path(tempfile.mkdtemp())
        for rel, body in files.items():
            p = d / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body)
        return d

    def test_exemptions_and_exit_codes(self):
        d = self._tree({
            "versions.env": "TRINO_VERSION=483\n",
            ".pins/core.env": "EXTRA_VERSION=1.0.0\n",
            ".env": "LAB_DOMAIN=lab.localhost\nSOME_VERSION=1.2.3\n",
            "state/ca/x.env": "X_VERSION=1.0\n",
            "compose.yaml": "services:\n  t:\n    image: trinodb/trino:${TRINO_VERSION}\n",
        })
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = cv.main(["--v3-dir", str(d)])
        self.assertEqual(rc, 0, out.getvalue())

        (d / "compose.yaml").write_text("services:\n  t:\n    image: trinodb/trino:483\n")
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            rc = cv.main(["--v3-dir", str(d), "--format", "github"])
        self.assertEqual(rc, 1)
        text = out.getvalue()
        self.assertRegex(text, r"compose\.yaml:3:12: \[image-tag\]")
        self.assertIn("::error file=", text)

    def test_tooling_files_are_clean(self):
        """The checker and the other tools pass their own check."""
        tool = Path(cv.__file__)
        files = sorted(str(p) for p in tool.parent.iterdir() if p.is_file())
        r = subprocess.run([sys.executable, str(tool), *files], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
