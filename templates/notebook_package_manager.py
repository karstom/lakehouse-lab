#!/usr/bin/env python3
"""
Notebook Package Manager for Lakehouse Lab
Allows safe dynamic installation of Python packages in Jupyter notebooks
"""

import subprocess
import sys
import os
import importlib
import pkg_resources
from typing import List, Dict, Optional
import warnings

class NotebookPackageManager:
    def __init__(self, user_install=True):
        """
        Initialize the package manager
        
        Args:
            user_install: Install packages for current user only (safer)
        """
        self.user_install = user_install
        self.installed_packages = set()
        
    def install(self, packages: str, upgrade=False, quiet=True, force_reinstall=False):
        """
        Install one or more packages using pip
        
        Args:
            packages: Package name(s) - can be space-separated string or single package
            upgrade: Whether to upgrade if already installed
            quiet: Reduce pip output
            force_reinstall: Force reinstall even if satisfied
        """
        if isinstance(packages, str):
            package_list = packages.split()
        else:
            package_list = packages
            
        print(f"📦 Installing packages: {', '.join(package_list)}")
        
        # Build pip command
        cmd = [sys.executable, "-m", "pip", "install"]
        
        if self.user_install:
            cmd.append("--user")
            
        if upgrade:
            cmd.append("--upgrade")
            
        if quiet:
            cmd.append("--quiet")
            
        if force_reinstall:
            cmd.append("--force-reinstall")
            
        cmd.extend(package_list)
        
        try:
            # Show what we're running
            if not quiet:
                print(f"Running: {' '.join(cmd)}")
                
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if not quiet and result.stdout:
                print("STDOUT:", result.stdout)
                
            print(f"✅ Successfully installed: {', '.join(package_list)}")
            
            # Track installed packages
            self.installed_packages.update(package_list)
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install packages: {e}")
            if e.stderr:
                print("Error details:", e.stderr)
            if e.stdout:
                print("Output:", e.stdout)
            return False
    
    def uninstall(self, packages: str, quiet=True):
        """
        Uninstall packages using pip
        
        Args:
            packages: Package name(s) to uninstall
            quiet: Reduce pip output
        """
        if isinstance(packages, str):
            package_list = packages.split()
        else:
            package_list = packages
            
        print(f"🗑️ Uninstalling packages: {', '.join(package_list)}")
        
        cmd = [sys.executable, "-m", "pip", "uninstall", "-y"]
        
        if quiet:
            cmd.append("--quiet")
            
        cmd.extend(package_list)
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print(f"✅ Successfully uninstalled: {', '.join(package_list)}")
            
            # Remove from tracking
            self.installed_packages.discard(set(package_list))
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to uninstall packages: {e}")
            if e.stderr:
                print("Error details:", e.stderr)
            return False
    
    def list_installed(self, pattern: Optional[str] = None):
        """
        List installed packages
        
        Args:
            pattern: Optional pattern to filter packages
        """
        try:
            result = subprocess.run([sys.executable, "-m", "pip", "list"], 
                                  capture_output=True, text=True, check=True)
            
            lines = result.stdout.strip().split('\n')[2:]  # Skip header
            packages = []
            
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        name, version = parts[0], parts[1]
                        if not pattern or pattern.lower() in name.lower():
                            packages.append((name, version))
            
            if packages:
                pattern_msg = f' (matching "{pattern}")' if pattern else ""
                print(f"📋 Installed packages{pattern_msg}:")
                for name, version in packages:
                    print(f"   • {name} == {version}")
            else:
                search_msg = f" matching '{pattern}'" if pattern else ""
                print(f"No packages found{search_msg}")
                
            return packages
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to list packages: {e}")
            return []
    
    def show_package_info(self, package_name: str):
        """
        Show detailed information about a package
        """
        try:
            result = subprocess.run([sys.executable, "-m", "pip", "show", package_name], 
                                  capture_output=True, text=True, check=True)
            
            print(f"📄 Package information for '{package_name}':")
            print(result.stdout)
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Package '{package_name}' not found or error occurred: {e}")
    
    def search_packages(self, query: str, limit: int = 10):
        """
        Search for packages (note: pip search is deprecated, this uses PyPI API)
        """
        try:
            import requests
            
            print(f"🔍 Searching PyPI for packages matching '{query}'...")
            
            # Use PyPI simple API
            response = requests.get(f"https://pypi.org/search/?q={query}")
            
            if response.status_code == 200:
                print(f"💡 Search completed. Use 'pip search' or visit https://pypi.org/search/?q={query}")
                print("   Popular data science packages you might want:")
                
                suggestions = [
                    "pandas", "numpy", "matplotlib", "seaborn", "plotly", 
                    "scikit-learn", "scipy", "statsmodels", "bokeh", "altair",
                    "streamlit", "dash", "jupyter", "ipywidgets", "tqdm"
                ]
                
                matching_suggestions = [pkg for pkg in suggestions if query.lower() in pkg.lower()]
                if matching_suggestions:
                    print(f"   Suggested matches: {', '.join(matching_suggestions[:5])}")
                    
            else:
                print("❌ Search failed - please visit https://pypi.org to search manually")
                
        except ImportError:
            print("❌ 'requests' package needed for search. Install it first: install('requests')")
        except Exception as e:
            print(f"❌ Search failed: {e}")
    
    def check_package(self, package_name: str) -> bool:
        """
        Check if a package is installed and importable
        """
        try:
            importlib.import_module(package_name)
            print(f"✅ Package '{package_name}' is installed and importable")
            return True
        except ImportError:
            print(f"❌ Package '{package_name}' is not installed or not importable")
            return False
    
    def install_and_import(self, package_name: str, import_name: Optional[str] = None):
        """
        Install a package and then import it
        
        Args:
            package_name: Name of package to install
            import_name: Name to use for import (if different from package name)
        """
        import_name = import_name or package_name
        
        # Check if already available
        try:
            module = importlib.import_module(import_name)
            print(f"✅ Package '{import_name}' already available")
            return module
        except ImportError:
            pass
        
        # Install the package
        if self.install(package_name):
            try:
                # Reload the module cache
                importlib.invalidate_caches()
                module = importlib.import_module(import_name)
                print(f"✅ Package '{import_name}' installed and imported successfully")
                return module
            except ImportError as e:
                print(f"❌ Package installed but import failed: {e}")
                print(f"💡 Try restarting the kernel or importing manually")
                return None
        else:
            return None

# Create a global instance for easy use
package_manager = NotebookPackageManager()

# Convenience functions
def install(packages: str, upgrade=False, quiet=True):
    """Quick install function"""
    return package_manager.install(packages, upgrade=upgrade, quiet=quiet)

def uninstall(packages: str):
    """Quick uninstall function"""  
    return package_manager.uninstall(packages)

def list_packages(pattern: str = None):
    """Quick list function"""
    return package_manager.list_installed(pattern)

def search(query: str):
    """Quick search function"""
    return package_manager.search_packages(query)

def info(package_name: str):
    """Quick info function"""
    return package_manager.show_package_info(package_name)

def check(package_name: str):
    """Quick check function"""
    return package_manager.check_package(package_name)

def install_import(package_name: str, import_name: str = None):
    """Quick install and import function"""
    return package_manager.install_and_import(package_name, import_name)

# Show usage on import
print("📦 Notebook Package Manager loaded!")
print("Available functions:")
print("   • install('package_name') - Install packages")
print("   • uninstall('package_name') - Uninstall packages") 
print("   • list_packages() - List installed packages")
print("   • search('query') - Search for packages")
print("   • info('package_name') - Show package details")
print("   • check('package_name') - Check if package is available")
print("   • install_import('package', 'import_name') - Install and import")
print("\nExample: install('plotly seaborn') or install_import('scikit-learn', 'sklearn')")