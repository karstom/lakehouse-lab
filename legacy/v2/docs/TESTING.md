# Lakehouse Lab Testing Framework

This document provides a comprehensive overview of the testing framework for the Lakehouse Lab project, designed to prevent regressions and ensure code quality.

## 📋 Overview

The testing framework includes:

- **Unit Tests** - Test individual components and scripts
- **Integration Tests** - Test Docker Compose configurations and service interactions
- **Iceberg Tests** - Test Apache Iceberg integration functionality
- **Documentation Tests** - Validate documentation completeness and accuracy
- **GitHub Actions CI/CD** - Automated testing pipeline
- **Test Framework** - Utilities and fixtures for consistent testing

## 🏗️ Test Structure

```
tests/
├── conftest.py                        # Test configuration and fixtures
├── requirements.txt                   # Test dependencies
├── run_tests.sh                       # Main test runner script
├── run_stack_health_tests.sh          # Stack health testing
├── test_init_scripts.py               # Unit tests for initialization scripts
├── test_docker_compose.py             # Integration tests for Docker Compose
├── test_iceberg_integration.py        # Iceberg functionality tests
├── test_documentation.py              # Documentation validation tests
├── test_v2_fixes.py                   # Version 2.x specific tests
├── test_service_health.py             # Service health monitoring tests
├── test_cross_service_integration.py  # Cross-service integration tests
├── test_data_pipeline.py              # Data pipeline functionality tests
└── unit/                              # Additional unit test modules
```

## 🚀 Running Tests

### Quick Start

```bash
# Run all tests
cd tests
./run_tests.sh

# Run only unit tests
./run_tests.sh --unit-only

# Run only integration tests
./run_tests.sh --integration-only

# Run with verbose output
./run_tests.sh --verbose

# Run tests in parallel
./run_tests.sh --parallel
```

### Available Options

| Option | Description |
|--------|-------------|
| `-u, --unit-only` | Run only unit tests |
| `-i, --integration-only` | Run only integration tests |
| `-d, --docker-only` | Run only Docker-related tests |
| `-l, --lint-only` | Run only linting and code quality checks |
| `-n, --no-coverage` | Skip coverage report generation |
| `-v, --verbose` | Enable verbose output |
| `-p, --parallel` | Run tests in parallel |
| `-k, --keep-venv` | Keep virtual environment after tests |
| `--docker` | Force enable Docker tests |
| `--no-docker` | Force disable Docker tests |

## 📊 Test Categories

### 1. Unit Tests (`test_init_scripts.py`)

Tests individual components and scripts:

- **Script Validation**: Syntax, executability, and structure
- **Error Handling**: Proper error handling and cleanup
- **Environment Variables**: Correct handling of configuration
- **Logging**: Proper logging functionality
- **Function Logic**: Core functionality testing

**Example Test**:
```python
def test_init_script_has_error_handling(self):
    """Test that init script has proper error handling"""
    with open(self.init_script, 'r') as f:
        content = f.read()
    
    self.assertIn('set -e', content, "Script should have 'set -e' for error handling")
    self.assertIn('trap', content, "Script should have trap for cleanup")
```

### 2. Integration Tests (`test_docker_compose.py`)

Tests Docker Compose configurations and service interactions:

- **Compose File Validation**: YAML syntax and structure
- **Service Dependencies**: Proper dependency chains
- **Port Mappings**: No conflicts and reasonable ranges
- **Volume Definitions**: Proper storage configuration
- **Network Configuration**: Service networking
- **Environment Variables**: Required variables present

**Example Test**:
```python
def test_service_dependencies(self):
    """Test that services have proper dependencies"""
    dependency_checks = {
        'spark-master': ['postgres', 'minio'],
        'spark-worker': ['spark-master'],
        'jupyter': ['spark-master']
    }
    
    for service, expected_deps in dependency_checks.items():
        # Validate dependencies are properly defined
```

### 3. Iceberg Integration Tests (`test_iceberg_integration.py`)

Tests Apache Iceberg functionality:

- **Compose Override**: Iceberg Docker Compose configuration
- **JAR Configuration**: Proper JAR file mapping
- **Spark Configuration**: Iceberg extensions and catalog setup
- **S3 Configuration**: MinIO integration for storage
- **Warehouse Configuration**: Iceberg warehouse setup
- **Documentation**: Iceberg feature documentation

**Example Test**:
```python
def test_iceberg_spark_configuration(self):
    """Test Iceberg Spark configuration in compose"""
    # Verify Iceberg Spark extensions are configured
    extensions = env_vars['SPARK_CONF_spark.sql.extensions']
    self.assertIn('IcebergSparkSessionExtensions', extensions)
```

### 4. Documentation Tests (`test_documentation.py`)

Validates documentation completeness and accuracy:

- **File Existence**: Required documentation files present
- **Content Validation**: Substantial content in documentation
- **Structure Validation**: Required sections present
- **Code Examples**: Valid syntax in code blocks
- **Link Validation**: Internal links point to existing files
- **Version Consistency**: Consistent version numbers
- **Port References**: Accurate port documentation

**Example Test**:
```python
def test_code_examples_syntax(self):
    """Test that code examples in documentation have valid syntax"""
    code_blocks = self._extract_code_blocks(content)
    
    for lang, code in code_blocks:
        if lang == 'sql':
            self._validate_sql_syntax(code, doc_name)
```

## 🔄 GitHub Actions CI/CD

The GitHub Actions workflow (`.github/workflows/ci.yml`) provides:

### Pipeline Jobs

1. **Lint and Validate Code**
   - Python linting (flake8, black, isort)
   - YAML validation (yamllint)
   - Shell script validation (shellcheck)
   - Docker Compose syntax validation

2. **Unit Tests**
   - Run unit tests with coverage
   - Run comprehensive test suite

3. **Docker Build and Test**
   - Build Docker services
   - Test basic service startup
   - Test Iceberg integration

4. **Integration Tests**
   - Full service stack testing
   - Service endpoint validation
   - Log collection on failure

5. **Security Scanning**
   - Trivy vulnerability scanning
   - Docker configuration security checks

6. **Documentation Validation**
   - README and documentation checks
   - Link validation
   - Code example validation

7. **Performance Benchmarks** (scheduled)
   - Startup time measurement
   - Resource usage monitoring

8. **Deployment Readiness**
   - Final validation checks
   - Deployment summary generation

### Triggers

- **Push**: On pushes to `main` and `dev` branches
- **Pull Request**: On PRs to `main` and `dev` branches
- **Schedule**: Nightly tests at 2 AM UTC
- **Manual**: On-demand with `[benchmark]` in commit message

## 🧪 Test Framework Features

### Fixtures and Utilities

- **`conftest.py`**: Shared fixtures and configuration
- **`TestContainerManager`**: Docker container management
- **`ServiceHealthChecker`**: Service health validation
- **Mock utilities**: Subprocess and Docker mocking

### Key Fixtures

```python
@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create and cleanup temporary directory for tests"""

@pytest.fixture
def container_manager(compose_files: Dict[str, Path]) -> TestContainerManager:
    """Get container manager instance"""

@pytest.fixture
def health_checker() -> ServiceHealthChecker:
    """Get service health checker instance"""
```

### Test Markers

- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.slow` - Slow running tests
- `@pytest.mark.docker` - Tests requiring Docker
- `@pytest.mark.iceberg` - Iceberg-specific tests

## 📈 Coverage and Reporting

### Coverage Reports

- **HTML Report**: `tests/results/coverage_html/index.html`
- **XML Report**: `tests/results/coverage.xml`
- **Console Output**: Summary during test runs

### Test Reports

- **HTML Report**: Generated after each test run
- **Logs**: Separate log files for each test category
- **CI Artifacts**: Uploaded to GitHub Actions

## 🔧 Configuration

### Test Configuration

```python
TEST_CONFIG = {
    'timeout': 300,  # 5 minutes
    'service_wait_time': 30,  # 30 seconds
    'docker_compose_file': 'docker-compose.yml',
    'iceberg_compose_file': 'docker-compose.iceberg.yml'
}
```

### Environment Variables

- `DOCKER_AVAILABLE`: Force Docker availability
- `LAKEHOUSE_ROOT`: Override data directory
- `PYTEST_MARKERS`: Custom test markers

## 🚨 Troubleshooting

### Common Issues

1. **Docker Not Available**
   ```bash
   # Check Docker status
   docker --version
   docker compose version
   docker info
   ```

2. **Permission Issues**
   ```bash
   # Make test runner executable
   chmod +x run_tests.sh
   
   # Fix Docker permissions
   sudo usermod -aG docker $USER
   ```

3. **Test Failures**
   ```bash
   # Run with verbose output
   ./run_tests.sh --verbose
   
   # Check specific test category
   ./run_tests.sh --unit-only
   ```

4. **Missing Dependencies**
   ```bash
   # Install test dependencies
   pip install -r tests/requirements.txt
   ```

## 📚 Best Practices

### Writing Tests

1. **Use descriptive test names**
2. **Test both success and failure cases**
3. **Mock external dependencies**
4. **Use fixtures for common setup**
5. **Include edge cases**

### Test Organization

1. **Group related tests in classes**
2. **Use appropriate test markers**
3. **Keep tests independent**
4. **Clean up resources**
5. **Use meaningful assertions**

### CI/CD Integration

1. **Keep tests fast**
2. **Use parallel execution where possible**
3. **Provide clear failure messages**
4. **Upload artifacts for debugging**
5. **Monitor test stability**

## 🎯 Regression Prevention

This testing framework prevents regressions by:

- **Automated Testing**: Every code change is tested
- **Comprehensive Coverage**: Multiple test types ensure thorough validation
- **Environment Consistency**: Containerized testing environment
- **Documentation Validation**: Ensures docs stay current
- **Security Scanning**: Prevents security vulnerabilities
- **Performance Monitoring**: Tracks performance over time

## 📞 Support

For questions or issues with the testing framework:

1. Check the troubleshooting section
2. Review test logs in `tests/results/`
3. Run tests with `--verbose` flag
4. Open an issue in the repository

## 💾 Backup System Testing

### Testing Backup and Restore Functionality

**Manual Testing:**
```bash
# Test backup creation
./scripts/backup-lakehouse.sh --dry-run
./scripts/backup-lakehouse.sh --compress --verify

# Test specific service backup
./scripts/backup-lakehouse.sh --services postgres --dry-run
./scripts/backup-lakehouse.sh --services postgres,minio

# Test restore functionality
./scripts/restore-lakehouse.sh BACKUP_ID --dry-run
./scripts/restore-lakehouse.sh BACKUP_ID --service postgres --dry-run

# Test CRON setup
./examples/cron-backup-setup.sh --dry-run
```

**Backup System Verification:**
```bash
# Verify backup script permissions
ls -la scripts/backup-lakehouse.sh scripts/restore-lakehouse.sh

# Test backup metadata generation
./scripts/backup-lakehouse.sh --dry-run | grep -i metadata

# Verify backup directory structure
./scripts/backup-lakehouse.sh --output-dir /tmp/test-backup --dry-run

# Test backup verification feature
./scripts/backup-lakehouse.sh --verify --dry-run
```

**Integration Testing:**
- Test backup creation with all services running
- Verify restore preserves data integrity
- Test CRON integration and scheduling
- Validate Airflow DAG deployment and execution
- Test backup retention policy enforcement

---

**Note**: This testing framework is designed to be comprehensive yet maintainable. It has been updated for Lakehouse Lab v2.1.1 to reflect the dashboard-free architecture and modern Docker Compose syntax. The framework should continue to be updated as the project evolves to ensure continued regression prevention and code quality.