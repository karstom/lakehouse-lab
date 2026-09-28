#!/usr/bin/env python3
"""
JupyterHub Configuration for Lakehouse Lab
Multi-user Jupyter environment with Spark integration
"""

import os
import pwd
import subprocess
from dockerspawner import DockerSpawner

#------------------------------------------------------------------------------
# JupyterHub Configuration
#------------------------------------------------------------------------------

# Basic JupyterHub settings
c.JupyterHub.ip = '0.0.0.0'
c.JupyterHub.port = 8000
c.JupyterHub.hub_ip = '0.0.0.0'
c.JupyterHub.hub_port = 8081

# Database configuration - use SQLite for JupyterHub
c.JupyterHub.db_url = 'sqlite:////srv/jupyterhub/jupyterhub.db'

# Admin users
c.Authenticator.admin_users = {'admin'}

# Allow named servers (optional - users can create multiple servers)
c.JupyterHub.allow_named_servers = True

#------------------------------------------------------------------------------
# Spawner Configuration - Docker
#------------------------------------------------------------------------------

c.JupyterHub.spawner_class = DockerSpawner

# Docker image for user notebooks (with Spark support)
c.DockerSpawner.image = 'quay.io/jupyter/pyspark-notebook:spark-3.5.0'

# Network configuration
c.DockerSpawner.network_name = os.environ.get('DOCKER_NETWORK_NAME', 'lakehouse-lab_lakehouse')
c.DockerSpawner.use_internal_ip = True
c.DockerSpawner.remove = True

# Notebook configuration
c.DockerSpawner.notebook_dir = '/home/jovyan'
c.DockerSpawner.default_url = '/lab'

# Environment variables to pass to user containers
c.DockerSpawner.environment = {
    'JUPYTER_ENABLE_LAB': 'yes',
    'SPARK_MASTER': os.environ.get('SPARK_MASTER', 'spark://spark-master:7077'),
    'MINIO_ROOT_USER': os.environ.get('MINIO_ROOT_USER', 'admin'),
    'MINIO_ROOT_PASSWORD': os.environ.get('MINIO_ROOT_PASSWORD', ''),
    'SPARK_DRIVER_MEMORY': '2g',
    'SPARK_EXECUTOR_MEMORY': '2g', 
    'SPARK_EXECUTOR_CORES': '2',
    'SPARK_HOME': '/usr/local/spark',
    'PYTHONPATH': '/usr/local/spark/python:/usr/local/spark/python/lib/py4j-0.10.9.7-src.zip',
    'PYSPARK_PYTHON': '/opt/conda/bin/python',
    'PYSPARK_DRIVER_PYTHON': '/opt/conda/bin/python',
}

# Use environment variable to trigger package installation
c.DockerSpawner.environment['INSTALL_LAKEHOUSE_PACKAGES'] = '1'

# Volume mounts - preserve shared access from original Jupyter setup
# Use absolute host paths that DockerSpawner can mount into user containers
lakehouse_root = os.environ.get('LAKEHOUSE_ROOT', '/root/lakehouse-test/lakehouse-lab/lakehouse-data')
c.DockerSpawner.volumes = {
    # User's private workspace (replaces original /notebooks)
    f'{lakehouse_root}/jupyterhub/{{username}}': '/home/jovyan/work',
    
    # Shared read-only data (same as original setup)  
    f'{lakehouse_root}/notebooks': {'bind': '/home/jovyan/shared', 'mode': 'ro'},
    
    # Shared notebooks for collaboration
    f'{lakehouse_root}/shared-notebooks': '/home/jovyan/shared-notebooks',
}

# Resource limits per user
c.DockerSpawner.mem_limit = '4G'
c.DockerSpawner.cpu_limit = 2.0

# Increase startup timeout for package installation
c.DockerSpawner.start_timeout = 300  # 5 minutes
c.DockerSpawner.http_timeout = 120   # 2 minutes

#------------------------------------------------------------------------------
# Authentication - Native JupyterHub users
#------------------------------------------------------------------------------

# Use the default PAM authenticator initially
# This can be extended to LDAP/OAuth later
c.JupyterHub.authenticator_class = 'jupyterhub.auth.PAMAuthenticator'

# Create system users automatically if they don't exist
c.Authenticator.create_system_users = True

#------------------------------------------------------------------------------
# Services and API
#------------------------------------------------------------------------------

# Enable admin panel
c.JupyterHub.admin_access = True

# Set default URL for users after login
c.JupyterHub.default_url = '/hub/home'

# API tokens for external services (for user provisioning script)
c.JupyterHub.services = [
    {
        'name': 'admin-api',
        'api_token': os.environ.get('JUPYTERHUB_API_TOKEN', 'lakehouse-admin-token-change-me'),
        'admin': True,
    }
]

#------------------------------------------------------------------------------
# Logging
#------------------------------------------------------------------------------

c.Application.log_level = 'INFO'
c.JupyterHub.log_level = 'INFO'

#------------------------------------------------------------------------------
# Custom User Creation Hook
#------------------------------------------------------------------------------

def pre_spawn_hook(spawner):
    """Hook to run before spawning user container"""
    username = spawner.user.name
    
    # Ensure user has a home directory
    user_dir = f"/srv/jupyterhub/users/{username}"
    os.makedirs(user_dir, exist_ok=True)
    
    # Create startup script to install packages
    startup_script_path = os.path.join(user_dir, 'install_packages.sh')
    startup_script_content = """#!/bin/bash
set -e
echo "🚀 Installing lakehouse dependencies..."

# Install core packages first
pip install --no-cache-dir --quiet \
    duckdb==1.3.2 \
    duckdb-engine==0.17.0 \
    boto3==1.35.5 \
    s3fs>=2023.1.0 \
    pyarrow==14.0.2 \
    plotly>=5.17.0 \
    seaborn>=0.12.0 \
    python-dotenv>=1.0.0 \
    openpyxl>=3.0.0 \
    requests>=2.28.0

# Install ML packages
pip install --no-cache-dir --quiet \
    scikit-learn>=1.3.0 \
    umap-learn>=0.5.0

# Install visualization packages (these might fail, so continue on error)
pip install --no-cache-dir --quiet vizro>=0.1.0 || echo "⚠️ Vizro installation failed, skipping..."
pip install --no-cache-dir --quiet lancedb>=0.1.0 || echo "⚠️ LanceDB installation failed, skipping..."

echo "✅ Core dependencies installed successfully!"
touch /home/jovyan/.packages_installed
"""
    
    # Write the startup script
    with open(startup_script_path, 'w') as f:
        f.write(startup_script_content)
    os.chmod(startup_script_path, 0o755)
    
    # Set environment variables specific to user
    spawner.environment.update({
        'JUPYTERHUB_USER': username,
        'USER': username,
    })

c.DockerSpawner.pre_spawn_hook = pre_spawn_hook

#------------------------------------------------------------------------------
# Security Settings
#------------------------------------------------------------------------------

# Cookie secret
c.JupyterHub.cookie_secret_file = '/srv/jupyterhub/cookie_secret'

# SSL (disabled for internal use)
c.JupyterHub.ssl_cert = ''
c.JupyterHub.ssl_key = ''

print("JupyterHub configuration loaded successfully!")
print(f"Hub will run on port {c.JupyterHub.port}")
print(f"Database: {c.JupyterHub.db_url}")
print(f"Docker network: {c.DockerSpawner.network_name}")
print(f"Admin users: {c.Authenticator.admin_users}")