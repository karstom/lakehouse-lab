# Changelog

## [3.0.0-beta.1] - 2026-09-28

The first V3 release: a new stack, not an in-place upgrade of V2. It is a **beta**; see the
[release notes](../v3/RELEASE_NOTES_v3.0.0-beta.1.md) for known gaps and how to report
issues. Coming from V2? Read the [migration guide](MIGRATION.md).

### Stack
- **One login and one catalog.** Keycloak SSO on subdomains behind Caddy (with a local CA
  created once and kept across upgrades), Lakekeeper as the Iceberg REST catalog with
  OpenFGA authorization, and SeaweedFS (replacing MinIO) with STS. Engines get short-lived,
  table-scoped credentials from the catalog: no static S3 keys in Trino, Spark or notebooks.
- **Engines:** Trino, Spark 4.1 with Spark Connect (the logged-in user's identity per
  session), DuckDB and dbt in every workspace.
- **Per-user workspace:** JupyterHub spawns JupyterLab + code-server per user, signed in
  through Keycloak, with Trino, Spark, DuckDB, PyIceberg and dbt preconfigured as that user.
- **Orchestration and BI** (profiles `engineer`/`full`): Airflow 3 with the Keycloak auth
  manager and per-user DAG folders; Superset 6 querying Trino as the logged-in user.
- **Lab Console** with service tiles and health, and optional "Sign in with GitHub" through
  Keycloak (new GitHub users get no access until an admin adds them to a group).
- **Profiles:** `core`, `engineer`, `full`, chosen at install time.

### Learning
- Two **learning tracks**, data engineer (E1–E4) and data analyst (A1–A4), with a
  checkpoint (`lab-tracks check`) and a safe reset for every module, using lab data only.

### AI assist (profile `full`)
- A model gateway (LiteLLM, open-source part only) with per-user keys and budgets, and a
  Lab Assistant in JupyterLab whose MCP tools (Trino, dbt, Superset, lab context) act as the
  user, read-only.
- **Hosted providers are off by default**; an admin turns one on explicitly with its key.
  Local models work through any OpenAI-compatible server, with optional **quiet hours**.
  With no provider enabled, the lab makes no outbound AI call.

### Installer and operations
- `v3/install.sh` (re-runnable; keeps settings, secrets and the CA) and the `v3/lab` CLI
  (`up`, `down`, `status`, `urls`, `sync`, `logs`, `reset`, `test`, `ca`, `ai …`).
- Every version is pinned once, in `v3/versions.env`; images are built from pinned bases with
  no package installs at container start.
- CI installs each profile for real and runs an end-to-end smoke test as real users
  (`v3-ci` for `core`/`engineer` on every PR, `v3-nightly` for `full`).

### Repository
- V2 moved to [`legacy/v2/`](../legacy/v2/) (its docs to `legacy/v2/docs/`, its CI
  workflows to `legacy/v2/workflows/`, where they no longer run). The V2 code on `main` is
  tagged `v2.1.1-final`.
- The root `install.sh` is now a small bootstrap for the one-line install: it fetches the
  repository at a ref and runs `v3/install.sh`.
- The V3 design docs moved from `docs/v3/` to `docs/`.

## [2.1.1] - 2025-09-08

### 🏗️ Infrastructure Stability & Core Stack Focus
- **🎯 Dashboard System Removal**: Removed all dashboard functionality (Homer, Homepage, Dashy) to focus on core stack reliability
- **🛠️ Docker Compose Fixes**: Fixed duplicate YAML keys and orphaned container warnings preventing installations
- **🔧 Installation Process Improvements**: Resolved YAML syntax errors and volume creation issues blocking upgrades
- **⚡ Service Integration**: Added Vizro Dashboard Framework and LanceDB Vector Database to core stack

### 🐛 Critical Bug Fixes
- **📋 YAML Syntax Error**: Fixed duplicate 'deploy' key in Portainer service causing installation failures
- **🐳 Orphaned Containers**: Added `--remove-orphans` flags across all Docker Compose commands to eliminate warnings
- **🔍 MinIO Configuration**: Removed unnecessary MinIO restarts during Smart Upgrade preventing timeout issues
- **🔗 Host Validation**: Fixed Homepage host validation errors when accessing from external IP addresses
- **💾 Credential Display**: Fixed misleading credential displays by reading actual values from .env files

### 🚀 Service & Network Improvements  
- **🌐 Dynamic HOST_IP Detection**: Enhanced IP detection and configuration for external access scenarios
- **🔄 PostgreSQL Synchronization**: Improved password synchronization between .env files and container state
- **📊 Variable Handling**: Fixed Docker Compose variable warnings by properly escaping shell variables
- **🔧 Service Dependencies**: Better error handling for service startup and dependency management

### 📚 Architecture Simplification
- **🎯 Core Focus**: Eliminated complex dashboard dependencies and potential failure points
- **⚡ Reduced Overhead**: Removed dashboard services improving overall system performance
- **🛡️ Enhanced Reliability**: Simplified initialization process focusing on data engineering functionality
- **📋 Clean Configuration**: Streamlined docker-compose.yml without dashboard-related complexity

This patch release prioritizes **rock-solid stability** and **installation reliability** while maintaining all core data engineering capabilities. All services remain fully accessible via direct URLs without dashboard overhead.

## [2.1.0] - 2025-09-05

### 💾 Comprehensive Backup & Restore System
- **🔄 Complete Backup Solution**: Full-featured backup system supporting all services (PostgreSQL, MinIO, Jupyter, Airflow, Spark, Superset, etc.)
- **📅 Flexible Scheduling**: CRON integration with automated setup script and Airflow DAG template for workflow-integrated backups
- **🗜️ Advanced Features**: Compression, verification, parallel processing, service exclusion, and configurable retention policies
- **📧 Monitoring & Notifications**: Email notifications, comprehensive logging, backup verification, and automatic cleanup
- **🔧 Easy Setup**: Interactive CRON setup wizard and ready-to-use Airflow DAG template
- **⚡ Granular Restore**: Complete system restore or service-specific recovery with safety confirmations and dry-run mode

### 🛠️ Smart Upgrade System & Data Migration
- **🧠 Intelligent Upgrade Detection**: Automatic detection of existing installations with user-friendly upgrade options
- **🔒 Named Volume Migration**: Migration from vulnerable bind mounts to persistent Docker named volumes for better security
- **📁 Data Preservation**: Safe migration of all existing data using rsync with metadata preservation
- **🔧 Template Updates**: Automatic service template updates during migration to ensure latest code deployment
- **🎯 Smart Installer**: Enhanced installer with directory nesting detection and path resolution improvements
- **✅ Migration Verification**: Comprehensive verification of data integrity during migration process

### 🔐 Enhanced Security & Volume Management  
- **🛡️ External Volume Security**: Proper external volume declarations with explicit naming to prevent Docker warnings
- **🔑 Airflow Permissions**: Fixed volume ownership issues with proper user/group assignment (50000:0)
- **🔧 Credential Management**: Enhanced credential script with intelligent .env file discovery across directories
- **📊 Volume Creation**: Automatic named volume creation with proper permissions during startup
- **🔄 Service Dependencies**: Improved service startup order and health checks for reliable initialization

### 🐛 Critical Bug Fixes & Stability Improvements
- **🔧 LanceDB Syntax Errors**: Fixed Python syntax errors in init-lancedb.sh and template deployment issues
- **📁 MinIO Configuration**: Resolved missing access keys after migration by ensuring hidden file migration
- **🏗️ Install Process**: Fixed installer directory nesting problems and enhanced path resolution
- **⚡ Service Startup**: Improved reliability of service initialization and dependency management
- **🔄 Migration Reliability**: Enhanced data migration with rsync and comprehensive error handling

### 📚 Documentation & User Experience
- **📖 Learning-Focused Messaging**: Updated documentation to emphasize learning and lab-scale use cases
- **⚠️ Production Guidance**: Clear messaging that Lakehouse Lab is designed for learning environments, not mission-critical production workloads
- **📋 Backup Documentation**: Comprehensive backup and restore documentation with examples
- **🎯 Upgrade Guidance**: Enhanced installation documentation with upgrade paths and troubleshooting
- **🔧 Improved Help**: Better error messages and user guidance throughout the system

This release significantly enhances data protection, system reliability, and user experience while maintaining the learning-focused mission of Lakehouse Lab.

## [2.0.0] - 2025-08-23

### 🏢 Enterprise Authentication & Team Collaboration
- **🔐 Optional Federated Authentication**: Complete OAuth integration with Google, Microsoft, and GitHub
- **🎯 Role-Based Access Control**: Four user roles (data_viewer, data_analyst, data_engineer, admin) with granular permissions
- **🛡️ Authentication Proxy**: Service access control with audit logging and permission checking
- **🏠 Preserve One-Click Install**: Original simple installation completely unchanged and preserved
- **⚡ Flexible Deployment**: Can start simple and add authentication later, or install with full security


### 📊 Modern Interactive Dashboards (Vizro)
- **🎨 Vizro Dashboard Framework**: Low-code interactive dashboard creation
- **🔗 Lakehouse Integration**: Direct connection to PostgreSQL and MinIO data sources
- **📈 Sample Dashboards**: Pre-built examples with sales analytics and business metrics
- **🎯 Configuration-Based**: JSON/YAML dashboard definitions with hot-reload
- **📱 Modern UI**: Responsive, interactive dashboards with Plotly integration

### 🗄️ High-Performance Vector Database (LanceDB)
- **⚡ LanceDB Integration**: High-performance vector operations for AI/ML workloads
- **🔍 Semantic Search**: Vector similarity search with TF-IDF and custom embeddings
- **📊 REST API**: FastAPI-based service for vector operations and management
- **📈 Analytics Ready**: Integration with clustering, UMAP, and ML workflows
- **🎯 Production Ready**: Persistent storage with backup and recovery capabilities

### 🎛️ Advanced Service Configuration System  
- **⚙️ Interactive Configuration Wizard**: Easy service selection with resource estimates
- **📋 Preset Configurations**: Minimal (8GB), Analytics (14GB), ML/AI (16GB), Full (20GB), Secure (22GB)
- **🔧 Docker Compose Override**: Automatic service enable/disable via compose profiles
- **📊 Resource Planning**: RAM usage estimates and system recommendations
- **🔄 Runtime Reconfiguration**: Change service configurations without rebuilding

### 📚 Comprehensive Learning Resources
- **📓 Advanced Example Notebooks**: Three new comprehensive tutorials showcasing modern capabilities
  - `04_Vizro_Interactive_Dashboards.ipynb`: Complete Vizro dashboard development guide
  - `05_LanceDB_Vector_Search.ipynb`: Vector database and semantic search tutorial  
  - `06_Advanced_Analytics_Vizro_LanceDB.ipynb`: Combined AI-powered analytics workflows
- **🤖 LLM Development Guide**: Complete metadata guide for AI/LLM developers (`LAKEHOUSE_LLM_GUIDE.md`)
- **⚙️ Configuration Documentation**: Comprehensive service configuration guide (`CONFIGURATION.md`)

### 🚀 Installation & User Experience
- **📦 Multiple Installation Paths**:
  - `install.sh` - Original one-click install (unchanged)
  - `install-with-auth.sh` - New secure team installation
  - `scripts/enable-auth.sh` - Add authentication to existing installations
- **🎯 Setup Wizards**: Interactive configuration for OAuth providers and service selection
- **📋 Enhanced Documentation**: Updated README with all new capabilities and architecture
- **🔧 Backward Compatibility**: All existing installations continue to work unchanged

### 🏗️ Architecture Enhancements
- **🏢 Triple Analytics Architecture**: Data Lake (DuckDB) + Data Warehouse (PostgreSQL) + Vector Database (LanceDB)
- **🔒 Security-First Design**: Authentication, authorization, audit, and monitoring built-in
- **📊 Microservices Pattern**: Optional authentication services with health checks and monitoring
- **🐳 Container Orchestration**: Enhanced Docker Compose with profiles and service dependencies
- **📈 Production Ready**: Resource limits, health checks, and enterprise-grade configurations

### 🛡️ Security & Compliance
- **🔐 OAuth 2.0/OIDC**: Standards-compliant authentication with popular identity providers
- **📋 Comprehensive Audit Logging**: All user actions logged with timestamps and details
- **🎯 Permission Matrix**: Granular operation-level permissions per user role
- **🔒 JWT Security**: Secure session management with configurable expiration
- **📊 Security Monitoring**: Built-in anomaly detection and security event logging

### 🔧 Developer Experience
- **🎯 Zero-Config for Development**: Local authentication fallback requires no OAuth setup
- **🔧 Gradual Complexity**: Start simple, add features as needed
- **📚 Complete Code Examples**: Full implementation patterns for all services
- **🤖 AI-Friendly**: Comprehensive metadata for LLM-assisted development
- **🔄 Hot Reload**: Configuration changes without service rebuilds

### 📚 Comprehensive Documentation Overhaul
- **📖 README.md**: Complete rewrite with enterprise features, comparison tables, and updated architecture
- **🚀 QUICKSTART.md**: New v2.0.0 walkthrough with AI features, authentication, and modern dashboards
- **⚙️ INSTALLATION.md**: Enterprise installation paths, OAuth setup, and configuration-based requirements
- **🔧 CONFIGURATION.md**: Updated service presets including secure configuration option
- **🤖 LAKEHOUSE_LLM_GUIDE.md**: Enhanced with AI layer architecture and vector database integration
- **🎯 User Experience**: Clear separation between individual developer and enterprise team workflows

This release transforms Lakehouse Lab from a development-focused data platform into a production-ready, team-collaboration platform while preserving the simplicity that made it popular for individual developers and learners.

## [1.3.0] - 2025-07-29

### 🚀 Dynamic Package Management System
- **📦 Notebook Package Manager**: New interactive system for installing Python packages on-the-fly in Jupyter notebooks
- **🎯 User-Level Installation**: Safe package installation to user directory without affecting base environment
- **🔍 Package Discovery**: Built-in search and package information functions
- **📚 Categorized Suggestions**: Curated lists of popular data science packages by use case
- **🛠️ Comprehensive Management**: Install, uninstall, list, search, and check package availability
- **⚡ Install & Import**: Convenience function to install and immediately import packages

### 🏗️ Modular Architecture Enhancements  
- **80% Code Reduction**: Streamlined initialization system with modular design
- **🔧 Enhanced Error Handling**: Robust retry mechanisms for MinIO and service initialization
- **📊 Dual-Engine Iceberg Support**: Both DuckDB and Spark engines with automatic fallback
- **🎯 Dynamic JAR Management**: Automatic download and configuration of Iceberg dependencies
- **🔄 Improved Service Dependencies**: Better Docker health checks and startup sequencing

### 🧊 Apache Iceberg Integration Fixes
- **✅ JAR Download Resolution**: Fixed Maven repository URLs and artifact paths  
- **🔗 AWS SDK Compatibility**: Added both v1 and v2 SDK JARs for complete S3A support
- **🦆 DuckDB Primary Engine**: DuckDB as recommended engine with Spark as advanced option
- **⚙️ Automatic Configuration**: Self-configuring Iceberg setup with MinIO integration
- **🎯 Enhanced Debugging**: Comprehensive logging for JAR detection and loading

### 🐛 Critical Fixes
- **Fixed MinIO initialization**: Added retry logic and authentication debugging for startup reliability
- **Fixed PostgreSQL SQLAlchemy**: Updated to SQLAlchemy 2.0 syntax with text() wrapper for raw SQL
- **Fixed notebook template corruption**: Resolved missing JSON structure in Jupyter notebooks  
- **Fixed package manager deployment**: Proper file copying during analytics initialization
- **Fixed f-string syntax errors**: Resolved Python syntax issues in package management code

### 📚 New Documentation
- **NOTEBOOK_PACKAGE_MANAGER.md**: Comprehensive user guide for dynamic package management
- **Enhanced README**: Updated with latest features and package management capabilities
- **Improved code documentation**: Better inline documentation and usage examples

### 🔧 Developer Experience
- **Automated deployment**: Package manager automatically deployed during clean installations
- **Template organization**: Moved package manager to templates directory for better organization
- **Git cleanup**: Removed obsolete development files and improved repository structure
- **Enhanced testing**: Better integration testing and error reporting

## [1.2.0] - 2025-07-23

### 🔒 Major Security Overhaul
- **🎯 Unique Credential Generation**: Every installation now gets unique, secure credentials automatically
- **🚫 Eliminated Default Passwords**: Removed all hardcoded credentials (admin/admin, minio/minio123, token: lakehouse)
- **🎪 Memorable Passphrases**: User-friendly formats like `swift-river-bright-847` for easy typing
- **🔐 Strong Backend Passwords**: Cryptographically secure passwords for databases and internal services
- **🛡️ Environment Variable Security**: All secrets now stored in .env file (automatically git-ignored)

### 🆕 New Credential Management System
- **`./scripts/generate-credentials.sh`** - Automatic secure credential generation during installation
- **`./scripts/show-credentials.sh`** - User-friendly credential display with copy-paste ready format
- **`./scripts/rotate-credentials.sh`** - Safe credential rotation with automatic backups
- **`.env.example`** - Comprehensive configuration template with security documentation
- **Enhanced .gitignore** - Prevents accidental credential commits

### 🔧 Critical Bug Fixes
- **Fixed shell variable expansion errors** - Resolved "unbound variable" errors in credential scripts
- **Fixed Superset permission issues** - Resolved directory creation and package installation failures
- **Fixed PySpark integration** - Resolved module import conflicts in Jupyter notebooks
- **Fixed PostgreSQL role errors** - Corrected database user creation for proper startup
- **Fixed MinIO initialization** - Updated credential handling in bucket creation scripts
- **Fixed Airflow database connections** - Dynamic credential integration for all database operations
- **Fixed Docker Compose warnings** - Resolved environment variable and attribute warnings

### ✨ Enhancements
- **PIL/Pillow support in Superset** - Enables dashboard screenshots and PDF export functionality
- **Enhanced PySpark error handling** - Better diagnostic messages for Jupyter notebook issues
- **Improved installation validation** - Password generation validation and error recovery
- **Enhanced debugging output** - Better diagnostic information during setup and troubleshooting

### 📚 Documentation Updates
- **README.md** - Complete security section with credential management documentation
- **QUICKSTART.md** - Updated all login instructions to use credential scripts
- **INSTALLATION.md** - Comprehensive security and credential management guide
- **Technical documentation** - Replaced all hardcoded credential references with secure alternatives

### 🔄 Migration & Compatibility
- **Preserves existing installations** - Upgrade detection with smart migration options
- **Maintains profile compatibility** - Works with existing .env.fat-server configurations
- **Backward compatible** - Existing workflows continue to function with enhanced security
- **Safe credential rotation** - Non-disruptive password updates with service restart handling

### 🐛 Infrastructure Fixes
- **Jupyter notebook JSON generation** - Fixed f-string syntax errors in notebook creation
- **Docker Compose modernization** - Removed obsolete version attributes and warnings
- **Service initialization order** - Improved dependency handling and startup reliability
- **Container permission handling** - Enhanced file system permission management across services

### 📊 Service-Specific Improvements

#### Superset
- Fixed package installation permission errors
- Added PIL support for dashboard export features
- Updated MinIO credential integration for S3 connections
- Enhanced database connection string generation

#### Jupyter
- Resolved PySpark module availability issues
- Fixed conda environment path configuration
- Enhanced notebook generation with proper JSON syntax
- Improved Spark connection configuration

#### Airflow
- Fixed database initialization and migration issues
- Updated connection string generation with dynamic credentials
- Enhanced webserver startup reliability
- Improved scheduler database connectivity

#### MinIO
- Fixed bucket creation with dynamic credentials
- Enhanced readiness check reliability
- Updated initialization scripts for credential integration
- Improved error diagnostics for storage operations

## [1.1.0] - 2025-07-18

### Added
- **Smart upgrade detection** - Installer automatically detects existing installations
- **User-friendly upgrade options** - Interactive prompts for upgrade vs replace
- **Automatic backup creation** during upgrades to preserve data
- **Direct upgrade/replace flags** for automated deployments (`--upgrade`, `--replace`)

### Fixed
- **Lakehouse initialization service** - Fixed exit 2 errors on clean installations
- **Shell compatibility issues** - Fixed bash vs POSIX shell compatibility in Alpine containers
- **Airflow database initialization** - Resolved database connection and initialization issues
- **Test runner script** - Fixed requirements.txt path in test framework
- **Iceberg JAR file management** - Fixed directory creation and volume mapping issues
- **Docker Compose volume paths** - Updated to use proper LAKEHOUSE_ROOT directory structure

### Changed
- **Enhanced installer.sh** with upgrade detection and smart handling
- **Improved error handling** for failed initialization scenarios
- **Better documentation** with upgrade procedures and troubleshooting
- **Shell script compatibility** - All scripts now work across different shell environments

### Technical Details
- Fixed bash array syntax compatibility with Alpine Linux sh
- Updated iceberg-jars path from `./iceberg-jars` to `${LAKEHOUSE_ROOT}/iceberg-jars`
- Improved lakehouse-init service with proper error reporting
- Enhanced install.sh with backup/restore functionality for upgrades

## [1.0.0] - 2025-06-05

### Added
- Complete lakehouse stack with Docker Compose
- DuckDB + S3 native analytics
- Apache Spark 3.5 distributed processing
- Apache Airflow 2.8 workflow orchestration
- Apache Superset BI and visualization
- MinIO S3-compatible object storage
- Portainer container management
- Jupyter notebooks with examples
- Automated initialization and sample data
- Fat server configuration for high-performance deployments
- Comprehensive documentation and quickstart guide

### Features
- 15-minute setup from zero to running analytics
- Multi-file S3 querying with DuckDB
- Pre-configured sample datasets and notebooks
- Production-ready container orchestration
- Scalable from laptop to enterprise server
