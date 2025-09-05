#!/usr/bin/env python3
"""
Iceberg JAR Manager for Jupyter Notebooks
Allows dynamic downloading and management of Iceberg JARs
"""

import os
import requests
from pathlib import Path

class IcebergJarManager:
    def __init__(self, jar_dir="/home/jovyan/work/iceberg-jars"):
        self.jar_dir = jar_dir
        self.jars_config = [
            {
                "name": "iceberg-spark-runtime-3.5_2.12-1.9.2.jar",
                "url": "https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-spark-runtime-3.5_2.12/1.9.2/iceberg-spark-runtime-3.5_2.12-1.9.2.jar",
                "description": "Iceberg Spark runtime (core functionality)"
            },
            {
                "name": "iceberg-aws-1.9.2.jar", 
                "url": "https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-aws/1.9.2/iceberg-aws-1.9.2.jar",
                "description": "Iceberg AWS integration (S3FileIO)"
            },
            {
                "name": "hadoop-aws-3.3.4.jar",
                "url": "https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar",
                "description": "Hadoop AWS support (S3AFileSystem)"
            },
            {
                "name": "aws-java-sdk-bundle-1.12.262.jar",
                "url": "https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar",
                "description": "AWS SDK v1 (for Hadoop compatibility)"
            },
            {
                "name": "bundle-2.17.295.jar",
                "url": "https://repo1.maven.org/maven2/software/amazon/awssdk/bundle/2.17.295/bundle-2.17.295.jar",
                "description": "AWS SDK v2 bundle (for Iceberg S3FileIO)"
            },
            {
                "name": "url-connection-client-2.17.295.jar",
                "url": "https://repo1.maven.org/maven2/software/amazon/awssdk/url-connection-client/2.17.295/url-connection-client-2.17.295.jar",
                "description": "AWS SDK v2 HTTP client"
            }
        ]
    
    def download_jar(self, jar_config, force=False):
        """Download a single JAR file"""
        jar_path = os.path.join(self.jar_dir, jar_config["name"])
        
        if os.path.exists(jar_path) and not force:
            print(f"   ✅ Already exists: {jar_config['name']}")
            return True
        
        try:
            print(f"   📥 Downloading: {jar_config['name']}")
            print(f"      {jar_config['description']}")
            
            response = requests.get(jar_config["url"], stream=True)
            response.raise_for_status()
            
            # Create directory if it doesn't exist
            os.makedirs(self.jar_dir, exist_ok=True)
            
            # Download with progress indication
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(jar_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        if downloaded % (1024 * 1024) == 0:  # Show progress every MB
                            print(f"      Progress: {progress:.1f}% ({downloaded // (1024*1024)}MB)")
            
            print(f"   ✅ Downloaded: {jar_config['name']} ({downloaded // (1024*1024)}MB)")
            return True
            
        except Exception as e:
            print(f"   ❌ Failed to download {jar_config['name']}: {e}")
            return False
    
    def download_all(self, force=False):
        """Download all required JARs"""
        print(f"🔧 Downloading Iceberg JARs to: {self.jar_dir}")
        print("=" * 60)
        
        downloaded = []
        failed = []
        
        for jar_config in self.jars_config:
            if self.download_jar(jar_config, force):
                downloaded.append(jar_config["name"])
            else:
                failed.append(jar_config["name"])
        
        print("\n📊 Download Summary:")
        print(f"   ✅ Successful: {len(downloaded)}")
        print(f"   ❌ Failed: {len(failed)}")
        
        if failed:
            print(f"   Failed files: {', '.join(failed)}")
        
        return self.get_jar_paths()
    
    def get_jar_paths(self):
        """Get paths to all available JAR files"""
        jar_paths = []
        for jar_config in self.jars_config:
            jar_path = os.path.join(self.jar_dir, jar_config["name"])
            if os.path.exists(jar_path):
                jar_paths.append(jar_path)
        return jar_paths
    
    def list_jars(self):
        """List all JARs and their status"""
        print(f"📋 JAR Status in: {self.jar_dir}")
        print("=" * 60)
        
        available = 0
        missing = 0
        
        for jar_config in self.jars_config:
            jar_path = os.path.join(self.jar_dir, jar_config["name"])
            exists = os.path.exists(jar_path)
            
            status = "✅ Available" if exists else "❌ Missing"
            size = ""
            
            if exists:
                size_bytes = os.path.getsize(jar_path)
                size = f" ({size_bytes // (1024*1024)}MB)"
                available += 1
            else:
                missing += 1
            
            print(f"   {status}: {jar_config['name']}{size}")
            print(f"      {jar_config['description']}")
        
        print(f"\n📊 Summary: {available} available, {missing} missing")
        return available, missing
    
    def clean_jars(self):
        """Remove all downloaded JARs"""
        print(f"🗑️ Cleaning JARs from: {self.jar_dir}")
        
        removed = 0
        for jar_config in self.jars_config:
            jar_path = os.path.join(self.jar_dir, jar_config["name"])
            if os.path.exists(jar_path):
                try:
                    os.remove(jar_path)
                    print(f"   ✅ Removed: {jar_config['name']}")
                    removed += 1
                except Exception as e:
                    print(f"   ❌ Failed to remove {jar_config['name']}: {e}")
        
        print(f"🧹 Cleaned {removed} JAR file(s)")

# Convenience functions for notebook use
def download_iceberg_jars(force=False):
    """Download all Iceberg JARs"""
    manager = IcebergJarManager()
    return manager.download_all(force=force)

def list_iceberg_jars():
    """List status of all Iceberg JARs"""
    manager = IcebergJarManager()
    return manager.list_jars()

def clean_iceberg_jars():
    """Remove all Iceberg JARs"""
    manager = IcebergJarManager()
    return manager.clean_jars()

def get_iceberg_jar_paths():
    """Get paths to available JARs"""
    manager = IcebergJarManager()
    return manager.get_jar_paths()

# Demo usage
if __name__ == "__main__":
    print("🧊 Iceberg JAR Manager Demo")
    print("=" * 50)
    
    manager = IcebergJarManager()
    
    # List current status
    manager.list_jars()
    
    # Download all JARs
    print("\n" + "=" * 50)
    jar_paths = manager.download_all()
    
    print(f"\n🎯 Ready to use with {len(jar_paths)} JARs:")
    for jar_path in jar_paths:
        print(f"   • {os.path.basename(jar_path)}")