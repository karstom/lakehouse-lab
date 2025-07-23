# 🚀 Lakehouse Lab Installation Guide

Complete installation options for all platforms and use cases.

## ⚡ One-Command Installation

### **Standard Installation (Recommended)**
```bash
# For laptops, workstations, small servers (16GB RAM, 4+ cores)
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
```

**Windows WSL or macOS users** (if piping fails):
```bash
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh -o /tmp/install.sh && bash /tmp/install.sh
```

### **High-Performance Installation**
```bash
# For powerful servers (64GB+ RAM, 16+ cores)
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --fat-server
```

**Windows WSL or macOS users:**
```bash
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh -o /tmp/install.sh && bash /tmp/install.sh --fat-server
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

## 🔧 Installation Options

| Option | Description | Example |
|--------|-------------|---------|
| `--fat-server` | High-performance config (64GB+ RAM) | `--fat-server` |
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

### **Minimum Requirements**
- **OS**: Linux, macOS, or Windows with WSL2
- **RAM**: 8GB (16GB recommended)
- **CPU**: 2 cores (4+ recommended)
- **Storage**: 20GB free space (50GB recommended)
- **Docker**: Auto-installed if missing

### **Recommended for Fat Server**
- **RAM**: 64GB+
- **CPU**: 16+ cores
- **Storage**: 500GB+ SSD
- **Network**: Gigabit connection

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
- 📓 **JupyterLab**: http://localhost:9040 (data science)
- 📋 **Airflow**: http://localhost:9020 (workflows)
- ☁️ **MinIO**: http://localhost:9001 (file storage)
- ⚡ **Spark**: http://localhost:8080 (processing)

**Default credentials**: `admin/admin` for most services

**Next steps:**
1. 📖 Read `QUICKSTART.md` for tutorials
2. 🚀 Start with Superset for instant analytics
3. 📊 Upload your own data to MinIO
4. 🔬 Create analysis notebooks in Jupyter

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
