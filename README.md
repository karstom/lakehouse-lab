# Lakehouse Lab 🏠📊

[![GitHub release](https://img.shields.io/github/release/karstom/lakehouse-lab.svg)](https://github.com/karstom/lakehouse-lab/releases)
[![Docker Compose](https://img.shields.io/badge/docker--compose-ready-blue)](https://docs.docker.com/compose/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Enterprise Auth](https://img.shields.io/badge/Enterprise-Authentication-green)](CONFIGURATION.md)
[![AI Ready](https://img.shields.io/badge/AI-Ready-purple)](LAKEHOUSE_LLM_GUIDE.md)

> **🚀 Enterprise-Ready Data Analytics Platform in 15 Minutes**  
> **🔒 Optional Team Authentication • 🤖 AI-Powered API • 📊 Modern Dashboards**

**Version 2.1.0** - A complete lakehouse environment that scales from individual learning to enterprise team collaboration. **Features enterprise authentication, AI-powered data API, modern interactive dashboards, vector search, multi-user JupyterHub, comprehensive user provisioning, and configurable service deployment.**

### 🎯 Choose Your Experience

| **🏠 Individual Developer** | **🏢 Enterprise Team** |
|----------------------------|------------------------|
| **One-click install** | **Secure team collaboration** |
| No setup complexity | OAuth with Google/Microsoft/GitHub |
| Perfect for learning | Multi-user JupyterHub environment |
| Interactive dashboard development | Role-based access control |
| AI-powered analytics | Central user provisioning |
| Local development | Audit logging & compliance |
| ⚡ 15-minute setup | 🔒 Production-ready security |

Both experiences use the **same powerful data platform** underneath!

## ⚡ Ultra-Quick Start

### 🏠 Individual Developer (Simple & Fast)

**One-click install - no authentication setup needed:**

```bash
# Simple installation for individual use
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
```

### 🏢 Enterprise Team (Secure & Collaborative)

**Secure installation with team authentication:**

```bash
# Enterprise installation with authentication
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install-with-auth.sh | bash
```

### 🎯 Interactive Setup Wizard (Recommended for Both)

**Configure your services and get running with the interactive installer:**

```bash
# Download and run setup wizard
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
```

**Or use the setup wizard directly:**
```bash
git clone https://github.com/karstom/lakehouse-lab.git
cd lakehouse-lab
./scripts/setup-wizard.sh
```

### 🚀 Quick Installation Modes

**Choose your installation mode:**

```bash
# Minimal setup (8GB RAM) - Core + Jupyter only
./scripts/setup-wizard.sh --minimal

# Analytics focus (14GB RAM) - BI and dashboards
./scripts/setup-wizard.sh --analytics

# ML/AI focus (16GB RAM) - Vector search and ML workflows
./scripts/setup-wizard.sh --ml

# Full installation (20GB RAM) - All services
./scripts/setup-wizard.sh --full
```

### 🔧 Service Configuration

**Configure which services to enable:**
```bash
# Interactive service selection
./scripts/configure-services.sh

# Use presets
./scripts/configure-services.sh preset minimal
./scripts/configure-services.sh preset analytics
./scripts/configure-services.sh preset ml
./scripts/configure-services.sh preset full
```

**For Windows WSL or macOS users** (if you get piping issues):
```bash
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh -o /tmp/install.sh && bash /tmp/install.sh
```

**⚠️ WSL users:** If Docker is installed during setup, restart your terminal and re-run the installer to complete the process.

That's it! ☕ Grab a coffee while it sets up your customized lakehouse environment.

**For high-performance servers (64GB+ RAM):**
```bash
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --fat-server
```

**Alternative setup with Git:**
```bash
git clone https://github.com/karstom/lakehouse-lab.git
cd lakehouse-lab
./install.sh
```

> ⚠️ **Important**: Always use the installer or setup wizard for new installations. Running `docker compose up -d` directly will fail because it requires secure credentials and initialization that only the installer provides.

Wait 3-5 minutes for initialization, then run `./scripts/show-credentials.sh` to see all service URLs with your detected IP address.

## ⚠️ Installation vs Service Management

### For New Installations (First Time)
**Always use the installer:**
```bash
./install.sh
```
The installer handles:
- ✅ Secure credential generation
- ✅ Script permissions and dependencies  
- ✅ Resource optimization for your system
- ✅ Complete environment initialization
- ✅ Service startup and health verification

### For Existing Installations (Day-to-Day)
**Use Docker Compose commands:**
```bash
docker compose up -d        # Start services
docker compose down         # Stop services  
docker compose restart     # Restart services
docker compose logs -f     # View logs
```

> 💡 **Key Point**: `docker compose up -d` only works **after** running the installer at least once. The installer creates the required `.env` file with secure credentials that Docker Compose needs.

## 🔄 Upgrading Existing Installation

**Already have Lakehouse Lab installed?** The installer automatically detects existing installations and offers smart upgrade options:

```bash
# Run the same installation command - it will detect and offer options
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
```

You'll get user-friendly options:
- **Upgrade** - Updates to latest version while preserving your data and settings
- **Replace** - Fresh installation with clean slate (removes all data)
- **Cancel** - Exit without changes

**Or use direct flags:**
```bash
# Upgrade preserving data
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --upgrade

# Fresh installation (clean slate)
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --replace
```

## 🎯 What You Get

### 🏗️ Core Services (Always Enabled)
| Service | Purpose | URL | Credentials |
|---------|---------|-----|-------------|
| **PostgreSQL** | Analytics Database | Auto-detected IP:5432 | 🔐 Generated securely |
| **MinIO Console** | Object Storage | Auto-detected IP:9001 | 🔐 Generated securely |
| **Spark Master** | Distributed Computing | Auto-detected IP:8080 | N/A |
| **Portainer** | Container Management | Auto-detected IP:9060 | Create admin user |

### 📊 Optional Services (Configurable)
| Service | Purpose | URL | RAM | Use Case |
|---------|---------|-----|-----|----------|
| **Apache Airflow** | Workflow Orchestration | :9020 | 4GB | Data pipelines, ETL |
| **Apache Superset** | BI & Visualization | :9030 | 4GB | Business dashboards |
| **JupyterLab** | Data Science Notebooks | :9040 | 8GB | Analysis, ML development |
| **JupyterHub** | Multi-User Notebooks | :9041 | 8GB | Team collaboration, user management |
| **Vizro** | Interactive Dashboards | :9050 | 2GB | Modern visualizations |
| **LanceDB** | Vector Database API | :9080 | 3GB | AI/ML, semantic search |
| **Homer** | Service Links Dashboard | :9061 | 0.1GB | Easy service access |

### 🔒 Enterprise Authentication Services (Optional)
| Service | Purpose | URL | RAM | Use Case |
|---------|---------|-----|-----|----------|
| **Auth Service** | OAuth & Local Authentication | :9091 | 1GB | User management, federated login |
| **Auth Proxy** | Service Access Control | :9092 | 0.5GB | Role-based access, audit logging |
| **MCP Server** | AI-Powered Data API | :9090 | 2GB | Natural language data queries |
| **Audit Service** | Compliance & Monitoring | - | 0.5GB | Activity logging, security monitoring |

📋 **Get exact URLs**: Run `./scripts/show-credentials.sh` to see service URLs with your detected IP address.

### 🎛️ Service Configurations Available

- **🔍 Minimal** (8GB): Core services + Jupyter only
- **📊 Analytics** (14GB): BI-focused with Superset + Vizro dashboards  
- **🤖 ML/AI** (16GB): Machine learning with LanceDB vector search
- **🚀 Full** (20GB): Complete data platform with all services
- **🔒 Secure** (22GB): Full platform + enterprise authentication

Configure services with: `./scripts/configure-services.sh` or use the setup wizard.

## 👥 Team Management & Multi-User Features

**Enterprise-grade user management across the entire lakehouse platform:**

### 🎯 **Central User Provisioning**
```bash
# Provision users across all services with one command
./scripts/provision-user.sh john.doe john.doe@company.com SecurePass123 analyst
```

**What this does:**
- ✅ **Superset**: Creates BI dashboard user with appropriate role  
- ✅ **Airflow**: Sets up workflow orchestration access
- ✅ **MinIO**: Configures object storage permissions
- ✅ **JupyterHub**: Creates containerized notebook environment
- ✅ **Role Mapping**: Automatically maps lakehouse roles to service-specific permissions

### 🏗️ **Multi-User JupyterHub**
Replace single-user Jupyter with team-ready JupyterHub:

```bash
# Use JupyterHub configuration overlay
docker compose -f docker-compose.yml -f docker-compose.jupyterhub.yml up -d
```

**JupyterHub Features:**
- 👥 **Multi-user environment** with containerized isolation
- 🔗 **Spark integration** for all users
- 📁 **Shared notebooks** (readonly templates + collaborative workspace)  
- 🔐 **User authentication** with role-based access
- 📊 **Resource management** with per-user limits
- 🏢 **Team collaboration** with shared data access

### 📋 **User Roles & Permissions**
| Role | Superset | Airflow | MinIO | JupyterHub | Description |
|------|----------|---------|-------|------------|-------------|
| **admin** | Admin | Admin | consoleAdmin | sudo access | Full platform administration |
| **analyst** | Alpha | User | readwrite | standard user | Create dashboards, run workflows |
| **viewer** | Gamma | Viewer | readonly | standard user | View dashboards, read-only data |

## 🔒 Secure Credential Management

**No more default passwords!** Lakehouse Lab now generates unique, secure credentials for each installation:

### View Your Credentials
```bash
./scripts/show-credentials.sh
```

### Credential Features
- 🎯 **Memorable Passphrases**: Easy-to-type formats like `swift-river-bright-847`
- 🔐 **Strong Database Passwords**: Cryptographically secure for backend services
- 🔄 **Unique Per Installation**: Every deployment gets different credentials
- 🛡️ **Environment Variables**: Secure configuration without hardcoded secrets

### Credential Management Scripts
```bash
# Generate new credentials (done automatically during installation)
./scripts/generate-credentials.sh

# View current credentials in a friendly format
./scripts/show-credentials.sh

# Rotate all credentials (generates new ones)
./scripts/rotate-credentials.sh
```

**⚠️ Important**: Your credentials are stored in the `.env` file. Back it up securely and never commit it to version control.

## 🔐 Enterprise Authentication & Team Collaboration

### 🎯 Authentication Options

**Hybrid Mode (Default for Enterprise)**
- **Local Authentication**: Simple admin@localhost login for development
- **Federated OAuth**: Google, Microsoft, GitHub for team access
- **Role-Based Access Control**: Four user roles with granular permissions

### 🚀 Quick Enterprise Setup

**Option 1: Secure Installation from Start**
```bash
# Complete secure installation with authentication
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install-with-auth.sh | bash
```

**Option 2: Add Authentication to Existing Installation**
```bash
# Enable authentication on existing installation
./scripts/enable-auth.sh
```

### ⚙️ Configure OAuth Providers

**Setup OAuth integration with popular providers:**
```bash
# Interactive OAuth configuration wizard
./scripts/setup-auth.sh
```

**Supported Providers:**
- **Google Workspace**: Perfect for organizations using Gmail/Google
- **Microsoft Azure AD**: Ideal for Office 365 environments  
- **GitHub**: Great for development teams
- **Custom OIDC**: Support for any OpenID Connect provider

### 👥 User Roles & Permissions

| Role | Permissions | Use Case |
|------|-------------|----------|
| **data_viewer** | Read-only access to dashboards and reports | Executives, stakeholders |
| **data_analyst** | Query data, create charts, basic analysis | Business analysts |
| **data_engineer** | ETL pipelines, data modeling, advanced queries | Data engineers |
| **admin** | Full system access, user management | IT administrators |

### 📊 Authentication Architecture

**Service Access Control:**
- **Authentication Service** (port 9091): OAuth login, user management
- **Authentication Proxy** (port 9092): Secure access to all services
- **Audit Logging**: Complete activity monitoring and compliance
- **Role Enforcement**: Granular permissions per service and operation

### 🔄 Migration from Simple to Secure

**Seamless upgrade path:**
```bash
# Your existing data and configuration are preserved
./scripts/enable-auth.sh
```

**What stays the same:**
- ✅ All your existing data and notebooks
- ✅ Service URLs and functionality  
- ✅ Docker Compose workflow
- ✅ One-click install still available

**What gets enhanced:**
- 🔐 OAuth login with federated providers
- 👥 Multi-user access with roles
- 📋 Complete audit trail
- 🛡️ Secure service access control

## 📖 Documentation

- [🚀 **Quick Start**](QUICKSTART.md) - Get running in 15 minutes
- [🔧 **Configuration Guide**](CONFIGURATION.md) - Service configuration and presets
- [📚 **Installation Guide**](INSTALLATION.md) - Complete installation options
- [🤖 **AI/ML Integration**](LAKEHOUSE_LLM_GUIDE.md) - LLM development and vector search
- [☁️ **Cloud Deployment**](CLOUD_DEPLOYMENT.md) - AWS, GCP, Azure deployment guides
- [🤝 **Contributing**](CONTRIBUTING.md) - How to contribute
- [📋 **Changelog**](CHANGELOG.md) - Version history

## 🏗️ Architecture

```mermaid
graph TB
    subgraph "🔐 Authentication Layer (Optional)"
        AU[Auth Service<br/>OAuth & Local Login]
        AP[Auth Proxy<br/>Access Control]
        AD[Audit Service<br/>Activity Logging]
    end
    
    subgraph "Data Sources"
        DS1[CSV Files]
        DS2[APIs] 
        DS3[Databases]
    end
    
    subgraph "🤖 AI-Powered Data API"
        MCP[MCP Server<br/>Natural Language<br/>Data Queries]
    end
    
    subgraph "Processing Layer"
        AF[Airflow<br/>Orchestration]
        SP[Spark<br/>Processing]
        JU[Jupyter<br/>Analysis]
    end
    
    subgraph "Storage Layer"
        MI[MinIO<br/>S3-Compatible<br/>Object Storage]
        PG[PostgreSQL<br/>Analytics Database]
        LD[LanceDB<br/>Vector Database]
    end
    
    subgraph "Query Engine"
        DU[DuckDB + S3<br/>Data Lake Analytics]
        SS[Spark SQL<br/>Distributed Queries]
        PA[PostgreSQL<br/>Structured Analytics]
        VS[Vector Search<br/>Semantic Similarity]
    end
    
    subgraph "Visualization"
        SU[Superset<br/>BI Dashboards]
        VZ[Vizro<br/>Interactive Dashboards]
        JD[Jupyter<br/>Data Science]
    end
    
    subgraph "Management"
        PO[Portainer<br/>Container Management]
        HO[Homer<br/>Service Dashboard]
    end
    
    %% Authentication flows
    AU --> AP
    AP --> AF
    AP --> SU
    AP --> VZ
    AP --> JU
    AP --> MCP
    AU --> AD
    
    %% Data flows
    DS1 --> AF
    DS2 --> AF
    DS3 --> AF
    AF --> SP
    AF --> JU
    SP --> MI
    SP --> PG
    SP --> LD
    JU --> MI
    JU --> PG
    JU --> LD
    MI --> DU
    MI --> SS
    PG --> PA
    LD --> VS
    DU --> SU
    DU --> VZ
    DU --> JD
    DU --> MCP
    SS --> SU
    SS --> VZ
    SS --> JD
    PA --> SU
    PA --> VZ
    PA --> JD
    PA --> MCP
    VS --> JD
    VS --> MCP
    DU --> PG
    
    %% Management connections
    PO -.-> AF
    PO -.-> SP
    PO -.-> JU
    PO -.-> MI
    PO -.-> PG
    PO -.-> LD
    PO -.-> AU
    PO -.-> AP
    HO -.-> AF
    HO -.-> SU
    HO -.-> VZ
    HO -.-> JU
    
    classDef storage fill:#e1f5fe
    classDef processing fill:#f3e5f5
    classDef visualization fill:#e8f5e8
    classDef management fill:#fff3e0
    classDef security fill:#ffebee
    classDef ai fill:#f3e5f5
    
    class MI,PG,LD storage
    class AF,SP,JU processing
    class SU,VZ,JD visualization
    class PO,HO management
    class AU,AP,AD security
    class MCP,VS ai
    class DU,SS,PA storage
```

### **Component Overview**

| **Layer** | **Components** | **Purpose** |
|-----------|----------------|-------------|
| **Authentication** | Auth Service, Auth Proxy, Audit Service | OAuth/local login, access control, compliance |
| **AI-Powered API** | MCP Server | Natural language data queries, AI-assisted analytics |
| **Data Sources** | CSV Files, APIs, Databases | Raw data ingestion from various sources |
| **Processing** | Apache Airflow, Apache Spark, Jupyter | ETL workflows, distributed processing, analysis |
| **Storage** | MinIO (S3-compatible), PostgreSQL, LanceDB | Object storage + analytics database + vector database |
| **Query Engine** | DuckDB + S3, Spark SQL, PostgreSQL, Vector Search | Data lake + structured + semantic analytics |
| **Visualization** | Apache Superset, Vizro, Jupyter | BI dashboards, interactive dashboards, analysis |
| **Management** | Portainer, Homer, Docker Compose | Container orchestration, monitoring, service links |

### **Data Flow**

1. **Authenticate** → Login via OAuth providers or local authentication (optional)
2. **Ingest** → Upload data files to MinIO or connect external sources
3. **Process** → Transform data using Spark jobs orchestrated by Airflow  
4. **Store** → Save processed data to MinIO (data lake), PostgreSQL (warehouse), and LanceDB (vectors)
5. **Analyze** → Query data with DuckDB (data lake), PostgreSQL (structured), or natural language (MCP)
6. **AI/ML** → Perform semantic search, vector similarity, and embedding operations via LanceDB
7. **Visualize** → Create dashboards in Superset/Vizro or notebooks in Jupyter from all data sources
8. **Monitor** → Manage services through Portainer, track access via audit logs

**Triple Analytics Architecture:**
- **Data Lake (DuckDB + MinIO)**: Direct file queries, multi-format support, schema-on-read
- **Data Warehouse (PostgreSQL)**: Structured analytics, ACID transactions, optimized performance  
- **Vector Database (LanceDB)**: High-performance vector operations, semantic search, AI/ML workflows
- **AI Data API (MCP)**: Natural language queries, intelligent data discovery, automated insights

### **Key Architectural Benefits**

- **🔐 Enterprise Security**: Optional OAuth authentication with role-based access control
- **🤖 AI-Powered API**: Natural language data queries via Model Context Protocol (MCP)
- **🚀 S3-Native Analytics**: Query files directly without data movement
- **🏗️ Quadruple Analytics**: Data lake (DuckDB) + warehouse (PostgreSQL) + vector (LanceDB) + AI (MCP)
- **📊 Multi-Format Support**: CSV, Parquet, JSON, and more with seamless access
- **🔄 Scalable Processing**: Spark scales from single machine to cluster
- **🤖 AI/ML Ready**: Vector search, embeddings, semantic similarity, and LLM integration
- **📈 Modern Dashboards**: Interactive Vizro framework + traditional Superset BI
- **👥 Team Collaboration**: Multi-user access with granular permissions and audit logging
- **🎛️ Configurable Services**: Enable only what you need to save resources
- **🎯 Production-Ready**: Health checks, monitoring, orchestration, and compliance
- **🐳 Container-Based**: Consistent deployment across environments with Docker Compose
- **🔄 Flexible Deployment**: Start simple, add features incrementally as needs grow

## 🎛️ Service Configuration Options

### 🔧 Interactive Configuration (Recommended)
Use the configuration wizard to select which services to run:

```bash
# Interactive service selection with resource estimates
./scripts/configure-services.sh

# View current configuration
./scripts/configure-services.sh show

# Get system recommendations
./scripts/configure-services.sh recommend
```

### 📋 Preset Configurations

**Minimal Configuration (8GB RAM):**
```bash
./scripts/configure-services.sh preset minimal
# Includes: Core services + JupyterLab + Portainer
```

**Analytics Configuration (14GB RAM):**
```bash
./scripts/configure-services.sh preset analytics  
# Includes: Core + JupyterLab + Superset + Vizro + Homer
```

**ML/AI Configuration (16GB RAM):**
```bash
./scripts/configure-services.sh preset ml
# Includes: Core + JupyterLab + Airflow + LanceDB + Homer
```

**Full Configuration (20GB RAM):**
```bash
./scripts/configure-services.sh preset full
# Includes: All data services enabled (no authentication)
```

**Secure Configuration (22GB RAM):**
```bash
./scripts/configure-services.sh preset secure
# Includes: All services + enterprise authentication + audit logging
```

### 🖥️ Resource Configuration

**Standard Setup (Default):**
Perfect for laptops and development machines:
- **Memory**: 8-20GB depending on enabled services
- **CPU**: 4-8 cores recommended
- **Storage**: 50GB+ recommended

**Fat Server Setup:**
Optimized for powerful hardware (32+ cores, 64GB+ RAM):
```bash
# Install with fat server configuration
./install.sh --fat-server

# Or copy fat-server environment config
cp .env.fat-server .env
```

**Custom Resource Configuration:**
```bash
# Copy and edit default settings
cp .env.default .env
# Edit .env with your preferred settings
```

### 🧊 Apache Iceberg Support (Advanced Analytics)
For advanced lakehouse analytics with time travel, schema evolution, and ACID transactions:

```bash
# Install with Iceberg support
./install.sh --iceberg

# Or manually start with Iceberg overlay
docker compose -f docker-compose.yml -f docker-compose.iceberg.yml up -d
```

**Iceberg Features:**
- ✅ **Time Travel**: Query data as it existed at any point in time
- ✅ **Schema Evolution**: Add, drop, rename columns without breaking existing queries  
- ✅ **Partition Evolution**: Change partitioning schemes without data migration
- ✅ **ACID Transactions**: Full consistency for concurrent read/write operations
- ✅ **Rollback & Branching**: Easily revert changes or create data branches

**Use Cases:** Perfect for data warehousing, regulatory compliance, and production analytics where data lineage and consistency are critical.

### Remote Server Deployment 🌐

When deploying on a remote server, the system automatically detects your server's IP address. For best results, you can explicitly set the HOST_IP:

**Automatic IP Detection (Recommended):**
```bash
# The system will automatically detect your server's public IP
docker compose up -d
./scripts/show-credentials.sh  # Shows URLs with detected IP
```

**Manual IP Configuration:**
```bash
# Set your server's public/accessible IP address
export HOST_IP=192.168.1.100  # Replace with your server's IP
docker compose up -d

# Or add to .env file:
echo "HOST_IP=192.168.1.100" >> .env
```

**Examples:**
- **Local machine**: `HOST_IP=localhost` (auto-detected)
- **Home server**: `HOST_IP=192.168.1.100` 
- **Cloud instance**: `HOST_IP=203.0.113.45`
- **Corporate network**: `HOST_IP=10.0.1.50`

**Important Notes:**
- 🔥 **Firewall**: Ensure ports 8080, 9001, 9020, 9030, 9040, 9060, 9061 are accessible
- 🔒 **Security**: Consider using a reverse proxy (nginx/traefik) for production
- 📋 **Access**: Use `./scripts/show-credentials.sh` to see service URLs with detected IP
- 🔄 **Homer Update**: If Homer dashboard shows old IPs, restart: `docker compose restart lakehouse-init`

## 📚 Getting Started Guide

### 1. **First Steps**
After startup, run `./scripts/show-credentials.sh` to see all service URLs and credentials, then visit Portainer for container monitoring.

### 2. **Load Sample Data**
Sample datasets and notebooks are automatically created:
- Check `/notebooks/` for Jupyter examples
- MinIO contains sample CSV files in `lakehouse/raw-data/`

#### 📔 **Available Jupyter Notebooks**

**Getting Started & Core Analytics:**
- `00_Package_Manager.ipynb` - Automated dependency management
- `01_Getting_Started.ipynb` - Platform overview and first steps  
- `02_PostgreSQL_Analytics.ipynb` - Structured data analysis
- `03_Iceberg_Tables.ipynb` - Advanced table formats

**Interactive Dashboards & AI:**
- `04_Vizro_Interactive_Dashboards.ipynb` - Modern dashboard creation
- `05_LanceDB_Vector_Search.ipynb` - Vector database and semantic search
- `06_Advanced_Analytics_Vizro_LanceDB.ipynb` - AI-powered analytics combining dashboards + vectors
- `07_Interactive_Dashboard_Development.ipynb` - Dashboard development template

**✨ Highlight: Dashboard Development**
- 🎨 **Interactive charts** that work in any environment (no network setup required)
- 🤖 **AI-powered clustering** and semantic similarity analysis  
- 📊 **Professional dashboards** with hover, zoom, and filtering
- 🚀 **Ready-to-use templates** for business intelligence and ML analytics

### 3. **Query Data with DuckDB + S3 (Persistent Setup)**
**In Superset** - Get your service URL from `./scripts/show-credentials.sh`:

**Step 1: One-time S3 configuration (creates persistent secret):**
```sql
-- 🔐 Get your MinIO password: Run './scripts/show-credentials.sh'
CREATE PERSISTENT SECRET minio_secret (
    TYPE S3,
    KEY_ID 'admin',
    SECRET 'YOUR_MINIO_PASSWORD',  -- Replace with your actual password
    ENDPOINT 'minio:9000',
    USE_SSL false,
    URL_STYLE 'path',
    SCOPE 's3://lakehouse'
);
```

**Step 2: Query data (no setup needed after Step 1):**
```sql
-- Query sample data - works immediately
SELECT * FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv') LIMIT 10;

-- Multi-file analytics
SELECT 
    product_category,
    COUNT(*) as orders,
    SUM(total_amount) as revenue
FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')
GROUP BY product_category
ORDER BY revenue DESC;

-- Multi-file queries across all CSVs
SELECT COUNT(*) as total_records 
FROM read_csv_auto('s3://lakehouse/raw-data/*.csv', union_by_name=true);
```

🎉 **The persistent secret survives sessions, logins, and container restarts!**

### 4. **Create Your First Pipeline**
**In JupyterLab** - Get your service URL from `./scripts/show-credentials.sh`:

**DuckDB Analytics:**
```python
import duckdb

# Connect to DuckDB (persistent secret already configured)
conn = duckdb.connect("/app/superset_home/lakehouse.duckdb")

# Query your data lake directly (no setup needed if secret exists)
result = conn.execute("""
    SELECT COUNT(*) as total_records 
    FROM read_csv_auto('s3://lakehouse/raw-data/*.csv', union_by_name=true)
""").fetchone()
print(f"Total records: {result[0]}")

# Advanced analytics
analytics = conn.execute("""
    SELECT 
        product_category,
        COUNT(*) as orders,
        SUM(total_amount) as revenue,
        AVG(total_amount) as avg_order_value
    FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')
    GROUP BY product_category
    ORDER BY revenue DESC
""").fetchall()

for row in analytics:
    print(f"Category: {row[0]}, Orders: {row[1]}, Revenue: ${row[2]:.2f}")
```

**PostgreSQL Analytics:**
```python
import psycopg2
import pandas as pd

# Connect to PostgreSQL analytics database  
# Get password from: ./scripts/show-credentials.sh
conn = psycopg2.connect(
    host="postgres", 
    database="lakehouse",
    user="postgres", 
    password="YOUR_POSTGRES_PASSWORD"
)

# Run analytical queries
df = pd.read_sql("""
    SELECT 
        order_date,
        SUM(total_revenue) as daily_revenue,
        COUNT(*) as daily_orders
    FROM analytics.order_facts 
    WHERE order_date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY order_date 
    ORDER BY order_date
""", conn)

print(df.head())
```

### 5. **AI-Powered Data API (MCP Server)**
**Natural language queries with the MCP Server** - Get your service URL from `./scripts/show-credentials.sh`:

**Example natural language queries:**
```bash
# Query via REST API (if authentication enabled, include JWT token)
curl -X POST http://localhost:9090/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me the top 5 product categories by revenue", "limit": 5}'

# Vector similarity search
curl -X POST http://localhost:9090/api/vector-search \
  -H "Content-Type: application/json" \
  -d '{"text": "find products similar to electronics", "limit": 10}'
```

**In Python (Jupyter):**
```python
import requests

# Natural language data query
response = requests.post('http://localhost:9090/api/query', json={
    "query": "What were the sales trends last month?",
    "source": "postgres"  # or "duckdb"
})
print(response.json())

# Vector search for semantic similarity
response = requests.post('http://localhost:9090/api/vector-search', json={
    "text": "customer complaints about delivery",
    "limit": 5
})
similar_records = response.json()
```

### 6. **Build Dashboards**
1. **Get Superset URL**: Run `./scripts/show-credentials.sh` to see your service URLs and login credentials
2. **Choose your database connection:**
   - **"DuckDB-S3"** - For data lake queries with persistent S3 access
   - **"PostgreSQL Analytics"** - For structured analytics and real-time dashboards  
3. **Create charts** with simple queries:
   - **DuckDB**: `SELECT * FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')`
   - **PostgreSQL**: `SELECT * FROM analytics.order_facts WHERE order_date >= CURRENT_DATE - 7`
4. **Advanced features**: Both connections support CREATE, INSERT, UPDATE, DELETE operations
5. See the [Superset Database Setup Guide](SUPERSET_DATABASE_SETUP.md) for detailed configuration

### 7. **Modern Interactive Dashboards (Vizro)**
**Get Vizro URL**: Run `./scripts/show-credentials.sh` to see your service URLs

**🎨 Dashboard Development Options:**
1. **Notebook-Based Development** (Recommended):
   - Open `04_Vizro_Interactive_Dashboards.ipynb` in JupyterLab
   - Interactive development with immediate chart preview
   - AI-powered analytics combining Vizro + LanceDB vector search
   - Professional templates for business intelligence

2. **Advanced Analytics Dashboard**:
   - Open `06_Advanced_Analytics_Vizro_LanceDB.ipynb` for AI-powered dashboards
   - Semantic similarity analysis and clustering
   - Vector-based recommendation systems
   - Multi-modal analytics visualization

3. **Ready-to-Use Templates**:
   - `07_Interactive_Dashboard_Development.ipynb` - Complete development template
   - Works in any environment (no network setup required) 
   - Professional charts with hover, zoom, pan, and filtering

**🚀 Production Dashboards:**
1. **Pre-built Examples**: Access `/sample-dashboard` for sales analytics demo
2. **Configuration-Based**: Modify YAML/JSON files in `/config/dashboards/`
3. **Live Data**: Dashboards automatically update with fresh data from PostgreSQL and MinIO
4. **Interactive Features**: Filtering, drilling, real-time updates with modern UI

### 8. **Orchestrate with Airflow**
1. **Get Airflow URL**: Run `./scripts/show-credentials.sh` to see your service URLs and login credentials
2. **Available DAGs:**
   - **`sample_duckdb_pipeline`** - DuckDB ETL pipeline with S3 data processing
   - **`postgres_analytics_etl`** - ETL pipeline from DuckDB to PostgreSQL analytics
   - **`postgres_streaming_analytics`** - Real-time data processing with anomaly detection
3. **Getting started:** Enable and trigger the `sample_duckdb_pipeline` DAG to see DuckDB in action

## 🗂️ Project Structure

```
lakehouse-lab/
├── docker-compose.yml           # Main stack definition
├── init-all-in-one-modular.sh  # Modular initialization script
├── scripts/                    # Initialization modules
├── templates/                  # Configuration templates
├── .env.default                # Default configuration
├── .env.fat-server             # High-resource configuration
├── README.md                   # This file
├── QUICKSTART.md               # Step-by-step guide
└── lakehouse-data/             # Data directory (created on startup)
    ├── airflow/
    │   ├── dags/               # Airflow workflows
    │   └── logs/               # Execution logs
    ├── notebooks/              # Jupyter notebooks with examples
    ├── minio/                  # Object storage data
    ├── postgres/               # Metadata database
    ├── spark/jobs/             # Spark job files
    └── homer/assets/           # Dashboard configuration
```

## 🔧 Advanced Usage

### Multi-File Analytics with DuckDB
```sql
-- Query all CSV files in a directory (after persistent secret setup)
SELECT * FROM read_csv_auto('s3://lakehouse/raw-data/*.csv', union_by_name=true);

-- Cross-format queries  
SELECT * FROM read_parquet('s3://lakehouse/warehouse/*.parquet')
UNION ALL
SELECT * FROM read_csv_auto('s3://lakehouse/raw-data/*.csv');

-- Partitioned data analysis
SELECT * FROM read_csv_auto('s3://lakehouse/data/year=2024/month=*/day=*/*.csv');

-- Advanced analytics with window functions
SELECT 
    product_category,
    order_date,
    total_amount,
    AVG(total_amount) OVER (
        PARTITION BY product_category 
        ORDER BY order_date 
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) as moving_avg_7day
FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv')
ORDER BY product_category, order_date;
```

### Adding New Data Sources
1. **CSV Files**: Upload to MinIO via console or API
2. **Database Connections**: Configure in Trino catalogs (if enabled)
3. **APIs**: Create Airflow DAGs for ingestion

### Scaling Up
1. **More Spark Workers**: Increase `SPARK_WORKER_INSTANCES` in `.env`
2. **Database Performance**: Tune Postgres settings for your workload
3. **Memory Allocation**: Adjust service limits in `.env`

### Development Workflow
1. **Develop**: Use JupyterLab for interactive development
2. **Pipeline**: Convert notebooks to Airflow DAGs
3. **Monitor**: Check execution in Airflow UI and Portainer
4. **Visualize**: Create dashboards in Superset

## 🐛 Troubleshooting

### Installation Issues

**Problem: "lakehouse-init" service fails with exit 2**
```bash
# Solution: Use the upgraded installer (automatically fixes this)
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --replace
```

**Problem: Airflow database not initialized**
```bash
# Check if Airflow database tables exist
docker exec lakehouse-lab-postgres-1 psql -U postgres -d airflow -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';"

# If no tables, manually run initialization
docker-compose run --rm airflow-init
```

**Problem: Previous installation blocking new install**
```bash
# The installer now automatically detects and offers upgrade options, or:
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --replace
```

### Services Won't Start
```bash
# Check service status
docker compose ps

# View logs for specific service
docker compose logs airflow-webserver
docker compose logs lakehouse-init

# Restart specific service
docker compose restart superset

# Full restart of all services
docker compose restart
```

### DuckDB S3 Connection Issues
```sql
-- Check if persistent secret exists
SELECT * FROM duckdb_secrets();

-- If no secret, create one (get password from ./scripts/show-credentials.sh)
CREATE PERSISTENT SECRET minio_secret (
    TYPE S3,
    KEY_ID 'admin',
    SECRET 'YOUR_MINIO_PASSWORD',
    ENDPOINT 'minio:9000',
    USE_SSL false,
    URL_STYLE 'path',
    SCOPE 's3://lakehouse'
);

-- Test connectivity
SELECT COUNT(*) FROM read_csv_auto('s3://lakehouse/raw-data/sample_orders.csv');
```

### Memory Issues
```bash
# Check memory usage
docker stats --no-stream

# Reduce memory limits in .env file
SUPERSET_MEMORY_LIMIT=2G
SPARK_WORKER_MEMORY_LIMIT=4G
```

### Port Conflicts
Change port mappings in docker-compose.yml:
```yaml
ports:
  - "9999:8080"  # Change 9010 to 9999
```

### Data Access Issues
```bash
# Test MinIO access (get URL from ./scripts/show-credentials.sh)
curl http://YOUR_IP:9001

# Check file permissions
ls -la lakehouse-data/

# Test PostgreSQL connection
docker exec lakehouse-lab-postgres-1 psql -U postgres -d lakehouse -c "SELECT version();"

# Reset all data (WARNING: Destroys everything)
docker compose down -v
rm -rf lakehouse-data/
docker compose up -d
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Test with both standard and fat-server configs
4. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

Built with these amazing open source projects:
- [DuckDB](https://duckdb.org/) - Fast analytical database with S3 support
- [PostgreSQL](https://www.postgresql.org/) - Advanced open source relational database
- [Apache Spark](https://spark.apache.org/) - Unified analytics engine
- [Apache Airflow](https://airflow.apache.org/) - Workflow orchestration
- [Apache Superset](https://superset.apache.org/) - Modern BI platform
- [MinIO](https://min.io/) - High-performance S3-compatible storage
- [Portainer](https://www.portainer.io/) - Container management platform
- [Homer](https://github.com/bastienwirtz/homer) - Static service dashboard

## 🌟 Key Features

- ✅ **15-minute setup** - Complete lakehouse in minutes with one-click install
- ✅ **Enterprise-ready security** - Optional OAuth authentication with federated providers
- ✅ **AI-powered data API** - Natural language queries via Model Context Protocol (MCP)
- ✅ **S3-native analytics** - Query files directly with DuckDB without data movement
- ✅ **Modern interactive dashboards** - Vizro framework for dynamic, responsive visualizations
- ✅ **Vector database integration** - LanceDB for semantic search and AI/ML workflows
- ✅ **Multi-file processing** - Wildcard queries across datasets with format auto-detection
- ✅ **Role-based access control** - Granular permissions for team collaboration
- ✅ **Triple analytics architecture** - Data lake + warehouse + vector database unified
- ✅ **Production patterns** - Learn real-world data engineering with enterprise features
- ✅ **Container monitoring** - Full observability with Portainer and audit logging
- ✅ **Scalable architecture** - From individual laptops to enterprise team deployments
- ✅ **Configurable deployment** - Enable only the services you need to optimize resources

---

**Happy Data Engineering!** 🚀

For questions and support, please open an issue on GitHub.
