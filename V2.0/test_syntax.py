#!/usr/bin/env python3
"""
Test syntax validation for fixed files
"""

import py_compile
import sys
import os

def test_file_syntax(filepath):
    """Test if a Python file has valid syntax"""
    try:
        py_compile.compile(filepath, doraise=True)
        print(f"✅ {filepath} - syntax OK")
        return True
    except py_compile.PyCompileError as e:
        print(f"❌ {filepath} - syntax error: {e}")
        return False

def main():
    """Test syntax of key files"""
    
    print("=== Testing File Syntax ===")
    
    test_files = [
        "motion/simplified_fluidnc_protocol_fixed.py",
        "web/start_web_interface.py",
        "motion/simplified_fluidnc_controller_fixed.py"
    ]
    
    all_ok = True
    
    for file_path in test_files:
        if os.path.exists(file_path):
            if not test_file_syntax(file_path):
                all_ok = False
        else:
            print(f"⚠️  {file_path} - file not found")
    
    if all_ok:
        print("\n🎉 All files have valid syntax!")
        print("You can now test real hardware initialization:")
        print("  python test_real_hardware.py")
    else:
        print("\n❌ Some files have syntax errors.")
    
    return all_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)