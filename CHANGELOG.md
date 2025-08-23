# Changelog

## [2.0.0] - 2025-08-23

### 🏢 Enterprise Authentication & Team Collaboration
- **🔐 Optional Federated Authentication**: Complete OAuth integration with Google, Microsoft, and GitHub
- **🎯 Role-Based Access Control**: Four user roles (data_viewer, data_analyst, data_engineer, admin) with granular permissions
- **🛡️ Authentication Proxy**: Service access control with audit logging and permission checking
- **🏠 Preserve One-Click Install**: Original simple installation completely unchanged and preserved
- **⚡ Flexible Deployment**: Can start simple and add authentication later, or install with full security

### 🤖 AI-Powered Data API (MCP Server)
- **🧠 Model Context Protocol Server**: AI-powered data access with natural language capabilities
- **🔍 Intelligent Query Assistant**: Convert natural language to SQL and data insights
- **🎨 Vizro Integration**: Generate interactive dashboards from SQL queries via natural language
- **📊 Smart Chart Creation**: Automatic chart type selection based on data analysis
- **🔒 Security Integrated**: Full authentication and authorization for AI operations
- **📊 Multi-Source Access**: Unified API for PostgreSQL, MinIO, DuckDB, and LanceDB
- **📋 Audit & Compliance**: Complete audit trail for all AI-assisted data operations

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
- **🤖 LAKEHOUSE_LLM_GUIDE.md**: Enhanced with AI layer architecture and MCP server integration
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
