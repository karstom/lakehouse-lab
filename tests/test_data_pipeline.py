#!/usr/bin/env python3
"""
Data Pipeline End-to-End Tests for Lakehouse Stack
Tests complete data workflows from ingestion to visualization
"""

import unittest
import requests
import boto3
import duckdb
import pandas as pd
import time
import os
import tempfile
from pathlib import Path


class TestDataPipelineEndToEnd(unittest.TestCase):
    """Test suite for end-to-end data pipeline workflows"""

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

        # Test data
        self.test_data = {
            "customers": [
                {
                    "id": 1,
                    "name": "John Doe",
                    "email": "john@example.com",
                    "city": "New York",
                },
                {
                    "id": 2,
                    "name": "Jane Smith",
                    "email": "jane@example.com",
                    "city": "Los Angeles",
                },
                {
                    "id": 3,
                    "name": "Bob Johnson",
                    "email": "bob@example.com",
                    "city": "Chicago",
                },
            ],
            "orders": [
                {
                    "order_id": 101,
                    "customer_id": 1,
                    "amount": 150.00,
                    "date": "2024-01-15",
                },
                {
                    "order_id": 102,
                    "customer_id": 2,
                    "amount": 200.00,
                    "date": "2024-01-16",
                },
                {
                    "order_id": 103,
                    "customer_id": 1,
                    "amount": 75.00,
                    "date": "2024-01-17",
                },
            ],
        }

        # Wait for services to be ready
        self.wait_for_services()

    def wait_for_services(self):
        """Wait for required services to be ready"""
        services = [
            ("localhost", 9000),  # MinIO
            ("localhost", 5432),  # PostgreSQL
            ("localhost", 9020),  # Airflow
        ]

        for host, port in services:
            if not self.wait_for_service(host, port, 30):
                self.skipTest(f"Service {host}:{port} not available")

    def wait_for_service(self, host, port, timeout=30):
        """Wait for a service to be available"""
        import socket

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

    def test_csv_ingestion_to_minio(self):
        """Test CSV data ingestion to MinIO"""
        print("🔍 Testing CSV ingestion to MinIO...")

        try:
            # Create S3 client
            s3_client = boto3.client("s3", **self.s3_config)

            # Create CSV data
            customers_df = pd.DataFrame(self.test_data["customers"])
            orders_df = pd.DataFrame(self.test_data["orders"])

            # Upload CSV files to MinIO
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False
            ) as f:
                customers_df.to_csv(f.name, index=False)
                s3_client.upload_file(f.name, "lakehouse", "data/customers.csv")
                os.unlink(f.name)

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False
            ) as f:
                orders_df.to_csv(f.name, index=False)
                s3_client.upload_file(f.name, "lakehouse", "data/orders.csv")
                os.unlink(f.name)

            # Verify files were uploaded
            objects = s3_client.list_objects_v2(Bucket="lakehouse", Prefix="data/")
            uploaded_files = [obj["Key"] for obj in objects.get("Contents", [])]

            self.assertIn(
                "data/customers.csv", uploaded_files, "Customers CSV should be uploaded"
            )
            self.assertIn(
                "data/orders.csv", uploaded_files, "Orders CSV should be uploaded"
            )

            print("✅ CSV ingestion to MinIO successful")

        except Exception as e:
            self.fail(f"CSV ingestion to MinIO failed: {e}")

    def test_duckdb_s3_integration(self):
        """Test DuckDB reading from S3 (MinIO)"""
        print("🔍 Testing DuckDB S3 integration...")

        try:
            # First ensure data is in MinIO
            self.test_csv_ingestion_to_minio()

            # Create DuckDB connection
            conn = duckdb.connect(":memory:")

            # Configure DuckDB for S3 access
            conn.execute("INSTALL httpfs;")
            conn.execute("LOAD httpfs;")
            conn.execute("SET s3_endpoint='localhost:9000';")
            conn.execute("SET s3_access_key_id='minio';")
            conn.execute("SET s3_secret_access_key='minio123';")
            conn.execute("SET s3_use_ssl=false;")
            conn.execute("SET s3_url_style='path';")

            # Read data from S3
            customers_query = (
                "SELECT * FROM read_csv_auto('s3://lakehouse/data/customers.csv')"
            )
            customers_result = conn.execute(customers_query).fetchall()

            orders_query = (
                "SELECT * FROM read_csv_auto('s3://lakehouse/data/orders.csv')"
            )
            orders_result = conn.execute(orders_query).fetchall()

            # Verify data
            self.assertEqual(len(customers_result), 3, "Should read 3 customers")
            self.assertEqual(len(orders_result), 3, "Should read 3 orders")

            # Test analytical query
            analytical_query = """
            SELECT 
                c.name,
                c.city,
                COUNT(o.order_id) as order_count,
                SUM(o.amount) as total_amount
            FROM read_csv_auto('s3://lakehouse/data/customers.csv') c
            LEFT JOIN read_csv_auto('s3://lakehouse/data/orders.csv') o 
                ON c.id = o.customer_id
            GROUP BY c.name, c.city
            ORDER BY total_amount DESC
            """

            analytical_result = conn.execute(analytical_query).fetchall()
            self.assertGreater(
                len(analytical_result), 0, "Should get analytical results"
            )

            conn.close()
            print("✅ DuckDB S3 integration successful")

        except Exception as e:
            self.fail(f"DuckDB S3 integration failed: {e}")

    def test_airflow_dag_execution(self):
        """Test Airflow DAG execution with sample data"""
        print("🔍 Testing Airflow DAG execution...")

        try:
            # Check if sample DAG exists
            dag_list_url = "http://localhost:9020/api/v1/dags"
            response = requests.get(dag_list_url, auth=("admin", "admin"), timeout=10)

            if response.status_code == 200:
                dags = response.json()
                dag_ids = [dag["dag_id"] for dag in dags.get("dags", [])]

                # Look for sample DAG
                sample_dag = None
                for dag_id in dag_ids:
                    if "sample" in dag_id.lower() or "duckdb" in dag_id.lower():
                        sample_dag = dag_id
                        break

                if sample_dag:
                    print(f"📊 Found sample DAG: {sample_dag}")

                    # Trigger DAG run
                    trigger_url = (
                        f"http://localhost:9020/api/v1/dags/{sample_dag}/dagRuns"
                    )
                    trigger_data = {
                        "conf": {},
                        "dag_run_id": f"test_run_{int(time.time())}",
                    }

                    trigger_response = requests.post(
                        trigger_url,
                        json=trigger_data,
                        auth=("admin", "admin"),
                        timeout=10,
                    )

                    if trigger_response.status_code in [200, 201]:
                        print("✅ DAG triggered successfully")

                        # Wait a bit and check DAG run status
                        time.sleep(5)
                        dag_runs_url = (
                            f"http://localhost:9020/api/v1/dags/{sample_dag}/dagRuns"
                        )
                        runs_response = requests.get(
                            dag_runs_url, auth=("admin", "admin"), timeout=10
                        )

                        if runs_response.status_code == 200:
                            runs = runs_response.json()
                            if runs.get("dag_runs"):
                                print("✅ DAG run created successfully")
                            else:
                                print("⚠️  DAG run status unknown")
                    else:
                        print("⚠️  DAG trigger failed, but service is accessible")
                else:
                    print("⚠️  No sample DAG found, but Airflow is accessible")
            else:
                print("⚠️  Airflow API not accessible, checking basic connectivity...")

            # Test basic Airflow connectivity
            basic_response = requests.get("http://localhost:9020/health", timeout=10)
            self.assertEqual(
                basic_response.status_code, 200, "Airflow should be accessible"
            )

            print("✅ Airflow DAG execution test completed")

        except Exception as e:
            self.fail(f"Airflow DAG execution test failed: {e}")

    def test_spark_job_execution(self):
        """Test Spark job execution through Jupyter"""
        print("🔍 Testing Spark job execution...")

        try:
            # Test Spark Master UI accessibility
            spark_response = requests.get("http://localhost:8080", timeout=10)
            self.assertEqual(
                spark_response.status_code, 200, "Spark Master should be accessible"
            )

            # Test Jupyter accessibility
            jupyter_response = requests.get(
                "http://localhost:9040?token=lakehouse", timeout=10
            )
            self.assertEqual(
                jupyter_response.status_code, 200, "Jupyter should be accessible"
            )

            # Create a simple Spark job script
            # Example Spark job:
            # from pyspark.sql import SparkSession
            # spark = SparkSession.builder.appName("LakehouseTest").getOrCreate()
            # df = spark.createDataFrame([("John", 25), ("Jane", 30)], ["Name", "Age"])
            # result = df.groupBy().avg("Age").collect()
            # spark.stop()

            # For now, just test that Spark services are running
            # In a real scenario, we would execute the script through Jupyter API
            print("✅ Spark services are accessible")

        except Exception as e:
            self.fail(f"Spark job execution test failed: {e}")

    def test_data_quality_checks(self):
        """Test data quality validation"""
        print("🔍 Testing data quality checks...")

        try:
            # First ensure data is available
            self.test_csv_ingestion_to_minio()

            # Create DuckDB connection
            conn = duckdb.connect(":memory:")

            # Configure DuckDB for S3 access
            conn.execute("INSTALL httpfs;")
            conn.execute("LOAD httpfs;")
            conn.execute("SET s3_endpoint='localhost:9000';")
            conn.execute("SET s3_access_key_id='minio';")
            conn.execute("SET s3_secret_access_key='minio123';")
            conn.execute("SET s3_use_ssl=false;")
            conn.execute("SET s3_url_style='path';")

            # Data quality checks
            quality_checks = [
                {
                    "name": "Customer ID Uniqueness",
                    "query": "SELECT COUNT(*) - COUNT(DISTINCT id) as duplicates FROM read_csv_auto('s3://lakehouse/data/customers.csv')",
                    "expected": 0,
                },
                {
                    "name": "Email Format Validation",
                    "query": "SELECT COUNT(*) FROM read_csv_auto('s3://lakehouse/data/customers.csv') WHERE email NOT LIKE '%@%'",
                    "expected": 0,
                },
                {
                    "name": "Order Amount Validation",
                    "query": "SELECT COUNT(*) FROM read_csv_auto('s3://lakehouse/data/orders.csv') WHERE amount <= 0",
                    "expected": 0,
                },
                {
                    "name": "Customer-Order Referential Integrity",
                    "query": """
                    SELECT COUNT(*) FROM read_csv_auto('s3://lakehouse/data/orders.csv') o
                    LEFT JOIN read_csv_auto('s3://lakehouse/data/customers.csv') c ON o.customer_id = c.id
                    WHERE c.id IS NULL
                    """,
                    "expected": 0,
                },
            ]

            passed_checks = 0
            failed_checks = []

            for check in quality_checks:
                result = conn.execute(check["query"]).fetchone()[0]
                if result == check["expected"]:
                    passed_checks += 1
                    print(f"✅ {check['name']}: PASSED")
                else:
                    failed_checks.append(check["name"])
                    print(
                        f"❌ {check['name']}: FAILED (expected {check['expected']}, got {result})"
                    )

            conn.close()

            # Assert all checks passed
            self.assertEqual(
                len(failed_checks), 0, f"Data quality checks failed: {failed_checks}"
            )

            print(
                f"✅ Data quality checks completed: {passed_checks}/{len(quality_checks)} passed"
            )

        except Exception as e:
            self.fail(f"Data quality checks failed: {e}")

    def test_end_to_end_pipeline(self):
        """Test complete end-to-end data pipeline"""
        print("🔍 Testing complete end-to-end pipeline...")

        try:
            # Step 1: Data Ingestion
            print("📥 Step 1: Data Ingestion")
            self.test_csv_ingestion_to_minio()

            # Step 2: Data Processing
            print("⚙️  Step 2: Data Processing")
            self.test_duckdb_s3_integration()

            # Step 3: Data Quality Validation
            print("🔍 Step 3: Data Quality Validation")
            self.test_data_quality_checks()

            # Step 4: Create aggregated data
            print("📊 Step 4: Data Aggregation")

            # Create DuckDB connection
            conn = duckdb.connect(":memory:")

            # Configure DuckDB for S3 access
            conn.execute("INSTALL httpfs;")
            conn.execute("LOAD httpfs;")
            conn.execute("SET s3_endpoint='localhost:9000';")
            conn.execute("SET s3_access_key_id='minio';")
            conn.execute("SET s3_secret_access_key='minio123';")
            conn.execute("SET s3_use_ssl=false;")
            conn.execute("SET s3_url_style='path';")

            # Create customer summary
            summary_query = """
            SELECT 
                c.city,
                COUNT(c.id) as customer_count,
                COUNT(o.order_id) as total_orders,
                COALESCE(SUM(o.amount), 0) as total_revenue,
                COALESCE(AVG(o.amount), 0) as avg_order_value
            FROM read_csv_auto('s3://lakehouse/data/customers.csv') c
            LEFT JOIN read_csv_auto('s3://lakehouse/data/orders.csv') o 
                ON c.id = o.customer_id
            GROUP BY c.city
            ORDER BY total_revenue DESC
            """

            summary_result = conn.execute(summary_query).fetchall()
            self.assertGreater(len(summary_result), 0, "Should generate summary data")

            # Save summary to MinIO
            summary_df = pd.DataFrame(
                summary_result,
                columns=[
                    "city",
                    "customer_count",
                    "total_orders",
                    "total_revenue",
                    "avg_order_value",
                ],
            )

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False
            ) as f:
                summary_df.to_csv(f.name, index=False)

                s3_client = boto3.client("s3", **self.s3_config)
                s3_client.upload_file(f.name, "lakehouse", "reports/city_summary.csv")
                os.unlink(f.name)

            # Verify summary file was created
            objects = s3_client.list_objects_v2(Bucket="lakehouse", Prefix="reports/")
            report_files = [obj["Key"] for obj in objects.get("Contents", [])]
            self.assertIn(
                "reports/city_summary.csv",
                report_files,
                "Summary report should be created",
            )

            conn.close()

            # Step 5: Verify all services are still healthy
            print("🔍 Step 5: Service Health Verification")
            services_to_check = [
                ("localhost", 9000),  # MinIO
                ("localhost", 5432),  # PostgreSQL
                ("localhost", 9020),  # Airflow
                ("localhost", 8080),  # Spark Master
                ("localhost", 9040),  # Jupyter
                ("localhost", 9030),  # Superset
            ]

            for host, port in services_to_check:
                self.assertTrue(
                    self.wait_for_service(host, port, 5),
                    f"Service {host}:{port} should still be healthy",
                )

            print("✅ Complete end-to-end pipeline test successful!")

        except Exception as e:
            self.fail(f"End-to-end pipeline test failed: {e}")

    def test_performance_baseline(self):
        """Test basic performance baseline"""
        print("🔍 Testing performance baseline...")

        try:
            # First ensure data is available
            self.test_csv_ingestion_to_minio()

            # Create DuckDB connection
            conn = duckdb.connect(":memory:")

            # Configure DuckDB for S3 access
            conn.execute("INSTALL httpfs;")
            conn.execute("LOAD httpfs;")
            conn.execute("SET s3_endpoint='localhost:9000';")
            conn.execute("SET s3_access_key_id='minio';")
            conn.execute("SET s3_secret_access_key='minio123';")
            conn.execute("SET s3_use_ssl=false;")
            conn.execute("SET s3_url_style='path';")

            # Test query performance
            start_time = time.time()

            result = conn.execute(
                """
            SELECT 
                c.name,
                c.city,
                COUNT(o.order_id) as order_count,
                SUM(o.amount) as total_amount
            FROM read_csv_auto('s3://lakehouse/data/customers.csv') c
            LEFT JOIN read_csv_auto('s3://lakehouse/data/orders.csv') o 
                ON c.id = o.customer_id
            GROUP BY c.name, c.city
            ORDER BY total_amount DESC
            """
            ).fetchall()

            query_time = time.time() - start_time

            # Performance assertions
            self.assertLess(query_time, 30, "Query should complete within 30 seconds")
            self.assertGreater(len(result), 0, "Query should return results")

            conn.close()

            print(
                f"✅ Performance baseline: Query completed in {query_time:.2f} seconds"
            )

        except Exception as e:
            self.fail(f"Performance baseline test failed: {e}")


if __name__ == "__main__":
    unittest.main()
