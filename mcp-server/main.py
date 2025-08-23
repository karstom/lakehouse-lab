#!/usr/bin/env python3
"""
Lakehouse Lab MCP Server

Provides AI-powered data access and analytics through the Model Context Protocol.
Integrates with authentication proxy for security and audit.
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from mcp import Server, types
import httpx
import jwt
from pydantic import BaseModel, Field

# Data access imports
import asyncpg
import boto3
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import pandas as pd
import duckdb
import lancedb

# Visualization imports
import plotly.graph_objects as go
import plotly.express as px
from vizro import Vizro
from vizro.models import Dashboard, Page, Graph, Card
from vizro.tables import dash_data_table
import json

# Configuration
from config import Settings, get_settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variables
engine = None
async_session = None
s3_client = None
lance_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    await startup()
    try:
        yield
    finally:
        # Shutdown
        await shutdown()

async def startup():
    """Initialize the application"""
    global engine, async_session, s3_client, lance_client
    
    settings = get_settings()
    logger.info("Starting Lakehouse Lab MCP Server")
    
    try:
        # Initialize database connection
        engine = create_async_engine(settings.postgres_url, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        logger.info("PostgreSQL connection initialized")
        
        # Initialize S3 client
        s3_client = boto3.client(
            's3',
            endpoint_url=settings.minio_endpoint,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key
        )
        logger.info("MinIO S3 client initialized")
        
        # Initialize LanceDB client
        lance_client = httpx.AsyncClient(base_url=settings.lancedb_url)
        logger.info("LanceDB client initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize MCP server: {e}")
        raise

async def shutdown():
    """Cleanup on shutdown"""
    global engine, lance_client
    
    if engine:
        await engine.dispose()
    
    if lance_client:
        await lance_client.aclose()
    
    logger.info("MCP server shutdown complete")

# FastAPI app with lifespan
app = FastAPI(
    title="Lakehouse Lab MCP Server",
    description="AI-powered data access and analytics API",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API
class QueryRequest(BaseModel):
    query: str = Field(..., description="SQL query to execute")
    params: Optional[Dict[str, Any]] = Field(default=None, description="Query parameters")
    limit: Optional[int] = Field(default=1000, description="Result limit")

class VectorSearchRequest(BaseModel):
    table: str = Field(..., description="Vector table name")
    query_text: str = Field(..., description="Text to search for")
    limit: Optional[int] = Field(default=10, description="Number of results")

class DataInsightRequest(BaseModel):
    table: str = Field(..., description="Table to analyze")
    analysis_type: str = Field(default="summary", description="Type of analysis")

class VizroDashboardRequest(BaseModel):
    title: str = Field(..., description="Dashboard title")
    data_query: str = Field(..., description="SQL query to get dashboard data")
    chart_types: List[str] = Field(default=["bar"], description="Types of charts to create")
    description: Optional[str] = Field(default=None, description="Natural language description of desired dashboard")

class VizroChartRequest(BaseModel):
    chart_type: str = Field(..., description="Type of chart (bar, line, scatter, etc.)")
    data_query: str = Field(..., description="SQL query to get chart data") 
    x_column: str = Field(..., description="X-axis column")
    y_column: str = Field(..., description="Y-axis column")
    title: Optional[str] = Field(default=None, description="Chart title")
    color_column: Optional[str] = Field(default=None, description="Column for color grouping")

class User(BaseModel):
    id: int
    email: str
    name: str
    role: str
    provider: str

# Authentication middleware
async def verify_token(request: Request) -> User:
    """Verify JWT token and return user info"""
    settings = get_settings()
    
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        # Try to verify with auth service
        auth_service_url = settings.auth_service_url
        if auth_service_url:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{auth_service_url}/api/verify-token",
                    headers={"Authorization": auth_header or ""}
                )
                if response.status_code == 200:
                    user_data = response.json()['user']
                    return User(**user_data)
        
        raise HTTPException(401, "Authentication required")
    
    token = auth_header[7:]  # Remove 'Bearer '
    
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=['HS256'])
        return User(
            id=payload['user_id'],
            email=payload['email'],
            name=payload['name'],
            role=payload['role'],
            provider=payload['provider']
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

# Permission checking
def check_permission(user: User, operation: str, resource: str = None) -> bool:
    """Check if user has permission for operation"""
    
    # Admin can do everything
    if user.role == 'admin':
        return True
    
    # Define permission matrix
    permissions = {
        'data_viewer': {
            'query_postgres': True,
            'search_vectors': True,
            'analyze_s3_data': True,
            'write_data': False,
            'create_tables': False,
            'create_dashboards': False,
            'admin_operations': False
        },
        'data_analyst': {
            'query_postgres': True,
            'search_vectors': True,
            'analyze_s3_data': True,
            'write_data': True,
            'create_tables': False,
            'create_dashboards': True,
            'admin_operations': False
        },
        'data_engineer': {
            'query_postgres': True,
            'search_vectors': True,
            'analyze_s3_data': True,
            'write_data': True,
            'create_tables': True,
            'create_dashboards': True,
            'admin_operations': False
        }
    }
    
    user_permissions = permissions.get(user.role, {})
    return user_permissions.get(operation, False)

# Audit logging
async def audit_log(user: User, operation: str, resource: str, 
                   success: bool, details: Dict = None):
    """Log operation for audit"""
    try:
        async with async_session() as session:
            await session.execute(
                text("""
                    INSERT INTO mcp_audit_log (
                        user_id, user_email, operation, resource, success, details, timestamp
                    ) VALUES (
                        :user_id, :user_email, :operation, :resource, :success, :details, :timestamp
                    )
                """),
                {
                    'user_id': user.id,
                    'user_email': user.email,
                    'operation': operation,
                    'resource': resource,
                    'success': success,
                    'details': details,
                    'timestamp': datetime.utcnow()
                }
            )
            await session.commit()
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")

# MCP Tools Implementation
class LakehouseTools:
    """MCP tools for Lakehouse Lab data access"""
    
    @staticmethod
    async def query_postgres(user: User, query: str, params: Dict = None, limit: int = 1000) -> Dict:
        """Execute PostgreSQL query with security checks"""
        
        if not check_permission(user, 'query_postgres'):
            raise HTTPException(403, "Insufficient permissions for PostgreSQL queries")
        
        # Basic SQL injection protection (in production, use proper query parsing)
        dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'CREATE', 'ALTER', 'TRUNCATE']
        if user.role not in ['admin', 'data_engineer']:
            for keyword in dangerous_keywords:
                if keyword.upper() in query.upper():
                    raise HTTPException(403, f"Operation '{keyword}' not permitted for role '{user.role}'")
        
        try:
            async with async_session() as session:
                result = await session.execute(text(query), params or {})
                
                # Handle different result types
                if result.returns_rows:
                    rows = result.fetchmany(limit)
                    columns = list(result.keys()) if rows else []
                    data = [dict(zip(columns, row)) for row in rows]
                    
                    await audit_log(user, 'query_postgres', query[:100], True, {
                        'rows_returned': len(data),
                        'limit': limit
                    })
                    
                    return {
                        'success': True,
                        'data': data,
                        'columns': columns,
                        'row_count': len(data)
                    }
                else:
                    await session.commit()
                    await audit_log(user, 'query_postgres', query[:100], True, {
                        'operation': 'non_select'
                    })
                    
                    return {
                        'success': True,
                        'message': 'Query executed successfully',
                        'affected_rows': result.rowcount
                    }
                    
        except Exception as e:
            await audit_log(user, 'query_postgres', query[:100], False, {
                'error': str(e)
            })
            raise HTTPException(400, f"Query execution failed: {str(e)}")
    
    @staticmethod
    async def search_vectors(user: User, table: str, query_text: str, limit: int = 10) -> Dict:
        """Search vectors in LanceDB"""
        
        if not check_permission(user, 'search_vectors'):
            raise HTTPException(403, "Insufficient permissions for vector search")
        
        try:
            # This would interface with LanceDB
            # For now, return a mock response
            await audit_log(user, 'search_vectors', table, True, {
                'query_text': query_text[:100],
                'limit': limit
            })
            
            return {
                'success': True,
                'results': [
                    {
                        'id': f'doc_{i}',
                        'content': f'Mock result {i} for query: {query_text}',
                        'score': 0.9 - (i * 0.1),
                        'metadata': {'source': f'document_{i}.txt'}
                    }
                    for i in range(min(limit, 5))
                ],
                'query': query_text,
                'table': table
            }
            
        except Exception as e:
            await audit_log(user, 'search_vectors', table, False, {
                'error': str(e)
            })
            raise HTTPException(400, f"Vector search failed: {str(e)}")
    
    @staticmethod
    async def analyze_s3_data(user: User, bucket: str, prefix: str = '') -> Dict:
        """Analyze data in S3 using DuckDB"""
        
        if not check_permission(user, 'analyze_s3_data'):
            raise HTTPException(403, "Insufficient permissions for S3 data analysis")
        
        try:
            # List objects in S3
            objects = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
            files = [obj['Key'] for obj in objects.get('Contents', []) if obj['Key'].endswith(('.csv', '.parquet', '.json'))]
            
            # Basic analysis using DuckDB (mock for now)
            analysis = {
                'bucket': bucket,
                'prefix': prefix,
                'file_count': len(files),
                'file_types': {},
                'total_size_mb': sum(obj['Size'] for obj in objects.get('Contents', [])) / (1024 * 1024),
                'sample_files': files[:10]
            }
            
            # Count file types
            for file in files:
                ext = file.split('.')[-1].lower()
                analysis['file_types'][ext] = analysis['file_types'].get(ext, 0) + 1
            
            await audit_log(user, 'analyze_s3_data', f'{bucket}/{prefix}', True, {
                'file_count': len(files)
            })
            
            return {
                'success': True,
                'analysis': analysis
            }
            
        except Exception as e:
            await audit_log(user, 'analyze_s3_data', f'{bucket}/{prefix}', False, {
                'error': str(e)
            })
            raise HTTPException(400, f"S3 data analysis failed: {str(e)}")
    
    @staticmethod
    async def generate_insights(user: User, table: str, analysis_type: str = 'summary') -> Dict:
        """Generate data insights"""
        
        if not check_permission(user, 'query_postgres'):
            raise HTTPException(403, "Insufficient permissions for data insights")
        
        try:
            # This would use AI/ML to generate insights
            # For now, return mock insights
            insights = {
                'table': table,
                'analysis_type': analysis_type,
                'insights': [
                    f"Table '{table}' appears to have consistent data patterns",
                    f"Recommended analysis approach for '{analysis_type}' analysis",
                    "Data quality metrics suggest good data integrity"
                ],
                'recommendations': [
                    "Consider adding indexes for better query performance",
                    "Regular data validation checks recommended",
                    "Monitor for data freshness and completeness"
                ],
                'generated_at': datetime.utcnow().isoformat()
            }
            
            await audit_log(user, 'generate_insights', table, True, {
                'analysis_type': analysis_type
            })
            
            return {
                'success': True,
                'insights': insights
            }
            
        except Exception as e:
            await audit_log(user, 'generate_insights', table, False, {
                'error': str(e)
            })
            raise HTTPException(400, f"Insight generation failed: {str(e)}")

# Initialize tools
lakehouse_tools = LakehouseTools()

# Routes
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow()}

@app.get("/")
async def root():
    """MCP server information"""
    return {
        "name": "Lakehouse Lab MCP Server",
        "version": "1.0.0",
        "description": "AI-powered data access and analytics API",
        "tools": [
            "query_postgres",
            "search_vectors", 
            "analyze_s3_data",
            "generate_insights"
        ]
    }

@app.post("/tools/query-postgres")
async def query_postgres_endpoint(
    request: QueryRequest,
    user: User = Depends(verify_token)
):
    """Execute PostgreSQL query"""
    return await lakehouse_tools.query_postgres(
        user, request.query, request.params, request.limit
    )

@app.post("/tools/search-vectors")
async def search_vectors_endpoint(
    request: VectorSearchRequest,
    user: User = Depends(verify_token)
):
    """Search vectors in LanceDB"""
    return await lakehouse_tools.search_vectors(
        user, request.table, request.query_text, request.limit
    )

@app.post("/tools/analyze-s3")
async def analyze_s3_endpoint(
    bucket: str,
    prefix: str = "",
    user: User = Depends(verify_token)
):
    """Analyze S3 data"""
    return await lakehouse_tools.analyze_s3_data(user, bucket, prefix)

@app.post("/tools/generate-insights")
async def generate_insights_endpoint(
    request: DataInsightRequest,
    user: User = Depends(verify_token)
):
    """Generate data insights"""
    return await lakehouse_tools.generate_insights(
        user, request.table, request.analysis_type
    )

@app.post("/tools/create-vizro-dashboard")
async def create_vizro_dashboard(
    request: VizroDashboardRequest,
    user: User = Depends(verify_token)
):
    """Create a Vizro dashboard from SQL query and specifications"""
    if not check_permission(user, 'create_dashboards'):
        raise HTTPException(status_code=403, detail="Insufficient permissions for dashboard creation")
    
    await audit_log(user, "create_vizro_dashboard", request.title, True)
    
    try:
        # Execute the data query
        async with async_session() as session:
            result = await session.execute(text(request.data_query))
            data = result.fetchall()
            columns = result.keys()
        
        # Convert to DataFrame
        df = pd.DataFrame(data, columns=columns)
        
        # Generate dashboard configuration
        dashboard_config = await generate_vizro_dashboard_config(
            df, request.title, request.chart_types, request.description
        )
        
        # Save dashboard config to filesystem
        config_path = f"/app/config/dashboards/{request.title.lower().replace(' ', '_')}_dashboard.json"
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, 'w') as f:
            json.dump(dashboard_config, f, indent=2)
        
        return {
            'dashboard_id': request.title.lower().replace(' ', '_'),
            'config_path': config_path,
            'config': dashboard_config,
            'preview_url': f"/vizro/dashboard/{request.title.lower().replace(' ', '_')}",
            'rows_processed': len(df)
        }
        
    except Exception as e:
        await audit_log(user, "create_vizro_dashboard", request.title, False, {'error': str(e)})
        raise HTTPException(status_code=500, detail=f"Dashboard creation failed: {str(e)}")

@app.post("/tools/create-vizro-chart")
async def create_vizro_chart(
    request: VizroChartRequest,
    user: User = Depends(verify_token)
):
    """Create a single Vizro chart from SQL query"""
    if not check_permission(user, 'create_dashboards'):
        raise HTTPException(status_code=403, detail="Insufficient permissions for dashboard creation")
    
    await audit_log(user, "create_vizro_chart", request.chart_type, True)
    
    try:
        # Execute the data query
        async with async_session() as session:
            result = await session.execute(text(request.data_query))
            data = result.fetchall()
            columns = result.keys()
        
        # Convert to DataFrame  
        df = pd.DataFrame(data, columns=columns)
        
        # Generate chart configuration
        chart_config = await generate_vizro_chart_config(
            df, request.chart_type, request.x_column, request.y_column, 
            request.title, request.color_column
        )
        
        return {
            'chart_config': chart_config,
            'data_summary': {
                'rows': len(df),
                'columns': list(df.columns),
                'x_values': df[request.x_column].unique().tolist()[:10] if request.x_column in df.columns else []
            }
        }
        
    except Exception as e:
        await audit_log(user, "create_vizro_chart", request.chart_type, False, {'error': str(e)})
        raise HTTPException(status_code=500, detail=f"Chart creation failed: {str(e)}")

@app.get("/user/permissions")
async def get_user_permissions(user: User = Depends(verify_token)):
    """Get current user permissions"""
    
    operations = ['query_postgres', 'search_vectors', 'analyze_s3_data', 
                 'write_data', 'create_tables', 'admin_operations', 'create_dashboards']
    
    permissions = {
        op: check_permission(user, op) for op in operations
    }
    
    return {
        'user': user.dict(),
        'permissions': permissions
    }

# Vizro helper functions
async def generate_vizro_dashboard_config(
    df: pd.DataFrame, 
    title: str, 
    chart_types: List[str], 
    description: Optional[str] = None
) -> Dict[str, Any]:
    """Generate Vizro dashboard configuration from DataFrame"""
    
    # Analyze DataFrame to suggest appropriate visualizations
    numeric_columns = df.select_dtypes(include=['number']).columns.tolist()
    categorical_columns = df.select_dtypes(include=['object', 'category']).columns.tolist()
    
    charts = []
    
    for i, chart_type in enumerate(chart_types):
        chart_id = f"chart_{i+1}"
        
        if chart_type == "bar" and len(categorical_columns) > 0 and len(numeric_columns) > 0:
            chart_config = {
                "id": chart_id,
                "type": "bar_chart",
                "data_frame": "df",
                "x": categorical_columns[0],
                "y": numeric_columns[0],
                "title": f"{chart_type.title()} Chart - {categorical_columns[0]} vs {numeric_columns[0]}"
            }
        elif chart_type == "line" and len(numeric_columns) >= 2:
            chart_config = {
                "id": chart_id,
                "type": "line_chart", 
                "data_frame": "df",
                "x": numeric_columns[0],
                "y": numeric_columns[1] if len(numeric_columns) > 1 else numeric_columns[0],
                "title": f"{chart_type.title()} Chart - Trend Analysis"
            }
        elif chart_type == "scatter" and len(numeric_columns) >= 2:
            chart_config = {
                "id": chart_id,
                "type": "scatter_chart",
                "data_frame": "df", 
                "x": numeric_columns[0],
                "y": numeric_columns[1],
                "title": f"{chart_type.title()} Chart - Correlation Analysis"
            }
        else:
            # Default to simple bar chart
            chart_config = {
                "id": chart_id,
                "type": "bar_chart",
                "data_frame": "df",
                "x": df.columns[0],
                "y": df.columns[1] if len(df.columns) > 1 else df.columns[0],
                "title": f"Chart {i+1}"
            }
        
        charts.append(chart_config)
    
    # Generate dashboard configuration
    dashboard_config = {
        "pages": [
            {
                "title": title,
                "components": [
                    {
                        "type": "graph",
                        "figure": chart
                    } for chart in charts
                ]
            }
        ],
        "data_sources": {
            "df": {
                "type": "pandas",
                "data": df.to_dict('records'),
                "columns": df.columns.tolist()
            }
        },
        "metadata": {
            "title": title,
            "description": description or f"Dashboard generated from {len(df)} rows of data",
            "created_at": datetime.utcnow().isoformat(),
            "data_summary": {
                "rows": len(df),
                "columns": len(df.columns),
                "numeric_columns": numeric_columns,
                "categorical_columns": categorical_columns
            }
        }
    }
    
    return dashboard_config

async def generate_vizro_chart_config(
    df: pd.DataFrame,
    chart_type: str,
    x_column: str, 
    y_column: str,
    title: Optional[str] = None,
    color_column: Optional[str] = None
) -> Dict[str, Any]:
    """Generate Vizro chart configuration"""
    
    chart_config = {
        "type": f"{chart_type}_chart",
        "data_frame": "df", 
        "x": x_column,
        "y": y_column,
        "title": title or f"{chart_type.title()} Chart: {x_column} vs {y_column}"
    }
    
    if color_column:
        chart_config["color"] = color_column
    
    # Add chart-specific configurations
    if chart_type == "scatter":
        chart_config["size"] = None  # Could be configured based on data
        chart_config["hover_data"] = df.columns.tolist()[:5]  # First 5 columns for hover
    elif chart_type == "line":
        chart_config["markers"] = True
    elif chart_type == "bar":
        chart_config["orientation"] = "v"  # Vertical bars by default
        
    return {
        "chart": chart_config,
        "data": {
            "type": "pandas",
            "data": df.to_dict('records'),
            "columns": df.columns.tolist()
        }
    }

# Initialize MCP Server
mcp_server = Server("lakehouse-lab-mcp")

# Register MCP tools (this would be expanded in a full implementation)
# For now, we're using FastAPI endpoints instead of pure MCP

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv('PORT', 8000))
    host = os.getenv('HOST', '0.0.0.0')
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=os.getenv('ENVIRONMENT') == 'development',
        log_level="info"
    )