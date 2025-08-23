# 🔧 Lakehouse Lab Configuration Guide

This guide explains how to configure which services are enabled in your Lakehouse Lab installation.

## Overview

Lakehouse Lab now supports selective service installation, allowing you to:
- **Enable only the services you need** to save system resources
- **Create custom configurations** for different use cases
- **Switch between configurations** without rebuilding containers
- **Use preset configurations** for common scenarios

## Quick Start

### Using Preset Configurations

The easiest way to configure services is using presets:

```bash
# Minimal setup (8GB RAM) - Core services + Jupyter only
./scripts/configure-services.sh preset minimal

# Analytics focus (14GB RAM) - Jupyter + Superset + Vizro  
./scripts/configure-services.sh preset analytics

# ML/AI focus (16GB RAM) - Jupyter + LanceDB + Airflow
./scripts/configure-services.sh preset ml

# Full installation (20GB RAM) - All services enabled
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
| **JupyterLab** | Interactive data science environment | 9040 | 8GB | Data analysis, ML development |
| **Vizro** | Low-code dashboard framework | 9050 | 2GB | Interactive visualizations |
| **LanceDB** | High-performance vector database | 9080 | 3GB | AI/ML, semantic search |
| **Portainer** | Docker container management | 9060 | 0.5GB | System monitoring |
| **Homer** | Service dashboard with links | 9061 | 0.1GB | Easy service access |

## Preset Configurations

### 1. Minimal Configuration
**Best for**: Learning, development, resource-constrained systems
```
✅ Core Services: PostgreSQL, MinIO, Spark
✅ JupyterLab: Data science notebooks
✅ Portainer: Container management
❌ All other services disabled

📊 Resources: ~8GB RAM, 4 CPU cores minimum
🎯 Use case: Data exploration, learning Spark/lakehouse concepts
```

### 2. Analytics Configuration  
**Best for**: Business intelligence, reporting, data visualization
```
✅ Core Services: PostgreSQL, MinIO, Spark
✅ JupyterLab: Data science notebooks
✅ Apache Superset: BI dashboards
✅ Vizro: Interactive dashboards
✅ Portainer: Container management
✅ Homer: Service links
❌ Airflow, LanceDB disabled

📊 Resources: ~14GB RAM, 8 CPU cores recommended
🎯 Use case: BI teams, data analysts, dashboard creators
```

### 3. ML/AI Configuration
**Best for**: Machine learning, AI workflows, vector operations
```
✅ Core Services: PostgreSQL, MinIO, Spark
✅ JupyterLab: Data science notebooks
✅ Apache Airflow: ML pipeline orchestration
✅ LanceDB: Vector database for AI
✅ Portainer: Container management
✅ Homer: Service links
❌ Superset, Vizro disabled

📊 Resources: ~16GB RAM, 8+ CPU cores recommended  
🎯 Use case: ML engineers, AI researchers, vector search
```

### 4. Full Configuration
**Best for**: Production environments, comprehensive data platforms
```
✅ All services enabled

📊 Resources: ~20GB RAM, 16+ CPU cores recommended
🎯 Use case: Production data platforms, comprehensive analytics
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