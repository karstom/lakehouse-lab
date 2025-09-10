# 🚀 Lakehouse Lab Installation Guide

**Version 2.1.1** - Complete installation options for all platforms and use cases, from individual learning to educational institutions with multi-user JupyterHub environments.

> ⚠️ **Critical for New Users**: You **MUST** use `./install.sh` for first-time installation. Running `docker compose up -d` directly will fail because it requires secure credentials and proper initialization that only the installer provides.

## ⚡ One-Command Installation

### 🎓 **Individual Student Installation (Simple & Fast)**

**Standard Installation (Recommended for Learning):**
```bash
# For laptops, workstations, small servers (8-16GB RAM)
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
```

**High-Performance Installation:**
```bash
# For powerful servers (32+ cores, 64GB+ RAM)
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --fat-server
```

### 🏫 **Educational Institution Installation (Multi-User & Collaborative)**

**Standard Multi-User Installation:**
```bash
# Complete installation for classrooms and computer labs
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
```

### 🎯 **Interactive Setup Wizard (After Installation)**

**Configure Services After Installation:**
```bash
# Standard installation first
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash

# Then run the setup wizard to configure services
cd lakehouse-lab
./scripts/setup-wizard.sh
```

**Or use preset configurations:**
```bash
# After installation, configure with presets
cd lakehouse-lab
./scripts/setup-wizard.sh --minimal    # 8GB RAM
./scripts/setup-wizard.sh --analytics  # 14GB RAM  
./scripts/setup-wizard.sh --ml         # 16GB RAM
./scripts/setup-wizard.sh --full       # 20GB RAM
```

**Windows WSL or macOS users** (if piping fails):
```bash
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh -o /tmp/install.sh && bash /tmp/install.sh
```

### **Unattended Installation (CI/CD)**
```bash
# No prompts, automatic installation
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --unattended
```

### **Download Only (Manual Start)**
```bash
# Download and configure, but don't start services
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --no-start
```

## 🔄 Upgrading Existing Installation

### **Automatic Detection & Smart Upgrade**

The installer automatically detects existing Lakehouse Lab installations and provides user-friendly upgrade options:

```bash
# Run the installer - it will detect existing installation and offer options
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
```

**What the installer detects:**
- Existing installation directory
- Running Docker services  
- Data directory with your analytics data

**You'll see options like:**
```
🔍 Existing Lakehouse Lab installation detected!

📁 Found installation directory: lakehouse-lab
🐳 Found running services:
     lakehouse-lab-airflow-webserver-1	Up 2 hours
     lakehouse-lab-postgres-1		Up 2 hours (healthy)
💾 Found data directory with your analytics data

What would you like to do?

1) Upgrade - Update to latest version (keeps your data and settings)
2) Replace - Fresh installation (⚠️  removes all data and starts over)
3) Cancel - Exit without making changes
```

### **Direct Upgrade Commands**

```bash
# Upgrade preserving all data and settings
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --upgrade

# Fresh installation (clean slate) - useful for fixing issues
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --replace

# Unattended upgrade (defaults to preserve data)
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --upgrade --unattended
```

### **What Happens During Upgrade**

**Upgrade Mode (--upgrade):**
1. ✅ Gracefully stops running services
2. ✅ Creates timestamped backup (`lakehouse-lab_backup_20250718_120500`)
3. ✅ Downloads latest version
4. ✅ Restores your data directory and custom settings
5. ✅ Preserves all dashboards, workflows, and configurations

**Replace Mode (--replace):**
1. 🧹 Stops and removes all services (`docker compose down -v`)
2. 🧹 Removes existing directories and data
3. 🧹 Removes initialization markers (fixes corrupted installations)
4. ✨ Performs fresh clean installation

### **When to Use Each Mode**

| Use Case | Recommended Mode | Why |
|----------|------------------|-----|
| **Regular updates** | Upgrade | Preserves all your work |
| **Getting new features** | Upgrade | Keeps existing data and settings |
| **Fixing broken installation** | Replace | Clean slate fixes initialization issues |
| **Starting fresh** | Replace | Removes all old data |
| **After failed initial install** | Replace | Cleans up any partial state |

## 🔧 Service Configuration

### **Service Configuration Presets**
```bash
# Configure which services to enable
./scripts/configure-services.sh

# Use presets
./scripts/configure-services.sh preset minimal     # 8GB RAM
./scripts/configure-services.sh preset analytics  # 14GB RAM  
./scripts/configure-services.sh preset ml         # 16GB RAM
./scripts/configure-services.sh preset full       # 20GB RAM
```

## 🔧 Installation Options

| Option | Description | Example |
|--------|-------------|---------|
| `--fat-server` | Use high-performance configuration (64GB+ RAM) | `--fat-server` |
| `--iceberg` | Enable Apache Iceberg table format support | `--iceberg` |
| `--no-start` | Download only, don't start services | `--no-start` |
| `--unattended` | No prompts, assume yes to all | `--unattended` |
| `--skip-deps` | Skip dependency installation | `--skip-deps` |
| `--dir DIR` | Install to custom directory | `--dir my-lakehouse` |
| `--branch BRANCH` | Use specific git branch | `--branch develop` |
| `--upgrade` | Upgrade existing installation (preserve data) | `--upgrade` |
| `--replace` | Replace existing installation (clean slate) | `--replace` |

## 🔒 Security & Credentials

### **Automatic Secure Credential Generation**

**No more default passwords!** Lakehouse Lab automatically generates unique, secure credentials for every installation:

- 🎯 **Memorable Passphrases**: Easy-to-type formats like `swift-river-bright-847`
- 🔐 **Strong Database Passwords**: Cryptographically secure for backend services  
- 🔄 **Unique Per Installation**: Every deployment gets different credentials
- 🛡️ **Environment Variables**: Secure configuration without hardcoded secrets

### **Credential Management**

```bash
# View all your service credentials
./scripts/show-credentials.sh

# Generate new credentials (overwrites existing)
./scripts/generate-credentials.sh

# Rotate all credentials (backup old ones)
./scripts/rotate-credentials.sh
```

### **Security Best Practices**

- ✅ Credentials are stored in `.env` file (automatically git-ignored)
- ✅ Back up your `.env` file in a secure location
- ✅ Never commit `.env` to version control
- ✅ Use `./scripts/show-credentials.sh` to access credentials securely
- ✅ Rotate credentials periodically with `./scripts/rotate-credentials.sh`

### **Credential Storage**

Your credentials are stored in:
- **Main file**: `.env` (environment variables)
- **Summary**: `.credentials-summary.txt` (human-readable format)
- **Backups**: `.env.backup.YYYYMMDD_HHMMSS` (created during rotation)

## 🖥️ Traditional Installation

### **Manual Git Clone**
```bash
git clone https://github.com/karstom/lakehouse-lab.git
cd lakehouse-lab
cp .env.default .env  # or .env.fat-server for high-end systems
docker compose up -d
```

### **Using the Startup Script**
```bash
git clone https://github.com/karstom/lakehouse-lab.git
cd lakehouse-lab
./start-lakehouse.sh         # Standard startup
./start-lakehouse.sh debug   # Step-by-step startup
```

## 📋 System Requirements

### **Configuration-Based Requirements**

| Configuration | RAM Needed | CPU Cores | Storage | Use Case |
|---------------|------------|-----------|---------|----------|
| **Minimal** | 8GB | 2+ | 20GB | Core services + Jupyter |
| **Analytics** | 14GB | 4+ | 50GB | BI dashboards + visualization |
| **ML/AI** | 16GB | 6+ | 100GB | Vector database + ML workflows |
| **Full** | 20GB | 8+ | 200GB | All data services |
| **Fat Server** | 64GB+ | 16+ | 500GB+ | High-performance deployment |

### **Base System Requirements**
- **OS**: Linux, macOS, or Windows with WSL2
- **Docker**: Auto-installed if missing during setup
- **Network**: Internet connection for installation
- **Ports**: 8080, 9001, 9020-9092 available


## 🛡️ Security Considerations

**The one-liner is safe because:**
- ✅ Uses HTTPS for secure download
- ✅ Downloads from official GitHub repository
- ✅ No elevated privileges required (except for Docker installation)
- ✅ Open source - you can inspect the script first

**To inspect before running:**
```bash
# Download and review the script first
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh > install.sh
less install.sh  # Review the script
bash install.sh  # Run after review
```

## 🚨 Troubleshooting

### **Common Errors, Symptoms, and Solutions Matrix**

| Error/Symptom | Likely Cause | Solution/Workaround | Affected Service/Component |
|---------------|-------------|---------------------|---------------------------|
| `lakehouse-init` service fails with exit 2 | Corrupted or partial installation | Run installer with `--replace` to force clean install | lakehouse-init, install.sh |
| Airflow database not initialized (services keep restarting) | Airflow DB tables missing | Manually initialize Airflow DB, then restart services | Airflow, Postgres |
| Previous failed installation blocks new install | Residual files or containers | Use `--replace` or manually clean up with `docker compose down -v` and remove directories | All services |
| Docker permission errors after installation | User not in `docker` group | Run `sudo usermod -aG docker $USER` and re-login | Docker, all services |
| WSL/macOS "Failure writing output" or silent failure | Piping issues in shell | Use download-then-execute method for install.sh | Installer, WSL/macOS |
| Port already in use | Port conflict with another process | Edit `docker-compose.yml` to change port mappings | Any service (see port list) |
| Low memory warning or OOM errors | Insufficient system resources | Use minimal config, reduce memory limits in `.env` | All services |
| Installation fails with generic error | Incomplete cleanup or dependency issue | Remove all files, clone fresh, use debug startup | All services |
| Superset package install permission error | Docker user permissions | Use updated installer, ensure correct user/group | Superset |
| MinIO access/credential issues | Missing or outdated `.env` | Regenerate credentials, restart MinIO | MinIO |
| JupyterHub not available | Overlay not enabled or port conflict | Enable overlay, check port 9041, restart | JupyterHub |
| Backup/restore fails | Incorrect backup path or permissions | Verify backup path, permissions, and logs | Backup/restore scripts |
| Credential not accepted | Outdated or rotated credentials | Run `./scripts/show-credentials.sh` to get current | Any service |
| "unbound variable" or shell errors | Shell compatibility or missing env var | Use updated scripts, check `.env` completeness | Shell scripts, install |
| Airflow/Superset/MinIO user provisioning fails | Incorrect script usage or missing role | Use correct script syntax, check user roles | Provisioning scripts |

> For detailed steps and more troubleshooting, see the sections below.

### **Recent Installation Issues (Fixed in v1.1.0)**

**Problem: "lakehouse-init" service fails with exit 2**
```bash
# Solution: Use the upgraded installer (automatically fixes this)
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --replace
```

**Problem: Airflow database not initialized (services keep restarting)**
```bash
# Check if Airflow database tables exist
docker exec lakehouse-lab-postgres-1 psql -U postgres -d airflow -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';"

# If no tables (returns 0), manually run initialization
docker-compose run --rm airflow-init

# Then restart the services
docker-compose restart airflow-scheduler airflow-webserver
```

**Problem: Previous failed installation blocking new install**
```bash
# The installer now automatically detects and offers options, or force replace:
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --replace

# Manual cleanup if needed:
docker compose down -v
rm -rf lakehouse-lab
rm -rf lakehouse-data
rm -f .lakehouse-initialized
```

### **Docker Permission Issues**
```bash
# If you get permission errors after installation:
sudo usermod -aG docker $USER
# Then log out and back in
```

### **WSL/macOS "Failure writing output" or Silent Failure**
```bash
# Use the download-then-execute method:
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh -o /tmp/install.sh && bash /tmp/install.sh

# Or with wget:
wget -O /tmp/install.sh https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh && bash /tmp/install.sh

# Or download to current directory:
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh -o install.sh && bash install.sh
```

### **Port Conflicts**
```bash
# If ports are already in use, edit docker-compose.yml:
cd lakehouse-lab
nano docker-compose.yml  # Change port mappings
docker compose up -d
```

### **Low Memory Warning**
```bash
# If you see memory warnings, try minimal config:
cd lakehouse-lab
cp .env.default .env
# Edit .env to reduce memory limits
docker compose restart
```

### **Installation Fails**
```bash
# Clean up and try manual installation:
rm -rf lakehouse-lab
git clone https://github.com/karstom/lakehouse-lab.git
cd lakehouse-lab
./start-lakehouse.sh debug  # Step-by-step startup
```

## 🎉 After Installation

**Services will be available at:**
- 🐳 **Portainer**: http://localhost:9060 (container management)
- 📈 **Superset**: http://localhost:9030 (BI dashboards) 
- 📓 **JupyterLab**: http://localhost:9040 (single-user notebooks)
- 👥 **JupyterHub**: http://localhost:9041 (multi-user notebooks)
- 📋 **Airflow**: http://localhost:9020 (workflows)
- ☁️ **MinIO**: http://localhost:9001 (file storage)
- ⚡ **Spark**: http://localhost:8080 (processing)

**🔐 Secure Credentials**: Run `./scripts/show-credentials.sh` to see your unique generated passwords

**Next steps:**
1. 📖 Read `QUICKSTART.md` for tutorials
2. 🚀 Start with Superset for instant analytics
3. 📊 Upload your own data to MinIO
4. 🔬 Create analysis notebooks in Jupyter

## 👥 Multi-User Setup & Educational Institution Management

### **Enabling Multi-User JupyterHub**

**For educational environments, replace single-user Jupyter with multi-user JupyterHub:**

```bash
# Enable JupyterHub with Docker Compose overlay
docker compose -f docker-compose.yml -f docker-compose.jupyterhub.yml up -d
```

**JupyterHub will be available at:** http://localhost:9041

### **Student and Instructor Provisioning Across All Services**

**Provision students and instructors across Superset, Airflow, MinIO, and JupyterHub with one command:**

```bash
# Provision a student with analyst role
./scripts/provision-user.sh john.student john.student@university.edu SecurePass123 analyst

# Provision an instructor/admin user
./scripts/provision-user.sh prof.smith prof.smith@university.edu AdminPass456 admin

# Provision a read-only user
./scripts/provision-user.sh guest.user guest.user@university.edu ViewPass789 viewer
```

### **User Roles & Service Access**

| Role | Superset | Airflow | MinIO | JupyterHub | Description |
|------|----------|---------|-------|------------|-------------|
| **admin** | Admin | Admin | consoleAdmin | sudo access | Instructor/administrator access |
| **analyst** | Alpha | User | readwrite | standard user | Student access - create dashboards, run workflows |
| **viewer** | Gamma | Viewer | readonly | standard user | Guest access - view dashboards, read-only data |

### **JupyterHub Features**

- **👥 Multi-user environment** with containerized isolation per user
- **🔗 Spark integration** automatically configured for all users
- **📁 Shared notebooks** (readonly templates + collaborative workspace)
- **🔐 User management** with role-based access control
- **📊 Resource management** with per-user CPU and memory limits
- **🎓 Classroom collaboration** with shared data access across services

### **Managing Users**

```bash
# View all provisioned users
./scripts/provision-user.sh --list

# Remove a user from all services
./scripts/provision-user.sh --remove john.student

# Update user role
./scripts/provision-user.sh john.student john.student@university.edu NewPass123 admin --update
```

## 🔄 Updating

### **Smart Upgrade (Recommended)**
```bash
# The installer automatically detects existing installations and offers upgrade options
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash

# Or force upgrade preserving data
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --upgrade
```

### **Manual Update**
```bash
cd lakehouse-lab
git pull origin main
docker compose pull  # Get latest images
docker compose up -d  # Restart with updates
```

### **Fresh Installation (Clean Slate)**
```bash
./start-lakehouse.sh reset  # Remove everything
cd ..
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
```

## 🌟 Platform-Specific Notes

### **Linux**
- Works on all major distributions (Ubuntu, CentOS, Debian, etc.)
- Auto-installs Docker if missing
- Best performance and compatibility

### **macOS**
- Requires Homebrew for Docker installation
- Works with both Intel and Apple Silicon
- May need to start Docker Desktop manually
- **Use download-then-execute method if piping fails**

### **Windows WSL2**
- Use the alternative installation commands above
- Ensure WSL2 is properly configured
- Docker Desktop integration recommended
- **Use download-then-execute method for piping issues**

### **Cloud Platforms**
- Works on AWS, Azure, GCP, DigitalOcean
- Use `--unattended` flag for automated deployments
- Consider `--fat-server` for cloud instances with high specs

## 💾 Post-Installation: Backup Setup

After installation, set up automated backups to protect your valuable data and configurations:

### **CRON-Based Backups (Recommended for most users)**
```bash
# Setup daily automated backups with email notifications
./examples/cron-backup-setup.sh --email admin@university.edu --compress

# Interactive setup wizard
./examples/cron-backup-setup.sh

# Custom schedule examples:
./examples/cron-backup-setup.sh --schedule "0 3 * * 0" --compress  # Weekly Sunday 3 AM
./examples/cron-backup-setup.sh --schedule "0 1 1 * *"             # Monthly 1st at 1 AM
```

### **Airflow-Integrated Backups (For workflow environments)**
```bash
# Copy the backup DAG template to your Airflow instance
cp templates/airflow/dags/lakehouse_backup_dag.py lakehouse-data/airflow/dags/

# Configure environment variables
export BACKUP_NOTIFICATION_EMAIL="admin@university.edu"
export LAKEHOUSE_BACKUP_PATH="/path/to/backups"

# The DAG will appear in Airflow UI for scheduling and monitoring
```

### **Manual Backup Commands**
```bash
# Complete backup with compression and verification
./scripts/backup-lakehouse.sh --compress --verify --retention-days 30

# Backup specific services only
./scripts/backup-lakehouse.sh --services postgres,minio,jupyter

# Test backup without actually creating files
./scripts/backup-lakehouse.sh --dry-run
```

### **Data Restoration**
```bash
# List available backups
ls -la backups/

# Complete system restore (with safety prompts)
./scripts/restore-lakehouse.sh lakehouse-backup-20240304_143052

# Restore specific service only
./scripts/restore-lakehouse.sh lakehouse-backup-20240304_143052 --service postgres

# Preview what would be restored
./scripts/restore-lakehouse.sh lakehouse-backup-20240304_143052 --dry-run
```

**💡 Backup Best Practices:**
- Set up automated backups immediately after installation
- Test your restore process regularly
- Store backups on a different disk/server for disaster recovery
- Monitor backup logs and email notifications
- Keep at least 30 days of backups for data recovery options
