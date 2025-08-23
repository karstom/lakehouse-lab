#!/bin/bash
# ==============================================================================
# init-vizro.sh - Vizro Dashboard Framework Initialization
# ==============================================================================
# Sets up Vizro dashboards with sample visualizations and data connections

set -e

# Get script directory and source shared utilities
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
source "$SCRIPT_DIR/lib/init-core.sh"

# ==============================================================================
# CONFIGURATION
# ==============================================================================

MODULE_NAME="vizro"
VIZRO_DIR="$LAKEHOUSE_ROOT/vizro"

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

create_vizro_directories() {
    log_info "Creating Vizro directory structure..."
    
    mkdir -p "$VIZRO_DIR"/{dashboards,data,assets}
    
    log_success "Vizro directories created"
}

create_vizro_dashboard() {
    log_info "Creating sample Vizro dashboard..."
    
    cat > "$VIZRO_DIR/app.py" << 'EOF'
import vizro
from vizro import Vizro
import vizro.plotly.express as px
import vizro.models as vm
import pandas as pd
import psycopg2
import os
from sqlalchemy import create_engine
import boto3
from botocore.client import Config
import duckdb

def load_sample_data():
    """Load sample data from various sources"""
    try:
        # Try to load data from PostgreSQL
        db_url = os.getenv('DATABASE_URL')
        if db_url:
            log_info("Connecting to PostgreSQL...")
            engine = create_engine(db_url)
            
            # Get some sample data from PostgreSQL system tables
            query = '''
                SELECT 
                    schemaname as schema_name,
                    tablename as table_name,
                    'table' as object_type
                FROM pg_tables 
                WHERE schemaname NOT IN ('information_schema', 'pg_catalog')
                UNION ALL
                SELECT 
                    schemaname as schema_name,
                    viewname as table_name,
                    'view' as object_type
                FROM pg_views 
                WHERE schemaname NOT IN ('information_schema', 'pg_catalog')
                LIMIT 20
            '''
            df = pd.read_sql(query, engine)
            
            if not df.empty:
                return df
    except Exception as e:
        print(f'Could not load from PostgreSQL: {e}')
    
    try:
        # Try to connect to MinIO and load data
        minio_endpoint = os.getenv('MINIO_ENDPOINT', 'http://minio:9000')
        minio_access_key = os.getenv('MINIO_ROOT_USER', 'admin')
        minio_secret_key = os.getenv('MINIO_ROOT_PASSWORD')
        
        if minio_secret_key:
            print("Attempting to connect to MinIO...")
            
            # Configure DuckDB with S3 credentials
            conn = duckdb.connect(':memory:')
            
            # Install and load httpfs extension
            conn.execute("INSTALL httpfs;")
            conn.execute("LOAD httpfs;")
            
            # Set S3 credentials
            conn.execute(f"""
                SET s3_endpoint = '{minio_endpoint.replace('http://', '')}';
                SET s3_access_key_id = '{minio_access_key}';
                SET s3_secret_access_key = '{minio_secret_key}';
                SET s3_use_ssl = false;
                SET s3_url_style = 'path';
            """)
            
            # Try to read CSV files from lakehouse bucket
            result = conn.execute("""
                SELECT * FROM read_csv_auto('s3://lakehouse/raw-data/*.csv', union_by_name=true) 
                LIMIT 100
            """).fetchdf()
            
            if not result.empty:
                return result
                
    except Exception as e:
        print(f'Could not load from MinIO: {e}')
    
    # Fallback to generated sample data
    print("Using generated sample data...")
    return pd.DataFrame({
        'category': ['Analytics', 'Raw Data', 'Processed', 'ML Models', 'Reports'] * 4,
        'value': [150, 300, 75, 200, 450, 180, 320, 85, 210, 480, 160, 310, 95, 190, 470, 140, 290, 65, 220, 460],
        'date': pd.date_range('2024-01-01', periods=20, freq='D'),
        'region': ['North', 'South', 'East', 'West', 'Central'] * 4
    })

# Load the data
sample_data = load_sample_data()

# Define the dashboard pages
overview_page = vm.Page(
    title='Lakehouse Overview',
    components=[
        vm.Graph(
            id='overview_bar',
            figure=px.bar(
                sample_data.groupby('category').agg({'value': 'sum'}).reset_index() if 'category' in sample_data.columns else sample_data.head(),
                x='category' if 'category' in sample_data.columns else sample_data.columns[0],
                y='value' if 'value' in sample_data.columns else sample_data.columns[1] if len(sample_data.columns) > 1 else sample_data.columns[0],
                title='Data Overview by Category',
                color='category' if 'category' in sample_data.columns else None
            )
        ),
        vm.Graph(
            id='overview_line',
            figure=px.line(
                sample_data.head(10) if 'date' in sample_data.columns else sample_data.head(10),
                x='date' if 'date' in sample_data.columns else sample_data.columns[0],
                y='value' if 'value' in sample_data.columns else sample_data.columns[1] if len(sample_data.columns) > 1 else sample_data.columns[0],
                title='Trend Analysis',
                color='region' if 'region' in sample_data.columns else None
            )
        )
    ]
)

analytics_page = vm.Page(
    title='Analytics Deep Dive',
    components=[
        vm.Graph(
            id='analytics_scatter',
            figure=px.scatter(
                sample_data.head(20),
                x=sample_data.columns[0],
                y=sample_data.columns[1] if len(sample_data.columns) > 1 else sample_data.columns[0],
                color=sample_data.columns[2] if len(sample_data.columns) > 2 else None,
                size=sample_data.columns[1] if len(sample_data.columns) > 1 and 'value' in sample_data.columns else None,
                title='Data Relationships'
            )
        ),
        vm.Graph(
            id='analytics_pie',
            figure=px.pie(
                sample_data.groupby(sample_data.columns[2] if len(sample_data.columns) > 2 else sample_data.columns[0]).agg({sample_data.columns[1] if len(sample_data.columns) > 1 else sample_data.columns[0]: 'sum'}).reset_index() if len(sample_data.columns) > 1 else sample_data.head(),
                values=sample_data.columns[1] if len(sample_data.columns) > 1 else sample_data.columns[0],
                names=sample_data.columns[2] if len(sample_data.columns) > 2 else sample_data.columns[0],
                title='Distribution Analysis'
            )
        )
    ]
)

# Create the dashboard
dashboard = vm.Dashboard(
    title="🏠 Lakehouse Lab - Vizro Dashboard",
    pages=[overview_page, analytics_page]
)

if __name__ == '__main__':
    print("Starting Vizro Dashboard...")
    print(f"Data loaded: {len(sample_data)} rows, {len(sample_data.columns)} columns")
    print(f"Columns: {list(sample_data.columns)}")
    
    app = Vizro().build(dashboard)
    app.run(host='0.0.0.0', port=8050, debug=True)
EOF
    
    log_success "Vizro dashboard application created"
}

create_vizro_data_samples() {
    log_info "Creating Vizro data samples..."
    
    # Create sample CSV data
    cat > "$VIZRO_DIR/data/sample_metrics.csv" << 'EOF'
date,service,requests,response_time,error_rate
2024-01-01,superset,1250,0.85,0.02
2024-01-01,airflow,890,1.2,0.01
2024-01-01,jupyter,650,0.95,0.005
2024-01-01,minio,2100,0.45,0.001
2024-01-02,superset,1380,0.82,0.018
2024-01-02,airflow,920,1.15,0.012
2024-01-02,jupyter,720,0.88,0.008
2024-01-02,minio,2250,0.42,0.002
2024-01-03,superset,1420,0.79,0.015
2024-01-03,airflow,980,1.1,0.009
2024-01-03,jupyter,780,0.91,0.006
2024-01-03,minio,2400,0.48,0.001
EOF
    
    log_success "Vizro sample data created"
}

create_vizro_config() {
    log_info "Creating Vizro configuration..."
    
    cat > "$VIZRO_DIR/config.yaml" << 'EOF'
# Vizro Configuration for Lakehouse Lab
app:
  title: "Lakehouse Lab Analytics"
  theme: "default"
  
data_sources:
  postgresql:
    type: "postgresql"
    connection_string: "${DATABASE_URL}"
    
  minio:
    type: "s3"
    endpoint: "${MINIO_ENDPOINT}"
    access_key: "${MINIO_ROOT_USER}"
    secret_key: "${MINIO_ROOT_PASSWORD}"
    bucket: "lakehouse"
    
dashboards:
  - name: "overview"
    title: "Lakehouse Overview"
    description: "High-level metrics and KPIs"
    
  - name: "analytics"
    title: "Deep Analytics"
    description: "Detailed analysis and insights"
EOF
    
    log_success "Vizro configuration created"
}

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

main() {
    print_separator "🎨 INITIALIZING VIZRO DASHBOARD FRAMEWORK"
    
    # Check prerequisites  
    log_info "Setting up Vizro in: $LAKEHOUSE_ROOT"
    
    # Create directory structure
    create_vizro_directories
    
    # Set up Vizro components
    create_vizro_dashboard
    create_vizro_data_samples
    create_vizro_config
    
    # Set proper permissions
    log_info "Setting directory permissions..."
    chmod -R 755 "$VIZRO_DIR"
    
    log_success "✅ Vizro initialization completed successfully"
    log_info "   • Dashboard application: $VIZRO_DIR/app.py"
    log_info "   • Sample data: $VIZRO_DIR/data/"
    log_info "   • Configuration: $VIZRO_DIR/config.yaml"
    log_info "   • Access URL: http://localhost:9050 (after stack startup)"
    
    return 0
}

# Execute main function if script is run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi