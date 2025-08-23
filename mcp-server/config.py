"""
Configuration management for Lakehouse Lab MCP Server
"""

import os
from typing import Optional
from pydantic import BaseSettings, Field
from functools import lru_cache


class Settings(BaseSettings):
    """MCP Server settings"""
    
    # Core configuration
    environment: str = Field(default="production", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    
    # Authentication
    auth_service_url: str = Field(..., env="AUTH_SERVICE_URL")
    jwt_secret: str = Field(..., env="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    
    # Database configuration
    postgres_url: str = Field(..., env="POSTGRES_URL")
    
    # MinIO/S3 configuration
    minio_endpoint: str = Field(..., env="MINIO_ENDPOINT")
    minio_access_key: str = Field(..., env="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(..., env="MINIO_SECRET_KEY")
    
    # LanceDB configuration
    lancedb_url: str = Field(..., env="LANCEDB_URL")
    
    # Spark configuration
    spark_master_url: Optional[str] = Field(default=None, env="SPARK_MASTER_URL")
    
    # Security settings
    rate_limit_enabled: bool = Field(default=True, env="RATE_LIMIT_ENABLED")
    max_query_size: str = Field(default="100MB", env="MAX_QUERY_SIZE")
    max_execution_time: int = Field(default=300, env="MAX_EXECUTION_TIME")
    
    # Logging
    log_level: str = Field(default="INFO", env="MCP_LOG_LEVEL")
    audit_enabled: bool = Field(default=True, env="MCP_AUDIT_ENABLED")
    
    # AI/ML features (optional)
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    enable_ai_insights: bool = Field(default=False, env="ENABLE_AI_INSIGHTS")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


def get_database_url() -> str:
    """Get database URL for connections"""
    return get_settings().postgres_url


def get_minio_config() -> dict:
    """Get MinIO configuration"""
    settings = get_settings()
    return {
        'endpoint': settings.minio_endpoint,
        'access_key': settings.minio_access_key,
        'secret_key': settings.minio_secret_key
    }


def is_ai_enabled() -> bool:
    """Check if AI features are enabled"""
    settings = get_settings()
    return settings.enable_ai_insights and bool(settings.openai_api_key)