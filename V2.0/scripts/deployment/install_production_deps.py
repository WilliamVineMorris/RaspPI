#!/usr/bin/env python3
"""
Install missing production dependencies for the scanner system
"""

import subprocess
import sys
import os

def run_command(cmd, description):
    """Run a command and handle errors"""
    print(f"🔧 {description}...")
    print(f"   Running: {cmd}")
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            print(f"✅ {description} successful!")
            if result.stdout.strip():
                print(f"   Output: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ {description} failed!")
            print(f"   Error: {result.stderr.strip()}")
            return False
    except subprocess.TimeoutExpired:
        print(f"❌ {description} timed out!")
        return False
    except Exception as e:
        print(f"❌ {description} error: {e}")
        return False

def install_production_dependencies():
    """Install production dependencies for the Pi"""
    print("🚀 Installing Production Dependencies")
    print("=" * 50)
    
    # Check if we're on the Pi
    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read()
            if 'Raspberry Pi' not in cpuinfo:
                print("⚠️  Warning: This doesn't appear to be a Raspberry Pi")
    except:
        pass
    
    success_count = 0
    total_commands = 0
    
    # Update pip first
    total_commands += 1
    if run_command("python3 -m pip install --upgrade pip", "Upgrading pip"):
        success_count += 1
    
    # Install gunicorn for production web server
    total_commands += 1
    if run_command("python3 -m pip install gunicorn>=20.1.0", "Installing Gunicorn WSGI server"):
        success_count += 1
    
    # Install requests if missing (for the test script)
    total_commands += 1
    if run_command("python3 -m pip install requests", "Installing requests library"):
        success_count += 1
    
    # Verify gunicorn installation
    total_commands += 1
    if run_command("gunicorn --version", "Verifying Gunicorn installation"):
        success_count += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Installation Summary: {success_count}/{total_commands} successful")
    
    if success_count == total_commands:
        print("✅ All production dependencies installed successfully!")
        print("\n🎯 Next steps:")
        print("   1. Test the restart monitor: python3 test_restart_monitor.py")
        print("   2. Start production server: python3 run_web_interface.py --mode production")
        return True
    else:
        print("❌ Some installations failed!")
        print("\n🔧 Manual installation commands:")
        print("   pip3 install gunicorn>=20.1.0 requests")
        return False

def main():
    """Main installation function"""
    if not os.path.exists("requirements.txt"):
        print("❌ Error: requirements.txt not found!")
        print("   Please run this script from the V2.0 directory")
        sys.exit(1)
    
    success = install_production_dependencies()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()