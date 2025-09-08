# 🔧 Lakehouse Lab Configuration Guide

**Version 2.1.0** - This guide explains how to configure which services are enabled in your Lakehouse Lab installation for educational environments, including AI-powered services and multi-user JupyterHub environments perfect for classroom and student lab settings.

## Overview

Lakehouse Lab supports selective service installation, making it ideal for educational environments where you need to:
- **Enable only the services you need** to optimize classroom hardware resources
- **Create custom configurations** for different courses and learning objectives
- **Switch between configurations** without rebuilding containers for different class sessions
- **Use preset configurations** for common educational scenarios
- **Support multi-user environments** for student collaboration

## Quick Start

### Using Preset Configurations

The easiest way to configure services is using presets:

```bash
# Minimal setup (8GB RAM) - Core services + Jupyter only
# Perfect for introductory data science courses
./scripts/configure-services.sh preset minimal

# Analytics focus (14GB RAM) - Jupyter + Superset + Vizro
# Ideal for business intelligence and data visualization courses
./scripts/configure-services.sh preset analytics

# ML/AI focus (16GB RAM) - Jupyter + LanceDB + Airflow
# Great for machine learning and advanced data engineering courses
./scripts/configure-services.sh preset ml

# Full installation (20GB RAM) - All data services enabled
# Complete platform for comprehensive data science programs
./scripts/configure-services.sh preset full
```

### Interactive Configuration

For custom service selection:

```bash
./scripts/configure-services.sh interactive
```

This will guide you through enabling/disabling each service individually.

## Service Overview

### Core Services (Always Enabled)
These services cannot be disabled as they form the foundation of the lakehouse:

| Service | Description | RAM |
|---------|-------------|-----|
| **PostgreSQL** | Primary metadata and application database | ~2GB |
| **MinIO** | S3-compatible object storage | ~2GB |
| **Spark Master/Worker** | Distributed data processing engine | ~2GB |
| **Lakehouse-Init** | Data initialization and setup | ~0GB |

### Optional Services (Configurable)

| Service | Description | Port | RAM | Use Case |
|---------|-------------|------|-----|----------|
| **Apache Airflow** | Workflow orchestration and scheduling | 9020 | 4GB | Data pipelines, ETL automation |
| **Apache Superset** | Modern BI and data visualization | 9030 | 4GB | Business dashboards, reporting |
| **JupyterLab** | Single-user data science environment | 9040 | 8GB | Individual data analysis, ML development |
| **JupyterHub** | Multi-user notebook environment | 9041 | 8GB | Team collaboration, user management |
| **Vizro** | Low-code dashboard framework | 9050 | 2GB | Interactive visualizations |
| **LanceDB** | High-performance vector database | 9080 | 3GB | AI/ML, semantic search |
| **Portainer** | Docker container management | 9060 | 0.5GB | System monitoring |
| **Homer** | Service dashboard with links | 9061 | 0.1GB | Easy service access |

## Preset Configurations

### 1. Minimal Configuration
**Best for**: Introductory courses, student laptops, resource-constrained classroom environments
```
✅ Core Services: PostgreSQL, MinIO, Spark
✅ JupyterLab: Data science notebooks
✅ Portainer: Container management
❌ All other services disabled

📊 Resources: ~8GB RAM, 4 CPU cores minimum
🎯 Use case: Introductory data science, learning Spark/lakehouse fundamentals, individual student work
```

### 2. Analytics Configuration  
**Best for**: Business intelligence courses, data visualization classes, reporting workshops
```
✅ Core Services: PostgreSQL, MinIO, Spark
✅ JupyterLab: Data science notebooks
✅ Apache Superset: BI dashboards
✅ Vizro: Interactive dashboards
✅ Portainer: Container management
✅ Homer: Service links
❌ Airflow, LanceDB disabled

📊 Resources: ~14GB RAM, 8 CPU cores recommended
🎯 Use case: Advanced analytics courses, business intelligence programs, dashboard creation workshops
```

### 3. ML/AI Configuration
**Best for**: Machine learning courses, AI workshops, advanced data engineering programs
```
✅ Core Services: PostgreSQL, MinIO, Spark
✅ JupyterLab: Data science notebooks
✅ Apache Airflow: ML pipeline orchestration
✅ LanceDB: Vector database for AI
✅ Portainer: Container management
✅ Homer: Service links
❌ Superset, Vizro disabled

📊 Resources: ~16GB RAM, 8+ CPU cores recommended  
🎯 Use case: Machine learning courses, AI research projects, graduate-level data science programs
```

### 4. Full Configuration
**Best for**: Comprehensive data science programs, capstone projects, advanced coursework
```
✅ All services enabled

📊 Resources: ~20GB RAM, 16+ CPU cores recommended
🎯 Use case: Complete data science curriculum, multi-semester programs, research environments
```

## Configuration Management

### View Current Configuration
```bash
./scripts/configure-services.sh show
```

### Validate Configuration
Checks for dependency conflicts:
```bash
./scripts/configure-services.sh validate
```

### Get Resource Recommendations
See system requirements for current configuration:
```bash
./scripts/configure-services.sh recommend
```

### Reset to Defaults
```bash
./scripts/configure-services.sh reset
```

## Advanced Usage

### Manual Configuration
Edit the configuration file directly:
```bash
# Edit service settings
nano .lakehouse-services.conf

# Apply changes
./scripts/configure-services.sh validate
```

### Configuration File Format
```bash
# .lakehouse-services.conf
airflow=true
superset=false
jupyter=true
vizro=true
lancedb=false
portainer=true
homer=true
```

### Docker Compose Integration
The configuration system works by generating a `docker-compose.override.yml` file that:
- Sets `replicas: 0` for disabled services
- Uses Docker Compose profiles to exclude services
- Maintains compatibility with existing compose files

## Installation Integration

### Setup Wizard
Use the setup wizard for new installations:
```bash
./scripts/setup-wizard.sh
```

Options:
- `--minimal`: Quick minimal installation
- `--analytics`: Quick analytics installation  
- `--ml`: Quick ML/AI installation
- `--full`: Quick full installation
- Interactive mode (default)

### Starting Services
The startup script automatically detects and uses your configuration:
```bash
./start-lakehouse.sh
```

Disabled services will not start, saving system resources.

## 👥 Multi-User Configuration

### **Enabling JupyterHub for Team Environments**

**Replace single-user Jupyter with multi-user JupyterHub:**

```bash
# Use Docker Compose overlay to enable JupyterHub
docker compose -f docker-compose.yml -f docker-compose.jupyterhub.yml up -d
```

### **User Provisioning**

**Provision users across all lakehouse services with unified role management:**

```bash
# Provision users with different roles
./scripts/provision-user.sh john.doe john.doe@company.com SecurePass123 analyst
./scripts/provision-user.sh jane.admin jane.admin@company.com AdminPass456 admin
./scripts/provision-user.sh bob.viewer bob.viewer@company.com ViewPass789 viewer
```

### **JupyterHub Configuration**

**Key features of the multi-user environment:**

- **Container Isolation**: Each user gets their own containerized environment
- **Resource Limits**: Per-user CPU and memory allocation
- **Shared Data Access**: Unified access to MinIO, PostgreSQL, and LanceDB
- **Spark Integration**: Automatic Spark configuration for all users
- **Notebook Templates**: Shared readonly templates and collaborative workspace

### **Role-Based Access Control**

| Role | JupyterHub Access | Resource Limits | Shared Notebooks |
|------|------------------|-----------------|------------------|
| **admin** | Full sudo access | Unlimited | Read/Write all |
| **analyst** | Standard user | 4GB RAM, 2 CPU | Read-only templates, personal workspace |
| **viewer** | Standard user | 2GB RAM, 1 CPU | Read-only access only |

### **Managing Multi-User Environment**

```bash
# Monitor JupyterHub users
docker exec jupyterhub-container jupyterhub token --help

# View user containers
docker ps --filter "name=jupyter-"

# Scale user resources (edit docker-compose.jupyterhub.yml)
# Then restart JupyterHub:
docker compose -f docker-compose.yml -f docker-compose.jupyterhub.yml restart jupyterhub
```

## Troubleshooting

### Common Issues

1. **Service Dependencies**: Some services depend on others. The validator will warn you about conflicts.

2. **Resource Constraints**: Monitor your system resources:
   ```bash
   ./start-lakehouse.sh resources
   ```

3. **Configuration Not Applied**: Restart services after changing configuration:
   ```bash
   docker compose down
   ./start-lakehouse.sh
   ```

4. **Reset Everything**: If you encounter issues:
   ```bash
   ./scripts/configure-services.sh reset
   ./start-lakehouse.sh stop
   ./start-lakehouse.sh
   ```

### Verification
Check which services are actually running:
```bash
docker compose ps
./start-lakehouse.sh status
```

## Best Practices

1. **Start Small**: Begin with minimal configuration and add services as needed
2. **Monitor Resources**: Use `docker stats` to monitor resource usage
3. **Validate Configuration**: Always validate before applying changes
4. **Backup Configs**: Keep copies of working configurations
5. **Use Presets**: Leverage presets for common scenarios instead of manual configuration

## Examples

### Switching Configurations
```bash
# Start with minimal for development
./scripts/configure-services.sh preset minimal
./start-lakehouse.sh

# Later switch to analytics for BI work
./scripts/configure-services.sh preset analytics
docker compose down
./start-lakehouse.sh

# Switch to full for production
./scripts/configure-services.sh preset full
docker compose down
./start-lakehouse.sh
```

### Custom Configuration for Specific Team
```bash
# Configure for data engineering team
./scripts/configure-services.sh interactive
# Enable: Jupyter, Airflow, Portainer
# Disable: Superset, Vizro, LanceDB, Homer

# Save and start
./start-lakehouse.sh
```

This configuration system provides the flexibility requested while maintaining ease of use for both new and experienced users.

## 💾 Backup Configuration

### Automated Backup Setup
Configure automated backups to protect your lakehouse data and configurations:

```bash
# Interactive CRON backup configuration
./examples/cron-backup-setup.sh

# Automated daily backups with email notifications
./examples/cron-backup-setup.sh --schedule "0 2 * * *" --email admin@company.com --compress

# Weekly backups with custom retention
./examples/cron-backup-setup.sh --schedule "0 3 * * 0" --retention-days 90 --compress
```

### Airflow Backup DAG
For environments using Airflow, deploy the backup DAG:

```bash
# Copy backup DAG template
cp templates/airflow/dags/lakehouse_backup_dag.py lakehouse-data/airflow/dags/

# Configure backup environment variables
export LAKEHOUSE_PATH="/path/to/lakehouse-lab"
export LAKEHOUSE_BACKUP_PATH="/path/to/backups"
export BACKUP_NOTIFICATION_EMAIL="admin@company.com"
```

### Backup Service Configuration
The backup system can be configured to backup only specific services:

```bash
# Backup only core data services
./scripts/backup-lakehouse.sh --services postgres,minio --compress

# Exclude specific services from backup
./scripts/backup-lakehouse.sh --exclude-services homer,portainer --compress

# Full backup with all options
./scripts/backup-lakehouse.sh --compress --verify --parallel --retention-days 30
```

### Backup Storage Options
Configure where backups are stored:

```bash
# Local directory backup (default)
./scripts/backup-lakehouse.sh --output-dir /data/backups

# Network storage backup
./scripts/backup-lakehouse.sh --output-dir /mnt/nas/lakehouse-backups

# Custom backup location with CRON
./examples/cron-backup-setup.sh --backup-dir /external/storage/backups
```