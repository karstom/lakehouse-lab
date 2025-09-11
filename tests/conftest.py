"""
Test configuration and shared fixtures for the lakehouse test suite.
This module provides common test utilities and fixtures.
"""

import pytest
import tempfile
import shutil
import os
from pathlib import Path
from unittest.mock import Mock, patch
import docker
import yaml
import subprocess
import time
from typing import Dict, List, Any, Generator, Optional

# Test configuration
TEST_CONFIG = {
    "timeout": 300,  # 5 minutes
    "service_wait_time": 30,  # 30 seconds
    "docker_compose_file": "docker-compose.yml",
    "iceberg_compose_file": "docker-compose.iceberg.yml",
    "test_data_dir": "test_data",
    "temp_dir_prefix": "lakehouse_test_",
}


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def test_config() -> Dict[str, Any]:
    """Get test configuration."""
    return TEST_CONFIG


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create and cleanup temporary directory for tests."""
    temp_dir = Path(tempfile.mkdtemp(prefix=TEST_CONFIG["temp_dir_prefix"]))
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_docker_client():
    """Mock Docker client for testing."""
    with patch("docker.from_env") as mock_docker:
        mock_client = Mock()
        mock_docker.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_subprocess():
    """Mock subprocess for testing shell commands."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Success"
        mock_run.return_value.stderr = ""
        yield mock_run


@pytest.fixture(scope="session")
def docker_available() -> bool:
    """Check if Docker is available for testing."""
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


@pytest.fixture
def compose_files(project_root: Path) -> Dict[str, Path]:
    """Get paths to Docker Compose files."""
    return {
        "main": project_root / TEST_CONFIG["docker_compose_file"],
        "iceberg": project_root / TEST_CONFIG["iceberg_compose_file"],
    }


@pytest.fixture
def script_files(project_root: Path) -> Dict[str, Path]:
    """Get paths to script files."""
    return {
        "init": project_root / "init-all-in-one-modular.sh",
        "start": project_root / "start-lakehouse.sh",
        "install": project_root / "install.sh",
    }


@pytest.fixture
def sample_compose_data() -> Dict[str, Any]:
    """Sample Docker Compose data for testing."""
    return {
        "version": "3.8",
        "services": {
            "postgres": {
                "image": "postgres:13",
                "environment": {
                    "POSTGRES_DB": "test_db",
                    "POSTGRES_USER": "test_user",
                    "POSTGRES_PASSWORD": "test_pass",
                },
                "ports": ["5432:5432"],
                "volumes": ["postgres-data:/var/lib/postgresql/data"],
                "networks": ["lakehouse-network"],
            },
            "minio": {
                "image": "minio/minio:latest",
                "environment": {
                    "MINIO_ROOT_USER": "minio",
                    "MINIO_ROOT_PASSWORD": "minio123",
                },
                "ports": ["9000:9000", "9001:9001"],
                "volumes": ["minio-data:/data"],
                "networks": ["lakehouse-network"],
                "healthcheck": {
                    "test": [
                        "CMD",
                        "curl",
                        "-f",
                        "http://localhost:9000/minio/health/live",
                    ],
                    "interval": "30s",
                    "timeout": "10s",
                    "retries": 3,
                },
            },
            "spark-master": {
                "image": "apache/spark:3.5.6",
                "environment": {"SPARK_MODE": "master"},
                "ports": ["8080:8080"],
                "depends_on": ["postgres", "minio"],
                "networks": ["lakehouse-network"],
            },
        },
        "volumes": {"postgres-data": {}, "minio-data": {}},
        "networks": {"lakehouse-network": {"driver": "bridge"}},
    }


@pytest.fixture
def sample_iceberg_override() -> Dict[str, Any]:
    """Sample Iceberg override data for testing."""
    return {
        "services": {
            "spark-master": {
                "volumes": ["./iceberg-jars:/opt/spark/jars/iceberg:ro"],
                "environment": {
                    "SPARK_CONF_spark.sql.extensions": (
                        "org.apache.iceberg.spark.extensions."
                        "IcebergSparkSessionExtensions"
                    ),
                    "SPARK_CONF_spark.sql.catalog.iceberg": (
                        "org.apache.iceberg.spark.SparkCatalog"
                    ),
                    "SPARK_CONF_spark.sql.catalog.iceberg.type": "hadoop",
                    "SPARK_CONF_spark.sql.catalog.iceberg.warehouse": (
                        "s3a://lakehouse/iceberg-warehouse/"
                    ),
                    "SPARK_CONF_spark.hadoop.fs.s3a.endpoint": ("http://minio:9000"),
                    "SPARK_CONF_spark.hadoop.fs.s3a.access.key": "minio",
                    "SPARK_CONF_spark.hadoop.fs.s3a.secret.key": "minio123",
                    "SPARK_CONF_spark.hadoop.fs.s3a.path.style.access": ("true"),
                    "SPARK_CONF_spark.hadoop.fs.s3a.connection.ssl.enabled": ("false"),
                },
            }
        }
    }


class TestContainerManager:
    """Utility class for managing test containers."""

    def __init__(self, compose_files: Dict[str, Path]):
        self.compose_files = compose_files
        self.running_containers: List[str] = []

    def start_services(
        self, services: Optional[List[str]] = None, use_iceberg: bool = False
    ) -> bool:
        """Start Docker Compose services."""
        try:
            cmd = ["docker-compose", "-f", str(self.compose_files["main"])]

            if use_iceberg and self.compose_files["iceberg"].exists():
                cmd.extend(["-f", str(self.compose_files["iceberg"])])

            cmd.extend(["up", "-d"])

            if services:
                cmd.extend(services)

            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0

        except Exception as e:
            print(f"Error starting services: {e}")
            return False

    def stop_services(self) -> bool:
        """Stop Docker Compose services."""
        try:
            cmd = ["docker-compose", "-f", str(self.compose_files["main"])]

            if self.compose_files["iceberg"].exists():
                cmd.extend(["-f", str(self.compose_files["iceberg"])])

            cmd.extend(["down", "-v"])

            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0

        except Exception as e:
            print(f"Error stopping services: {e}")
            return False

    def wait_for_service(
        self, service_name: str, port: int, timeout: int = TEST_CONFIG["timeout"]
    ) -> bool:
        """Wait for a service to be ready."""
        import requests

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"http://localhost:{port}", timeout=5)
                if response.status_code == 200:
                    return True
            except Exception:
                pass
            time.sleep(5)

        return False

    def get_service_logs(self, service_name: str) -> str:
        """Get logs for a specific service."""
        try:
            cmd = [
                "docker-compose",
                "-f",
                str(self.compose_files["main"]),
                "logs",
                "--tail=50",
                service_name,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.stdout

        except Exception as e:
            return f"Error getting logs: {e}"


@pytest.fixture
def container_manager(compose_files: Dict[str, Path]) -> TestContainerManager:
    """Get container manager instance."""
    return TestContainerManager(compose_files)


@pytest.fixture
def mock_yaml_file(temp_dir: Path):
    """Create a mock YAML file for testing."""

    def _create_yaml_file(filename: str, data: Dict[str, Any]) -> Path:
        file_path = temp_dir / filename
        with open(file_path, "w") as f:
            yaml.dump(data, f)
        return file_path

    return _create_yaml_file


@pytest.fixture
def mock_script_file(temp_dir: Path):
    """Create a mock shell script for testing."""

    def _create_script_file(
        filename: str, content: str, executable: bool = True
    ) -> Path:
        file_path = temp_dir / filename
        with open(file_path, "w") as f:
            f.write(content)

        if executable:
            os.chmod(file_path, 0o755)

        return file_path

    return _create_script_file


class ServiceHealthChecker:
    """Utility class for checking service health."""

    HEALTH_ENDPOINTS = {
        "minio": "http://localhost:9000/minio/health/live",
        "spark-master": "http://localhost:8080",
        "postgres": "localhost:5432",  # Special case for TCP check
        "superset": "http://localhost:9030/health",
        "airflow": "http://localhost:9020/health",
        "jupyter": "http://localhost:9040",
        "portainer": "http://localhost:9060",
    }

    @staticmethod
    def check_http_endpoint(url: str, timeout: int = 10) -> bool:
        """Check if an HTTP endpoint is responding."""
        try:
            import requests

            response = requests.get(url, timeout=timeout)
            return response.status_code == 200
        except Exception:
            return False

    @staticmethod
    def check_tcp_port(host: str, port: int, timeout: int = 10) -> bool:
        """Check if a TCP port is open."""
        import socket

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    @classmethod
    def check_service(cls, service_name: str, timeout: int = 10) -> bool:
        """Check if a service is healthy."""
        if service_name not in cls.HEALTH_ENDPOINTS:
            return False

        endpoint = cls.HEALTH_ENDPOINTS[service_name]

        if endpoint.startswith("http"):
            return cls.check_http_endpoint(endpoint, timeout)
        else:
            # TCP check
            host, port = endpoint.split(":")
            return cls.check_tcp_port(host, int(port), timeout)


@pytest.fixture
def health_checker() -> ServiceHealthChecker:
    """Get service health checker instance."""
    return ServiceHealthChecker()


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "slow: marks tests as slow running")
    config.addinivalue_line("markers", "docker: marks tests that require Docker")
    config.addinivalue_line(
        "markers", "iceberg: marks tests specific to Iceberg functionality"
    )


def pytest_runtest_setup(item):
    """Set up test run conditions."""
    # Skip Docker tests if Docker is not available
    if item.get_closest_marker("docker"):
        try:
            client = docker.from_env()
            client.ping()
        except Exception:
            pytest.skip("Docker is not available")

    # Skip integration tests in unit test mode
    if item.get_closest_marker("integration"):
        if item.config.getoption("--unit-only", default=False):
            pytest.skip("Skipping integration tests in unit-only mode")


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--unit-only",
        action="store_true",
        default=False,
        help="Run only unit tests, skip integration tests",
    )
    parser.addoption(
        "--integration-only",
        action="store_true",
        default=False,
        help="Run only integration tests, skip unit tests",
    )
    parser.addoption(
        "--docker-available",
        action="store_true",
        default=False,
        help="Run tests that require Docker",
    )


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_environment():
    """Clean up test environment after all tests."""
    yield

    # Clean up any leftover containers
    try:
        subprocess.run(["docker-compose", "down", "-v"], capture_output=True, text=True)
    except Exception:
        pass

    # Clean up temporary files
    import glob

    temp_files = glob.glob(f"/tmp/{TEST_CONFIG['temp_dir_prefix']}*")
    for temp_file in temp_files:
        try:
            if os.path.isdir(temp_file):
                shutil.rmtree(temp_file)
            else:
                os.remove(temp_file)
        except Exception:
            pass
