# Changelog

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
