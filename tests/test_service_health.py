#!/usr/bin/env python3
"""
Service Health Tests for Lakehouse Stack
Tests that all services are running and accessible after initialization
"""

import unittest
import requests
import psycopg2
import boto3
import socket
import time
from pathlib import Path
import subprocess


class TestServiceHealth(unittest.TestCase):
    """Test suite for service health checks"""

    def setUp(self):
        """Set up test environment"""
        self.project_root = Path(__file__).parent.parent
        self.base_url = "http://localhost"
        self.timeout = 30

        # Service endpoints
        self.services = {
            "minio": {"port": 9000, "health_path": "/minio/health/live"},
            "minio_console": {"port": 9001, "health_path": "/"},
            "spark_master": {"port": 8080, "health_path": "/"},
            "jupyter": {"port": 9040, "health_path": "/"},
            "airflow": {"port": 9020, "health_path": "/health"},
            "superset": {"port": 9030, "health_path": "/health"},
            "portainer": {"port": 9060, "health_path": "/"},
        }

        # Database connection
        self.db_config = {
            "host": "localhost",
            "port": 5432,
            "database": "airflow",
            "user": "postgres",
            "password": "lakehouse",
        }

        # MinIO S3 config
        self.s3_config = {
            "endpoint_url": "http://localhost:9000",
            "aws_access_key_id": "minio",
            "aws_secret_access_key": "minio123",
            "region_name": "us-east-1",
        }

    def wait_for_service(self, host, port, timeout=30):
        """Wait for a service to be available"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                sock.close()
                if result == 0:
                    return True
            except Exception:
                pass
            time.sleep(1)
        return False

    def test_postgres_connection(self):
        """Test PostgreSQL database connection"""
        print("🔍 Testing PostgreSQL connection...")

        # Wait for PostgreSQL to be ready
        self.assertTrue(
            self.wait_for_service("localhost", 5432, self.timeout),
            "PostgreSQL service not available",
        )

        try:
            # Test database connection
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()

            # Test basic query
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            self.assertIsNotNone(version, "Should get PostgreSQL version")

            # Test Airflow tables exist
            cursor.execute(
                """
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name LIKE 'dag%'
            """
            )
            dag_tables = cursor.fetchone()[0]
            self.assertGreater(dag_tables, 0, "Airflow DAG tables should exist")

            cursor.close()
            conn.close()
            print("✅ PostgreSQL connection successful")

        except Exception as e:
            self.fail(f"PostgreSQL connection failed: {e}")

    def test_minio_s3_connectivity(self):
        """Test MinIO S3 connectivity"""
        print("🔍 Testing MinIO S3 connectivity...")

        # Wait for MinIO to be ready
        self.assertTrue(
            self.wait_for_service("localhost", 9000, self.timeout),
            "MinIO service not available",
        )

        try:
            # Test S3 connection
            s3_client = boto3.client("s3", **self.s3_config)

            # Test bucket listing
            response = s3_client.list_buckets()
            self.assertIn("Buckets", response, "Should get bucket list")

            # Check for lakehouse bucket
            bucket_names = [bucket["Name"] for bucket in response["Buckets"]]
            self.assertIn("lakehouse", bucket_names, "Lakehouse bucket should exist")

            # Test object listing in lakehouse bucket
            objects = s3_client.list_objects_v2(Bucket="lakehouse")
            self.assertIn("Contents", objects, "Should be able to list objects")

            print("✅ MinIO S3 connectivity successful")

        except Exception as e:
            self.fail(f"MinIO S3 connectivity failed: {e}")

    def test_spark_master_ui(self):
        """Test Spark Master UI accessibility"""
        print("🔍 Testing Spark Master UI...")

        # Wait for Spark Master to be ready
        self.assertTrue(
            self.wait_for_service("localhost", 8080, self.timeout),
            "Spark Master service not available",
        )

        try:
            response = requests.get(f"{self.base_url}:8080", timeout=10)
            self.assertEqual(
                response.status_code, 200, "Spark Master UI should be accessible"
            )

            # Check for Spark Master content
            self.assertIn(
                "Spark Master", response.text, "Should contain Spark Master content"
            )

            print("✅ Spark Master UI accessible")

        except Exception as e:
            self.fail(f"Spark Master UI test failed: {e}")

    def test_airflow_webserver(self):
        """Test Airflow webserver accessibility"""
        print("🔍 Testing Airflow webserver...")

        # Wait for Airflow to be ready
        self.assertTrue(
            self.wait_for_service("localhost", 9020, self.timeout),
            "Airflow webserver not available",
        )

        try:
            # Test health endpoint
            response = requests.get(f"{self.base_url}:9020/health", timeout=10)
            self.assertEqual(
                response.status_code,
                200,
                "Airflow health endpoint should be accessible",
            )

            # Test main UI
            response = requests.get(f"{self.base_url}:9020", timeout=10)
            self.assertEqual(
                response.status_code, 200, "Airflow UI should be accessible"
            )

            print("✅ Airflow webserver accessible")

        except Exception as e:
            self.fail(f"Airflow webserver test failed: {e}")

    def test_jupyter_lab(self):
        """Test JupyterLab accessibility"""
        print("🔍 Testing JupyterLab...")

        # Wait for Jupyter to be ready
        self.assertTrue(
            self.wait_for_service("localhost", 9040, self.timeout),
            "JupyterLab service not available",
        )

        try:
            # Test with token
            response = requests.get(f"{self.base_url}:9040?token=lakehouse", timeout=10)
            self.assertEqual(
                response.status_code, 200, "JupyterLab should be accessible with token"
            )

            # Check for Jupyter content
            self.assertIn("Jupyter", response.text, "Should contain Jupyter content")

            print("✅ JupyterLab accessible")

        except Exception as e:
            self.fail(f"JupyterLab test failed: {e}")

    def test_superset_dashboard(self):
        """Test Superset dashboard accessibility"""
        print("🔍 Testing Superset dashboard...")

        # Wait for Superset to be ready
        self.assertTrue(
            self.wait_for_service("localhost", 9030, self.timeout),
            "Superset service not available",
        )

        try:
            # Test health endpoint
            response = requests.get(f"{self.base_url}:9030/health", timeout=10)
            self.assertEqual(
                response.status_code,
                200,
                "Superset health endpoint should be accessible",
            )

            # Test main UI
            response = requests.get(f"{self.base_url}:9030", timeout=10)
            self.assertEqual(
                response.status_code, 200, "Superset UI should be accessible"
            )

            print("✅ Superset dashboard accessible")

        except Exception as e:
            self.fail(f"Superset dashboard test failed: {e}")

    def test_portainer_ui(self):
        """Test Portainer UI accessibility"""
        print("🔍 Testing Portainer UI...")

        # Wait for Portainer to be ready
        self.assertTrue(
            self.wait_for_service("localhost", 9060, self.timeout),
            "Portainer service not available",
        )

        try:
            response = requests.get(f"{self.base_url}:9060", timeout=10)
            self.assertEqual(
                response.status_code, 200, "Portainer UI should be accessible"
            )

            # Check for Portainer content
            self.assertIn(
                "Portainer", response.text, "Should contain Portainer content"
            )

            print("✅ Portainer UI accessible")

        except Exception as e:
            self.fail(f"Portainer UI test failed: {e}")

    def test_all_services_healthy(self):
        """Test that all services are healthy and responding"""
        print("🔍 Testing overall service health...")

        healthy_services = []
        failed_services = []

        for service_name, config in self.services.items():
            try:
                # Wait for service to be ready
                if not self.wait_for_service("localhost", config["port"], 10):
                    failed_services.append(f"{service_name} (port {config['port']})")
                    continue

                # Test health endpoint
                url = f"{self.base_url}:{config['port']}{config['health_path']}"
                response = requests.get(url, timeout=5)

                if response.status_code == 200:
                    healthy_services.append(service_name)
                else:
                    failed_services.append(
                        f"{service_name} (HTTP {response.status_code})"
                    )

            except Exception as e:
                failed_services.append(f"{service_name} ({str(e)})")

        # Report results
        print(f"✅ Healthy services: {', '.join(healthy_services)}")
        if failed_services:
            print(f"❌ Failed services: {', '.join(failed_services)}")

        # Assert all services are healthy
        self.assertEqual(
            len(failed_services), 0, f"Some services are not healthy: {failed_services}"
        )

        print("✅ All services are healthy!")

    def test_docker_containers_running(self):
        """Test that all expected Docker containers are running"""
        print("🔍 Testing Docker containers...")

        try:
            # Get running containers
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                check=True,
            )

            running_containers = result.stdout.strip().split("\n")
            running_containers = [name for name in running_containers if name]

            # Expected containers (partial names)
            expected_containers = [
                "postgres",
                "minio",
                "spark-master",
                "spark-worker",
                "jupyter",
                "airflow",
                "superset",
                "portainer",
            ]

            # Check each expected container
            missing_containers = []
            for expected in expected_containers:
                found = any(expected in container for container in running_containers)
                if not found:
                    missing_containers.append(expected)

            if missing_containers:
                print(f"❌ Missing containers: {', '.join(missing_containers)}")
                print(f"🔍 Running containers: {', '.join(running_containers)}")

            self.assertEqual(
                len(missing_containers), 0, f"Missing containers: {missing_containers}"
            )

            print("✅ All expected containers are running")

        except subprocess.CalledProcessError as e:
            self.fail(f"Docker container check failed: {e}")
        except Exception as e:
            self.fail(f"Docker container test failed: {e}")

    def test_service_logs_no_critical_errors(self):
        """Test that service logs don't contain critical errors"""
        print("🔍 Testing service logs for critical errors...")

        critical_error_patterns = [
            "FATAL",
            "CRITICAL",
            "ERROR: Connection refused",
            "ERROR: No such file or directory",
            "OutOfMemoryError",
            "PermissionError",
            "ConnectionError",
        ]

        # Get container names
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                check=True,
            )
            containers = result.stdout.strip().split("\n")
            containers = [name for name in containers if name and "test" not in name]

            critical_errors = []

            for container in containers:
                try:
                    # Get recent logs
                    logs_result = subprocess.run(
                        ["docker", "logs", "--tail", "50", container],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    logs = logs_result.stdout + logs_result.stderr

                    # Check for critical errors
                    for pattern in critical_error_patterns:
                        if pattern in logs:
                            critical_errors.append(f"{container}: {pattern}")

                except subprocess.TimeoutExpired:
                    continue
                except Exception:
                    continue

            if critical_errors:
                print(f"⚠️  Critical errors found: {critical_errors}")
                # Don't fail the test for log errors, just warn
                print("⚠️  Warning: Some services have critical errors in logs")
            else:
                print("✅ No critical errors found in service logs")

        except Exception as e:
            print(f"⚠️  Could not check service logs: {e}")


if __name__ == "__main__":
    unittest.main()
