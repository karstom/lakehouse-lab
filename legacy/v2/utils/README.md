# 🛠️ Lakehouse Lab Utilities

This directory contains standalone utilities and helper tools for Lakehouse Lab.

## 📁 Utility Scripts

### Python Utilities
- **`iceberg_jar_manager.py`** - Manages Apache Iceberg JAR dependencies
- **`jar_manager_cell.py`** - Jupyter notebook cell for JAR management  
- **`test_stack_health.py`** - Python-based stack health testing

## 🎯 Usage

### Iceberg JAR Management
```python
# Use in Jupyter notebooks
exec(open('utils/jar_manager_cell.py').read())

# Direct Python usage
python utils/iceberg_jar_manager.py
```

### Health Testing
```bash
# Run Python health tests
python utils/test_stack_health.py
```

## 📝 Utility Descriptions

### `iceberg_jar_manager.py`
- Manages Apache Iceberg JAR file dependencies
- Downloads and configures Iceberg libraries for Spark
- Handles version compatibility and dependency resolution

### `jar_manager_cell.py` 
- Jupyter notebook integration for JAR management
- Provides easy interface for managing Spark dependencies
- Can be executed directly in notebook cells

### `test_stack_health.py`
- Python-based health checking for all services
- More detailed testing than shell script equivalents
- Generates detailed reports on service status

## 🔧 Development

These utilities are:
- **Self-contained** - Can run independently
- **Optional** - Not required for basic Lakehouse Lab operation
- **Specialized** - Address specific advanced use cases

## 💡 Adding Utilities

When adding new utilities:
1. Keep them self-contained with minimal dependencies
2. Add proper error handling and logging
3. Include usage examples
4. Document in this README
5. Consider if they belong in `scripts/` instead for user-facing tools

---

**Note:** These utilities support advanced use cases. Most users won't need them directly.