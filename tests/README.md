# 🧪 Lakehouse Lab Testing

This directory contains test scripts and testing utilities for Lakehouse Lab.

## 📁 Test Scripts

- **`run_tests.sh`** - Main test runner for all test suites
- **`run_stack_health_tests.sh`** - Health check tests for running services

## 🔍 Test Categories

### Integration Tests
- Service startup and health checks
- Inter-service communication
- Data persistence and backup/restore
- Configuration validation

### Unit Tests (Future)
- Individual script testing
- Function-level validation
- Mock service testing

## 🚀 Running Tests

```bash
# Run all tests
./tests/run_tests.sh

# Run only health tests  
./tests/run_stack_health_tests.sh

# Run tests with verbose output
./tests/run_tests.sh --verbose

# Run tests in parallel
./tests/run_tests.sh --parallel
```

## 📋 Test Coverage

Current testing covers:
- ✅ Service startup and initialization
- ✅ Docker Compose configuration validation
- ✅ Documentation completeness
- ✅ Script permissions and syntax
- ✅ Backup system functionality
- ✅ Storage persistence across restarts
- ✅ Security validation

## 🎯 GitHub Actions CI/CD

Automated testing runs on:
- Push to main/dev branches
- Pull requests
- Nightly scheduled runs

See `.github/workflows/` for complete CI/CD configuration.

## 💡 Adding Tests

When adding new tests:
1. Follow the existing test structure
2. Add appropriate documentation
3. Ensure tests are deterministic
4. Include both positive and negative test cases
5. Update this README with new test coverage

---

**See also:** [TESTING.md](../docs/TESTING.md) for detailed testing framework documentation.