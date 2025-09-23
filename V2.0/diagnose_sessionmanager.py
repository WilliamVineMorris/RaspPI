#!/usr/bin/env python3
"""
Test script to diagnose SessionManager abstract method issues
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def diagnose_sessionmanager():
    """Diagnose what abstract methods are missing from SessionManager"""
    
    try:
        from storage.base import StorageManager
        from storage.session_manager import SessionManager
        import inspect
        
        print("🔍 DIAGNOSING SESSIONMANAGER IMPLEMENTATION")
        print("="*60)
        
        # Get abstract methods from base class
        print("1. Getting abstract methods from StorageManager base class...")
        abstract_methods = []
        for name, method in inspect.getmembers(StorageManager, predicate=inspect.isfunction):
            if hasattr(method, '__isabstractmethod__') and method.__isabstractmethod__:
                abstract_methods.append(name)
        
        print(f"✅ Found {len(abstract_methods)} abstract methods in base class:")
        for method in sorted(abstract_methods):
            print(f"   - {method}")
        
        # Get implemented methods in SessionManager
        print("\n2. Getting implemented methods in SessionManager...")
        implemented_methods = []
        for name, method in inspect.getmembers(SessionManager, predicate=inspect.isfunction):
            if not name.startswith('_'):  # Skip private methods
                implemented_methods.append(name)
        
        print(f"✅ Found {len(implemented_methods)} public methods in SessionManager:")
        for method in sorted(implemented_methods):
            print(f"   - {method}")
        
        # Find missing methods
        print("\n3. Finding missing abstract methods...")
        missing_methods = set(abstract_methods) - set(implemented_methods)
        
        if missing_methods:
            print(f"❌ Missing {len(missing_methods)} abstract methods:")
            for method in sorted(missing_methods):
                print(f"   - {method}")
        else:
            print("✅ All abstract methods appear to be implemented!")
        
        # Try to instantiate (this will show the real error)
        print("\n4. Testing instantiation...")
        try:
            config = {"base_path": "/tmp/test"}
            storage = SessionManager(config)
            print("✅ SessionManager instantiated successfully!")
            return True
        except TypeError as e:
            print(f"❌ Instantiation failed: {e}")
            # Extract the actual missing method from the error
            error_str = str(e)
            if "abstract method" in error_str:
                # Parse the error message to find missing methods
                import re
                matches = re.findall(r"abstract method (\w+)", error_str)
                if matches:
                    print("🎯 Actual missing methods from error:")
                    for method in matches:
                        print(f"   - {method}")
            return False
        
    except Exception as e:
        print(f"❌ Diagnosis failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = diagnose_sessionmanager()
    if success:
        print("\n🎉 SessionManager is ready!")
    else:
        print("\n🔧 SessionManager needs specific fixes.")