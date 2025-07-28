#!/bin/bash
# ==============================================================================
# init-all-in-one.sh - Legacy Compatibility Wrapper
# ==============================================================================
# This script provides backwards compatibility by redirecting to the new
# modular initialization system.

echo "⚠️  NOTICE: init-all-in-one.sh has been replaced with a modular system"
echo "🔄 Redirecting to: init-all-in-one-modular.sh"
echo ""

# Check if the new script exists
if [ ! -f "init-all-in-one-modular.sh" ]; then
    echo "❌ Error: init-all-in-one-modular.sh not found"
    echo "   Please ensure you have the latest version of lakehouse-lab"
    exit 1
fi

# Run the modular initialization script
exec ./init-all-in-one-modular.sh "$@"