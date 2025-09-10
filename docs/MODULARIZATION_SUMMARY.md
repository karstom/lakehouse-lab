# Lakehouse Lab v2.1.1 - Architecture Summary

This document provides an overview of the Lakehouse Lab architecture and modular design.

## Core Components

### Data Storage & Processing
- **PostgreSQL** - Primary relational database
- **MinIO** - S3-compatible object storage
- **Apache Spark** - Distributed data processing engine
- **Apache Iceberg** - Table format for large analytics datasets

### Analytics & Visualization
- **Apache Superset** - Business intelligence and data visualization
- **Vizro** - Modern dashboard framework
- **JupyterLab** - Interactive computing environment

### Orchestration & Management
- **Apache Airflow** - Workflow orchestration platform
- **Portainer** - Container management interface

### Vector & Advanced Analytics
- **LanceDB** - Vector database for AI/ML workloads

## Architecture Design

The platform follows a microservices architecture with:

- **Docker Compose** for container orchestration
- **Modular configuration** through environment variables
- **Service-specific configurations** in dedicated compose files
- **Standardized networking** through Docker networks
- **Volume management** for data persistence

## Configuration Management

- **Environment Variables** - Centralized through `.env` file
- **Service Presets** - Pre-configured service combinations
- **Template System** - For generating configuration files
- **Health Checks** - Automated service monitoring

## Security Features

- **Credential Management** - Automated secret generation
- **Network Isolation** - Containerized service boundaries
- **Access Control** - Role-based permissions
- **TLS Support** - Optional encryption in transit

## Installation Modes

- **Standard Install** - Full platform deployment
- **Minimal Install** - Core services only
- **Custom Install** - User-selected components
- **Upgrade Mode** - In-place platform updates

For detailed information, see the [Installation Guide](INSTALLATION.md) and [Configuration Guide](CONFIGURATION.md).