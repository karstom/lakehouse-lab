# ☁️ Cloud Deployment Guide

Deploy Lakehouse Lab on major cloud platforms with the same one-command experience.

## 🚀 Quick Cloud Deployment

**All major cloud platforms support the same installation:**

```bash
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
```

## ☁️ Platform-Specific Guides

### **Amazon Web Services (AWS)**

#### **Recommended Instance Types**
| Use Case | Instance Type | vCPU | RAM | Storage | Monthly Cost* |
|----------|---------------|------|-----|---------|---------------|
| Development | `t3.large` | 2 | 8GB | 20GB | ~$60 |
| Standard | `m5.xlarge` | 4 | 16GB | 50GB | ~$140 |
| Production | `m5.2xlarge` | 8 | 32GB | 100GB | ~$280 |
| High Performance | `m5.4xlarge` | 16 | 64GB | 500GB | ~$560 |

*Approximate costs in us-east-1, subject to change

#### **Quick Setup**
1. **Launch EC2 Instance**
   - AMI: Ubuntu 22.04 LTS
   - Instance type: `m5.xlarge` or larger
   - Storage: 50GB+ EBS GP3
   - Security group: Open ports 9020, 9030, 9040, 9060, 9001, 8080

2. **Install Lakehouse Lab**
   ```bash
   # SSH to instance
   ssh -i your-key.pem ubuntu@your-instance-ip
   
   # Install (use --fat-server for m5.2xlarge+)
   curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
   ```

3. **Access Services**
   - Replace `localhost` with your instance's public IP
   - Example: `http://your-instance-ip:9030` for Superset

#### **AWS-Specific Optimizations**
```bash
# Use instance storage for better performance
sudo mkfs.ext4 /dev/nvme1n1  # If instance has NVMe
sudo mount /dev/nvme1n1 /opt/lakehouse-data
export LAKEHOUSE_ROOT=/opt/lakehouse-data

# Install with custom data location
curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
```

#### **AWS Security Group Rules**
```
Type: Custom TCP, Port: 9060, Source: Your IP  # Portainer
Type: Custom TCP, Port: 9030, Source: Your IP  # Superset
Type: Custom TCP, Port: 9040, Source: Your IP  # JupyterLab
Type: Custom TCP, Port: 9020, Source: Your IP  # Airflow
Type: Custom TCP, Port: 9001, Source: Your IP  # MinIO Console
Type: Custom TCP, Port: 8080, Source: Your IP  # Spark
```

### **Google Cloud Platform (GCP)**

#### **Recommended Machine Types**
| Use Case | Machine Type | vCPU | RAM | Storage | Monthly Cost* |
|----------|--------------|------|-----|---------|---------------|
| Development | `n2-standard-2` | 2 | 8GB | 20GB | ~$65 |
| Standard | `n2-standard-4` | 4 | 16GB | 50GB | ~$130 |
| Production | `n2-standard-8` | 8 | 32GB | 100GB | ~$260 |
| High Performance | `n2-standard-16` | 16 | 64GB | 500GB | ~$520 |

*Approximate costs in us-central1, subject to change

#### **Quick Setup**
1. **Create VM Instance**
   ```bash
   gcloud compute instances create lakehouse-lab \
     --machine-type=n2-standard-4 \
     --image-family=ubuntu-2204-lts \
     --image-project=ubuntu-os-cloud \
     --boot-disk-size=50GB \
     --tags=lakehouse-lab
   ```

2. **Configure Firewall**
   ```bash
   gcloud compute firewall-rules create lakehouse-lab-ports \
     --allow tcp:8080,tcp:9001,tcp:9020,tcp:9030,tcp:9040,tcp:9060 \
     --source-ranges=YOUR_IP/32 \
     --target-tags=lakehouse-lab
   ```

3. **Install Lakehouse Lab**
   ```bash
   # SSH to instance
   gcloud compute ssh lakehouse-lab
   
   # Install
   curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
   ```

### **Microsoft Azure**

#### **Recommended VM Sizes**
| Use Case | VM Size | vCPU | RAM | Storage | Monthly Cost* |
|----------|---------|------|-----|---------|---------------|
| Development | `Standard_B2s` | 2 | 4GB | 20GB | ~$60 |
| Standard | `Standard_D4s_v3` | 4 | 16GB | 50GB | ~$140 |
| Production | `Standard_D8s_v3` | 8 | 32GB | 100GB | ~$280 |
| High Performance | `Standard_D16s_v3` | 16 | 64GB | 500GB | ~$560 |

*Approximate costs in East US, subject to change

#### **Quick Setup**
1. **Create Resource Group & VM**
   ```bash
   # Create resource group
   az group create --name lakehouse-lab-rg --location eastus
   
   # Create VM
   az vm create \
     --resource-group lakehouse-lab-rg \
     --name lakehouse-lab-vm \
     --image Ubuntu2204 \
     --size Standard_D4s_v3 \
     --admin-username azureuser \
     --generate-ssh-keys
   ```

2. **Open Ports**
   ```bash
   az vm open-port --port 8080,9001,9020,9030,9040,9060 \
     --resource-group lakehouse-lab-rg \
     --name lakehouse-lab-vm
   ```

3. **Install Lakehouse Lab**
   ```bash
   # SSH to VM
   ssh azureuser@your-vm-ip
   
   # Install
   curl -sSL https://raw.githubusercontent.com/karstom/lakehouse-lab/main/install.sh | bash
   ```

## 🔒 Security Best Practices

### **Network Security**
```bash
# Restrict access to your IP only
# AWS Security Groups, GCP Firewall Rules, Azure NSGs
# Replace 0.0.0.0/0 with YOUR_IP/32
```

### **SSL/TLS (Production)**
```bash
# Add reverse proxy with SSL
# Consider AWS ALB, GCP Load Balancer, or Azure Application Gateway
```

### **Authentication**
```bash
# Change default passwords immediately
# Consider integrating with cloud IAM services
```

## 💰 Cost Optimization

### **Development/Testing**
- Use smaller instances (`t3.medium` on AWS)
- Stop instances when not in use
- Use spot/preemptible instances for significant savings

### **Production**
- Reserved instances for predictable workloads
- Auto-scaling groups for variable demand
- Regular monitoring and right-sizing

## 📊 Monitoring & Logging

### **CloudWatch (AWS)**
```bash
# Install CloudWatch agent
sudo apt-get install amazon-cloudwatch-agent
```

### **Cloud Logging (GCP)**
```bash
# Install Ops Agent
curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
sudo bash add-google-cloud-ops-agent-repo.sh --also-install
```

### **Azure Monitor**
```bash
# Install Azure Monitor agent via portal or CLI
```

## 🔄 Backup Strategies

### **Data Backup**
```bash
# Backup persistent volumes
docker run --rm -v lakehouse-data:/data -v $(pwd):/backup ubuntu tar czf /backup/lakehouse-backup.tar.gz /data
```

### **Cloud-Native Backup**
- **AWS**: EBS Snapshots, S3 backup
- **GCP**: Persistent Disk Snapshots, Cloud Storage
- **Azure**: Disk Snapshots, Blob Storage

## 🚀 Advanced Cloud Integrations

### **Use Cloud Object Storage**
Replace MinIO with cloud storage for production:

**AWS S3 Integration:**
```yaml
# docker-compose.override.yml
services:
  jupyter:
    environment:
      - AWS_ACCESS_KEY_ID=your-key
      - AWS_SECRET_ACCESS_KEY=your-secret
      - AWS_DEFAULT_REGION=us-east-1
```

**GCP Cloud Storage:**
```yaml
services:
  jupyter:
    environment:
      - GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

### **Managed Databases**
Replace PostgreSQL with managed services:
- **AWS RDS PostgreSQL**
- **GCP Cloud SQL**
- **Azure Database for PostgreSQL**

## 🌐 Multi-Region Deployment

### **Global Load Balancing**
- AWS CloudFront + ALB
- GCP Cloud CDN + Load Balancer  
- Azure Front Door + Application Gateway

### **Data Replication**
- Cross-region storage replication
- Database read replicas
- Content delivery networks

## 📋 Cloud Migration Checklist

### **Pre-Migration**
- [ ] Choose appropriate instance/VM size
- [ ] Configure networking and security groups
- [ ] Plan data migration strategy
- [ ] Set up monitoring and logging

### **Migration**
- [ ] Deploy infrastructure
- [ ] Install Lakehouse Lab
- [ ] Migrate existing data
- [ ] Update DNS/networking
- [ ] Test all services

### **Post-Migration**
- [ ] Configure backups
- [ ] Set up monitoring alerts
- [ ] Optimize costs
- [ ] Document access procedures
- [ ] Train team on cloud management

## 🎯 Recommended Cloud Strategy

### **Development**
- Single cloud VM with standard installation
- Manual management and monitoring
- Cost-optimized instance sizing

### **Production**
- Multi-AZ/region deployment
- Managed databases and storage
- Auto-scaling and load balancing
- Comprehensive monitoring and alerting
- Automated backups and disaster recovery

---

**Ready to deploy in the cloud?** Start with a single VM and the standard installation, then scale up as your needs grow! ☁️🚀
