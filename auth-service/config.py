"""
Configuration management for Lakehouse Lab Authentication Service
"""

import os
from typing import Optional
from pydantic import BaseSettings, Field
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings"""
    
    # Core configuration
    environment: str = Field(default="production", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8080, env="PORT")
    
    # JWT configuration
    jwt_secret: str = Field(..., env="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_expiration_hours: int = Field(default=24, env="JWT_EXPIRATION_HOURS")
    
    # Authentication mode
    auth_mode: str = Field(default="hybrid", env="AUTH_MODE")  # local_only, oauth, hybrid
    
    # Database configuration
    postgres_url: str = Field(..., env="POSTGRES_URL")
    
    # Local authentication
    default_admin_email: str = Field(default="admin@localhost", env="DEFAULT_ADMIN_EMAIL")
    admin_emails: str = Field(default="admin@localhost", env="ADMIN_EMAILS")
    company_domain: Optional[str] = Field(default=None, env="COMPANY_DOMAIN")
    
    # OAuth Providers
    google_client_id: Optional[str] = Field(default=None, env="GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = Field(default=None, env="GOOGLE_CLIENT_SECRET")
    
    microsoft_client_id: Optional[str] = Field(default=None, env="MICROSOFT_CLIENT_ID")
    microsoft_client_secret: Optional[str] = Field(default=None, env="MICROSOFT_CLIENT_SECRET")
    microsoft_tenant_id: str = Field(default="common", env="MICROSOFT_TENANT_ID")
    
    github_client_id: Optional[str] = Field(default=None, env="GITHUB_CLIENT_ID")
    github_client_secret: Optional[str] = Field(default=None, env="GITHUB_CLIENT_SECRET")
    github_allowed_orgs: Optional[str] = Field(default=None, env="GITHUB_ALLOWED_ORGS")
    
    # External service URLs
    host_ip: str = Field(default="localhost", env="HOST_IP")
    
    # Security settings
    session_duration_hours: int = Field(default=24, env="SESSION_DURATION_HOURS")
    max_login_attempts: int = Field(default=5, env="MAX_LOGIN_ATTEMPTS")
    rate_limit_per_minute: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


def get_oauth_providers_config() -> dict:
    """Get enabled OAuth providers configuration"""
    settings = get_settings()
    providers = {}
    
    if settings.google_client_id:
        providers['google'] = {
            'display_name': 'Google',
            'client_id': settings.google_client_id,
            'enabled': True
        }
    
    if settings.microsoft_client_id:
        providers['microsoft'] = {
            'display_name': 'Microsoft',
            'client_id': settings.microsoft_client_id,
            'enabled': True
        }
    
    if settings.github_client_id:
        providers['github'] = {
            'display_name': 'GitHub',
            'client_id': settings.github_client_id,
            'enabled': True
        }
    
    return providers


def is_provider_enabled(provider: str) -> bool:
    """Check if OAuth provider is enabled"""
    settings = get_settings()
    
    if provider == 'google':
        return bool(settings.google_client_id and settings.google_client_secret)
    elif provider == 'microsoft':
        return bool(settings.microsoft_client_id and settings.microsoft_client_secret)
    elif provider == 'github':
        return bool(settings.github_client_id and settings.github_client_secret)
    
    return False


def get_redirect_url(provider: str) -> str:
    """Get OAuth redirect URL for provider"""
    settings = get_settings()
    base_url = f"http://{settings.host_ip}:9091"
    return f"{base_url}/auth/{provider}/callback"