# 📦 Notebook Package Manager User Guide

The Lakehouse Lab includes a dynamic package management system that allows data analysts to install Python packages on-the-fly within Jupyter notebooks without restarting containers or modifying system configurations.

## 🚀 Quick Start

1. **Open the Package Manager Notebook**: Navigate to `00_Package_Manager.ipynb` in your Jupyter environment
2. **Run the first cell** to load the package manager
3. **Start installing packages** using the simple functions provided

```python
# Install a single package
install('plotly')

# Install multiple packages at once  
install('seaborn matplotlib bokeh')

# Install and immediately import
sklearn = install_import('scikit-learn', 'sklearn')
```

## ✨ Key Features

### 🎯 Safe Installation
- **User-level installation**: Packages install to your user directory only
- **Non-destructive**: Won't break the base Jupyter environment
- **Reversible**: Easy to uninstall packages you no longer need

### 🔍 Package Discovery
- **Built-in search**: Find packages related to your needs
- **Categorized suggestions**: Pre-organized lists of popular data science packages
- **Package information**: View detailed information about any package

### 🛠️ Complete Management
- **Install/Uninstall**: Add and remove packages as needed
- **List packages**: See what's currently installed
- **Check availability**: Verify if a package is ready to import
- **Install & Import**: One-step installation and import

## 📚 Available Functions

### Installation Functions

```python
# Basic installation
install('package_name')

# Install multiple packages
install('pandas numpy matplotlib')

# Install with upgrade
install('scikit-learn', upgrade=True)

# Install and import in one step
requests = install_import('requests')
sklearn = install_import('scikit-learn', 'sklearn')  # Different import name
```

### Information Functions

```python
# List all installed packages
list_packages()

# List packages matching a pattern
list_packages('data')

# Show detailed package information
info('pandas')

# Check if package is available for import
check('numpy')

# Search for packages (with suggestions)
search('visualization')
```

### Management Functions

```python
# Uninstall packages
uninstall('package_name')

# Uninstall multiple packages
uninstall('pkg1 pkg2 pkg3')
```

## 🎨 Package Categories & Suggestions

The package manager includes curated suggestions organized by use case:

### 📊 Visualization
- **plotly**: Interactive plots and dashboards
- **bokeh**: Web-ready interactive visualizations  
- **altair**: Grammar of graphics for Python
- **seaborn**: Statistical data visualization
- **matplotlib**: Fundamental plotting library
- **pygal**: SVG charts and graphs

### 🤖 Machine Learning
- **scikit-learn**: Comprehensive ML library
- **xgboost**: Gradient boosting framework
- **lightgbm**: Fast gradient boosting
- **catboost**: Categorical feature boosting
- **tensorflow**: Deep learning framework
- **torch**: PyTorch deep learning

### 📈 Statistics & Analysis
- **scipy**: Scientific computing library
- **statsmodels**: Statistical modeling
- **pingouin**: Statistical package
- **lifelines**: Survival analysis
- **pymc3**: Probabilistic programming

### 🌐 Web & APIs
- **requests**: HTTP library for APIs
- **beautifulsoup4**: Web scraping
- **scrapy**: Web scraping framework
- **fastapi**: Modern web API framework
- **streamlit**: Data app framework
- **dash**: Interactive web applications

### ⚡ Performance
- **numba**: JIT compiler for Python
- **dask**: Parallel computing
- **ray**: Distributed computing
- **polars**: Fast DataFrame library
- **vaex**: Out-of-core DataFrame library

### 🔧 Utilities
- **tqdm**: Progress bars
- **joblib**: Lightweight pipelining
- **click**: Command line interfaces
- **pydantic**: Data validation
- **attrs**: Classes without boilerplate
- **rich**: Rich text and formatting

## 🎯 Common Use Cases

### Installing Visualization Libraries
```python
# For interactive dashboards
install('plotly dash streamlit')

# For statistical plots
install('seaborn matplotlib')

# For advanced visualizations
install('bokeh altair')
```

### Setting Up Machine Learning Environment
```python
# Core ML packages
install('scikit-learn pandas numpy')

# Advanced ML frameworks
install('xgboost lightgbm')

# Deep learning (choose one)
install('tensorflow')  # or
install('torch torchvision')
```

### Web Scraping & API Work
```python
# Basic web requests
install('requests')

# Web scraping toolkit
install('requests beautifulsoup4 lxml')

# Advanced scraping
install('scrapy selenium')
```

### Data Processing Performance
```python
# Fast DataFrames
install('polars')

# Parallel processing
install('dask')

# JIT compilation
install('numba')
```

## 🔧 Advanced Usage

### Installing Specific Versions
```python
# Install exact version
install('pandas==1.5.0')

# Install with version constraints
install('numpy>=1.20.0,<1.25.0')
```

### Development Dependencies
```python
# Testing frameworks
install('pytest pytest-cov')

# Code quality tools
install('black flake8 mypy')

# Jupyter extensions
install('ipywidgets jupyter-contrib-nbextensions')
```

### Working with Requirements Files
```python
# Note: The package manager works with individual packages
# For requirements.txt files, you can read and install each line:

with open('requirements.txt', 'r') as f:
    packages = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
for package in packages:
    install(package)
```

## ⚠️ Best Practices

### 🎯 Installation Strategy
- **Install as needed**: Only install packages you're actively using
- **Test immediately**: Run `check('package')` after installation to verify
- **Document dependencies**: Keep track of packages you've added for reproducibility

### 🧹 Maintenance
- **Clean up regularly**: Uninstall packages you no longer need
- **Check for conflicts**: Some packages may have conflicting dependencies
- **Monitor space**: User installations consume disk space

### 🔒 Safety Guidelines
- **Trusted sources only**: Only install packages from PyPI or trusted repositories
- **Version pinning**: For production work, pin specific versions for reproducibility
- **Environment isolation**: Remember that packages are user-level, not system-wide

### 🔄 Troubleshooting
- **Import issues**: If a package installs but won't import, try restarting the kernel
- **Dependency conflicts**: If installation fails, check the error message for conflicts
- **Permission errors**: The package manager uses user-level installation to avoid permission issues

## 🚨 Troubleshooting

### Common Issues

**Package won't import after installation**
```python
# Try checking if it's available
check('package_name')

# Restart the Jupyter kernel (Kernel -> Restart)
# Then try importing again
```

**Installation fails with dependency conflicts**
```python
# Try installing with upgrade flag
install('package_name', upgrade=True)

# Or check what's conflicting
info('conflicting_package')
```

**"Package not found" errors**
```python
# Verify the package name is correct
search('partial_name')

# Check PyPI directly: https://pypi.org
```

### Getting Help

1. **Check package information**: Use `info('package_name')` for details
2. **Search for alternatives**: Use `search('keyword')` to find similar packages  
3. **Consult PyPI**: Visit https://pypi.org for official package documentation
4. **Community support**: Check the package's GitHub repository or documentation

## 🎓 Examples & Tutorials

### Example 1: Data Visualization Pipeline
```python
# Install visualization stack
install('plotly seaborn matplotlib')

# Load and create sample data
import pandas as pd
import plotly.express as px

# Create interactive plot
df = pd.DataFrame({'x': range(10), 'y': range(10)})
fig = px.line(df, x='x', y='y', title='Interactive Line Plot')
fig.show()
```

### Example 2: Machine Learning Analysis
```python
# Install ML packages
sklearn = install_import('scikit-learn', 'sklearn')

# Quick ML example
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier

X, y = make_classification(n_samples=100, n_features=4)
clf = RandomForestClassifier()
clf.fit(X, y)
print(f"Model accuracy: {clf.score(X, y):.2f}")
```

### Example 3: Web API Integration
```python
# Install HTTP client
requests = install_import('requests')

# Fetch data from API
response = requests.get('https://api.github.com/users/octocat')
data = response.json()
print(f"User: {data['name']}, Repos: {data['public_repos']}")
```

## 💡 Tips & Tricks

### Performance Optimization
- Install packages at the beginning of your notebook session
- Use `install_import()` for packages you'll use immediately
- Group related package installations together

### Workflow Integration  
- Create a "setup" cell at the start of each notebook with required packages
- Use the Package Manager notebook as a testing ground for new packages
- Document package choices in your notebook markdown cells

### Collaboration
- Share package lists with team members using `list_packages()`
- Pin specific versions for reproducible analyses
- Include package installation commands in shared notebooks

---

## 🆘 Support

If you encounter issues with the package manager:

1. **Check the error message** carefully for specific guidance
2. **Try the troubleshooting steps** above  
3. **Consult the lakehouse-lab documentation** for system-wide issues
4. **Report bugs** to the lakehouse-lab GitHub repository

The dynamic package management system is designed to make your data analysis workflow more flexible and productive. Happy analyzing! 🚀