#!/usr/bin/env python3
"""
Quick Web Interface Implementation Validation

Validates that all current web interface elements are properly
implemented without requiring a running server.
"""

import os
import sys
from pathlib import Path

def check_file_exists(filepath: str, description: str) -> bool:
    """Check if a file exists"""
    exists = Path(filepath).exists()
    status = "✅" if exists else "❌"
    print(f"{status} {description}: {filepath}")
    return exists

def check_import_works(module_path: str, description: str) -> bool:
    """Check if a module can be imported"""
    try:
        # Add the V2.0 directory to Python path
        v2_path = Path(__file__).parent
        if str(v2_path) not in sys.path:
            sys.path.insert(0, str(v2_path))
        
        # Try importing
        exec(f"import {module_path}")
        print(f"✅ {description}: Can import {module_path}")
        return True
    except Exception as e:
        print(f"❌ {description}: Cannot import {module_path} - {e}")
        return False

def validate_web_interface_implementation():
    """Validate current web interface implementation"""
    print("🔍 Web Interface Implementation Validation")
    print("=" * 50)
    
    # Check core web interface files
    print("\n📁 Web Interface Files:")
    web_files = [
        ("web/web_interface.py", "Main Web Interface"),
        ("web/templates/dashboard.html", "Dashboard Template"),
        ("web/templates/manual.html", "Manual Control Template"),
        ("web/templates/scans.html", "Scans Template"),
        ("web/templates/settings.html", "Settings Template"),
        ("web/static/css/style.css", "Main Stylesheet"),
        ("web/static/js/dashboard.js", "Dashboard JavaScript"),
        ("web/static/js/manual.js", "Manual Control JavaScript"),
        ("run_web_interface.py", "Web Interface Launcher")
    ]
    
    web_files_exist = 0
    for filepath, desc in web_files:
        if check_file_exists(filepath, desc):
            web_files_exist += 1
    
    # Check core system modules  
    print("\n🔧 Core System Modules:")
    core_modules = [
        ("core.events", "Event System"),
        ("core.config_manager", "Configuration Manager"),
        ("motion.base", "Motion Controller Interface"),
        ("camera.base", "Camera Controller Interface"),
        ("lighting.base", "Lighting Controller Interface"),
        ("scanning.base", "Scanning Controller Interface")
    ]
    
    core_modules_working = 0
    for module, desc in core_modules:
        if check_import_works(module, desc):
            core_modules_working += 1
    
    # Check configuration
    print("\n⚙️ Configuration:")
    config_valid = check_file_exists("config/scanner_config.yaml", "Scanner Configuration")
    
    # Check Phase 5 enhancements
    print("\n🚀 Phase 5 Features:")
    phase5_files = [
        ("web/templates/file_browser.html", "File Browser Template"),
        ("web/static/js/file_browser.js", "File Browser JavaScript"),
        ("demo_phase5_web_interface.py", "Phase 5 Demo Interface")
    ]
    
    phase5_exist = 0
    for filepath, desc in phase5_files:
        if check_file_exists(filepath, desc):
            phase5_exist += 1
    
    # Calculate results
    total_web_files = len(web_files)
    total_core_modules = len(core_modules)
    total_phase5 = len(phase5_files)
    
    web_percentage = (web_files_exist / total_web_files) * 100
    core_percentage = (core_modules_working / total_core_modules) * 100
    phase5_percentage = (phase5_exist / total_phase5) * 100
    
    # Print summary
    print("\n" + "=" * 50)
    print("📊 IMPLEMENTATION SUMMARY")
    print("=" * 50)
    print(f"📁 Web Files: {web_files_exist}/{total_web_files} ({web_percentage:.0f}%)")
    print(f"🔧 Core Modules: {core_modules_working}/{total_core_modules} ({core_percentage:.0f}%)")
    print(f"⚙️ Configuration: {'✅' if config_valid else '❌'}")
    print(f"🚀 Phase 5: {phase5_exist}/{total_phase5} ({phase5_percentage:.0f}%)")
    
    # Overall status
    if web_files_exist >= 6 and core_modules_working >= 4:  # Minimum viable
        print("\n✅ IMPLEMENTATION STATUS: READY")
        print("✅ Web interface should be functional")
        print("✅ Core systems are available")
        
        if phase5_exist >= 2:
            print("✅ Phase 5 enhancements available")
        
        print("\n🚀 Next Steps:")
        print("1. Start web server: python run_web_interface.py")
        print("2. Run tests: python test_current_web_interface.py")
        print("3. Open browser: http://localhost:5000")
        
        return True
    else:
        print("\n❌ IMPLEMENTATION STATUS: INCOMPLETE")
        print("❌ Missing critical web interface components")
        
        if web_files_exist < 6:
            print("   📁 Missing web interface files")
        if core_modules_working < 4:
            print("   🔧 Core system modules not available")
        
        print("\n🔧 Required Actions:")
        print("1. Check file paths and directory structure")
        print("2. Verify all modules are properly implemented")
        print("3. Resolve import errors before testing")
        
        return False

def main():
    """Main validation function"""
    try:
        # Change to V2.0 directory
        v2_dir = Path(__file__).parent
        os.chdir(v2_dir)
        
        success = validate_web_interface_implementation()
        return success
        
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)