# JAR Manager Cell - Run this in a Jupyter notebook cell
# Copy and paste this code into a notebook cell for JAR management

import sys
sys.path.append('/home/jovyan/work')

# Import the JAR manager (assumes iceberg_jar_manager.py is available)
try:
    from iceberg_jar_manager import IcebergJarManager, download_iceberg_jars, list_iceberg_jars, clean_iceberg_jars
    
    print("🔧 Iceberg JAR Manager")
    print("=" * 30)
    
    # Quick status check
    manager = IcebergJarManager()
    available, missing = manager.list_jars()
    
    if missing > 0:
        print(f"\n📥 Found {missing} missing JARs. Download them?")
        user_input = input("Download missing JARs? (y/n): ").lower().strip()
        
        if user_input in ['y', 'yes']:
            jar_paths = download_iceberg_jars()
            print(f"\n🎯 Ready! {len(jar_paths)} JARs available for Spark")
        else:
            print("⏭️ Skipping download. You can run download_iceberg_jars() later.")
    else:
        print("✅ All JARs are available!")
        
    print("\n🛠️ Available commands:")
    print("   • download_iceberg_jars() - Download all missing JARs")
    print("   • list_iceberg_jars() - Show JAR status")  
    print("   • clean_iceberg_jars() - Remove all JARs")
    print("   • manager.get_jar_paths() - Get JAR file paths")

except ImportError:
    print("⚠️ JAR manager not found. Please ensure iceberg_jar_manager.py is available.")
    print("You can download it from the lakehouse-lab repository.")