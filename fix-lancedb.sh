#!/bin/bash

# Fix LanceDB syntax error and restart service
# This fixes the mismatched bracket on line 217

set -e

echo "🔧 Fixing LanceDB service syntax error..."

# Check if we're in the right directory
if [[ ! -f "docker-compose.yml" ]]; then
    echo "❌ Please run this from your lakehouse-lab directory"
    exit 1
fi

# Check if the problematic file exists
if [[ ! -f "lakehouse-data/lancedb/service/lancedb_service.py" ]]; then
    echo "❌ LanceDB service file not found"
    echo "🔧 Creating directory structure..."
    mkdir -p lakehouse-data/lancedb/service
    
    # Copy from template if it exists
    if [[ -f "templates/lancedb/service/lancedb_service.py" ]]; then
        cp templates/lancedb/service/lancedb_service.py lakehouse-data/lancedb/service/
        echo "✅ Copied from template"
    else
        echo "❌ Template not found - you need to pull latest updates first"
        exit 1
    fi
else
    echo "🔍 Found existing service file, fixing syntax error..."
    
    # Create backup
    cp lakehouse-data/lancedb/service/lancedb_service.py lakehouse-data/lancedb/service/lancedb_service.py.backup
    
    # Fix the syntax error on line 217 - remove extra closing bracket
    sed -i "s/'category': \['lakehouse', 'analytics', 'data', 'ml', 'ai'\]\[i%5\] for i in range(20)\],/'category': [\['lakehouse', 'analytics', 'data', 'ml', 'ai'\][i%5] for i in range(20)],/" lakehouse-data/lancedb/service/lancedb_service.py
    
    echo "✅ Fixed syntax error"
fi

echo "🔄 Restarting LanceDB service..."

# Stop LanceDB service
docker compose stop lancedb

# Wait a moment
sleep 2

# Start LanceDB service
docker compose up -d lancedb

# Wait for startup
sleep 10

# Check if it's working
echo "🔍 Checking LanceDB health..."
for i in {1..30}; do
    if curl -s http://localhost:9080/health >/dev/null 2>&1; then
        echo "✅ LanceDB is responding!"
        break
    elif [[ $i -eq 30 ]]; then
        echo "⚠️  LanceDB may still be starting up"
        echo "💡 Check logs with: docker compose logs lancedb"
        break
    else
        sleep 2
    fi
done

echo ""
echo "🎉 LanceDB fix completed!"
echo ""
echo "🔗 Test LanceDB service:"
echo "   • Health check: curl http://localhost:9080/health"
echo "   • API docs: http://localhost:9080/docs" 
echo "   • Service info: curl http://localhost:9080/"