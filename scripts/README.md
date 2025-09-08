# 🔧 Lakehouse Lab Scripts

This directory contains utility scripts for managing and operating Lakehouse Lab.

## 📁 Directory Structure

```
scripts/
├── install/                    # Installation and migration scripts
│   ├── migrate-to-named-volumes.sh    # Smart upgrade migration
│   ├── enable-jupyterhub.sh           # Enable multi-user JupyterHub
│   └── fix-credentials.sh             # Fix credential issues
├── legacy/                     # Legacy scripts (deprecated)
│   ├── init-all-in-one-modular.sh    # Old modular initialization
│   └── init-all-in-one.sh            # Old single initialization
├── backup-lakehouse.sh         # Comprehensive backup system
├── restore-lakehouse.sh        # Data restoration system  
├── generate-credentials.sh     # Secure credential generation
├── show-credentials.sh         # Display current credentials
├── provision-user.sh          # Direct user creation in services
├── configure-services.sh      # Service configuration wizard
└── setup-wizard.sh           # Interactive setup wizard
```

## 🚀 Main Scripts (User-Facing)

### Backup & Restore
- **`backup-lakehouse.sh`** - Complete backup system with compression and verification
- **`restore-lakehouse.sh`** - Restore from backups with safety confirmations

### Configuration & Setup  
- **`configure-services.sh`** - Interactive service selection and configuration
- **`setup-wizard.sh`** - Complete setup wizard for new installations
- **`generate-credentials.sh`** - Generate secure random credentials
- **`show-credentials.sh`** - Display service URLs and credentials

### User Management
- **`provision-user.sh`** - Create users directly in services (Superset, Airflow, etc.)


## 🛠️ Installation Scripts (`install/`)

### Migration & Upgrades
- **`migrate-to-named-volumes.sh`** - Migrate from bind mounts to named volumes
- **`enable-jupyterhub.sh`** - Switch from Jupyter to multi-user JupyterHub
- **`fix-credentials.sh`** - Fix common credential issues

## 📚 Legacy Scripts (`legacy/`)

**⚠️ Deprecated** - These scripts are kept for compatibility but are no longer actively maintained:
- **`init-all-in-one-modular.sh`** - Old modular initialization system  
- **`init-all-in-one.sh`** - Old single-file initialization

## 🎯 Usage Examples

```bash
# Backup all services with compression
./scripts/backup-lakehouse.sh --compress --verify

# Configure which services to run
./scripts/configure-services.sh

# Provision a new user across all services  
./scripts/provision-user.sh john.doe john.doe@company.com SecurePass123 analyst

# Show service URLs and credentials
./scripts/show-credentials.sh

# Run smart upgrade migration
./scripts/install/migrate-to-named-volumes.sh
```

## 💡 Script Development

When adding new scripts:
1. Make them executable: `chmod +x script-name.sh`
2. Add proper help output with `--help` flag
3. Include error handling and validation
4. Follow the existing naming conventions
5. Add entry to this README

---

**Need help?** Check the main [documentation](../docs/README.md) or run any script with `--help`.