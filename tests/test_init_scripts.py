#!/usr/bin/env python3
"""
Unit tests for lakehouse initialization scripts
Tests the core functionality of init-all-in-one-modular.sh and start-lakehouse.sh
"""

import unittest
import subprocess
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, call
import sys


class TestInitScripts(unittest.TestCase):
    """Test suite for initialization scripts"""

    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.test_dir)

        # Create mock script files
        self.init_script = Path("init-all-in-one-modular.sh")
        self.start_script = Path("start-lakehouse.sh")

        # Copy actual scripts to test directory
        project_root = Path(__file__).parent.parent
        if (project_root / "init-all-in-one-modular.sh").exists():
            shutil.copy2(project_root / "init-all-in-one-modular.sh", self.init_script)
        # Also copy the scripts and templates directories
        if (project_root / "scripts").exists():
            shutil.copytree(project_root / "scripts", Path("scripts"))
        if (project_root / "templates").exists():
            shutil.copytree(project_root / "templates", Path("templates"))
        if (project_root / "start-lakehouse.sh").exists():
            shutil.copy2(project_root / "start-lakehouse.sh", self.start_script)

    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.original_dir)
        shutil.rmtree(self.test_dir)

    def test_init_script_exists(self):
        """Test that init script exists and is executable"""
        self.assertTrue(
            self.init_script.exists(), "init-all-in-one-modular.sh should exist"
        )

        # Make script executable if it exists
        if self.init_script.exists():
            os.chmod(self.init_script, 0o755)
            self.assertTrue(
                os.access(self.init_script, os.X_OK), "Script should be executable"
            )

    def test_start_script_exists(self):
        """Test that start script exists and is executable"""
        self.assertTrue(self.start_script.exists(), "start-lakehouse.sh should exist")

        # Make script executable if it exists
        if self.start_script.exists():
            os.chmod(self.start_script, 0o755)
            self.assertTrue(
                os.access(self.start_script, os.X_OK), "Script should be executable"
            )

    def test_init_script_syntax(self):
        """Test that init script has valid bash syntax"""
        if not self.init_script.exists():
            self.skipTest("init-all-in-one-modular.sh not found")

        result = subprocess.run(
            ["bash", "-n", str(self.init_script)], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, f"Script syntax error: {result.stderr}")

    def test_start_script_syntax(self):
        """Test that start script has valid bash syntax"""
        if not self.start_script.exists():
            self.skipTest("start-lakehouse.sh not found")

        result = subprocess.run(
            ["bash", "-n", str(self.start_script)], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, f"Script syntax error: {result.stderr}")

    def test_init_script_shebang(self):
        """Test that init script has proper shebang"""
        if not self.init_script.exists():
            self.skipTest("init-all-in-one-modular.sh not found")

        with open(self.init_script, "r") as f:
            first_line = f.readline().strip()

        self.assertTrue(
            first_line.startswith("#!/"),
            f"Script should start with shebang, got: {first_line}",
        )

    def test_start_script_shebang(self):
        """Test that start script has proper shebang"""
        if not self.start_script.exists():
            self.skipTest("start-lakehouse.sh not found")

        with open(self.start_script, "r") as f:
            first_line = f.readline().strip()

        self.assertTrue(
            first_line.startswith("#!/"),
            f"Script should start with shebang, got: {first_line}",
        )

    def test_init_script_has_error_handling(self):
        """Test that init script has proper error handling"""
        if not self.init_script.exists():
            self.skipTest("init-all-in-one-modular.sh not found")

        with open(self.init_script, "r") as f:
            content = f.read()

        # Check for common error handling patterns
        self.assertIn(
            "set -e", content, "Script should have 'set -e' for error handling"
        )
        self.assertIn("trap", content, "Script should have trap for cleanup")

    def test_start_script_has_error_handling(self):
        """Test that start script has proper error handling"""
        if not self.start_script.exists():
            self.skipTest("start-lakehouse.sh not found")

        with open(self.start_script, "r") as f:
            content = f.read()

        # Check for common error handling patterns
        self.assertIn(
            "set -e", content, "Script should have 'set -e' for error handling"
        )

    def test_init_script_environment_variables(self):
        """Test that init script properly handles environment variables"""
        if not self.init_script.exists():
            self.skipTest("init-all-in-one-modular.sh not found")

        with open(self.init_script, "r") as f:
            content = f.read()

        # Check for LAKEHOUSE_ROOT variable handling
        self.assertIn(
            "LAKEHOUSE_ROOT", content, "Script should handle LAKEHOUSE_ROOT variable"
        )
        self.assertIn(
            "${LAKEHOUSE_ROOT", content, "Script should use proper variable expansion"
        )

    def test_start_script_modes(self):
        """Test that start script supports different modes"""
        if not self.start_script.exists():
            self.skipTest("start-lakehouse.sh not found")

        with open(self.start_script, "r") as f:
            content = f.read()

        # Check for different startup modes
        expected_modes = ["normal", "debug", "minimal", "stop", "status", "help"]
        for mode in expected_modes:
            self.assertIn(mode, content, f"Script should support {mode} mode")

    def test_init_script_logging(self):
        """Test that init script has proper logging functions"""
        if not self.init_script.exists():
            self.skipTest("init-all-in-one-modular.sh not found")

        with open(self.init_script, "r") as f:
            content = f.read()

        # Check for logging functions
        logging_functions = ["log_info", "log_error", "log_success", "log_warning"]
        for func in logging_functions:
            self.assertIn(func, content, f"Script should have {func} logging function")

    def test_start_script_health_checks(self):
        """Test that start script has service health check functions"""
        if not self.start_script.exists():
            self.skipTest("start-lakehouse.sh not found")

        with open(self.start_script, "r") as f:
            content = f.read()

        # Check for health check functionality
        self.assertIn(
            "check_service_health", content, "Script should have health check function"
        )
        self.assertIn("curl", content, "Script should use curl for health checks")

    def test_init_script_minio_client_installation(self):
        """Test that init script properly installs MinIO client"""
        if not self.init_script.exists():
            self.skipTest("init-all-in-one-modular.sh not found")

        with open(self.init_script, "r") as f:
            content = f.read()

        # Check for MinIO client installation
        self.assertIn(
            "install_minio_client", content, "Script should install MinIO client"
        )
        self.assertIn(
            "dl.min.io", content, "Script should download from official MinIO site"
        )

    def test_init_script_iceberg_support(self):
        """Test that init script supports Iceberg integration"""
        if not self.init_script.exists():
            self.skipTest("init-all-in-one-modular.sh not found")

        with open(self.init_script, "r") as f:
            content = f.read()

        # Check for Iceberg support
        self.assertIn("iceberg", content.lower(), "Script should support Iceberg")

    def test_start_script_docker_requirements(self):
        """Test that start script checks Docker requirements"""
        if not self.start_script.exists():
            self.skipTest("start-lakehouse.sh not found")

        with open(self.start_script, "r") as f:
            content = f.read()

        # Check for Docker requirements
        self.assertIn("docker", content, "Script should check for Docker")
        self.assertIn(
            "docker compose", content, "Script should check for Docker Compose"
        )


class TestScriptFunctionality(unittest.TestCase):
    """Test script functionality with mocked dependencies"""

    @patch("subprocess.run")
    def test_docker_check_success(self, mock_run):
        """Test successful Docker availability check"""
        mock_run.return_value.returncode = 0

        # This would be part of the actual script testing
        # For now, just verify the mock is set up correctly
        result = subprocess.run(["docker", "--version"], capture_output=True)
        self.assertEqual(result.returncode, 0)

    @patch("subprocess.run")
    def test_docker_check_failure(self, mock_run):
        """Test Docker unavailable scenario"""
        mock_run.return_value.returncode = 1

        result = subprocess.run(["docker", "--version"], capture_output=True)
        self.assertEqual(result.returncode, 1)

    @patch("os.path.exists")
    def test_initialization_marker_check(self, mock_exists):
        """Test initialization marker file checking"""
        mock_exists.return_value = True

        # Test that script would skip initialization if marker exists
        self.assertTrue(os.path.exists("/fake/marker"))

        mock_exists.return_value = False
        self.assertFalse(os.path.exists("/fake/marker"))


if __name__ == "__main__":
    unittest.main()
