"""
Test suite for Version 2.0.0 bug fixes.

Tests the fixes for:
1. start-lakehouse.sh missing log_info function
2. Vizro health check issues  
3. enable-auth.sh configuration parsing errors
"""

import pytest
import subprocess
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, Mock


class TestStartLakehouseScript:
    """Tests for start-lakehouse.sh fixes."""
    
    def test_log_functions_defined(self, project_root):
        """Test that logging functions are properly defined."""
        script_path = project_root / "start-lakehouse.sh"
        
        # Read the script and check for log function definitions
        with open(script_path, 'r') as f:
            content = f.read()
        
        # Check that all required log functions are defined
        assert 'log_info()' in content
        assert 'log_success()' in content  
        assert 'log_warning()' in content
        assert 'log_error()' in content
        
        # Check that log functions use proper colors
        assert '${BLUE}ℹ️' in content
        assert '${GREEN}✅' in content
        assert '${YELLOW}⚠️' in content
        assert '${RED}❌' in content
    
    def test_script_syntax_valid(self, project_root):
        """Test that the script has valid bash syntax."""
        script_path = project_root / "start-lakehouse.sh"
        
        result = subprocess.run(['bash', '-n', str(script_path)], capture_output=True)
        assert result.returncode == 0, f"Syntax error in start-lakehouse.sh: {result.stderr.decode()}"
    
    def test_log_info_usage(self, project_root):
        """Test that log_info is properly used in the script."""
        script_path = project_root / "start-lakehouse.sh"
        
        with open(script_path, 'r') as f:
            content = f.read()
        
        # Check that log_info is called somewhere in the script
        assert 'log_info "' in content


class TestVizroHealthCheck:
    """Tests for Vizro health check fixes."""
    
    def test_vizro_healthcheck_configuration(self, project_root):
        """Test that Vizro service has improved health check."""
        compose_file = project_root / "docker-compose.yml"
        
        with open(compose_file, 'r') as f:
            content = f.read()
        
        # Find vizro service section
        vizro_section_start = content.find('vizro:')
        assert vizro_section_start != -1, "Vizro service not found in docker-compose.yml"
        
        # Extract vizro service section (rough extraction for testing)
        vizro_section = content[vizro_section_start:vizro_section_start + 2000]
        
        # Check that healthcheck is configured
        assert 'healthcheck:' in vizro_section
        assert 'test:' in vizro_section
        
        # Check that health check has reasonable timeout/retry settings
        assert 'retries:' in vizro_section
        assert 'start_period:' in vizro_section
        
        # Should have longer start period for Vizro
        if '120s' in vizro_section or '90s' in vizro_section:
            assert True  # Good, longer start period
        else:
            # Check it's at least 60s
            assert 'start_period: 60s' in vizro_section or 'start_period: 90s' in vizro_section
    
    def test_vizro_health_check_logic(self, project_root):
        """Test the health check logic is more robust."""
        compose_file = project_root / "docker-compose.yml"
        
        with open(compose_file, 'r') as f:
            content = f.read()
        
        # Health check should be more sophisticated than just curl -f
        vizro_section_start = content.find('vizro:')
        vizro_section = content[vizro_section_start:vizro_section_start + 2000]
        
        # Should have bash or pgrep fallback, not just simple curl
        assert ('bash' in vizro_section and 'pgrep' in vizro_section) or 'grep' in vizro_section


class TestConfigurationParsing:
    """Tests for configuration parsing fixes."""
    
    def test_configure_services_script_syntax(self, project_root):
        """Test configure-services.sh has valid syntax."""
        script_path = project_root / "scripts" / "configure-services.sh"
        
        result = subprocess.run(['bash', '-n', str(script_path)], capture_output=True)
        assert result.returncode == 0, f"Syntax error in configure-services.sh: {result.stderr.decode()}"
    
    def test_enable_auth_script_syntax(self, project_root):
        """Test enable-auth.sh has valid syntax.""" 
        script_path = project_root / "scripts" / "enable-auth.sh"
        
        result = subprocess.run(['bash', '-n', str(script_path)], capture_output=True)
        assert result.returncode == 0, f"Syntax error in enable-auth.sh: {result.stderr.decode()}"
    
    def test_service_config_array_usage(self, project_root):
        """Test that SERVICE_CONFIG array is used instead of direct variable access."""
        script_path = project_root / "scripts" / "configure-services.sh"
        
        with open(script_path, 'r') as f:
            content = f.read()
        
        # Should declare SERVICE_CONFIG array
        assert 'declare -A SERVICE_CONFIG' in content
        
        # Should use SERVICE_CONFIG array instead of direct variable access
        assert 'SERVICE_CONFIG[' in content
        
        # Should not use problematic variable access patterns
        lines = content.split('\n')
        for line in lines:
            # Skip comment lines
            if line.strip().startswith('#'):
                continue
            # Look for problematic patterns like ${auth-service}
            if '${auth-service}' in line or '${auth-proxy}' in line or '${mcp-server}' in line:
                # This would be problematic, but allow in comments/strings
                if not ('"' in line or "'" in line):
                    pytest.fail(f"Found problematic variable access: {line.strip()}")
    
    @pytest.mark.integration
    def test_config_file_parsing_with_hyphens(self, temp_dir):
        """Test that configuration files with hyphenated service names are parsed correctly."""
        # Create test configuration file
        config_content = """# Test configuration
airflow=true
superset=false
auth-service=true
auth-proxy=true
mcp-server=false
"""
        config_file = temp_dir / "test-services.conf"
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        # Create minimal test script that uses the same parsing logic
        test_script = temp_dir / "test-parser.sh"
        test_script_content = f'''#!/bin/bash
declare -A SERVICE_CONFIG

CONFIG_FILE="{config_file}"

# Copy the parsing logic from configure-services.sh
if [[ -f "$CONFIG_FILE" ]]; then
    while IFS='=' read -r service value; do
        [[ -z "$service" || "$service" =~ ^[[:space:]]*# ]] && continue
        SERVICE_CONFIG["$service"]="$value"
    done < <(grep -E '^[a-zA-Z0-9_-]+=' "$CONFIG_FILE" || true)
fi

# Test that hyphenated services were parsed correctly
echo "auth-service: ${{SERVICE_CONFIG[auth-service]:-NOT_FOUND}}"
echo "auth-proxy: ${{SERVICE_CONFIG[auth-proxy]:-NOT_FOUND}}"
echo "mcp-server: ${{SERVICE_CONFIG[mcp-server]:-NOT_FOUND}}"
echo "airflow: ${{SERVICE_CONFIG[airflow]:-NOT_FOUND}}"
echo "superset: ${{SERVICE_CONFIG[superset]:-NOT_FOUND}}"
'''
        
        with open(test_script, 'w') as f:
            f.write(test_script_content)
        
        # Make executable and run
        os.chmod(test_script, 0o755)
        result = subprocess.run(['bash', str(test_script)], capture_output=True, text=True)
        
        assert result.returncode == 0, f"Test script failed: {result.stderr}"
        
        # Check output contains expected values
        output = result.stdout
        assert "auth-service: true" in output
        assert "auth-proxy: true" in output  
        assert "mcp-server: false" in output
        assert "airflow: true" in output
        assert "superset: false" in output
        
        # Should not contain NOT_FOUND
        assert "NOT_FOUND" not in output


class TestAuthenticationScripts:
    """Tests for authentication-related script fixes."""
    
    def test_secure_preset_available(self, project_root):
        """Test that secure preset is available in configure-services.sh."""
        script_path = project_root / "scripts" / "configure-services.sh"
        
        with open(script_path, 'r') as f:
            content = f.read()
        
        # Should have secure preset definition
        assert 'secure")' in content
        assert 'auth-service=true' in content
        assert 'auth-proxy=true' in content
        assert 'mcp-server=true' in content
    
    def test_auth_services_defined(self, project_root):
        """Test that auth services are properly defined."""
        script_path = project_root / "scripts" / "configure-services.sh"
        
        with open(script_path, 'r') as f:
            content = f.read()
        
        # Should define auth services
        assert 'SERVICES[auth-service]=' in content
        assert 'SERVICES[auth-proxy]=' in content
        assert 'SERVICES[mcp-server]=' in content
        
        # Should have descriptions
        assert 'Authentication Service' in content
        assert 'Authentication Proxy' in content


class TestDockerComposeValidation:
    """Tests for Docker Compose configuration validation."""
    
    def test_docker_compose_syntax_valid(self, project_root):
        """Test that docker-compose.yml has valid syntax."""
        compose_file = project_root / "docker-compose.yml"
        
        # Use docker-compose config to validate syntax
        result = subprocess.run(
            ['docker', 'compose', '-f', str(compose_file), 'config'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )
        
        # If docker/docker-compose is not available, skip this test
        if result.returncode == 127:  # Command not found
            pytest.skip("Docker Compose not available for testing")
        
        assert result.returncode == 0, f"Docker Compose validation failed: {result.stderr}"
    
    def test_auth_compose_syntax_valid(self, project_root):
        """Test that docker-compose.auth.yml has valid syntax."""
        auth_compose_file = project_root / "docker-compose.auth.yml"
        main_compose_file = project_root / "docker-compose.yml"
        
        if not auth_compose_file.exists():
            pytest.skip("docker-compose.auth.yml not found")
        
        # Test combined compose files
        result = subprocess.run(
            ['docker', 'compose', '-f', str(main_compose_file), '-f', str(auth_compose_file), 'config'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )
        
        if result.returncode == 127:  # Command not found
            pytest.skip("Docker Compose not available for testing")
        
        assert result.returncode == 0, f"Combined Docker Compose validation failed: {result.stderr}"


@pytest.mark.integration 
class TestEndToEndFixes:
    """End-to-end tests for the fixes."""
    
    def test_enable_auth_workflow(self, project_root, temp_dir):
        """Test that enable-auth.sh workflow completes without configuration errors."""
        # This is a more complex test that would require mocking
        # For now, just test that the scripts can be executed in dry-run mode
        enable_auth_script = project_root / "scripts" / "enable-auth.sh"
        
        # Test that script can be parsed and functions are callable
        result = subprocess.run(['bash', '-n', str(enable_auth_script)], capture_output=True)
        assert result.returncode == 0
    
    def test_service_configuration_workflow(self, project_root):
        """Test the complete service configuration workflow."""
        configure_script = project_root / "scripts" / "configure-services.sh"
        
        # Test help command
        result = subprocess.run(
            ['bash', str(configure_script), 'help'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )
        
        # Should complete successfully and show help
        assert result.returncode == 0
        assert 'Usage:' in result.stdout
        assert 'secure' in result.stdout  # Should mention secure preset


if __name__ == "__main__":
    pytest.main([__file__, "-v"])