#!/usr/bin/env python3
"""
LanceDB REST API Service - Lakehouse Lab
Vector database service providing REST API for embeddings and similarity search
"""

import os
import sys
import json
import uuid
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# FastAPI and dependencies
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Data processing
import numpy as np
import pandas as pd
import pyarrow as pa

# LanceDB
try:
    import lancedb
except ImportError:
    print("Installing LanceDB...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "lancedb"])
    import lancedb

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
LANCE_DATA_DIR = os.environ.get('LANCE_DATA_DIR', '/app/data')
API_HOST = os.environ.get('API_HOST', '0.0.0.0')
API_PORT = int(os.environ.get('API_PORT', '8000'))

# FastAPI app
app = FastAPI(
    title='LanceDB Service - Lakehouse Lab',
    description='Vector database REST API for embeddings and similarity search',
    version='1.0.0'
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global database connection
db = None

# Pydantic models
class VectorRecord(BaseModel):
    id: Optional[int] = None
    text: str
    category: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}
    vector: Optional[List[float]] = None

class SearchQuery(BaseModel):
    query_text: Optional[str] = None
    query_vector: Optional[List[float]] = None
    limit: int = 10
    category_filter: Optional[str] = None

class SearchResult(BaseModel):
    id: int
    text: str
    category: Optional[str]
    metadata: Dict[str, Any]
    similarity_score: float

def initialize_database():
    """Initialize LanceDB connection and create sample data"""
    global db
    
    try:
        # Create data directory
        Path(LANCE_DATA_DIR).mkdir(parents=True, exist_ok=True)
        
        # Connect to LanceDB
        db = lancedb.connect(LANCE_DATA_DIR)
        logger.info(f"Connected to LanceDB at {LANCE_DATA_DIR}")
        
        # Create sample vectors table if it doesn't exist
        if 'sample_vectors' not in db.table_names():
            create_sample_data()
            
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False

def create_sample_data():
    """Create sample vector data for demonstration"""
    try:
        logger.info("Creating sample vector data...")
        
        # Sample data with embeddings
        sample_data = []
        categories = ["analytics", "engineering", "business", "research"]
        
        for i in range(20):
            # Create simple embeddings (in real use, these would come from a model)
            embedding = np.random.rand(128).astype(np.float32).tolist()
            
            record = {
                'id': i + 1,
                'text': f"Sample document {i+1} about {categories[i % len(categories)]}",
                'category': categories[i % len(categories)],
                'vector': embedding,
                'created_at': datetime.now().isoformat(),
                'metadata': {'source': 'sample_data', 'version': '1.0'}
            }
            sample_data.append(record)
        
        # Create table
        df = pd.DataFrame(sample_data)
        table = db.create_table('sample_vectors', df)
        
        logger.info(f"Created sample_vectors table with {len(sample_data)} records")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create sample data: {e}")
        return False

def simple_embedding(text: str) -> List[float]:
    """Simple text embedding (in production, use a proper embedding model)"""
    # Simple hash-based embedding for demo purposes
    import hashlib
    
    # Create a simple embedding based on text hash
    text_hash = hashlib.md5(text.encode()).hexdigest()
    
    # Convert to numbers
    embedding = []
    for i in range(0, len(text_hash), 2):
        hex_pair = text_hash[i:i+2]
        embedding.append(int(hex_pair, 16) / 255.0)
    
    # Pad or truncate to 128 dimensions
    while len(embedding) < 128:
        embedding.extend(embedding[:128-len(embedding)])
    
    return embedding[:128]

# API Routes

@app.get("/")
def root():
    """Root endpoint with API information"""
    return {
        'message': 'LanceDB Service is running',
        'version': '1.0.0',
        'data_directory': LANCE_DATA_DIR,
        'tables': db.table_names() if db else [],
        'endpoints': {
            '/health': 'Service health check',
            '/tables': 'List all tables',
            '/tables/{table_name}/search': 'Search vectors',
            '/tables/{table_name}/add': 'Add records',
            '/docs': 'API documentation'
        }
    }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    try:
        tables = db.table_names() if db else []
        return {
            'status': 'healthy',
            'database_connected': db is not None,
            'data_directory': LANCE_DATA_DIR,
            'tables': tables,
            'total_tables': len(tables)
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'database_connected': False
        }

@app.get("/tables")
def list_tables():
    """List all available tables"""
    try:
        if not db:
            raise HTTPException(status_code=500, detail="Database not initialized")
        
        tables = db.table_names()
        table_info = {}
        
        for table_name in tables:
            try:
                table = db.open_table(table_name)
                table_info[table_name] = {
                    'row_count': table.count_rows(),
                    'schema': str(table.schema)
                }
            except Exception as e:
                table_info[table_name] = {'error': str(e)}
        
        return {
            'tables': tables,
            'table_info': table_info
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tables/{table_name}/search")
def search_vectors(table_name: str, query: SearchQuery):
    """Search for similar vectors"""
    try:
        if not db:
            raise HTTPException(status_code=500, detail="Database not initialized")
        
        if table_name not in db.table_names():
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
        
        table = db.open_table(table_name)
        
        # Get query vector
        if query.query_vector:
            query_vector = query.query_vector
        elif query.query_text:
            query_vector = simple_embedding(query.query_text)
        else:
            raise HTTPException(status_code=400, detail="Either query_text or query_vector must be provided")
        
        # Perform search
        results = table.search(query_vector).limit(query.limit).to_pandas()
        
        # Format results
        search_results = []
        for _, row in results.iterrows():
            result = SearchResult(
                id=int(row.get('id', 0)),
                text=str(row.get('text', '')),
                category=row.get('category'),
                metadata=row.get('metadata', {}),
                similarity_score=float(row.get('_distance', 0))
            )
            search_results.append(result)
        
        return {
            'query': query.query_text or "vector_query",
            'results': search_results,
            'total_results': len(search_results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/tables/{table_name}/add")
def add_records(table_name: str, data: Dict[str, List[VectorRecord]]):
    """Add records to a table"""
    try:
        if not db:
            raise HTTPException(status_code=500, detail="Database not initialized")
        
        records = data.get('records', [])
        if not records:
            raise HTTPException(status_code=400, detail="No records provided")
        
        # Prepare data for insertion
        processed_records = []
        for record in records:
            # Generate embedding if not provided
            if not record.vector:
                record.vector = simple_embedding(record.text)
            
            # Assign ID if not provided
            if not record.id:
                record.id = len(processed_records) + 1
            
            processed_record = {
                'id': record.id,
                'text': record.text,
                'category': record.category,
                'vector': record.vector,
                'metadata': record.metadata,
                'created_at': datetime.now().isoformat()
            }
            processed_records.append(processed_record)
        
        # Add to table
        if table_name in db.table_names():
            table = db.open_table(table_name)
            df = pd.DataFrame(processed_records)
            table.add(df)
        else:
            # Create new table
            df = pd.DataFrame(processed_records)
            table = db.create_table(table_name, df)
        
        return {
            'message': f'Added {len(processed_records)} records to {table_name}',
            'records_added': len(processed_records),
            'table': table_name
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print("Initializing LanceDB service...")
    
    if initialize_database():
        print(f'LanceDB service ready with tables: {db.table_names()}')
        print(f'Starting server on {API_HOST}:{API_PORT}')
        uvicorn.run(app, host=API_HOST, port=API_PORT)
    else:
        print("Failed to initialize database")
        sys.exit(1)