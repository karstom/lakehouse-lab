#!/usr/bin/env python3
"""
Lakehouse Lab Authentication Service

Provides OAuth and local authentication for the Lakehouse Lab stack.
Supports Google, Microsoft, and GitHub OAuth providers.
"""

import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from authlib.common.security import generate_token
import jwt
from passlib.context import CryptContext
import httpx

# Database imports
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# Configuration
from config import Settings, get_settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Global variables
oauth = OAuth()
engine = None
async_session = None

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
    global engine, async_session
    
    settings = get_settings()
    logger.info("Starting Lakehouse Authentication Service")
    
    # Initialize database
    try:
        engine = create_async_engine(settings.postgres_url, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        # Initialize database schema
        await init_database()
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    # Initialize OAuth providers
    await init_oauth()
    logger.info("OAuth providers initialized")
    
    # Create default admin user
    await create_default_admin()
    logger.info("Default admin user created")

async def shutdown():
    """Cleanup on shutdown"""
    global engine
    if engine:
        await engine.dispose()
    logger.info("Authentication service shutdown complete")

# FastAPI app with lifespan
app = FastAPI(
    title="Lakehouse Lab Authentication Service",
    description="OAuth and local authentication for Lakehouse Lab",
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

# Add session middleware
app.add_middleware(
    SessionMiddleware, 
    secret_key=os.getenv('JWT_SECRET', 'development-secret-key'),
    max_age=24*3600  # 24 hours
)

# Mount static files for auth UI
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except:
    # Directory doesn't exist in development
    pass

class AuthService:
    """Authentication service class"""
    
    def __init__(self):
        self.settings = get_settings()
    
    async def init_database(self):
        """Initialize database tables"""
        async with engine.begin() as conn:
            # Create users table
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS auth_users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    provider VARCHAR(50) NOT NULL,
                    provider_id VARCHAR(255),
                    role VARCHAR(50) DEFAULT 'data_viewer',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP
                );
            """))
            
            # Create sessions table
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES auth_users(id) ON DELETE CASCADE,
                    session_token VARCHAR(255) UNIQUE NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            # Create audit log table
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS auth_audit (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES auth_users(id) ON DELETE SET NULL,
                    action VARCHAR(100) NOT NULL,
                    ip_address INET,
                    user_agent TEXT,
                    success BOOLEAN NOT NULL,
                    details JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            await conn.commit()
    
    async def get_or_create_user(self, email: str, name: str, provider: str, 
                                provider_id: str = None) -> Dict:
        """Get existing user or create new one"""
        async with async_session() as session:
            # Check for existing user
            result = await session.execute(
                text("SELECT * FROM auth_users WHERE email = :email"),
                {"email": email}
            )
            user = result.fetchone()
            
            if user:
                # Update last login
                await session.execute(
                    text("UPDATE auth_users SET last_login = CURRENT_TIMESTAMP WHERE id = :user_id"),
                    {"user_id": user.id}
                )
                await session.commit()
                
                return {
                    'id': user.id,
                    'email': user.email,
                    'name': user.name,
                    'provider': user.provider,
                    'role': user.role,
                    'is_active': user.is_active
                }
            else:
                # Create new user
                role = self.determine_user_role(email, provider)
                result = await session.execute(
                    text("""
                        INSERT INTO auth_users (email, name, provider, provider_id, role, last_login)
                        VALUES (:email, :name, :provider, :provider_id, :role, CURRENT_TIMESTAMP)
                        RETURNING *
                    """),
                    {
                        "email": email,
                        "name": name,
                        "provider": provider,
                        "provider_id": provider_id,
                        "role": role
                    }
                )
                new_user = result.fetchone()
                await session.commit()
                
                logger.info(f"Created new user: {email} with role {role}")
                
                return {
                    'id': new_user.id,
                    'email': new_user.email,
                    'name': new_user.name,
                    'provider': new_user.provider,
                    'role': new_user.role,
                    'is_active': new_user.is_active
                }
    
    def determine_user_role(self, email: str, provider: str) -> str:
        """Determine user role based on email and provider"""
        settings = self.settings
        
        # Check admin emails
        admin_emails = [e.strip() for e in settings.admin_emails.split(',') if e.strip()]
        if email in admin_emails:
            return 'admin'
        
        # Check company domain
        domain = email.split('@')[1] if '@' in email else ''
        if settings.company_domain and domain.lower() == settings.company_domain.lower():
            return 'data_analyst'
        
        # Default role
        return 'data_viewer'
    
    async def create_session(self, user_id: int) -> str:
        """Create user session and return token"""
        token = generate_token(32)
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        async with async_session() as session:
            await session.execute(
                text("""
                    INSERT INTO auth_sessions (user_id, session_token, expires_at)
                    VALUES (:user_id, :token, :expires_at)
                """),
                {
                    "user_id": user_id,
                    "token": token,
                    "expires_at": expires_at
                }
            )
            await session.commit()
        
        return token
    
    async def validate_session(self, token: str) -> Optional[Dict]:
        """Validate session token and return user info"""
        async with async_session() as session:
            result = await session.execute(
                text("""
                    SELECT u.*, s.expires_at
                    FROM auth_users u
                    JOIN auth_sessions s ON u.id = s.user_id
                    WHERE s.session_token = :token AND s.expires_at > CURRENT_TIMESTAMP AND u.is_active = TRUE
                """),
                {"token": token}
            )
            user_session = result.fetchone()
            
            if not user_session:
                return None
            
            # Update last accessed
            await session.execute(
                text("UPDATE auth_sessions SET last_accessed = CURRENT_TIMESTAMP WHERE session_token = :token"),
                {"token": token}
            )
            await session.commit()
            
            return {
                'id': user_session.id,
                'email': user_session.email,
                'name': user_session.name,
                'provider': user_session.provider,
                'role': user_session.role
            }
    
    def create_jwt_token(self, user: Dict) -> str:
        """Create JWT token for user"""
        payload = {
            'user_id': user['id'],
            'email': user['email'],
            'name': user['name'],
            'role': user['role'],
            'provider': user['provider'],
            'exp': datetime.utcnow() + timedelta(hours=24),
            'iat': datetime.utcnow()
        }
        
        return jwt.encode(payload, self.settings.jwt_secret, algorithm='HS256')
    
    async def audit_log(self, user_id: Optional[int], action: str, 
                       ip_address: str, user_agent: str, success: bool, 
                       details: Dict = None):
        """Log authentication events"""
        async with async_session() as session:
            await session.execute(
                text("""
                    INSERT INTO auth_audit (user_id, action, ip_address, user_agent, success, details)
                    VALUES (:user_id, :action, :ip_address, :user_agent, :success, :details)
                """),
                {
                    "user_id": user_id,
                    "action": action,
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "success": success,
                    "details": details
                }
            )
            await session.commit()

# Initialize auth service
auth_service = AuthService()

async def init_database():
    """Initialize database schema"""
    await auth_service.init_database()

async def init_oauth():
    """Initialize OAuth providers"""
    settings = get_settings()
    
    # Google OAuth
    if settings.google_client_id:
        oauth.register(
            name='google',
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            server_metadata_url='https://accounts.google.com/.well-known/openid_configuration',
            client_kwargs={'scope': 'openid email profile'}
        )
        logger.info("Google OAuth configured")
    
    # Microsoft OAuth
    if settings.microsoft_client_id:
        oauth.register(
            name='microsoft',
            client_id=settings.microsoft_client_id,
            client_secret=settings.microsoft_client_secret,
            server_metadata_url=f'https://login.microsoftonline.com/{settings.microsoft_tenant_id}/v2.0/.well-known/openid_configuration',
            client_kwargs={'scope': 'openid email profile'}
        )
        logger.info("Microsoft OAuth configured")
    
    # GitHub OAuth
    if settings.github_client_id:
        oauth.register(
            name='github',
            client_id=settings.github_client_id,
            client_secret=settings.github_client_secret,
            access_token_url='https://github.com/login/oauth/access_token',
            authorize_url='https://github.com/login/oauth/authorize',
            api_base_url='https://api.github.com/',
            client_kwargs={'scope': 'user:email'}
        )
        logger.info("GitHub OAuth configured")

async def create_default_admin():
    """Create default admin user if in local mode"""
    settings = get_settings()
    if settings.auth_mode in ['local_only', 'hybrid']:
        admin_email = settings.default_admin_email
        
        # Check if admin already exists
        async with async_session() as session:
            result = await session.execute(
                text("SELECT id FROM auth_users WHERE email = :email"),
                {"email": admin_email}
            )
            if not result.fetchone():
                # Create admin user
                await session.execute(
                    text("""
                        INSERT INTO auth_users (email, name, provider, role)
                        VALUES (:email, 'Local Admin', 'local', 'admin')
                    """),
                    {"email": admin_email}
                )
                await session.commit()
                logger.info(f"Created default admin user: {admin_email}")

# Routes

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow()}

@app.get("/")
async def root():
    """Authentication portal home page"""
    settings = get_settings()
    
    # Get available OAuth providers
    providers = []
    if settings.google_client_id:
        providers.append({"name": "google", "display": "Google"})
    if settings.microsoft_client_id:
        providers.append({"name": "microsoft", "display": "Microsoft"})
    if settings.github_client_id:
        providers.append({"name": "github", "display": "GitHub"})
    
    # Simple HTML login page
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Lakehouse Lab - Authentication</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 400px; margin: 100px auto; padding: 20px; }}
            .login-container {{ background: #f5f5f5; padding: 30px; border-radius: 10px; }}
            .oauth-button {{ display: block; width: 100%; padding: 12px; margin: 10px 0; 
                           background: #007bff; color: white; text-decoration: none; 
                           border-radius: 5px; text-align: center; }}
            .oauth-button:hover {{ background: #0056b3; }}
            .google {{ background: #db4437; }}
            .microsoft {{ background: #00a1f1; }}
            .github {{ background: #333; }}
            h1 {{ text-align: center; color: #333; }}
            .subtitle {{ text-align: center; color: #666; margin-bottom: 30px; }}
        </style>
    </head>
    <body>
        <div class="login-container">
            <h1>🏠 Lakehouse Lab</h1>
            <p class="subtitle">Sign in to access your data platform</p>
            
            {"".join([f'<a href="/login/{p["name"]}" class="oauth-button {p["name"]}">Continue with {p["display"]}</a>' for p in providers])}
            
            {f'<a href="/login/local" class="oauth-button">Local Login</a>' if settings.auth_mode in ['local_only', 'hybrid'] else ''}
            
            <p style="text-align: center; margin-top: 20px; font-size: 12px; color: #666;">
                Secure authentication powered by industry standards
            </p>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)

@app.get("/login/{provider}")
async def login(provider: str, request: Request):
    """Initiate OAuth login with provider"""
    if provider not in oauth._clients and provider != 'local':
        raise HTTPException(400, f"Provider {provider} not configured")
    
    if provider == 'local':
        # For local login, redirect to simple form
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Local Login - Lakehouse Lab</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 400px; margin: 100px auto; padding: 20px; }
                .login-form { background: #f5f5f5; padding: 30px; border-radius: 10px; }
                input { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; }
                button { width: 100%; padding: 12px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
                button:hover { background: #0056b3; }
            </style>
        </head>
        <body>
            <div class="login-form">
                <h2>Local Login</h2>
                <form method="post" action="/auth/local">
                    <input type="email" name="email" placeholder="Email" required>
                    <input type="password" name="password" placeholder="Password" required>
                    <button type="submit">Sign In</button>
                </form>
                <p><a href="/">← Back to main login</a></p>
            </div>
        </body>
        </html>
        """)
    
    # OAuth flow
    client = oauth.create_client(provider)
    redirect_uri = request.url_for('auth_callback', provider=provider)
    return await client.authorize_redirect(request, redirect_uri)

@app.get("/auth/{provider}/callback")
async def auth_callback(provider: str, request: Request):
    """Handle OAuth callback"""
    settings = get_settings()
    
    try:
        client = oauth.create_client(provider)
        token = await client.authorize_access_token(request)
        
        # Get user info from provider
        user_info = None
        if provider == 'google':
            user_info = token.get('userinfo')
            if not user_info:
                user_info = await client.parse_id_token(token)
            email = user_info['email']
            name = user_info['name']
            provider_id = user_info['sub']
            
        elif provider == 'microsoft':
            user_info = token.get('userinfo')
            if not user_info:
                user_info = await client.parse_id_token(token)
            email = user_info['email']
            name = user_info['name']
            provider_id = user_info['sub']
            
        elif provider == 'github':
            # GitHub doesn't provide userinfo in token, need to fetch
            async with httpx.AsyncClient() as http_client:
                resp = await http_client.get(
                    'https://api.github.com/user',
                    headers={'Authorization': f'token {token["access_token"]}'}
                )
                github_user = resp.json()
                
                # Get primary email
                resp = await http_client.get(
                    'https://api.github.com/user/emails',
                    headers={'Authorization': f'token {token["access_token"]}'}
                )
                emails = resp.json()
                primary_email = next((e['email'] for e in emails if e['primary']), None)
                
                email = primary_email or github_user.get('email')
                name = github_user.get('name') or github_user.get('login')
                provider_id = str(github_user['id'])
        
        if not email:
            raise HTTPException(400, "Could not retrieve email from provider")
        
        # Create or get user
        user = await auth_service.get_or_create_user(email, name, provider, provider_id)
        
        # Create JWT token
        jwt_token = auth_service.create_jwt_token(user)
        
        # Log successful login
        await auth_service.audit_log(
            user['id'], 
            f'oauth_login_{provider}', 
            request.client.host, 
            request.headers.get('user-agent', ''), 
            True,
            {'provider': provider}
        )
        
        # Redirect to main app with token
        host_ip = os.getenv('HOST_IP', 'localhost')
        return RedirectResponse(
            url=f"http://{host_ip}:9092/login-success?token={jwt_token}",
            status_code=302
        )
        
    except Exception as e:
        logger.error(f"OAuth callback error for {provider}: {e}")
        
        # Log failed login
        await auth_service.audit_log(
            None, 
            f'oauth_login_{provider}_failed', 
            request.client.host, 
            request.headers.get('user-agent', ''), 
            False,
            {'error': str(e), 'provider': provider}
        )
        
        raise HTTPException(400, f"Authentication failed: {str(e)}")

@app.post("/auth/local")
async def local_auth(request: Request):
    """Handle local authentication"""
    form = await request.form()
    email = form.get('email')
    password = form.get('password')
    
    if not email or not password:
        raise HTTPException(400, "Email and password required")
    
    # For now, just check if it's the admin user with any password
    # In production, you'd verify against hashed passwords
    settings = get_settings()
    admin_emails = [e.strip() for e in settings.admin_emails.split(',') if e.strip()]
    
    if email in admin_emails:
        # Get or create admin user
        user = await auth_service.get_or_create_user(email, "Local Admin", "local")
        
        # Create JWT token
        jwt_token = auth_service.create_jwt_token(user)
        
        # Log successful login
        await auth_service.audit_log(
            user['id'], 
            'local_login', 
            request.client.host, 
            request.headers.get('user-agent', ''), 
            True
        )
        
        # Redirect to main app with token
        host_ip = os.getenv('HOST_IP', 'localhost')
        return RedirectResponse(
            url=f"http://{host_ip}:9092/login-success?token={jwt_token}",
            status_code=302
        )
    else:
        # Log failed login
        await auth_service.audit_log(
            None, 
            'local_login_failed', 
            request.client.host, 
            request.headers.get('user-agent', ''), 
            False,
            {'email': email}
        )
        
        raise HTTPException(401, "Invalid credentials")

@app.post("/api/verify-token")
async def verify_token(request: Request):
    """Verify JWT token and return user info"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            raise HTTPException(401, "Missing or invalid authorization header")
        
        token = auth_header[7:]  # Remove 'Bearer '
        settings = get_settings()
        
        payload = jwt.decode(token, settings.jwt_secret, algorithms=['HS256'])
        
        return {
            'valid': True,
            'user': {
                'id': payload['user_id'],
                'email': payload['email'],
                'name': payload['name'],
                'role': payload['role'],
                'provider': payload['provider']
            }
        }
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

@app.get("/api/user/profile")
async def get_user_profile(request: Request):
    """Get current user profile"""
    # This endpoint would be called by other services to get user info
    token_info = await verify_token(request)
    return token_info['user']

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv('PORT', 8080))
    host = os.getenv('HOST', '0.0.0.0')
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=os.getenv('ENVIRONMENT') == 'development',
        log_level="info"
    )