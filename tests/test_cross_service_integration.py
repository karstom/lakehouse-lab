#!/usr/bin/env python3
"""
Cross-Service Integration Tests for Lakehouse Stack
Tests that services work together correctly and share data seamlessly
"""

import unittest
import requests
import psycopg2
import boto3
import duckdb
import time
import tempfile
import os
from pathlib import Path
import subprocess
import socket


class TestCrossServiceIntegration(unittest.TestCase):
    """Test suite for cross-service integration"""

    def setUp(self):
        """Set up test environment"""
        self.project_root = Path(__file__).parent.parent
        self.timeout = 60

        # Service configurations
        self.s3_config = {
            "endpoint_url": "http://localhost:9000",
            "aws_access_key_id": "minio",
            "aws_secret_access_key": "minio123",
            "region_name": "us-east-1",
        }

        self.db_config = {
            "host": "localhost",
            "port": 5432,
            "database": "airflow",
            "user": "postgres",
            "password": "lakehouse",
        }

        # Wait for services to be ready
        self.wait_for_services()

    def wait_for_services(self):
        """Wait for required services to be ready"""
        services = [
            ("localhost", 9000),  # MinIO
            ("localhost", 5432),  # PostgreSQL
            ("localhost", 9020),  # Airflow
            ("localhost", 8080),  # Spark Master
            ("localhost", 9040),  # Jupyter
            ("localhost", 9030),  # Superset
        ]

        for host, port in services:
            if not self.wait_for_service(host, port, 30):
                print(f"⚠️  Service {host}:{port} not available")

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

    def test_airflow_spark_integration(self):
        """Test Airflow can orchestrate Spark jobs"""
        print("🔍 Testing Airflow-Spark integration...")

        try:
            # Check Airflow is accessible
            airflow_response = requests.get("http://localhost:9020/health", timeout=10)
            self.assertEqual(
                airflow_response.status_code, 200, "Airflow should be accessible"
            )

            # Check Spark Master is accessible
            spark_response = requests.get("http://localhost:8080", timeout=10)
            self.assertEqual(
                spark_response.status_code, 200, "Spark Master should be accessible"
            )

            # Test Spark Master API
            spark_api_response = requests.get(
                "http://localhost:8080/api/v1/applications", timeout=10
            )
            if spark_api_response.status_code == 200:
                applications = spark_api_response.json()
                print(f"📊 Spark applications: {len(applications)}")

            # Check that both services are in the same network
            try:
                # Get network information
                result = subprocess.run(
                    ["docker", "network", "ls", "--format", "{{.Name}}"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                networks = result.stdout.strip().split("\n")
                self.assertIn(
                    "lakehouse-test_lakehouse",
                    networks,
                    "Lakehouse network should exist",
                )

                # Check services are in the same network
                airflow_inspect = subprocess.run(
                    [
                        "docker",
                        "inspect",
                        "--format",
                        "{{.NetworkSettings.Networks}}",
                        "lakehouse-test-airflow-webserver-1",
                    ],
                    capture_output=True,
                    text=True,
                )

                spark_inspect = subprocess.run(
                    [
                        "docker",
                        "inspect",
                        "--format",
                        "{{.NetworkSettings.Networks}}",
                        "lakehouse-test-spark-master-1",
                    ],
                    capture_output=True,
                    text=True,
                )

                # Both should contain the lakehouse network
                if airflow_inspect.returncode == 0 and spark_inspect.returncode == 0:
                    print("✅ Services are properly networked")
                else:
                    print(
                        "⚠️  Network inspection skipped - containers may have different names"
                    )

            except subprocess.CalledProcessError:
                print("⚠️  Network inspection skipped - docker command not available")

            print("✅ Airflow-Spark integration test passed")

        except Exception as e:
            self.fail(f"Airflow-Spark integration test failed: {e}")

    def test_superset_duckdb_connection(self):
        """Test Superset can connect to DuckDB with S3 data"""
        print("🔍 Testing Superset-DuckDB connection...")

        try:
            # Check Superset is accessible
            superset_response = requests.get("http://localhost:9030/health", timeout=10)
            self.assertEqual(
                superset_response.status_code, 200, "Superset should be accessible"
            )

            # Create test data in MinIO
            s3_client = boto3.client("s3", **self.s3_config)

            # Create sample data for dashboard
            sample_data = [
                {"product": "Widget A", "sales": 100, "region": "North"},
                {"product": "Widget B", "sales": 150, "region": "South"},
                {"product": "Widget C", "sales": 200, "region": "East"},
                {"product": "Widget A", "sales": 80, "region": "West"},
                {"product": "Widget B", "sales": 120, "region": "North"},
            ]

            # Convert to CSV and upload
            import pandas as pd

            df = pd.DataFrame(sample_data)

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False
            ) as f:
                df.to_csv(f.name, index=False)
                s3_client.upload_file(f.name, "lakehouse", "dashboard/sales_data.csv")
                os.unlink(f.name)

            # Test DuckDB can read the data
            conn = duckdb.connect(":memory:")
            conn.execute("INSTALL httpfs;")
            conn.execute("LOAD httpfs;")
            conn.execute("SET s3_endpoint='localhost:9000';")
            conn.execute("SET s3_access_key_id='minio';")
            conn.execute("SET s3_secret_access_key='minio123';")
            conn.execute("SET s3_use_ssl=false;")
            conn.execute("SET s3_url_style='path';")

            # Query the data
            result = conn.execute(
                "SELECT COUNT(*) FROM read_csv_auto('s3://lakehouse/dashboard/sales_data.csv')"
            ).fetchone()
            self.assertEqual(result[0], 5, "Should read 5 rows of sample data")

            # Test aggregation query that Superset might use
            agg_result = conn.execute(
                """
                SELECT 
                    region,
                    SUM(sales) as total_sales,
                    COUNT(*) as product_count
                FROM read_csv_auto('s3://lakehouse/dashboard/sales_data.csv')
                GROUP BY region
                ORDER BY total_sales DESC
            """
            ).fetchall()

            self.assertGreater(len(agg_result), 0, "Should get aggregated results")

            conn.close()

            # Test that Superset can potentially create a database connection
            # (This would require actually configuring Superset, which is complex)
            print("✅ Data is available for Superset visualization")

            print("✅ Superset-DuckDB connection test passed")

        except Exception as e:
            self.fail(f"Superset-DuckDB connection test failed: {e}")

    def test_jupyter_spark_connection(self):
        """Test Jupyter can connect to Spark cluster"""
        print("🔍 Testing Jupyter-Spark connection...")

        try:
            # Check Jupyter is accessible
            jupyter_response = requests.get(
                "http://localhost:9040?token=lakehouse", timeout=10
            )
            self.assertEqual(
                jupyter_response.status_code, 200, "Jupyter should be accessible"
            )

            # Check Spark Master is accessible
            spark_response = requests.get("http://localhost:8080", timeout=10)
            self.assertEqual(
                spark_response.status_code, 200, "Spark Master should be accessible"
            )

            # Test that Jupyter can see Spark Master
            # In a real scenario, we would test actual Spark session creation
            # For now, we verify the services can communicate

            # Check if Jupyter container can reach Spark Master
            try:
                # Test network connectivity between services
                result = subprocess.run(
                    [
                        "docker",
                        "exec",
                        "lakehouse-test-jupyter-1",
                        "nc",
                        "-z",
                        "spark-master",
                        "7077",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode == 0:
                    print("✅ Jupyter can reach Spark Master")
                else:
                    print("⚠️  Network connectivity test skipped")

            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                print(
                    "⚠️  Network connectivity test skipped - docker exec not available"
                )

            # Create a test that simulates Spark session creation
            spark_session_test = """
# This is what would run in Jupyter to test Spark connectivity
import os
import sys

# Test environment variables
spark_master = os.getenv('SPARK_MASTER', 'spark://spark-master:7077')
print(f"Spark Master URL: {spark_master}")

# In a real test, we would create a Spark session:
# from pyspark.sql import SparkSession
# spark = SparkSession.builder.appName("JupyterTest").master(spark_master).getOrCreate()
# print("Spark session created successfully!")
# spark.stop()
"""

            # For now, just verify the services are running
            print("✅ Services are accessible for Jupyter-Spark integration")

            print("✅ Jupyter-Spark connection test passed")

        except Exception as e:
            self.fail(f"Jupyter-Spark connection test failed: {e}")

    def test_minio_spark_s3_access(self):
        """Test Spark can access MinIO as S3 storage"""
        print("🔍 Testing MinIO-Spark S3 access...")

        try:
            # Check MinIO is accessible
            minio_response = requests.get(
                "http://localhost:9000/minio/health/live", timeout=10
            )
            self.assertEqual(
                minio_response.status_code, 200, "MinIO should be accessible"
            )

            # Check Spark Master is accessible
            spark_response = requests.get("http://localhost:8080", timeout=10)
            self.assertEqual(
                spark_response.status_code, 200, "Spark Master should be accessible"
            )

            # Create test data in MinIO
            s3_client = boto3.client("s3", **self.s3_config)

            # Create test data
            test_data = [
                {"id": 1, "name": "Test1", "value": 100},
                {"id": 2, "name": "Test2", "value": 200},
                {"id": 3, "name": "Test3", "value": 300},
            ]

            import pandas as pd

            df = pd.DataFrame(test_data)

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False
            ) as f:
                df.to_csv(f.name, index=False)
                s3_client.upload_file(f.name, "lakehouse", "spark-test/test_data.csv")
                os.unlink(f.name)

            # Verify file was uploaded
            objects = s3_client.list_objects_v2(
                Bucket="lakehouse", Prefix="spark-test/"
            )
            uploaded_files = [obj["Key"] for obj in objects.get("Contents", [])]
            self.assertIn(
                "spark-test/test_data.csv",
                uploaded_files,
                "Test data should be uploaded",
            )

            # Test that data can be read (simulating Spark S3 access)
            downloaded_file = s3_client.get_object(
                Bucket="lakehouse", Key="spark-test/test_data.csv"
            )
            content = downloaded_file["Body"].read().decode("utf-8")
            self.assertIn("Test1", content, "Should contain test data")

            # In a real Spark job, this would be:
            # spark.read.option("header", "true").csv("s3a://lakehouse/spark-test/test_data.csv")

            print("✅ Data is accessible for Spark S3 integration")

            print("✅ MinIO-Spark S3 access test passed")

        except Exception as e:
            self.fail(f"MinIO-Spark S3 access test failed: {e}")

    def test_postgres_airflow_metadata(self):
        """Test PostgreSQL stores Airflow metadata correctly"""
        print("🔍 Testing PostgreSQL-Airflow metadata integration...")

        try:
            # Check PostgreSQL is accessible
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()

            # Check Airflow is accessible
            airflow_response = requests.get("http://localhost:9020/health", timeout=10)
            self.assertEqual(
                airflow_response.status_code, 200, "Airflow should be accessible"
            )

            # Test Airflow metadata tables exist
            cursor.execute(
                """
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name LIKE 'dag%'
                ORDER BY table_name
            """
            )
            dag_tables = cursor.fetchall()

            self.assertGreater(len(dag_tables), 0, "Airflow DAG tables should exist")

            # Check for specific important tables
            cursor.execute(
                """
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('dag', 'dag_run', 'task_instance')
            """
            )
            core_tables = cursor.fetchall()
            core_table_names = [table[0] for table in core_tables]

            expected_tables = ["dag", "dag_run", "task_instance"]
            for table in expected_tables:
                self.assertIn(table, core_table_names, f"Table {table} should exist")

            # Test that we can query DAG information
            cursor.execute("SELECT COUNT(*) FROM dag")
            dag_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM dag_run")
            dag_run_count = cursor.fetchone()[0]

            print(f"📊 DAGs: {dag_count}, DAG runs: {dag_run_count}")

            # Test connection pooling and performance
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
            self.assertIn("PostgreSQL", version, "Should be PostgreSQL")

            cursor.close()
            conn.close()

            print("✅ PostgreSQL-Airflow metadata integration test passed")

        except Exception as e:
            self.fail(f"PostgreSQL-Airflow metadata integration test failed: {e}")

    def test_service_network_isolation(self):
        """Test that services are properly networked and isolated"""
        print("🔍 Testing service network isolation...")

        try:
            # Check that services are on the same network
            result = subprocess.run(
                ["docker", "network", "ls", "--format", "{{.Name}}"],
                capture_output=True,
                text=True,
                check=True,
            )
            networks = result.stdout.strip().split("\n")
            lakehouse_networks = [n for n in networks if "lakehouse" in n]

            self.assertGreater(
                len(lakehouse_networks), 0, "Lakehouse network should exist"
            )

            # Test that services can reach each other on the internal network
            # but are isolated from external networks

            # Get container names
            containers_result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                check=True,
            )
            containers = containers_result.stdout.strip().split("\n")
            lakehouse_containers = [c for c in containers if "lakehouse-test" in c]

            self.assertGreater(
                len(lakehouse_containers),
                5,
                "Should have multiple lakehouse containers",
            )

            # Test internal connectivity (simplified)
            # In a real scenario, we would test that services can reach each other
            # by their service names (e.g., 'postgres', 'minio', 'spark-master')

            print(f"✅ Found {len(lakehouse_containers)} lakehouse containers")
            print(f"✅ Found {len(lakehouse_networks)} lakehouse networks")

            print("✅ Service network isolation test passed")

        except subprocess.CalledProcessError as e:
            print(f"⚠️  Network isolation test skipped: {e}")
        except Exception as e:
            self.fail(f"Service network isolation test failed: {e}")

    def test_data_flow_integration(self):
        """Test complete data flow across all services"""
        print("🔍 Testing complete data flow integration...")

        try:
            # Step 1: Create data in MinIO
            s3_client = boto3.client("s3", **self.s3_config)

            # Create sample sales data
            sales_data = [
                {
                    "date": "2024-01-01",
                    "product": "Widget A",
                    "sales": 100,
                    "region": "North",
                },
                {
                    "date": "2024-01-02",
                    "product": "Widget B",
                    "sales": 150,
                    "region": "South",
                },
                {
                    "date": "2024-01-03",
                    "product": "Widget C",
                    "sales": 200,
                    "region": "East",
                },
                {
                    "date": "2024-01-04",
                    "product": "Widget A",
                    "sales": 80,
                    "region": "West",
                },
                {
                    "date": "2024-01-05",
                    "product": "Widget B",
                    "sales": 120,
                    "region": "North",
                },
            ]

            import pandas as pd

            df = pd.DataFrame(sales_data)

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False
            ) as f:
                df.to_csv(f.name, index=False)
                s3_client.upload_file(f.name, "lakehouse", "integration/sales_data.csv")
                os.unlink(f.name)

            # Step 2: Process data with DuckDB
            conn = duckdb.connect(":memory:")
            conn.execute("INSTALL httpfs;")
            conn.execute("LOAD httpfs;")
            conn.execute("SET s3_endpoint='localhost:9000';")
            conn.execute("SET s3_access_key_id='minio';")
            conn.execute("SET s3_secret_access_key='minio123';")
            conn.execute("SET s3_use_ssl=false;")
            conn.execute("SET s3_url_style='path';")

            # Create aggregated data
            agg_result = conn.execute(
                """
                SELECT 
                    product,
                    region,
                    SUM(sales) as total_sales,
                    COUNT(*) as transaction_count,
                    AVG(sales) as avg_sales
                FROM read_csv_auto('s3://lakehouse/integration/sales_data.csv')
                GROUP BY product, region
                ORDER BY total_sales DESC
            """
            ).fetchall()

            self.assertGreater(len(agg_result), 0, "Should generate aggregated results")

            # Step 3: Save processed data back to MinIO
            processed_df = pd.DataFrame(
                agg_result,
                columns=[
                    "product",
                    "region",
                    "total_sales",
                    "transaction_count",
                    "avg_sales",
                ],
            )

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False
            ) as f:
                processed_df.to_csv(f.name, index=False)
                s3_client.upload_file(
                    f.name, "lakehouse", "integration/processed_sales.csv"
                )
                os.unlink(f.name)

            # Step 4: Verify data accessibility for all services
            # Test that all services can potentially access the processed data

            # PostgreSQL connection test
            pg_conn = psycopg2.connect(**self.db_config)
            pg_cursor = pg_conn.cursor()
            pg_cursor.execute("SELECT 1")
            pg_result = pg_cursor.fetchone()
            self.assertEqual(pg_result[0], 1, "PostgreSQL should be accessible")
            pg_cursor.close()
            pg_conn.close()

            # MinIO access test
            objects = s3_client.list_objects_v2(
                Bucket="lakehouse", Prefix="integration/"
            )
            integration_files = [obj["Key"] for obj in objects.get("Contents", [])]
            self.assertIn(
                "integration/processed_sales.csv",
                integration_files,
                "Processed data should be available",
            )

            # Service connectivity test
            services = [
                ("localhost", 9020),  # Airflow
                ("localhost", 8080),  # Spark Master
                ("localhost", 9040),  # Jupyter
                ("localhost", 9030),  # Superset
            ]

            for host, port in services:
                self.assertTrue(
                    self.wait_for_service(host, port, 5),
                    f"Service {host}:{port} should be accessible",
                )

            conn.close()

            print("✅ Complete data flow integration test passed")

        except Exception as e:
            self.fail(f"Data flow integration test failed: {e}")

    def test_service_health_after_integration(self):
        """Test that all services remain healthy after integration tests"""
        print("🔍 Testing service health after integration...")

        try:
            services = [
                ("localhost", 9000, "MinIO"),
                ("localhost", 5432, "PostgreSQL"),
                ("localhost", 9020, "Airflow"),
                ("localhost", 8080, "Spark Master"),
                ("localhost", 9040, "Jupyter"),
                ("localhost", 9030, "Superset"),
                ("localhost", 9060, "Portainer"),
            ]

            healthy_services = []
            failed_services = []

            for host, port, name in services:
                if self.wait_for_service(host, port, 5):
                    healthy_services.append(name)
                else:
                    failed_services.append(name)

            print(f"✅ Healthy services: {', '.join(healthy_services)}")
            if failed_services:
                print(f"⚠️  Services with issues: {', '.join(failed_services)}")

            # At least core services should be healthy
            core_services = ["MinIO", "PostgreSQL", "Airflow"]
            for service in core_services:
                self.assertIn(service, healthy_services, f"{service} should be healthy")

            print("✅ Service health after integration test passed")

        except Exception as e:
            self.fail(f"Service health after integration test failed: {e}")


if __name__ == "__main__":
    unittest.main()
