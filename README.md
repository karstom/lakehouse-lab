# Lakehouse Lab

[![GitHub release](https://img.shields.io/github/release/karstom/lakehouse-lab.svg)](https://github.com/karstom/lakehouse-lab/releases)
[![Docker Compose](https://img.shields.io/badge/docker--compose-ready-blue)](https://docs.docker.com/compose/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](docs/CONTRIBUTING.md)

> **Modern Data Engineering Platform in 15 Minutes**  
> **One-Click Install • Vector Search • Interactive Dashboards**

**Version 2.1.1** - A comprehensive lakehouse environment for learning, development, and experimentation with modern data engineering technologies. Features interactive dashboards, vector search, multi-user collaboration, and comprehensive tooling for data engineering workflows.

## 🎯 Who It's For

**Perfect for diverse users and use cases:**
- **Individual developers** learning data engineering
- **Students** in computer science and data programs  
- **Hobbyists** exploring modern data stack
- **Educational institutions** (universities, bootcamps)
- **Corporate training** environments
- **Research projects** requiring data infrastructure
- **Anyone** wanting to experiment with lakehouse architecture

Designed primarily for learning and development environments. While not specifically optimized for production workloads, you're welcome to experiment and adapt it for your specific needs.

## Quick Start

### One-Command Installation

```bash
# Complete lakehouse installation
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
```

### Configuration Options

```bash
# Minimal setup (8GB RAM)
./scripts/setup-wizard.sh --minimal

# Analytics focus (14GB RAM) 
./scripts/setup-wizard.sh --analytics

# ML/AI focus (16GB RAM)
./scripts/setup-wizard.sh --ml

# Full installation (20GB RAM)
./scripts/setup-wizard.sh --full
```

Wait 3-5 minutes for initialization, then run `./scripts/show-credentials.sh` to access all services.

> **Note**: Always use the installer for first-time setup. After installation, use `docker compose up -d` for daily service management.

For detailed installation options, upgrading, and troubleshooting, see the [Installation Guide](docs/INSTALLATION.md).

## What You Get

### Core Components
- **PostgreSQL** - Analytics database for structured data
- **MinIO** - S3-compatible object storage for data lake
- **Apache Spark** - Distributed data processing engine
- **JupyterLab/Hub** - Interactive notebooks for analysis and development
- **DuckDB** - Fast analytics with direct S3 querying

### Optional Services
- **Apache Airflow** - Workflow orchestration and scheduling
- **Apache Superset** - Business intelligence dashboards
- **Vizro** - Modern interactive dashboard framework  
- **LanceDB** - Vector database for AI/ML and semantic search
- **Portainer** - Container management interface

### Configuration Presets
- **Minimal** (8GB) - Core services + notebooks
- **Analytics** (14GB) - BI dashboards + visualizations
- **ML/AI** (16GB) - Vector search + machine learning
- **Full** (20GB) - All services enabled

Run `./scripts/show-credentials.sh` to see service URLs and login credentials.

## Multi-User Support

### JupyterHub
Enable multi-user collaborative notebooks:
```bash
docker compose -f docker-compose.yml -f docker-compose.jupyterhub.yml up -d
```

### User Management
Provision users across all services:
```bash
./scripts/provision-user.sh username email@domain.com password role
```

Creates accounts in Superset, Airflow, MinIO, and JupyterHub with appropriate permissions.

## Security & Credentials

Lakehouse Lab generates unique, secure credentials for each installation:

```bash
# View all service URLs and credentials
./scripts/show-credentials.sh

# Rotate credentials if needed
./scripts/rotate-credentials.sh
```

Credentials are stored in the `.env` file - back it up securely and never commit to version control.

## Documentation

**Essential Guides:**
- [Quick Start](docs/QUICKSTART.md) - 15-minute setup guide
- [Installation Guide](docs/INSTALLATION.md) - Complete installation options
- [Configuration Guide](docs/CONFIGURATION.md) - Service configuration and presets
- [AI/ML Integration](docs/LAKEHOUSE_LLM_GUIDE.md) - Vector search and LLM development
- [Cloud Deployment](docs/CLOUD_DEPLOYMENT.md) - AWS, GCP, Azure deployment guides

**Additional Resources:**
- [Contributing](docs/CONTRIBUTING.md) - How to contribute
- [Changelog](docs/CHANGELOG.md) - Version history
- [MCP Integration](docs/MCP.md) - Model Context Protocol servers

## Backup & Data Management

Basic backup and restore functionality:

```bash
# Manual backup
./scripts/backup-lakehouse.sh --compress --verify

# Automated backup setup
./examples/cron-backup-setup.sh

# Restore from backup
./scripts/restore-lakehouse.sh backup-name
```

For detailed backup and data management options, see the [Configuration Guide](docs/CONFIGURATION.md).

## Architecture Overview

Modern lakehouse architecture with three analytics layers:

### Data Flow
1. **Ingest** → Load data to MinIO object storage  
2. **Process** → Transform with Spark (orchestrated by Airflow)
3. **Store** → Data lake (MinIO) + warehouse (PostgreSQL) + vectors (LanceDB)
4. **Analyze** → Query with DuckDB, PostgreSQL, or vector search
5. **Visualize** → Build dashboards in Superset/Vizro or analyze in Jupyter

### Key Benefits
- **S3-native analytics** - Query files directly without data movement
- **Multiple query engines** - DuckDB for data lake, PostgreSQL for structured data, LanceDB for AI/ML
- **Modern dashboards** - Interactive Vizro + traditional Superset BI
- **Scalable processing** - Spark scales from laptops to clusters
- **Container-based** - Consistent deployment with Docker Compose

## Getting Started

### 1. Access Your Services
After installation, run `./scripts/show-credentials.sh` to see all service URLs and login credentials.

### 2. Explore Sample Data
Sample notebooks and datasets are automatically created:
- Check `/notebooks/` for Jupyter examples
- MinIO contains sample CSV files in `lakehouse/raw-data/`

### 3. Query Data with DuckDB
In Superset, setup persistent S3 access once:
```sql
CREATE PERSISTENT SECRET minio_secret (
    TYPE S3,
    KEY_ID 'admin',
    SECRET 'YOUR_MINIO_PASSWORD',  -- Get from ./scripts/show-credentials.sh
    ENDPOINT 'minio:9000',
    USE_SSL false,
    URL_STYLE 'path',
    SCOPE 's3://lakehouse'
);
```

Then query your data lake:
```sql
SELECT * FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv') LIMIT 10;
```

### 4. Build Dashboards
- **Superset**: Traditional BI dashboards with DuckDB and PostgreSQL connections
- **Vizro**: Modern interactive dashboards (see notebook examples)
- **Jupyter**: Interactive analysis and development

### 5. Create Data Pipelines  
Access Airflow to orchestrate ETL workflows and schedule data processing jobs.

## Advanced Features

### Service Configuration
Use the interactive configuration wizard:
```bash
./scripts/configure-services.sh
```

### Remote Server Deployment
The system automatically detects your server's IP address. For manual configuration:
```bash
export HOST_IP=192.168.1.100  # Replace with your server's IP
```

### Apache Iceberg Support
For advanced analytics with time travel and ACID transactions:
```bash
./install.sh --iceberg
```

For detailed configuration options, see the [Configuration Guide](docs/CONFIGURATION.md).

## Project Structure

```
lakehouse-lab/
├── install.sh              # Main installer
├── docker-compose.yml      # Stack definition  
├── scripts/                # Management scripts
├── docs/                   # Documentation
├── examples/               # Example configurations
└── lakehouse-data/         # Runtime data (auto-created)
```

## Troubleshooting

### Common Issues

**Services won't start:**
```bash
docker compose ps              # Check service status
docker compose logs SERVICE   # View specific service logs
docker compose restart        # Restart all services
```

**Memory issues:**
```bash
docker stats --no-stream      # Check memory usage
# Edit .env file to reduce memory limits
```

**Connection issues:**
```bash
./scripts/show-credentials.sh  # Get service URLs and credentials
```

**Reset everything (destroys all data):**
```bash
docker compose down -v
rm -rf lakehouse-data/
./install.sh
```

For detailed troubleshooting, see the [Installation Guide](docs/INSTALLATION.md).

## Key Features

- **15-minute setup** - Complete lakehouse environment with one command
- **S3-native analytics** - Query files directly with DuckDB without data movement  
- **Modern dashboards** - Interactive Vizro + traditional Superset BI
- **Vector database** - LanceDB for AI/ML and semantic search
- **Multi-user support** - JupyterHub with containerized environments
- **Triple analytics** - Data lake + warehouse + vector database
- **Scalable deployment** - From laptops to institutional networks
- **Ready-made examples** - Sample notebooks and datasets included

## Contributing

See [Contributing Guide](docs/CONTRIBUTING.md) for how to contribute to the project.

## License

MIT License - see LICENSE file for details.

## Acknowledgments

Built with amazing open source projects including DuckDB, PostgreSQL, Apache Spark, Apache Airflow, Apache Superset, MinIO, and Portainer.

---

**Happy Data Engineering!**

For questions and community discussions, please open an issue on GitHub.
