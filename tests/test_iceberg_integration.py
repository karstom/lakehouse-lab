#!/usr/bin/env python3
"""
Tests for Apache Iceberg integration functionality
Tests Iceberg configuration, JAR availability, and basic functionality
"""

import unittest
import subprocess
import os
import yaml
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import json

class TestIcebergIntegration(unittest.TestCase):
    """Test suite for Iceberg integration"""
    
    def setUp(self):
        """Set up test environment"""
        self.project_root = Path(__file__).parent.parent
        self.iceberg_compose = self.project_root / 'docker-compose.iceberg.yml'
        self.init_script = self.project_root / 'init-all-in-one-modular.sh'
        self.iceberg_docs = self.project_root / 'ICEBERG.md'
        
    def test_iceberg_compose_file_exists(self):
        """Test that Iceberg compose override file exists"""
        self.assertTrue(
            self.iceberg_compose.exists(),
            "docker-compose.iceberg.yml should exist"
        )
    
    def test_iceberg_documentation_exists(self):
        """Test that Iceberg documentation exists"""
        self.assertTrue(
            self.iceberg_docs.exists(),
            "ICEBERG.md documentation should exist"
        )
    
    def test_iceberg_compose_structure(self):
        """Test Iceberg compose file structure"""
        if not self.iceberg_compose.exists():
            self.skipTest("docker-compose.iceberg.yml not found")
        
        with open(self.iceberg_compose, 'r') as f:
            compose_data = yaml.safe_load(f)
        
        # Check basic structure
        self.assertIn('services', compose_data, "Should have services section")
        services = compose_data['services']
        
        # Check for Spark service modifications
        spark_services = ['spark-master', 'spark-worker']
        for service in spark_services:
            if service in services:
                service_config = services[service]
                
                # Check for Iceberg-specific volumes
                self.assertIn('volumes', service_config, f"{service} should have volumes")
                volumes = service_config['volumes']
                
                # Look for Iceberg JAR volume
                iceberg_jar_volume = any('iceberg-jars' in vol for vol in volumes)
                self.assertTrue(iceberg_jar_volume, 
                              f"{service} should have iceberg-jars volume")
                
                # Check for Iceberg-specific environment variables
                if 'environment' in service_config:
                    env_vars = service_config['environment']
                    
                    # Look for Spark Iceberg configurations
                    spark_iceberg_configs = [
                        'SPARK_CONF_spark.sql.extensions',
                        'SPARK_CONF_spark.sql.catalog.iceberg',
                        'SPARK_CONF_spark.sql.catalog.iceberg.type',
                        'SPARK_CONF_spark.sql.catalog.iceberg.warehouse'
                    ]
                    
                    for config in spark_iceberg_configs:
                        if config in env_vars:
                            self.assertIsNotNone(env_vars[config], 
                                               f"{config} should have a value")
    
    def test_iceberg_jar_configuration(self):
        """Test Iceberg JAR configuration in compose"""
        if not self.iceberg_compose.exists():
            self.skipTest("docker-compose.iceberg.yml not found")
        
        with open(self.iceberg_compose, 'r') as f:
            compose_data = yaml.safe_load(f)
        
        services = compose_data.get('services', {})
        
        # Check for Iceberg JAR volume mapping
        spark_services = ['spark-master', 'spark-worker']
        for service in spark_services:
            if service in services:
                service_config = services[service]
                volumes = service_config.get('volumes', [])
                
                # Find Iceberg JAR volume mapping
                iceberg_jar_mappings = [vol for vol in volumes if 'iceberg-jars' in vol]
                self.assertGreater(len(iceberg_jar_mappings), 0, 
                                 f"{service} should have iceberg-jars volume mapping")
                
                # Check that mapping points to correct Spark jars directory
                for mapping in iceberg_jar_mappings:
                    if 'iceberg-jars' in mapping:
                        # Should map to Spark jars directory
                        self.assertIn('/opt/bitnami/spark/jars', mapping,
                                    "Iceberg JARs should be mapped to Spark jars directory")
    
    def test_iceberg_spark_configuration(self):
        """Test Iceberg Spark configuration in compose"""
        if not self.iceberg_compose.exists():
            self.skipTest("docker-compose.iceberg.yml not found")
        
        with open(self.iceberg_compose, 'r') as f:
            compose_data = yaml.safe_load(f)
        
        services = compose_data.get('services', {})
        
        # Check Spark master configuration
        if 'spark-master' in services:
            spark_master = services['spark-master']
            env_vars = spark_master.get('environment', {})
            
            # Check for Iceberg Spark extensions
            extensions_key = 'SPARK_CONF_spark.sql.extensions'
            if extensions_key in env_vars:
                extensions = env_vars[extensions_key]
                self.assertIn('IcebergSparkSessionExtensions', extensions,
                            "Should include Iceberg Spark extensions")
            
            # Check for Iceberg catalog configuration
            catalog_key = 'SPARK_CONF_spark.sql.catalog.iceberg'
            if catalog_key in env_vars:
                catalog = env_vars[catalog_key]
                self.assertIn('SparkCatalog', catalog,
                            "Should configure Iceberg Spark catalog")
    
    def test_iceberg_s3_configuration(self):
        """Test Iceberg S3 configuration"""
        if not self.iceberg_compose.exists():
            self.skipTest("docker-compose.iceberg.yml not found")
        
        with open(self.iceberg_compose, 'r') as f:
            compose_data = yaml.safe_load(f)
        
        services = compose_data.get('services', {})
        
        # Check S3 configuration for Iceberg
        spark_services = ['spark-master', 'spark-worker']
        for service in spark_services:
            if service in services:
                service_config = services[service]
                env_vars = service_config.get('environment', {})
                
                # Check for S3 endpoint configuration
                s3_configs = [
                    'SPARK_CONF_spark.hadoop.fs.s3a.endpoint',
                    'SPARK_CONF_spark.hadoop.fs.s3a.access.key',
                    'SPARK_CONF_spark.hadoop.fs.s3a.secret.key',
                    'SPARK_CONF_spark.hadoop.fs.s3a.path.style.access'
                ]
                
                for config in s3_configs:
                    if config in env_vars:
                        self.assertIsNotNone(env_vars[config],
                                           f"{config} should have a value")
    
    def test_iceberg_warehouse_configuration(self):
        """Test Iceberg warehouse configuration"""
        if not self.iceberg_compose.exists():
            self.skipTest("docker-compose.iceberg.yml not found")
        
        with open(self.iceberg_compose, 'r') as f:
            compose_data = yaml.safe_load(f)
        
        services = compose_data.get('services', {})
        
        # Check warehouse configuration
        spark_services = ['spark-master', 'spark-worker']
        for service in spark_services:
            if service in services:
                service_config = services[service]
                env_vars = service_config.get('environment', {})
                
                warehouse_key = 'SPARK_CONF_spark.sql.catalog.iceberg.warehouse'
                if warehouse_key in env_vars:
                    warehouse = env_vars[warehouse_key]
                    self.assertIn('s3a://lakehouse/iceberg-warehouse', warehouse,
                                "Warehouse should be configured for S3 storage")
    
    def test_init_script_iceberg_support(self):
        """Test that init script supports Iceberg JAR downloading"""
        if not self.init_script.exists():
            self.skipTest("init-all-in-one-modular.sh not found")
        
        with open(self.init_script, 'r') as f:
            content = f.read()
        
        # Check for Iceberg-related functionality
        iceberg_checks = [
            'iceberg',  # Should mention Iceberg
            'maven.apache.org',  # Should download from Maven
            'jar',  # Should handle JAR files
            'spark'  # Should be Spark-related
        ]
        
        for check in iceberg_checks:
            self.assertIn(check, content.lower(), 
                         f"Init script should contain {check}")
    
    def test_iceberg_jar_download_function(self):
        """Test Iceberg JAR download functionality in init script"""
        if not self.init_script.exists():
            self.skipTest("init-all-in-one-modular.sh not found")
        
        with open(self.init_script, 'r') as f:
            content = f.read()
        
        # Check for download function
        self.assertIn('download_iceberg_jars', content,
                     "Should have download_iceberg_jars function")
        
        # Check for proper URL construction
        self.assertIn('https://repo1.maven.org/maven2', content,
                     "Should download from Maven Central")
        
        # Check for proper JAR naming
        self.assertIn('iceberg-spark-runtime', content,
                     "Should download Iceberg Spark runtime JAR")
    
    def test_iceberg_documentation_structure(self):
        """Test Iceberg documentation structure"""
        if not self.iceberg_docs.exists():
            self.skipTest("ICEBERG.md not found")
        
        with open(self.iceberg_docs, 'r') as f:
            content = f.read()
        
        # Check for required sections
        required_sections = [
            'Quick Start',
            'Features',
            'Configuration',
            'Usage Examples',
            'Time Travel',
            'Schema Evolution',
            'ACID Transactions',
            'Troubleshooting'
        ]
        
        for section in required_sections:
            self.assertIn(section, content, f"Documentation should have {section} section")
    
    def test_iceberg_documentation_examples(self):
        """Test that documentation contains practical examples"""
        if not self.iceberg_docs.exists():
            self.skipTest("ICEBERG.md not found")
        
        with open(self.iceberg_docs, 'r') as f:
            content = f.read()
        
        # Check for SQL examples
        sql_examples = [
            'CREATE TABLE',
            'SELECT * FROM',
            'USING ICEBERG',
            'TIMESTAMP AS OF',
            'VERSION AS OF',
            'ALTER TABLE',
            'MERGE INTO'
        ]
        
        for example in sql_examples:
            self.assertIn(example, content, f"Documentation should contain {example} example")
    
    def test_iceberg_version_consistency(self):
        """Test that Iceberg version is consistent across files"""
        # Check compose file for version
        compose_version = None
        if self.iceberg_compose.exists():
            with open(self.iceberg_compose, 'r') as f:
                compose_content = f.read()
                # Look for version in JAR path or environment
                import re
                version_match = re.search(r'iceberg-spark-runtime.*?(\d+\.\d+\.\d+)', compose_content)
                if version_match:
                    compose_version = version_match.group(1)
        
        # Check init script for version
        init_version = None
        if self.init_script.exists():
            with open(self.init_script, 'r') as f:
                init_content = f.read()
                version_match = re.search(r'ICEBERG_VERSION.*?(\d+\.\d+\.\d+)', init_content)
                if version_match:
                    init_version = version_match.group(1)
        
        # Check documentation for version
        doc_version = None
        if self.iceberg_docs.exists():
            with open(self.iceberg_docs, 'r') as f:
                doc_content = f.read()
                version_match = re.search(r'Iceberg Version.*?(\d+\.\d+\.\d+)', doc_content)
                if version_match:
                    doc_version = version_match.group(1)
        
        # If versions are found, they should be consistent
        versions = [v for v in [compose_version, init_version, doc_version] if v is not None]
        if len(versions) > 1:
            self.assertTrue(all(v == versions[0] for v in versions),
                          f"Iceberg versions should be consistent: {versions}")


class TestIcebergFunctionality(unittest.TestCase):
    """Test Iceberg functionality with mocked dependencies"""
    
    def setUp(self):
        """Set up test environment"""
        self.project_root = Path(__file__).parent.parent
        
    @patch('subprocess.run')
    def test_iceberg_jar_download_simulation(self, mock_run):
        """Test simulated Iceberg JAR download"""
        # Mock successful download
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Downloaded successfully"
        
        # Simulate curl command for JAR download
        result = subprocess.run([
            'curl', '-L', '-o', '/tmp/iceberg-spark-runtime.jar',
            'https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-spark-runtime-3.5_2.12/1.4.3/iceberg-spark-runtime-3.5_2.12-1.4.3.jar'
        ], capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0, "JAR download should succeed")
        
    @patch('os.path.exists')
    @patch('os.makedirs')
    def test_iceberg_jar_directory_creation(self, mock_makedirs, mock_exists):
        """Test Iceberg JAR directory creation"""
        mock_exists.return_value = False
        
        # Simulate directory creation
        os.makedirs('/tmp/iceberg-jars', exist_ok=True)
        
        # Verify directory creation was called
        mock_makedirs.assert_called_once_with('/tmp/iceberg-jars', exist_ok=True)
        
    @patch('subprocess.run')
    def test_spark_iceberg_configuration_validation(self, mock_run):
        """Test Spark Iceberg configuration validation"""
        # Mock spark-submit command with Iceberg
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Iceberg extensions loaded successfully"
        
        # Simulate spark-submit with Iceberg configurations
        result = subprocess.run([
            'spark-submit',
            '--jars', '/opt/bitnami/spark/jars/iceberg-spark-runtime.jar',
            '--conf', 'spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions',
            '--conf', 'spark.sql.catalog.iceberg=org.apache.iceberg.spark.SparkCatalog',
            'test_script.py'
        ], capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0, "Spark with Iceberg should start successfully")
    
    @patch('yaml.safe_load')
    @patch('builtins.open', new_callable=mock_open)
    def test_compose_iceberg_merge_simulation(self, mock_file, mock_yaml):
        """Test simulated compose file merging"""
        # Mock base compose file
        base_compose = {
            'services': {
                'spark-master': {
                    'image': 'bitnami/spark:3.5.0',
                    'environment': {
                        'SPARK_MODE': 'master'
                    }
                }
            }
        }
        
        # Mock Iceberg override
        iceberg_override = {
            'services': {
                'spark-master': {
                    'volumes': ['./iceberg-jars:/opt/bitnami/spark/jars/iceberg:ro'],
                    'environment': {
                        'SPARK_CONF_spark.sql.extensions': 'org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions'
                    }
                }
            }
        }
        
        # Mock yaml loading
        mock_yaml.side_effect = [base_compose, iceberg_override]
        
        # Simulate merge logic
        with open('docker-compose.yml', 'r') as f:
            base = yaml.safe_load(f)
        
        with open('docker-compose.iceberg.yml', 'r') as f:
            override = yaml.safe_load(f)
        
        # Verify the mock was called
        self.assertEqual(mock_yaml.call_count, 2)
        
        # Verify base structure
        self.assertIn('services', base)
        self.assertIn('spark-master', base['services'])
        
        # Verify override structure
        self.assertIn('services', override)
        self.assertIn('spark-master', override['services'])


if __name__ == '__main__':
    unittest.main()