#!/usr/bin/env python3
"""
Python version compatibility checker for LibreOffice Document Converter
Ensures the project runs on Python 3.11+ for optimal compatibility
"""

import sys
import subprocess
import platform
from pathlib import Path

def check_python_version():
    """Check if Python version meets requirements."""
    required_version = (3, 11)
    current_version = sys.version_info[:2]
    
    print(f"Current Python version: {sys.version}")
    print(f"Required: Python {required_version[0]}.{required_version[1]}+")
    
    if current_version >= required_version:
        print("✅ Python version check passed")
        return True
    else:
        print(f"❌ Python {required_version[0]}.{required_version[1]}+ required, but found {current_version[0]}.{current_version[1]}")
        return False

def check_dependencies():
    """Check if required system dependencies are available."""
    dependencies = {
        'pip': 'pip --version',
        'libreoffice': 'libreoffice --version'
    }
    
    print("\nChecking dependencies:")
    all_good = True
    
    for dep, cmd in dependencies.items():
        try:
            result = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"✅ {dep}: Available")
                if dep == 'libreoffice':
                    # Extract version info
                    version_line = result.stdout.split('\n')[0]
                    print(f"   {version_line}")
            else:
                print(f"❌ {dep}: Not working properly")
                all_good = False
        except FileNotFoundError:
            print(f"❌ {dep}: Not found")
            all_good = False
        except subprocess.TimeoutExpired:
            print(f"⚠️  {dep}: Timeout during check")
            all_good = False
        except Exception as e:
            print(f"⚠️  {dep}: Error checking - {e}")
            all_good = False
    
    return all_good

def check_virtual_env():
    """Check if running in virtual environment."""
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )
    
    if in_venv:
        print("✅ Running in virtual environment")
        print(f"   Virtual env path: {sys.prefix}")
    else:
        print("⚠️  Not running in virtual environment")
        print("   Consider using: python -m venv venv && source venv/bin/activate")
    
    return in_venv

def check_package_compatibility():
    """Check if required packages can be imported."""
    packages = [
        ('asyncio', 'Standard library async support'),
        ('pathlib', 'Path handling'),
        ('subprocess', 'Process execution'),
        ('tempfile', 'Temporary file handling'),
        ('concurrent.futures', 'Threading support'),
    ]
    
    print("\nChecking Python package compatibility:")
    all_good = True
    
    for package, description in packages:
        try:
            __import__(package)
            print(f"✅ {package}: Available ({description})")
        except ImportError:
            print(f"❌ {package}: Missing ({description})")
            all_good = False
    
    return all_good

def check_platform_specific():
    """Check platform-specific requirements."""
    system = platform.system()
    print(f"\nPlatform: {system} {platform.release()}")
    
    if system == "Linux":
        print("✅ Linux detected - Good for LibreOffice headless operation")
        
        # Check for common LibreOffice installation paths
        common_paths = [
            "/usr/bin/libreoffice",
            "/usr/local/bin/libreoffice",
            "/opt/libreoffice*/program/soffice"
        ]
        
        for path in common_paths:
            if Path(path).exists() or any(Path("/").glob(path.lstrip("/"))):
                print(f"   LibreOffice found at: {path}")
                break
        
    elif system == "Darwin":
        print("✅ macOS detected - LibreOffice should work with Homebrew")
        
        # Check for Homebrew LibreOffice
        homebrew_path = "/Applications/LibreOffice.app"
        if Path(homebrew_path).exists():
            print(f"   LibreOffice app found at: {homebrew_path}")
    
    elif system == "Windows":
        print("⚠️  Windows detected - Docker recommended for consistent behavior")
    
    else:
        print(f"⚠️  Unknown platform: {system}")

def main():
    """Main compatibility check."""
    print("🔍 LibreOffice Document Converter - Python Compatibility Check")
    print("=" * 60)
    
    checks = [
        ("Python Version", check_python_version),
        ("System Dependencies", check_dependencies),
        ("Virtual Environment", check_virtual_env),
        ("Package Compatibility", check_package_compatibility),
    ]
    
    results = []
    for check_name, check_func in checks:
        print(f"\n📋 {check_name}:")
        print("-" * 30)
        result = check_func()
        results.append((check_name, result))
    
    # Platform-specific checks (informational)
    print(f"\n🖥️  Platform Information:")
    print("-" * 30)
    check_platform_specific()
    
    # Summary
    print(f"\n📊 Summary:")
    print("=" * 30)
    
    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{check_name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print(f"\n🎉 All compatibility checks passed!")
        print("You can proceed with the setup.")
    else:
        print(f"\n⚠️  Some compatibility issues found.")
        print("Please resolve the issues above before proceeding.")
        
        # Provide suggestions
        print(f"\n💡 Suggestions:")
        if not results[0][1]:  # Python version failed
            print("- Upgrade Python to 3.11+ using your system package manager")
            print("- On Ubuntu/Debian: sudo apt install python3.13")
            print("- On macOS: brew install python@3.13")
        
        if not results[1][1]:  # Dependencies failed
            print("- Install LibreOffice: sudo apt install libreoffice (Linux) or brew install libreoffice (macOS)")
            print("- Ensure pip is installed: python3 -m ensurepip --upgrade")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())