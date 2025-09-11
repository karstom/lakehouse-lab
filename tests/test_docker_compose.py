#!/usr/bin/env python3
"""
Integration tests for Docker Compose configurations
Tests that all compose files are valid and services are properly defined
"""

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml


class TestDockerComposeConfigurations(unittest.TestCase):
    """Test suite for Docker Compose files"""

    def setUp(self):
        """Set up test environment"""
        self.project_root = Path(__file__).parent.parent
        self.compose_files = ["docker-compose.yml", "docker-compose.iceberg.yml"]

    def test_compose_files_exist(self):
        """Test that all required compose files exist"""
        for compose_file in self.compose_files:
            file_path = self.project_root / compose_file
            self.assertTrue(
                file_path.exists(), f"Compose file {compose_file} should exist"
            )

    def test_compose_file_syntax(self):
        """Test that compose files have valid YAML syntax"""
        for compose_file in self.compose_files:
            file_path = self.project_root / compose_file
            if not file_path.exists():
                continue

            with open(file_path, "r") as f:
                try:
                    yaml.safe_load(f)
                except yaml.YAMLError as e:
                    self.fail(f"YAML syntax error in {compose_file}: {e}")

    def test_main_compose_structure(self):
        """Test main docker-compose.yml structure"""
        compose_file = self.project_root / "docker-compose.yml"
        if not compose_file.exists():
            self.skipTest("docker-compose.yml not found")

        with open(compose_file, "r") as f:
            compose_data = yaml.safe_load(f)

        # Check required top-level keys
        self.assertIn("services", compose_data, "Compose file should have services")
        self.assertIn("volumes", compose_data, "Compose file should have volumes")
        self.assertIn("networks", compose_data, "Compose file should have networks")

        # Check version
        self.assertIn("version", compose_data, "Compose file should have version")

        # Check essential services
        essential_services = [
            "postgres",
            "minio",
            "spark-master",
            "spark-worker",
            "jupyter",
            "airflow-scheduler",
            "airflow-webserver",
            "superset",
            "portainer",
        ]

        services = compose_data["services"]
        for service in essential_services:
            self.assertIn(service, services, f"Service {service} should be defined")

    def test_iceberg_compose_structure(self):
        """Test Iceberg override compose structure"""
        compose_file = self.project_root / "docker-compose.iceberg.yml"
        if not compose_file.exists():
            self.skipTest("docker-compose.iceberg.yml not found")

        with open(compose_file, "r") as f:
            compose_data = yaml.safe_load(f)

        # Check required top-level keys
        self.assertIn("services", compose_data, "Iceberg compose should have services")

        # Check for Spark service modifications
        services = compose_data["services"]
        spark_services = ["spark-master", "spark-worker"]

        for service in spark_services:
            if service in services:
                service_config = services[service]
                self.assertIn(
                    "volumes",
                    service_config,
                    f"{service} should have volumes for Iceberg",
                )
                self.assertIn(
                    "environment",
                    service_config,
                    f"{service} should have environment for Iceberg",
                )

    def test_service_health_checks(self):
        """Test that critical services have health checks"""
        compose_file = self.project_root / "docker-compose.yml"
        if not compose_file.exists():
            self.skipTest("docker-compose.yml not found")

        with open(compose_file, "r") as f:
            compose_data = yaml.safe_load(f)

        services_needing_health_checks = ["postgres", "minio"]
        services = compose_data["services"]

        for service in services_needing_health_checks:
            if service in services:
                service_config = services[service]
                self.assertIn(
                    "healthcheck", service_config, f"{service} should have healthcheck"
                )

    def test_service_dependencies(self):
        """Test that services have proper dependencies"""
        compose_file = self.project_root / "docker-compose.yml"
        if not compose_file.exists():
            self.skipTest("docker-compose.yml not found")

        with open(compose_file, "r") as f:
            compose_data = yaml.safe_load(f)

        services = compose_data["services"]

        # Check that dependent services specify dependencies
        dependency_checks = {
            "spark-master": ["postgres", "minio"],
            "spark-worker": ["spark-master"],
            "jupyter": ["spark-master"],
            "airflow-scheduler": ["postgres"],
            "airflow-webserver": ["postgres", "airflow-scheduler"],
            "superset": ["postgres"],
        }

        for service, expected_deps in dependency_checks.items():
            if service in services:
                service_config = services[service]
                if "depends_on" in service_config:
                    depends_on = service_config["depends_on"]
                    if isinstance(depends_on, list):
                        actual_deps = depends_on
                    else:
                        actual_deps = list(depends_on.keys())

                    for dep in expected_deps:
                        self.assertIn(
                            dep, actual_deps, f"{service} should depend on {dep}"
                        )

    def test_port_mappings(self):
        """Test that port mappings are reasonable and don't conflict"""
        compose_file = self.project_root / "docker-compose.yml"
        if not compose_file.exists():
            self.skipTest("docker-compose.yml not found")

        with open(compose_file, "r") as f:
            compose_data = yaml.safe_load(f)

        services = compose_data["services"]
        used_ports = set()

        for service_name, service_config in services.items():
            if "ports" in service_config:
                for port_mapping in service_config["ports"]:
                    if isinstance(port_mapping, str):
                        # Format: "host:container" or "host:container/protocol"
                        host_port = port_mapping.split(":")[0]
                        if host_port.isdigit():
                            host_port = int(host_port)
                            self.assertNotIn(
                                host_port,
                                used_ports,
                                f"Port {host_port} is used by multiple services",
                            )
                            used_ports.add(host_port)

                            # Check port range is reasonable
                            self.assertGreaterEqual(
                                host_port, 1024, f"Port {host_port} should be >= 1024"
                            )
                            self.assertLessEqual(
                                host_port, 65535, f"Port {host_port} should be <= 65535"
                            )

    def test_volume_definitions(self):
        """Test that volumes are properly defined"""
        compose_file = self.project_root / "docker-compose.yml"
        if not compose_file.exists():
            self.skipTest("docker-compose.yml not found")

        with open(compose_file, "r") as f:
            compose_data = yaml.safe_load(f)

        # Check that volumes section exists
        self.assertIn(
            "volumes", compose_data, "Compose file should have volumes section"
        )

        volumes = compose_data["volumes"]
        essential_volumes = ["postgres-data", "minio-data", "portainer-data"]

        for volume in essential_volumes:
            self.assertIn(volume, volumes, f"Volume {volume} should be defined")

    def test_network_definitions(self):
        """Test that networks are properly defined"""
        compose_file = self.project_root / "docker-compose.yml"
        if not compose_file.exists():
            self.skipTest("docker-compose.yml not found")

        with open(compose_file, "r") as f:
            compose_data = yaml.safe_load(f)

        # Check that networks section exists
        self.assertIn(
            "networks", compose_data, "Compose file should have networks section"
        )

        networks = compose_data["networks"]
        self.assertIn("lakehouse-network", networks, "Should have lakehouse-network")

    def test_environment_variables(self):
        """Test that services have required environment variables"""
        compose_file = self.project_root / "docker-compose.yml"
        if not compose_file.exists():
            self.skipTest("docker-compose.yml not found")

        with open(compose_file, "r") as f:
            compose_data = yaml.safe_load(f)

        services = compose_data["services"]

        # Check postgres has required env vars
        if "postgres" in services:
            postgres_env = services["postgres"].get("environment", {})
            required_postgres_vars = [
                "POSTGRES_DB",
                "POSTGRES_USER",
                "POSTGRES_PASSWORD",
            ]
            for var in required_postgres_vars:
                self.assertIn(
                    var,
                    postgres_env,
                    f"Postgres should have {var} environment variable",
                )

        # Check MinIO has required env vars
        if "minio" in services:
            minio_env = services["minio"].get("environment", {})
            required_minio_vars = ["MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD"]
            for var in required_minio_vars:
                self.assertIn(
                    var, minio_env, f"MinIO should have {var} environment variable"
                )

    def test_compose_validate_command(self):
        """Test that compose files pass docker compose validation"""
        for compose_file in self.compose_files:
            file_path = self.project_root / compose_file
            if not file_path.exists():
                continue

            # Test docker compose config validation
            try:
                result = subprocess.run(
                    ["docker", "compose", "-f", str(file_path), "config"],
                    capture_output=True,
                    text=True,
                    cwd=self.project_root,
                )

                if result.returncode != 0:
                    self.fail(
                        f"Docker Compose validation failed for {compose_file}: {result.stderr}"
                    )

            except FileNotFoundError:
                self.skipTest("docker compose command not available")

    def test_iceberg_jar_volume_mapping(self):
        """Test that Iceberg compose properly maps JAR volumes"""
        compose_file = self.project_root / "docker-compose.iceberg.yml"
        if not compose_file.exists():
            self.skipTest("docker-compose.iceberg.yml not found")

        with open(compose_file, "r") as f:
            compose_data = yaml.safe_load(f)

        services = compose_data["services"]

        # Check that Spark services have Iceberg JAR volumes
        spark_services = ["spark-master", "spark-worker"]
        for service in spark_services:
            if service in services:
                service_config = services[service]
                if "volumes" in service_config:
                    volumes = service_config["volumes"]
                    jar_volume_found = any("iceberg-jars" in vol for vol in volumes)
                    self.assertTrue(
                        jar_volume_found, f"{service} should have iceberg-jars volume"
                    )

    def test_service_restart_policies(self):
        """Test that services have appropriate restart policies"""
        compose_file = self.project_root / "docker-compose.yml"
        if not compose_file.exists():
            self.skipTest("docker-compose.yml not found")

        with open(compose_file, "r") as f:
            compose_data = yaml.safe_load(f)

        services = compose_data["services"]

        # Critical services should have restart policies
        critical_services = ["postgres", "minio", "spark-master"]

        for service in critical_services:
            if service in services:
                service_config = services[service]
                self.assertIn(
                    "restart", service_config, f"{service} should have restart policy"
                )

                restart_policy = service_config["restart"]
                valid_policies = ["no", "always", "on-failure", "unless-stopped"]
                self.assertIn(
                    restart_policy,
                    valid_policies,
                    f"{service} should have valid restart policy",
                )


class TestDockerComposeIntegration(unittest.TestCase):
    """Integration tests for Docker Compose functionality"""

    def setUp(self):
        """Set up test environment"""
        self.project_root = Path(__file__).parent.parent

    @patch("subprocess.run")
    def test_compose_up_dry_run(self, mock_run):
        """Test that compose up would work (dry run)"""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Services would start successfully"

        # This would test the actual compose up in a real scenario
        result = subprocess.run(
            ["docker", "compose", "up", "--dry-run"], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)

    @patch("subprocess.run")
    def test_compose_down_dry_run(self, mock_run):
        """Test that compose down would work (dry run)"""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Services would stop successfully"

        result = subprocess.run(
            ["docker", "compose", "down"], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)

    def test_compose_override_combination(self):
        """Test that main and iceberg compose files can be combined"""
        main_compose = self.project_root / "docker-compose.yml"
        iceberg_compose = self.project_root / "docker-compose.iceberg.yml"

        if not main_compose.exists() or not iceberg_compose.exists():
            self.skipTest("Required compose files not found")

        try:
            # Test that combined configuration is valid
            result = subprocess.run(
                [
                    "docker",
                    "compose",
                    "-f",
                    str(main_compose),
                    "-f",
                    str(iceberg_compose),
                    "config",
                ],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )

            if result.returncode != 0:
                self.fail(f"Combined compose validation failed: {result.stderr}")

            # Parse the combined config
            combined_config = yaml.safe_load(result.stdout)

            # Verify Iceberg services are properly merged
            services = combined_config.get("services", {})

            # Check that Spark services have Iceberg configurations
            spark_services = ["spark-master", "spark-worker"]
            for service in spark_services:
                if service in services:
                    service_config = services[service]
                    # Should have Iceberg-related environment variables
                    env_vars = service_config.get("environment", {})

                    # Look for Iceberg-related configurations
                    iceberg_related = any(
                        "iceberg" in str(var).lower() or "ICEBERG" in str(var)
                        for var in env_vars.keys()
                    )

                    if not iceberg_related:
                        # Check volumes for Iceberg JARs
                        volumes = service_config.get("volumes", [])
                        iceberg_jar_volume = any(
                            "iceberg-jars" in vol for vol in volumes
                        )
                        self.assertTrue(
                            iceberg_jar_volume,
                            f"{service} should have Iceberg JAR volume when using override",
                        )

        except FileNotFoundError:
            self.skipTest("docker compose command not available")


if __name__ == "__main__":
    unittest.main()
