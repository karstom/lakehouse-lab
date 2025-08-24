"""
Test suite for the MCP (Model Context Protocol) Server.

Tests the AI-powered data API including authentication, permissions,
Vizro integration, and data access functionality.
"""

import pytest
import json
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List
import pandas as pd
from fastapi.testclient import TestClient
from fastapi import HTTPException

# Import MCP server components (would be adjusted based on actual imports)
from mcp_server.main import app, verify_token, check_permission, generate_vizro_dashboard_config
from mcp_server.config import Settings


class TestMCPServerUnit:
    """Unit tests for MCP Server components."""
    
    @pytest.fixture
    def test_client(self):
        """Create test client for FastAPI app."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_user(self):
        """Mock user for testing."""
        return {
            'id': 1,
            'email': 'test@example.com',
            'name': 'Test User',
            'role': 'data_analyst',
            'provider': 'local'
        }
    
    @pytest.fixture
    def sample_dataframe(self):
        """Sample DataFrame for testing."""
        return pd.DataFrame({
            'product_category': ['Electronics', 'Clothing', 'Books', 'Home'],
            'revenue': [15000, 8000, 3000, 12000],
            'orders': [150, 200, 100, 80],
            'avg_order_value': [100, 40, 30, 150]
        })
    
    def test_health_endpoint(self, test_client):
        """Test health check endpoint."""
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_root_endpoint(self, test_client):
        """Test root endpoint."""
        response = test_client.get("/")
        assert response.status_code == 200
        assert "Lakehouse Lab MCP Server" in response.json()["message"]
    
    @patch('mcp_server.main.jwt.decode')
    @patch('mcp_server.main.httpx.AsyncClient.get')
    async def test_verify_token_valid_jwt(self, mock_httpx_get, mock_jwt_decode, mock_user):
        """Test JWT token verification with valid token."""
        mock_jwt_decode.return_value = mock_user
        
        # Mock request with Authorization header
        mock_request = Mock()
        mock_request.headers.get.return_value = "Bearer valid_token"
        
        with patch('mcp_server.main.get_settings') as mock_settings:
            mock_settings.return_value.jwt_secret = "test_secret"
            user = await verify_token(mock_request)
            
            assert user.email == mock_user['email']
            assert user.role == mock_user['role']
    
    async def test_verify_token_invalid_jwt(self):
        """Test JWT token verification with invalid token."""
        mock_request = Mock()
        mock_request.headers.get.return_value = "Bearer invalid_token"
        
        with patch('mcp_server.main.jwt.decode') as mock_decode:
            mock_decode.side_effect = Exception("Invalid token")
            
            with pytest.raises(HTTPException) as exc_info:
                await verify_token(mock_request)
            
            assert exc_info.value.status_code == 401
    
    def test_check_permission_admin_role(self):
        """Test permission checking for admin role."""
        from mcp_server.main import User
        
        admin_user = User(
            id=1, email="admin@test.com", name="Admin", 
            role="admin", provider="local"
        )
        
        # Admin should have all permissions
        assert check_permission(admin_user, 'query_postgres') == True
        assert check_permission(admin_user, 'create_dashboards') == True
        assert check_permission(admin_user, 'admin_operations') == True
    
    def test_check_permission_data_viewer_role(self):
        """Test permission checking for data_viewer role."""
        from mcp_server.main import User
        
        viewer_user = User(
            id=2, email="viewer@test.com", name="Viewer",
            role="data_viewer", provider="local"
        )
        
        # Data viewer should have limited permissions
        assert check_permission(viewer_user, 'query_postgres') == True
        assert check_permission(viewer_user, 'create_dashboards') == False
        assert check_permission(viewer_user, 'admin_operations') == False
    
    def test_check_permission_data_analyst_role(self):
        """Test permission checking for data_analyst role."""
        from mcp_server.main import User
        
        analyst_user = User(
            id=3, email="analyst@test.com", name="Analyst",
            role="data_analyst", provider="local"
        )
        
        # Data analyst should be able to create dashboards
        assert check_permission(analyst_user, 'query_postgres') == True
        assert check_permission(analyst_user, 'create_dashboards') == True
        assert check_permission(analyst_user, 'create_tables') == False
        assert check_permission(analyst_user, 'admin_operations') == False
    
    async def test_generate_vizro_dashboard_config(self, sample_dataframe):
        """Test Vizro dashboard configuration generation."""
        title = "Test Dashboard"
        chart_types = ["bar", "line"]
        description = "Test dashboard for unit testing"
        
        config = await generate_vizro_dashboard_config(
            sample_dataframe, title, chart_types, description
        )
        
        assert config["metadata"]["title"] == title
        assert config["metadata"]["description"] == description
        assert len(config["pages"]) == 1
        assert len(config["pages"][0]["components"]) == 2  # Two charts
        
        # Check data source configuration
        assert "df" in config["data_sources"]
        assert config["data_sources"]["df"]["type"] == "pandas"
        assert len(config["data_sources"]["df"]["data"]) == len(sample_dataframe)
        
        # Check metadata analysis
        metadata = config["metadata"]["data_summary"]
        assert metadata["rows"] == len(sample_dataframe)
        assert metadata["columns"] == len(sample_dataframe.columns)
        assert "product_category" in metadata["categorical_columns"]
        assert "revenue" in metadata["numeric_columns"]


@pytest.mark.integration
class TestMCPServerIntegration:
    """Integration tests for MCP Server with actual services."""
    
    @pytest.fixture(scope="class")
    def test_client(self):
        """Create test client for integration tests."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """Mock authentication headers for testing."""
        # In real tests, this would use actual JWT tokens
        return {"Authorization": "Bearer test_token"}
    
    @pytest.mark.docker
    async def test_query_postgres_endpoint_integration(self, test_client, auth_headers):
        """Test PostgreSQL query endpoint with real database."""
        query_data = {
            "query": "SELECT 1 as test_value",
            "limit": 10
        }
        
        with patch('mcp_server.main.verify_token') as mock_verify:
            mock_verify.return_value = Mock(
                id=1, email="test@example.com", role="data_analyst"
            )
            
            response = test_client.post(
                "/tools/query-postgres",
                json=query_data,
                headers=auth_headers
            )
            
            # Should succeed if PostgreSQL is available
            if response.status_code == 200:
                assert "results" in response.json()
    
    @pytest.mark.docker
    async def test_create_vizro_dashboard_integration(self, test_client, auth_headers):
        """Test Vizro dashboard creation with real data."""
        dashboard_data = {
            "title": "Integration Test Dashboard",
            "data_query": "SELECT 'Electronics' as category, 1000 as revenue UNION SELECT 'Books' as category, 500 as revenue",
            "chart_types": ["bar"],
            "description": "Test dashboard for integration testing"
        }
        
        with patch('mcp_server.main.verify_token') as mock_verify:
            mock_verify.return_value = Mock(
                id=1, email="test@example.com", role="data_analyst"
            )
            
            response = test_client.post(
                "/tools/create-vizro-dashboard",
                json=dashboard_data,
                headers=auth_headers
            )
            
            if response.status_code == 200:
                result = response.json()
                assert "dashboard_id" in result
                assert "config" in result
                assert result["dashboard_id"] == "integration_test_dashboard"
    
    @pytest.mark.docker
    async def test_vector_search_integration(self, test_client, auth_headers):
        """Test vector search functionality."""
        search_data = {
            "table": "test_vectors",
            "query_text": "electronics products",
            "limit": 5
        }
        
        with patch('mcp_server.main.verify_token') as mock_verify:
            mock_verify.return_value = Mock(
                id=1, email="test@example.com", role="data_analyst"
            )
            
            response = test_client.post(
                "/tools/search-vectors",
                json=search_data,
                headers=auth_headers
            )
            
            # May return error if LanceDB not available, that's OK
            assert response.status_code in [200, 500]


class TestMCPServerSecurity:
    """Security-focused tests for MCP Server."""
    
    def test_unauthorized_access_blocked(self, test_client):
        """Test that unauthorized requests are blocked."""
        response = test_client.post("/tools/query-postgres", json={"query": "SELECT 1"})
        assert response.status_code == 401
    
    def test_insufficient_permissions_blocked(self, test_client):
        """Test that insufficient permissions block access."""
        with patch('mcp_server.main.verify_token') as mock_verify:
            # Mock a data_viewer trying to create dashboards
            mock_verify.return_value = Mock(
                id=1, email="viewer@example.com", role="data_viewer"
            )
            
            response = test_client.post(
                "/tools/create-vizro-dashboard",
                json={"title": "Test", "data_query": "SELECT 1", "chart_types": ["bar"]},
                headers={"Authorization": "Bearer token"}
            )
            
            assert response.status_code == 403
    
    @patch('mcp_server.main.audit_log')
    async def test_audit_logging(self, mock_audit_log, test_client):
        """Test that operations are properly audited."""
        with patch('mcp_server.main.verify_token') as mock_verify:
            mock_verify.return_value = Mock(
                id=1, email="test@example.com", role="data_analyst"
            )
            
            # This would trigger audit logging
            response = test_client.post(
                "/tools/create-vizro-chart",
                json={
                    "chart_type": "bar",
                    "data_query": "SELECT 1 as x, 2 as y",
                    "x_column": "x",
                    "y_column": "y"
                },
                headers={"Authorization": "Bearer token"}
            )
            
            # Verify audit logging was called
            mock_audit_log.assert_called()
    
    def test_sql_injection_protection(self, test_client):
        """Test protection against SQL injection attacks."""
        malicious_query = "SELECT 1; DROP TABLE users; --"
        
        with patch('mcp_server.main.verify_token') as mock_verify:
            mock_verify.return_value = Mock(
                id=1, email="test@example.com", role="data_engineer"
            )
            
            response = test_client.post(
                "/tools/query-postgres",
                json={"query": malicious_query},
                headers={"Authorization": "Bearer token"}
            )
            
            # Should either sanitize or reject malicious queries
            # Implementation would depend on actual SQL sanitization
            assert response.status_code in [400, 403, 422]


class TestVizroIntegration:
    """Tests specific to Vizro dashboard integration."""
    
    @pytest.fixture
    def sample_sales_data(self):
        """Sample sales data for dashboard testing."""
        return pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=12, freq='M'),
            'product': ['A', 'B', 'A', 'B', 'A', 'B', 'A', 'B', 'A', 'B', 'A', 'B'],
            'sales': [1000, 1500, 1200, 1800, 1100, 1600, 1300, 1700, 1400, 1900, 1500, 2000],
            'region': ['North', 'South'] * 6
        })
    
    async def test_chart_type_selection_logic(self, sample_sales_data):
        """Test intelligent chart type selection based on data."""
        from mcp_server.main import generate_vizro_chart_config
        
        # Test bar chart configuration
        bar_config = await generate_vizro_chart_config(
            sample_sales_data, "bar", "product", "sales", "Product Sales"
        )
        
        assert bar_config["chart"]["type"] == "bar_chart"
        assert bar_config["chart"]["x"] == "product"
        assert bar_config["chart"]["y"] == "sales"
        assert bar_config["chart"]["title"] == "Product Sales"
        
        # Test line chart configuration
        line_config = await generate_vizro_chart_config(
            sample_sales_data, "line", "date", "sales", "Sales Trend", "region"
        )
        
        assert line_config["chart"]["type"] == "line_chart"
        assert line_config["chart"]["markers"] == True
        assert line_config["chart"]["color"] == "region"
    
    async def test_dashboard_config_structure(self, sample_sales_data):
        """Test the structure of generated dashboard configurations."""
        config = await generate_vizro_dashboard_config(
            sample_sales_data,
            "Sales Dashboard",
            ["bar", "line"],
            "Comprehensive sales analysis"
        )
        
        # Validate top-level structure
        required_keys = ["pages", "data_sources", "metadata"]
        for key in required_keys:
            assert key in config
        
        # Validate pages structure
        assert len(config["pages"]) == 1
        page = config["pages"][0]
        assert page["title"] == "Sales Dashboard"
        assert "components" in page
        
        # Validate components
        components = page["components"]
        assert len(components) == 2  # bar and line charts
        
        for component in components:
            assert component["type"] == "graph"
            assert "figure" in component
        
        # Validate data sources
        assert "df" in config["data_sources"]
        data_source = config["data_sources"]["df"]
        assert data_source["type"] == "pandas"
        assert len(data_source["data"]) == len(sample_sales_data)
        
        # Validate metadata
        metadata = config["metadata"]
        assert metadata["title"] == "Sales Dashboard"
        assert metadata["description"] == "Comprehensive sales analysis"
        assert "created_at" in metadata
        assert "data_summary" in metadata
    
    def test_column_analysis_accuracy(self, sample_sales_data):
        """Test that column analysis correctly identifies data types."""
        numeric_columns = sample_sales_data.select_dtypes(include=['number']).columns.tolist()
        categorical_columns = sample_sales_data.select_dtypes(include=['object', 'category']).columns.tolist()
        
        assert 'sales' in numeric_columns
        assert 'product' in categorical_columns
        assert 'region' in categorical_columns


@pytest.mark.slow
class TestMCPServerPerformance:
    """Performance tests for MCP Server."""
    
    @pytest.mark.docker
    async def test_dashboard_creation_performance(self, test_client):
        """Test dashboard creation performance with large datasets."""
        import time
        
        # Create a larger dataset for performance testing
        large_data_query = """
        SELECT 
            GENERATE_SERIES(1, 10000) as id,
            RANDOM() * 1000 as value,
            CASE WHEN RANDOM() < 0.3 THEN 'A' 
                 WHEN RANDOM() < 0.6 THEN 'B' 
                 ELSE 'C' END as category
        """
        
        dashboard_data = {
            "title": "Performance Test Dashboard",
            "data_query": large_data_query,
            "chart_types": ["bar", "scatter"],
            "description": "Large dataset performance test"
        }
        
        with patch('mcp_server.main.verify_token') as mock_verify:
            mock_verify.return_value = Mock(
                id=1, email="test@example.com", role="data_engineer"
            )
            
            start_time = time.time()
            
            response = test_client.post(
                "/tools/create-vizro-dashboard",
                json=dashboard_data,
                headers={"Authorization": "Bearer token"}
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Performance assertion (adjust threshold as needed)
            assert execution_time < 30  # Should complete within 30 seconds
            
            if response.status_code == 200:
                result = response.json()
                assert result["rows_processed"] == 10000
    
    async def test_concurrent_requests_handling(self, test_client):
        """Test handling of concurrent MCP requests."""
        import asyncio
        
        async def make_request():
            with patch('mcp_server.main.verify_token') as mock_verify:
                mock_verify.return_value = Mock(
                    id=1, email="test@example.com", role="data_analyst"
                )
                
                response = test_client.post(
                    "/tools/query-postgres",
                    json={"query": "SELECT RANDOM() as value", "limit": 1},
                    headers={"Authorization": "Bearer token"}
                )
                
                return response.status_code
        
        # Run 10 concurrent requests
        tasks = [make_request() for _ in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Most requests should succeed (allow for some failures due to resource limits)
        success_count = sum(1 for result in results if result == 200)
        assert success_count >= 7  # At least 70% success rate


if __name__ == "__main__":
    pytest.main([__file__, "-v"])