# Lakehouse Lab

[![CI Status](https://github.com/karstom/lakehouse-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/karstom/lakehouse-lab/actions)
[![Coverage Status](https://codecov.io/gh/karstom/lakehouse-lab/branch/main/graph/badge.svg)](https://codecov.io/gh/karstom/lakehouse-lab)
[![GitHub release](https://img.shields.io/github/release/karstom/lakehouse-lab.svg)](https://github.com/karstom/lakehouse-lab/releases)
[![Docker Compose](https://img.shields.io/badge/docker--compose-ready-blue)](https://docs.docker.com/compose/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](docs/CONTRIBUTING.md)
[![Last Commit](https://img.shields.io/github/last-commit/karstom/lakehouse-lab)](https://github.com/karstom/lakehouse-lab/commits/main)

> _Note: Update the badge URLs above to match your actual CI and coverage providers if different._

---

## Table of Contents
- [Quick Start](#quick-start)
- [Feature Table](#feature-table)
- [User Provisioning & Roles](#user-provisioning--roles)
- [Documentation](#documentation)
- [Troubleshooting & FAQ](#troubleshooting--faq)
- [Credential Management & Security](#credential-management--security)
- [How to Contribute](#how-to-contribute)
- [Support & Community](#support--community)

---

## Quick Start

**One-Command Install (Recommended):**
```bash
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
```
- For advanced options, see [Installation Guide](docs/INSTALLATION.md).

---

## Feature Table

| Feature         | Included | Docs Link                |
|-----------------|:--------:|--------------------------|
| PostgreSQL      |   ✅     | [Configuration](docs/CONFIGURATION.md) |
| MinIO (S3)      |   ✅     | [Configuration](docs/CONFIGURATION.md) |
| Spark           |   ✅     | [Configuration](docs/CONFIGURATION.md) |
| JupyterLab      |   ✅     | [Notebooks](docs/NOTEBOOK_PACKAGE_MANAGER.md) |
| Superset        |   ✅     | [Superset](docs/SUPERSET_DATABASE_SETUP.md) |
| Airflow         |   ✅     | [Workflows](docs/INSTALLATION.md) |
| LanceDB         |   ✅     | [Vector Search](docs/LAKEHOUSE_LLM_GUIDE.md) |
| Vizro           |   ✅     | [Dashboards](docs/SERVICE_INTEGRATION_GUIDE.md) |
| Portainer       |   ✅     | [Management](docs/INSTALLATION.md) |

---

> **Modern Data Engineering Platform in 15 Minutes**  
> **One-Click Install • Vector Search • Interactive Dashboards**

**Version 2.1.1** - A comprehensive lakehouse environment for learning, development, and experimentation with modern data engineering technologies. Features interactive dashboards, vector search, multi-user collaboration, and comprehensive tooling for data engineering workflows.

## User Provisioning & Roles

See [User Provisioning Examples](docs/USER_PROVISIONING_EXAMPLES.md) for how to add users with different roles.

**Example:**
```bash
./scripts/provision-user.sh alice alice@company.com StrongAdminPass123 admin
./scripts/provision-user.sh bob bob@company.com AnalystPass456 analyst
./scripts/provision-user.sh carol carol@company.com ViewerPass789 viewer
```
- Roles: `admin`, `analyst`, `viewer`
- Sample `.env` entries for each role are provided in the linked doc.

---

## Documentation

- [Quick Start](docs/QUICKSTART.md) — 15-minute setup guide
- [Installation Guide](docs/INSTALLATION.md) — Complete install & troubleshooting
- [Configuration Guide](docs/CONFIGURATION.md) — Service configuration & presets
- [Service Integration Guide](docs/SERVICE_INTEGRATION_GUIDE.md) — Add new services
- [User Provisioning Examples](docs/USER_PROVISIONING_EXAMPLES.md) — Roles & scripts
- [Testing Guide](docs/TESTING.md) — Test framework & procedures
- [Changelog](docs/CHANGELOG.md) — Version history
- [Contributing](docs/CONTRIBUTING.md) — How to contribute

---

## Troubleshooting & FAQ

- See the [Troubleshooting Matrix](docs/INSTALLATION.md#-troubleshooting) for common errors, symptoms, and solutions.
- **FAQ:**
  - **How do I reset everything?**
    Run: `./start-lakehouse.sh reset`
  - **How do I add a new service?**
    See: [Service Integration Guide](docs/SERVICE_INTEGRATION_GUIDE.md)
  - **How do I rotate credentials?**
    See: [Credential Management & Security](#credential-management--security)

---

## Credential Management & Security

- **Credential Rotation:**
  Automated reminders are sent monthly via GitHub Actions. See `.github/credential-rotation-reminder.yml`.
- **Secret Scanning:**
  All code is scanned for secrets in CI using Trivy.
- **Best Practices:**
  - Never commit `.env` or secrets to version control.
  - Use `./scripts/rotate-credentials.sh` to rotate credentials.
  - Store credentials securely and update them regularly.

---

## How to Contribute

We welcome contributions!
- See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.
- Open issues or pull requests for bugs, features, or documentation.
- All code is tested and scanned for security in CI.

---

## Support & Community

- [GitHub Issues](https://github.com/karstom/lakehouse-lab/issues) — Report bugs, ask questions, request features
- For urgent help, mention `@karstom` in your issue.

---

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
