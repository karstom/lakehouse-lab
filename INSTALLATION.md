# 🚀 One-Command Installation

## ⚡ Ultra-Quick Start

**Get your complete data analytics stack running with a single command:**

```bash
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
```

That's it! ☕ Grab a coffee while it sets up your entire lakehouse environment.

## 🎯 Installation Options

### **Standard Installation (Recommended)**
```bash
# For laptops, workstations, small servers (16GB RAM, 4+ cores)
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
```

### **High-Performance Installation**
```bash
# For powerful servers (64GB+ RAM, 16+ cores)
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --fat-server
```

### **Download Only (Manual Start)**
```bash
# Download and configure, but don't start services automatically
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --no-start
```

### **Custom Directory**
```bash
# Install to a specific directory
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- --dir my-lakehouse
```

## 🔧 What the Installer Does

1. **✅ Checks system requirements** (memory, CPU, disk space)
2. **✅ Installs dependencies** (Docker, git, curl) if missing
3. **✅ Downloads Lakehouse Lab** from GitHub
4. **✅ Configures environment** for your hardware
5. **✅ Starts all services** automatically
6. **✅ Provides access URLs** and next steps

## 🎛️ Advanced Options

```bash
# All available options
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash -s -- \
  --fat-server \     # Use high-performance config
  --no-start \       # Don't auto-start services
  --skip-deps \      # Skip dependency installation
  --dir custom-dir \ # Custom installation directory
  --branch develop   # Use specific git branch
```

## 🖥️ Manual Installation (Alternative)

If you prefer the traditional approach:

```bash
git clone https://github.com/karstom/lakehouse-lab.git
cd lakehouse-lab
cp .env.default .env  # or .env.fat-server for high-end systems
docker compose up -d
```

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

## 🚨 Troubleshooting

### **Docker Permission Issues**
```bash
# If you get permission errors after installation:
sudo usermod -aG docker $USER
# Then log out and back in
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

## 🌟 Why This Approach?

**For Users:**
- ⚡ **Zero friction** - just one command
- 🛡️ **Error handling** - automatically fixes common issues
- 🎯 **Smart defaults** - optimizes for your hardware
- 📱 **Works everywhere** - Linux, macOS, Windows (WSL2)

**For the Project:**
- 📈 **Higher adoption** - removes setup barriers
- 🐛 **Fewer support issues** - standardized installation
- 🚀 **Viral potential** - easy to share and demo
- 🎓 **Educational value** - users see modern DevOps practices

## 🔄 Updating

To update to the latest version:
```bash
cd lakehouse-lab
git pull origin main
docker compose pull  # Get latest images
docker compose up -d  # Restart with updates
```

Or reinstall completely:
```bash
./start-lakehouse.sh reset  # Remove everything
cd ..
curl -sSL https://raw.githubusercontent.com/YOUR-USERNAME/lakehouse-lab/main/install.sh | bash
```
