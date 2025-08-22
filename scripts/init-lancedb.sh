#!/bin/bash
# ==============================================================================
# init-lancedb.sh - LanceDB Vector Database Initialization
# ==============================================================================
# Sets up LanceDB vector database with sample data and REST API service

set -e

# Get script directory and source shared utilities
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
source "$SCRIPT_DIR/lib/init-core.sh"

# ==============================================================================
# CONFIGURATION
# ==============================================================================

MODULE_NAME="lancedb"
LANCEDB_DIR="$LAKEHOUSE_ROOT/lancedb"

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

create_lancedb_directories() {
    log_info "Creating LanceDB directory structure..."
    
    mkdir -p "$LANCEDB_DIR"/{data,service,notebooks,examples}
    
    log_success "LanceDB directories created"
}

create_lancedb_service() {
    log_info "Creating LanceDB REST API service..."
    
    cat > "$LANCEDB_DIR/service/lancedb_service.py" << 'EOF'
import lancedb
import pyarrow as pa
import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException
from typing import List, Dict, Any, Optional
import os
import uvicorn
from datetime import datetime
import json

# Initialize FastAPI app
app = FastAPI(
    title='LanceDB Service - Lakehouse Lab',
    description='Vector database service for AI/ML workflows in Lakehouse Lab',
    version='1.0.0'
)

# Initialize LanceDB
DATA_DIR = os.getenv('LANCE_DATA_DIR', '/app/data')
db = lancedb.connect(DATA_DIR)

@app.get('/')
async def root():
    return {
        'message': 'LanceDB Service is running',
        'version': '1.0.0',
        'data_dir': DATA_DIR,
        'available_tables': db.table_names(),
        'endpoints': {
            'health': '/health',
            'tables': '/tables',
            'create_table': '/tables/{table_name}/create',
            'table_info': '/tables/{table_name}/info', 
            'search': '/tables/{table_name}/search',
            'insert': '/tables/{table_name}/insert'
        }
    }

@app.get('/health')
async def health():
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'tables': db.table_names(),
        'data_directory': DATA_DIR
    }

@app.get('/tables')
async def list_tables():
    tables_info = []
    for table_name in db.table_names():
        try:
            table = db.open_table(table_name)
            tables_info.append({
                'name': table_name,
                'count': table.count_rows(),
                'schema': str(table.schema)
            })
        except Exception as e:
            tables_info.append({
                'name': table_name,
                'error': str(e)
            })
    
    return {'tables': tables_info}

@app.post('/tables/{table_name}/create')
async def create_table(table_name: str, config: Optional[Dict[str, Any]] = None):
    try:
        if table_name in db.table_names():
            return {'message': f'Table {table_name} already exists', 'action': 'none'}
        
        # Create table based on type or with sample data
        table_type = config.get('type', 'sample') if config else 'sample'
        
        if table_type == 'documents':
            # Document embeddings table
            sample_data = pd.DataFrame({
                'id': range(50),
                'text': [f'Sample document {i}: This is a sample document for testing vector search capabilities.' for i in range(50)],
                'vector': [np.random.rand(384).astype(np.float32).tolist() for _ in range(50)],
                'category': [f'category_{i%5}' for i in range(50)],
                'metadata': [json.dumps({'index': i, 'created': datetime.now().isoformat()}) for i in range(50)]
            })
        elif table_type == 'images':
            # Image embeddings table
            sample_data = pd.DataFrame({
                'id': range(30),
                'filename': [f'image_{i:03d}.jpg' for i in range(30)],
                'vector': [np.random.rand(512).astype(np.float32).tolist() for _ in range(30)],
                'tags': [['sample', f'tag_{i%3}', f'type_{i%2}'] for i in range(30)],
                'metadata': [json.dumps({'size': f'{1024+i*100}x{768+i*50}', 'format': 'JPEG'}) for i in range(30)]
            })
        else:
            # Generic sample table
            sample_data = pd.DataFrame({
                'id': range(100),
                'name': [f'item_{i}' for i in range(100)],
                'vector': [np.random.rand(128).astype(np.float32).tolist() for _ in range(100)],
                'category': [f'category_{i%10}' for i in range(100)],
                'score': [np.random.rand() for _ in range(100)],
                'metadata': [json.dumps({'index': i, 'type': 'sample'}) for i in range(100)]
            })
        
        table = db.create_table(table_name, sample_data)
        
        return {
            'message': f'Table {table_name} created successfully',
            'type': table_type,
            'schema': str(table.schema),
            'count': table.count_rows(),
            'sample_query': f'GET /tables/{table_name}/search'
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get('/tables/{table_name}/info')
async def get_table_info(table_name: str):
    try:
        if table_name not in db.table_names():
            raise HTTPException(status_code=404, detail=f'Table {table_name} not found')
            
        table = db.open_table(table_name)
        
        # Get sample data
        sample_data = table.to_pandas().head(3)
        
        return {
            'name': table_name,
            'schema': str(table.schema),
            'count': table.count_rows(),
            'version': table.version,
            'sample_data': sample_data.to_dict('records') if not sample_data.empty else [],
            'columns': list(sample_data.columns) if not sample_data.empty else []
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post('/tables/{table_name}/search')
async def search_vectors(table_name: str, query_data: Dict[str, Any]):
    try:
        if table_name not in db.table_names():
            raise HTTPException(status_code=404, detail=f'Table {table_name} not found')
            
        table = db.open_table(table_name)
        query_vector = query_data.get('vector')
        limit = query_data.get('limit', 10)
        
        if not query_vector:
            # Return first few rows if no vector provided
            results = table.to_pandas().head(limit)
            return {
                'results': results.to_dict('records'),
                'count': len(results),
                'query_type': 'sample_data'
            }
        
        # Perform vector search
        results = table.search(query_vector).limit(limit).to_pandas()
        
        return {
            'results': results.to_dict('records'),
            'count': len(results),
            'query_type': 'vector_search',
            'query_vector_dim': len(query_vector)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post('/tables/{table_name}/insert')
async def insert_data(table_name: str, data: Dict[str, Any]):
    try:
        if table_name not in db.table_names():
            raise HTTPException(status_code=404, detail=f'Table {table_name} not found')
            
        table = db.open_table(table_name)
        
        # Convert data to DataFrame
        if isinstance(data.get('records'), list):
            df = pd.DataFrame(data['records'])
        else:
            df = pd.DataFrame([data])
        
        # Add the data to the table
        table.add(df)
        
        return {
            'message': f'Successfully inserted {len(df)} records into {table_name}',
            'inserted_count': len(df),
            'total_count': table.count_rows()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == '__main__':
    # Create default tables on startup
    try:
        print("Initializing LanceDB service...")
        
        # Create sample tables if they don't exist
        default_tables = {
            'sample_vectors': 'sample',
            'document_embeddings': 'documents', 
            'image_embeddings': 'images'
        }
        
        for table_name, table_type in default_tables.items():
            if table_name not in db.table_names():
                print(f'Creating default table: {table_name}')
                
                if table_type == 'documents':
                    sample_data = pd.DataFrame({
                        'id': range(20),
                        'text': [f'Sample document {i}: This document contains information about lakehouse architecture and data analytics.' for i in range(20)],
                        'vector': [np.random.rand(384).astype(np.float32).tolist() for _ in range(20)],
                        'category': ['lakehouse', 'analytics', 'data', 'ml', 'ai'][i%5] for i in range(20)],
                        'metadata': [json.dumps({'doc_id': i, 'source': 'sample'}) for i in range(20)]
                    })
                elif table_type == 'images':
                    sample_data = pd.DataFrame({
                        'id': range(15),
                        'filename': [f'chart_{i:03d}.png' for i in range(15)],
                        'vector': [np.random.rand(512).astype(np.float32).tolist() for _ in range(15)],
                        'tags': [['chart', 'visualization', f'type_{i%3}'] for i in range(15)],
                        'metadata': [json.dumps({'width': 800+i*10, 'height': 600+i*5}) for i in range(15)]
                    })
                else:
                    sample_data = pd.DataFrame({
                        'id': range(50),
                        'name': [f'sample_item_{i}' for i in range(50)],
                        'vector': [np.random.rand(128).astype(np.float32).tolist() for _ in range(50)],
                        'category': [f'cat_{i%5}' for i in range(50)],
                        'value': [np.random.rand() for _ in range(50)]
                    })
                
                table = db.create_table(table_name, sample_data)
                print(f'Created table {table_name} with {table.count_rows()} records')
        
        print(f'LanceDB service ready with tables: {db.table_names()}')
        
    except Exception as e:
        print(f'Error during initialization: {e}')
    
    # Start the API server
    uvicorn.run(app, host='0.0.0.0', port=8000)
EOF
    
    log_success "LanceDB REST API service created"
}

create_lancedb_notebooks() {
    log_info "Creating LanceDB example notebooks..."
    
    cat > "$LANCEDB_DIR/notebooks/lancedb_intro.ipynb" << 'EOF'
{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# LanceDB Vector Database - Introduction\n",
    "\n",
    "This notebook demonstrates how to use LanceDB for vector storage and similarity search in the Lakehouse Lab environment.\n"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import requests\n",
    "import pandas as pd\n",
    "import numpy as np\n",
    "import json\n",
    "\n",
    "# LanceDB service URL\n",
    "LANCEDB_URL = 'http://lancedb:8000'\n",
    "\n",
    "print('LanceDB Service Introduction')\n",
    "print('===========================')"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Check LanceDB service health\n",
    "response = requests.get(f'{LANCEDB_URL}/health')\n",
    "health_info = response.json()\n",
    "\n",
    "print('LanceDB Service Status:')\n",
    "print(json.dumps(health_info, indent=2))"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# List available tables\n",
    "response = requests.get(f'{LANCEDB_URL}/tables')\n",
    "tables_info = response.json()\n",
    "\n",
    "print('Available Tables:')\n",
    "for table in tables_info['tables']:\n",
    "    print(f\"- {table['name']}: {table['count']} records\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Search for similar vectors\n",
    "# Generate a random query vector\n",
    "query_vector = np.random.rand(128).tolist()\n",
    "\n",
    "search_payload = {\n",
    "    'vector': query_vector,\n",
    "    'limit': 5\n",
    "}\n",
    "\n",
    "response = requests.post(f'{LANCEDB_URL}/tables/sample_vectors/search', json=search_payload)\n",
    "search_results = response.json()\n",
    "\n",
    "print(f\"Found {search_results['count']} similar vectors:\")\n",
    "results_df = pd.DataFrame(search_results['results'])\n",
    "print(results_df[['id', 'name', 'category', 'value']].head())"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## Document Embeddings Example\n",
    "\n",
    "Working with document embeddings for semantic search."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Get document embeddings table info\n",
    "response = requests.get(f'{LANCEDB_URL}/tables/document_embeddings/info')\n",
    "table_info = response.json()\n",
    "\n",
    "print(f\"Document Embeddings Table:\")\n",
    "print(f\"- Records: {table_info['count']}\")\n",
    "print(f\"- Columns: {table_info['columns']}\")\n",
    "print(f\"\\nSample documents:\")\n",
    "\n",
    "for i, doc in enumerate(table_info['sample_data'][:3]):\n",
    "    print(f\"{i+1}. {doc['text'][:100]}...\")"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "# Search documents by vector similarity\n",
    "doc_query_vector = np.random.rand(384).tolist()  # 384-dim for documents\n",
    "\n",
    "doc_search_payload = {\n",
    "    'vector': doc_query_vector,\n",
    "    'limit': 3\n",
    "}\n",
    "\n",
    "response = requests.post(f'{LANCEDB_URL}/tables/document_embeddings/search', json=doc_search_payload)\n",
    "doc_results = response.json()\n",
    "\n",
    "print(\"Most similar documents:\")\n",
    "for i, doc in enumerate(doc_results['results'][:3]):\n",
    "    print(f\"{i+1}. [{doc['category']}] {doc['text'][:80]}...\")"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.8.5"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}
EOF
    
    log_success "LanceDB example notebooks created"
}

create_lancedb_examples() {
    log_info "Creating LanceDB usage examples..."
    
    cat > "$LANCEDB_DIR/examples/vector_search_example.py" << 'EOF'
#!/usr/bin/env python3
"""
LanceDB Vector Search Example

This script demonstrates basic vector operations with LanceDB
in the Lakehouse Lab environment.
"""

import lancedb
import pandas as pd
import numpy as np
from datetime import datetime
import os

def main():
    # Connect to LanceDB
    data_dir = os.getenv('LANCE_DATA_DIR', './data')
    db = lancedb.connect(data_dir)
    
    print("LanceDB Vector Search Example")
    print("============================")
    print(f"Data directory: {data_dir}")
    print(f"Available tables: {db.table_names()}")
    
    # Create a test table if it doesn't exist
    table_name = "example_vectors"
    
    if table_name not in db.table_names():
        print(f"\nCreating example table: {table_name}")
        
        # Generate sample data
        num_vectors = 1000
        vector_dim = 256
        
        data = pd.DataFrame({
            'id': range(num_vectors),
            'vector': [np.random.rand(vector_dim).astype(np.float32).tolist() for _ in range(num_vectors)],
            'category': [f'category_{i%10}' for i in range(num_vectors)],
            'text': [f'Sample text document {i}' for i in range(num_vectors)],
            'timestamp': [datetime.now().isoformat() for _ in range(num_vectors)]
        })
        
        table = db.create_table(table_name, data)
        print(f"Created table with {table.count_rows()} vectors")
    else:
        table = db.open_table(table_name)
        print(f"\nUsing existing table with {table.count_rows()} vectors")
    
    # Perform vector search
    query_vector = np.random.rand(256).astype(np.float32)
    
    print(f"\nPerforming vector search...")
    results = table.search(query_vector).limit(5).to_pandas()
    
    print(f"Found {len(results)} similar vectors:")
    for idx, row in results.iterrows():
        print(f"  {row['id']}: {row['text']} (category: {row['category']})")
    
    # Filter by category
    print(f"\nFiltering by category...")
    category_filter = "category_1"
    filtered_results = table.search(query_vector).where(f"category = '{category_filter}'").limit(3).to_pandas()
    
    print(f"Results in {category_filter}:")
    for idx, row in filtered_results.iterrows():
        print(f"  {row['id']}: {row['text']}")

if __name__ == "__main__":
    main()
EOF
    
    chmod +x "$LANCEDB_DIR/examples/vector_search_example.py"
    
    log_success "LanceDB examples created"
}

create_lancedb_config() {
    log_info "Creating LanceDB configuration..."
    
    cat > "$LANCEDB_DIR/config.yaml" << 'EOF'
# LanceDB Configuration for Lakehouse Lab
service:
  name: "LanceDB Vector Database"
  version: "1.0.0"
  port: 8000
  host: "0.0.0.0"
  
storage:
  data_directory: "/app/data"
  backup_enabled: true
  
default_tables:
  - name: "sample_vectors"
    type: "sample"
    dimension: 128
    
  - name: "document_embeddings" 
    type: "documents"
    dimension: 384
    
  - name: "image_embeddings"
    type: "images"
    dimension: 512

integrations:
  minio:
    endpoint: "${MINIO_ENDPOINT}"
    access_key: "${MINIO_ROOT_USER}"
    secret_key: "${MINIO_ROOT_PASSWORD}"
    bucket: "lakehouse"
    
  jupyter:
    notebooks_path: "/app/notebooks"
    examples_path: "/app/examples"
EOF
    
    log_success "LanceDB configuration created"
}

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

main() {
    log_section "INITIALIZING LANCEDB VECTOR DATABASE"
    
    # Check prerequisites
    check_lakehouse_root
    
    # Create directory structure
    create_lancedb_directories
    
    # Set up LanceDB components
    create_lancedb_service
    create_lancedb_notebooks
    create_lancedb_examples
    create_lancedb_config
    
    # Set proper permissions
    log_info "Setting directory permissions..."
    chmod -R 755 "$LANCEDB_DIR"
    
    log_success "✅ LanceDB initialization completed successfully"
    log_info "   • REST API service: $LANCEDB_DIR/service/lancedb_service.py"
    log_info "   • Example notebooks: $LANCEDB_DIR/notebooks/"
    log_info "   • Python examples: $LANCEDB_DIR/examples/"
    log_info "   • Configuration: $LANCEDB_DIR/config.yaml"
    log_info "   • API URL: http://localhost:9080 (after stack startup)"
    log_info "   • API docs: http://localhost:9080/docs"
    
    return 0
}

# Execute main function if script is run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi