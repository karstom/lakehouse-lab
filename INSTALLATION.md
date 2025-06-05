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

## 🔧 Installation Options

| Option | Description | Example |
|--------|-------------|---------|
| `--fat-server` | High-performance config (64GB+ RAM) | `--fat-server` |
| `--no-start` | Download only, don't start services | `--no-start` |
| `--unattended` | No prompts, assume yes to all | `--unattended` |
| `--skip-deps` | Skip dependency installation | `--skip-deps` |
| `--dir DIR` | Install to custom directory | `--dir my-lakehouse` |
| `--branch BRANCH` | Use specific git branch | `--branch develop` |

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
