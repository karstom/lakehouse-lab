#!/usr/bin/env python3
"""
Comprehensive Stack Health Test Runner
Runs all end-to-end tests for the lakehouse stack after initialization
"""

import unittest
import sys
import time
import socket
import subprocess
import json
from pathlib import Path
from datetime import datetime
import argparse

# Import our test modules
from tests.test_service_health import TestServiceHealth
from tests.test_data_pipeline import TestDataPipelineEndToEnd
from tests.test_cross_service_integration import TestCrossServiceIntegration


class LakehouseStackTester:
    """Main test orchestrator for the lakehouse stack"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'test_suites': {},
            'summary': {
                'total_tests': 0,
                'passed': 0,
                'failed': 0,
                'errors': 0,
                'skipped': 0
            }
        }
    
    def wait_for_stack_ready(self, timeout=300):
        """Wait for the entire stack to be ready"""
        print("🔍 Waiting for lakehouse stack to be ready...")
        
        services = [
            ('localhost', 9000, 'MinIO'),
            ('localhost', 5432, 'PostgreSQL'),
            ('localhost', 9020, 'Airflow'),
            ('localhost', 8080, 'Spark Master'),
            ('localhost', 9040, 'Jupyter'),
            ('localhost', 9030, 'Superset'),
            ('localhost', 9060, 'Portainer'),
        ]
        
        start_time = time.time()
        ready_services = set()
        
        while time.time() - start_time < timeout:
            for host, port, name in services:
                if name not in ready_services and self.wait_for_service(host, port, 1):
                    ready_services.add(name)
                    print(f"✅ {name} is ready")
            
            if len(ready_services) >= len(services) - 1:  # Allow one service to be optional
                print(f"🚀 Stack is ready! ({len(ready_services)}/{len(services)} services)")
                return True
            
            time.sleep(5)
        
        print(f"⚠️  Stack readiness timeout. Ready services: {ready_services}")
        return len(ready_services) >= 4  # At least core services should be ready
    
    def wait_for_service(self, host, port, timeout=1):
        """Wait for a single service to be ready"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except:
            return False
    
    def run_test_suite(self, test_class, suite_name):
        """Run a specific test suite"""
        print(f"\n📊 Running {suite_name}...")
        print("=" * 60)
        
        # Create test suite
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(test_class)
        
        # Run tests
        runner = unittest.TextTestRunner(
            verbosity=2,
            stream=sys.stdout,
            buffer=True
        )
        
        result = runner.run(suite)
        
        # Record results
        self.results['test_suites'][suite_name] = {
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'skipped': len(result.skipped) if hasattr(result, 'skipped') else 0,
            'success': result.wasSuccessful()
        }
        
        # Update summary
        self.results['summary']['total_tests'] += result.testsRun
        self.results['summary']['failed'] += len(result.failures)
        self.results['summary']['errors'] += len(result.errors)
        self.results['summary']['skipped'] += len(result.skipped) if hasattr(result, 'skipped') else 0
        
        if result.wasSuccessful():
            print(f"✅ {suite_name} - ALL TESTS PASSED")
        else:
            print(f"❌ {suite_name} - {len(result.failures)} failures, {len(result.errors)} errors")
        
        return result.wasSuccessful()
    
    def run_all_tests(self):
        """Run all test suites"""
        print("🚀 Starting Lakehouse Stack Health Tests")
        print("=" * 60)
        
        # Wait for stack to be ready
        if not self.wait_for_stack_ready():
            print("❌ Stack is not ready. Aborting tests.")
            return False
        
        # Define test suites in order of execution
        test_suites = [
            (TestServiceHealth, "Service Health Tests"),
            (TestDataPipelineEndToEnd, "Data Pipeline End-to-End Tests"),
            (TestCrossServiceIntegration, "Cross-Service Integration Tests"),
        ]
        
        all_passed = True
        
        for test_class, suite_name in test_suites:
            try:
                success = self.run_test_suite(test_class, suite_name)
                if not success:
                    all_passed = False
            except Exception as e:
                print(f"❌ Error running {suite_name}: {e}")
                all_passed = False
        
        # Calculate passed tests
        self.results['summary']['passed'] = (
            self.results['summary']['total_tests'] - 
            self.results['summary']['failed'] - 
            self.results['summary']['errors'] - 
            self.results['summary']['skipped']
        )
        
        return all_passed
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("📋 TEST SUMMARY")
        print("=" * 60)
        
        summary = self.results['summary']
        print(f"Total Tests: {summary['total_tests']}")
        print(f"✅ Passed: {summary['passed']}")
        print(f"❌ Failed: {summary['failed']}")
        print(f"⚠️  Errors: {summary['errors']}")
        print(f"⏭️  Skipped: {summary['skipped']}")
        
        print("\n📊 Test Suite Results:")
        for suite_name, results in self.results['test_suites'].items():
            status = "✅ PASSED" if results['success'] else "❌ FAILED"
            print(f"  {suite_name}: {status} ({results['tests_run']} tests)")
        
        # Overall result
        if summary['failed'] == 0 and summary['errors'] == 0:
            print("\n🎉 ALL TESTS PASSED! Your lakehouse stack is healthy!")
            return True
        else:
            print(f"\n⚠️  {summary['failed'] + summary['errors']} tests failed. Please check the logs above.")
            return False
    
    def save_results(self, filename=None):
        """Save test results to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"stack_health_results_{timestamp}.json"
        
        results_path = self.project_root / "results" / filename
        results_path.parent.mkdir(exist_ok=True)
        
        with open(results_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n📄 Results saved to: {results_path}")
        return results_path
    
    def check_docker_compose(self):
        """Check if docker-compose is running"""
        try:
            result = subprocess.run(
                ['docker', 'ps', '--format', '{{.Names}}'],
                capture_output=True, text=True, check=True
            )
            
            containers = result.stdout.strip().split('\n')
            lakehouse_containers = [c for c in containers if 'lakehouse-test' in c or 'lakehouse' in c]
            
            if len(lakehouse_containers) < 5:
                print("⚠️  Warning: Expected more lakehouse containers to be running")
                print(f"   Found: {lakehouse_containers}")
                return False
            
            print(f"✅ Found {len(lakehouse_containers)} lakehouse containers")
            return True
            
        except subprocess.CalledProcessError:
            print("❌ Docker is not available or containers are not running")
            return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Run lakehouse stack health tests")
    parser.add_argument("--wait-timeout", type=int, default=300, 
                       help="Timeout in seconds to wait for stack readiness")
    parser.add_argument("--quick", action="store_true", 
                       help="Run only service health tests")
    parser.add_argument("--save-results", type=str, 
                       help="Save results to specific file")
    
    args = parser.parse_args()
    
    # Create tester
    tester = LakehouseStackTester()
    
    # Check Docker
    if not tester.check_docker_compose():
        print("❌ Docker containers are not running. Please start the stack first:")
        print("   docker-compose up -d")
        return False
    
    # Run tests
    if args.quick:
        print("🏃 Running quick health check...")
        success = tester.run_test_suite(TestServiceHealth, "Service Health Tests")
    else:
        success = tester.run_all_tests()
    
    # Print summary
    overall_success = tester.print_summary()
    
    # Save results
    tester.save_results(args.save_results)
    
    # Exit with appropriate code
    sys.exit(0 if overall_success else 1)


if __name__ == "__main__":
    main()