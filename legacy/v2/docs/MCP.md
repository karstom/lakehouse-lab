# 🤖 Model Context Protocol (MCP) Integration

While Lakehouse Lab doesn't include a built-in MCP server, you can easily integrate compatible MCP servers to add AI-powered natural language data query capabilities to your lakehouse environment.

## 📋 Compatible MCP Servers

The following MCP servers are compatible with Lakehouse Lab services and can be integrated to provide AI-powered data interactions:

### 🎨 **Vizro MCP Server**
- **Repository**: [mckinsey/vizro](https://github.com/mckinsey/vizro/tree/main/vizro-mcp)
- **Purpose**: AI-powered dashboard creation and visualization
- **Integration**: Works with Lakehouse Lab's Vizro dashboard service
- **Features**: Natural language dashboard generation, chart recommendations

### 📓 **Jupyter MCP Server**
- **Repository**: [datalayer/jupyter-mcp-server](https://github.com/datalayer/jupyter-mcp-server)
- **Purpose**: AI-assisted Jupyter notebook operations
- **Integration**: Enhances JupyterLab/JupyterHub environments
- **Features**: Code generation, notebook analysis, cell execution assistance

### 🗄️ **MinIO MCP Server**
- **Repository**: [ucesys/minio-python-mcp](https://github.com/ucesys/minio-python-mcp)
- **Purpose**: AI-powered object storage operations
- **Integration**: Works with Lakehouse Lab's MinIO S3-compatible storage
- **Features**: Natural language file operations, bucket management, data discovery

### 🔍 **LanceDB MCP Server**
- **Repository**: [kyryl-opens-ml/mcp-server-lancedb](https://github.com/kyryl-opens-ml/mcp-server-lancedb)
- **Purpose**: AI-enhanced vector database operations
- **Integration**: Extends Lakehouse Lab's LanceDB vector search capabilities
- **Features**: Natural language vector queries, semantic search, similarity operations

### 📊 **Superset MCP Server**
- **Repository**: [aptro/superset-mcp](https://github.com/aptro/superset-mcp)
- **Purpose**: AI-powered business intelligence and analytics
- **Integration**: Enhances Lakehouse Lab's Apache Superset dashboards
- **Features**: Natural language query generation, chart creation, data exploration

### 🔄 **Apache Airflow MCP Server**
- **Repository**: [yangkyeongmo/mcp-server-apache-airflow](https://github.com/yangkyeongmo/mcp-server-apache-airflow)
- **Purpose**: AI-assisted workflow orchestration
- **Integration**: Works with Lakehouse Lab's Airflow service
- **Features**: DAG generation, task management, workflow optimization

## 🚀 Integration Guide

### Prerequisites
- Working Lakehouse Lab installation
- Services you want to enhance (Vizro, Jupyter, MinIO, LanceDB, Superset, Airflow)
- Python 3.11+ environment for MCP servers

### Basic Integration Steps

1. **Choose Your MCP Server**
   ```bash
   # Clone the desired MCP server repository
   git clone https://github.com/[repository-url]
   cd [mcp-server-directory]
   ```

2. **Install Dependencies**
   ```bash
   # Install MCP server requirements
   pip install -r requirements.txt
   ```

3. **Configure Integration**
   ```bash
   # Set environment variables to point to your Lakehouse Lab services
   export LAKEHOUSE_SERVICE_URL="http://localhost:[service-port]"
   export LAKEHOUSE_CREDENTIALS="your-credentials"
   ```

4. **Run MCP Server**
   ```bash
   # Start the MCP server
   python main.py
   ```

5. **Connect to Lakehouse Services**
   - Configure your AI client (Claude, ChatGPT, etc.) to use the MCP server
   - Access enhanced AI capabilities for your lakehouse data

### Docker Integration

For production deployments, you can run MCP servers as additional Docker services:

```yaml
# Add to your docker-compose.override.yml
services:
  mcp-vizro:
    build: ./external-mcp-servers/vizro-mcp
    ports:
      - "9091:8000"
    environment:
      - VIZRO_URL=http://vizro:8050
    networks:
      - lakehouse
    depends_on:
      - vizro
```

## 🎯 Use Cases

### **Data Exploration**
- "Show me sales trends for the last quarter"
- "Create a dashboard comparing product performance"
- "Find similar customers to our top buyers"

### **Workflow Management**
- "Schedule a daily ETL pipeline for new customer data"
- "Create an alert when data quality drops below 95%"
- "Generate a report summarization workflow"

### **Data Operations**
- "Upload this CSV to the sales bucket"
- "Find all files related to customer analytics"
- "Create embeddings for our product descriptions"

## 💡 Best Practices

1. **Start Simple**: Begin with one MCP server for your most-used service
2. **Security**: Ensure MCP servers only access necessary lakehouse services
3. **Monitoring**: Track MCP server performance and usage patterns
4. **Documentation**: Document your AI workflows for team collaboration
5. **Testing**: Test MCP integrations in development before production use

## 🔧 Troubleshooting

### Common Issues
- **Connection Refused**: Check that Lakehouse Lab services are running and accessible
- **Authentication Errors**: Verify credentials and service URLs are correct
- **Performance Issues**: Consider resource limits and MCP server scaling

### Getting Help
- Check individual MCP server repositories for specific documentation
- Review Lakehouse Lab service logs for integration issues
- Join the MCP community for integration support

---

**Note**: These MCP servers are developed and maintained by the community. Please refer to their respective repositories for detailed setup instructions, feature documentation, and support.

For Lakehouse Lab-specific integration questions, please open an issue in the [Lakehouse Lab repository](https://github.com/karstom/lakehouse-lab).